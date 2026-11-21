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
 */
import { existsSync, readFileSync } from 'node:fs'
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
  process.env.PLATFORM_REPOS_ROOT ||= path.join(ALLIN_ROOT, '..', 'repos')
  const core = await import('@allin/core')
  const { locateCli, hasInfoSubcommand } = await import('@allin/cli-bus')
  const registryDir = path.join(path.dirname(core.PORTS_YAML), 'projects')
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
} catch (e) {
  fails.push(`registry 加载失败：${e.message}`)
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
