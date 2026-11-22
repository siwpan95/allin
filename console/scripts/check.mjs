#!/usr/bin/env node
/**
 * allin-console 契约审计（SPEC-205 的可机械验证部分）
 *
 * 判据全部是**可失败的断言**，exit 0 = 全通过：
 *   1. 结构完整：shell / ui / cli-bus 入口存在
 *   2. 安全三件套：app.js 必须开 contextIsolation + sandbox、关 nodeIntegration
 *   3. preload 只暴露白名单：不得把 ipcRenderer 本体递出去
 *   4. registry 可加载：entries > 0（否则 console 是空壳）
 *   5. 接入覆盖率：按「有 info 子命令」统计，**不阻断**（B 批次允许缺口）
 *   6. P3 治理面板：三个内置面板都要注册且能渲染出数据行
 *   7. P3 安全：渲染层不得用 innerHTML 拼插件数据（插件可能来自用户目录）
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(HERE, '..')
const ALLIN_ROOT = path.join(ROOT, '..')

const fails = []
const notes = []

function need(rel) {
  const p = path.join(ROOT, rel)
  if (!existsSync(p)) fails.push(`缺少文件：${rel}`)
  return p
}

// 1. 结构
// 安全三件套在 app.js 里 —— main.js 只是生命周期入口（2026-11-22 拆分，供 smoke 复用）
const shellPath = need('apps/shell/app.js')
const preloadPath = need('apps/shell/preload.cjs')
need('apps/shell/main.js')
need('apps/ui/index.html')
need('apps/ui/app.js')
need('packages/cli-bus/src/index.js')

// 2. 安全三件套
if (existsSync(shellPath)) {
  const src = readFileSync(shellPath, 'utf8')
  if (!/contextIsolation:\s*true/.test(src)) fails.push('app.js 未开启 contextIsolation')
  if (!/sandbox:\s*true/.test(src)) fails.push('app.js 未开启 sandbox')
  if (!/nodeIntegration:\s*false/.test(src)) fails.push('app.js 未关闭 nodeIntegration')
  if (/nodeIntegration:\s*true/.test(src)) fails.push('app.js 出现了 nodeIntegration: true')
}

// 3. preload 白名单
if (existsSync(preloadPath)) {
  const src = readFileSync(preloadPath, 'utf8')
  if (!/contextBridge\.exposeInMainWorld/.test(src)) fails.push('preload 未使用 contextBridge')
  // 直接把 ipcRenderer 作为值暴露（而不是包成函数）才算违规
  if (/exposeInMainWorld\([^)]*,\s*ipcRenderer\s*\)/.test(src)) {
    fails.push('preload 把 ipcRenderer 本体暴露给了渲染层')
  }
}

// 4 + 5. registry 与接入覆盖率
try {
  const core = await import('@allin/core')
  const { locateCli, hasInfoSubcommand } = await import('@allin/cli-bus')
  const { createHost } = await import('@allin/cordis-js')
  const { pathToFileURL } = await import('node:url')
  const { readFileSync: rf, existsSync: ex } = await import('node:fs')
  const registryDir = path.join(path.dirname(core.PORTS_YAML), 'projects')

  // 门禁留痕读取（与主进程同源，供 gate-reds 面板用）
  const GATE_RUNS = path.join(core.PLATFORM_ROOT, '..', 'tools', 'gate', 'audit', 'gate-runs.jsonl')
  function readGateBatches() {
    if (!ex(GATE_RUNS)) return []
    const byBatch = new Map()
    for (const line of rf(GATE_RUNS, 'utf8').split('\n')) {
      if (!line.trim()) continue
      let row
      try { row = JSON.parse(line) } catch { continue }
      if (!row.batch) continue
      if (!byBatch.has(row.batch)) byBatch.set(row.batch, { batch: row.batch, ts: row.ts, gates: [] })
      byBatch.get(row.batch).gates.push({
        label: row.label, exit: row.exit, skipped: Boolean(row.skipped),
      })
    }
    return [...byBatch.values()].sort((a, b) => String(a.ts).localeCompare(String(b.ts)))
  }

  const { entries } = core.loadRegistry(registryDir)
  if (!entries.length) fails.push(`registry 为空：${registryDir}`)
  else notes.push(`registry entries = ${entries.length}`)

  let hasInfo = 0
  let cliOnly = 0
  for (const e of entries) {
    let abs
    try { abs = core.resolvePath(e.path) } catch { continue }
    const cli = locateCli(abs)
    if (hasInfoSubcommand(cli)) hasInfo += 1
    else if (cli) cliOnly += 1
  }
  const pct = entries.length ? Math.round((hasInfo / entries.length) * 100) : 0
  // 判据是「有 info 子命令」而不是「有 cli.py」—— 后者虚高 6 个（2026-11-22 实测）
  notes.push(`info 覆盖 = ${hasInfo}/${entries.length}（${pct}%，SPEC-205 §C1 B3 待补）`)
  if (cliOnly) notes.push(`有 cli.py 但无 info = ${cliOnly} 个（B0′ 批次）`)

  // P3 治理面板：注册 + 真渲染出数据
  const REQUIRED_PANELS = [
    { id: 'governance.gates', title: '门禁红项' },
    { id: 'governance.ports', title: '端口占用' },
    { id: 'governance.registry', title: 'registry 审计' },
  ]
  const pluginDir = path.join(ROOT, 'plugins')
  const files = readdirSync(pluginDir).filter((f) => f.endsWith('.mjs'))
  const mods = []
  for (const f of files) {
    mods.push(await import(pathToFileURL(path.join(pluginDir, f)).href))
  }
  const host = createHost({
    logger: () => {},
    deps: {
      core: {
        probePort: core.probePort,
        loadPorts: core.loadPorts,
        loadRegistry: core.loadRegistry,
        resolvePath: core.resolvePath,
        REGISTRY_DIR: registryDir,
      },
      cliBus: { locateCli, hasInfoSubcommand },
      readGateRuns: readGateBatches,
    },
  })
  await host.load(mods)
  if (host.errors.length) {
    fails.push(`插件加载失败 ${host.errors.length} 个：${host.errors.map((e) => e.plugin).join(', ')}`)
  }
  for (const want of REQUIRED_PANELS) {
    const p = host.panels.find((x) => x.id === want.id)
    if (!p) {
      fails.push(`缺少治理面板 ${want.id}`)
      continue
    }
    if (typeof p.render !== 'function') {
      fails.push(`治理面板 ${want.id} 没有 render()（常驻视图必须是动态的）`)
      continue
    }
    let data
    try {
      data = await p.render()
    } catch (e) {
      fails.push(`治理面板 ${want.id} 渲染抛错：${e.message}`)
      continue
    }
    const rows = Array.isArray(data?.rows) ? data.rows.length : 0
    if (!rows) fails.push(`治理面板 ${want.id} 渲染出 0 行数据（空壳面板不算数）`)
    else notes.push(`治理面板 ${want.id}：${data.status} / ${data.summary} / ${rows} 行`)
  }
} catch (e) {
  fails.push(`registry 加载失败：${e.message}`)
}

// 7. 渲染层安全：插件数据不得经 innerHTML 注入
{
  const uiPath = path.join(ROOT, 'apps', 'ui', 'app.js')
  if (existsSync(uiPath)) {
    const src = readFileSync(uiPath, 'utf8')
    const govStart = src.indexOf('function renderGovStrip')
    if (govStart >= 0) {
      // 边界：下一个「行首的 }」即函数结束。
      // 不能用 `indexOf('\nfunction ')` —— 紧随其后的 refreshGov 是
      // `async function`，匹配不到，区间会一路延伸到后面的 innerHTML 代码。
      const govEnd = src.indexOf('\n}', govStart)
      const govSrc = src.slice(govStart, govEnd > 0 ? govEnd : undefined)
      // 只看**代码语句**，不看注释 —— 注释里写着「不拼 innerHTML」本身含这个词，
      // 按原文匹配会误报（第一次跑就误报了）。
      const codeOnly = govSrc
        .split('\n')
        .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l))
        .join('\n')
      if (/\.innerHTML\s*=/.test(codeOnly)) {
        fails.push('治理面板渲染用了 innerHTML —— 插件数据必须经 textContent 赋值')
      }
    }
  }
}

// ---------- 输出 ----------
console.log('== allin-console 契约审计（SPEC-205）==')
for (const n of notes) console.log('  · ' + n)
if (fails.length) {
  console.error('\n阻断项：')
  for (const f of fails) console.error('  ✗ ' + f)
  process.exit(1)
}
console.log('\n契约审计通过')
process.exit(0)
