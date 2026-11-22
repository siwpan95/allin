/**
 * allin-console · 主进程逻辑（可复用模块）
 *
 * 拆成模块是为了让 `scripts/smoke.mjs` 能用**同一套**窗口与 IPC 逻辑做冒烟验证，
 * 而不是另写一份「看起来差不多」的实现 —— 那样验证的就不是真东西了。
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { BaseWindow, WebContentsView, ipcMain } = require('electron')
import path from 'node:path'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { applyEnv } from './config.js'

/**
 * ⚠ `@allin/core` 必须**动态导入**，不能静态 import。
 *
 * 原因：core 在模块顶层就把 `PORTS_YAML` / `REPOS_ROOT` 求值成 const
 * （`platform/packages/core/src/registry.js:18`），而安装态下这些路径
 * 取决于「本机 allin 仓在哪」—— 要先设好 `PLATFORM_PORTS` /
 * `PLATFORM_REPOS_ROOT` env 才有效。
 *
 * ESM 的静态 import 会被**提升**到模块顶部先执行 ⇒ 静态 import 时 env 还没设，
 * core 会锁死成打包目录里的假路径（`resources/app.asar/...`），
 * 于是 registry 加载失败、148 条变 0 条。
 *
 * ⇒ 动态 import 是唯一正确解法（不是「绕路」，是必要）。
 */

/** 安装态配置解析结果（P4）：本机 allin 仓根 / 发布区根从哪来。 */
const HOME = applyEnv()
if (!HOME.root) {
  console.error('[allin-console] ⚠ 未定位到 allin 仓（env ALLIN_HOME / %APPDATA%\\allin-console\\config.json）')
}

// ↓↓↓ 必须在 applyEnv() 之后 ↓↓↓
const core = await import('@allin/core')
const {
  loadRegistry, PORTS_YAML, resolvePath, startEntry, stopEntry, runningIds,
  DATA_DIR, PLATFORM_ROOT, probePort, loadPorts,
} = core

import { createHost } from '@allin/cordis-js'
import { locateCli, hasInfoSubcommand, runCli, failureSummary } from '@allin/cli-bus'

const HERE = path.dirname(fileURLToPath(import.meta.url))
export const UI_INDEX = path.join(HERE, '..', 'ui', 'index.html')
export const PRELOAD = path.join(HERE, 'preload.cjs')
/** 内置插件目录（P2 首批自带；后续可从用户目录加载） */
const PLUGIN_DIR = path.join(HERE, '..', '..', 'plugins')
/** 门禁留痕：JSONL，一行一道门禁的一次运行 */
const GATE_RUNS = path.join(PLATFORM_ROOT, '..', 'tools', 'gate', 'audit', 'gate-runs.jsonl')

/** registry 目录由 @allin/core 的端口表位置反推，不写死盘符。 */
export const REGISTRY_DIR = path.join(path.dirname(PORTS_YAML), 'projects')

/** 允许渲染层触发的子命令白名单（主进程收敛执行面）。 */
const ALLOWED = new Set(['info', 'version', 'selfcheck', 'launch', 'stop', 'logs'])

let win = null
let uiView = null

function layout() {
  if (!win || !uiView) return
  const [w, h] = win.getContentSize()
  uiView.setBounds({ x: 0, y: 0, width: w, height: h })
}

/** 创建控制台窗口（BaseWindow + 单个 UI 视图；P1 会在此挂 WebContentsView 标签）。 */
export function createConsoleWindow({ width = 1280, height = 840, show = true } = {}) {
  win = new BaseWindow({
    width, height, show,
    minWidth: 960,
    minHeight: 600,
    title: 'allin console',
    backgroundColor: '#0b0f14',
  })

  uiView = new WebContentsView({
    webPreferences: {
      preload: PRELOAD,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  win.contentView.addChildView(uiView)
  uiView.webContents.loadFile(UI_INDEX)
  layout()
  win.on('resize', layout)
  win.on('closed', () => { win = null; uiView = null })
  return { win, uiView }
}

function projectPath(entry) {
  try {
    return resolvePath(entry.path)
  } catch {
    return null
  }
}

function compact(entry) {
  const abs = projectPath(entry)
  return {
    id: entry.id,
    name: entry.name || entry.id,
    category: entry.category || 'unclassified',
    version: entry.version || '',
    path: abs,
    launchCommand: (entry.launch && entry.launch.command) || '',
    verifyCommand: (entry.verify && entry.verify.command) || '',
    hasCli: abs ? Boolean(locateCli(abs)) : false,
    hasInfo: abs ? hasInfoSubcommand(locateCli(abs)) : false,
    valid: entry._valid !== false,
  }
}

/**
 * 读门禁留痕并按 batch 分组（batch = 一次全量门禁跑）。
 * 只读、纯解析 —— 不跑门禁、不改留痕。
 */
function readGateBatches() {
  if (!existsSync(GATE_RUNS)) return []
  const byBatch = new Map()
  for (const line of readFileSync(GATE_RUNS, 'utf8').split('\n')) {
    if (!line.trim()) continue
    let row
    try { row = JSON.parse(line) } catch { continue }
    if (!row.batch) continue
    if (!byBatch.has(row.batch)) {
      byBatch.set(row.batch, { batch: row.batch, ts: row.ts, commit: row.commit, gates: [] })
    }
    byBatch.get(row.batch).gates.push({
      label: row.label, exit: row.exit, ms: row.ms, skipped: Boolean(row.skipped),
    })
  }
  return [...byBatch.values()].sort((a, b) => String(a.ts).localeCompare(String(b.ts)))
}

/**
 * 列出本机实际在监听的 TCP 端口。
 *
 * 为什么需要它：core 的 `probePort` 是「给定端口问通不通」，**反推不出**
 * 「哪些端口被占」—— 对 65535 个端口逐个探测要十几小时，不可行。
 * 端口占用视图（发现「有东西占着端口但 registry 没登记」）必须读系统的
 * 监听表。Windows 上是 `netstat -ano`；非 Windows 返回 null（视图降级，
 * 不假装）。
 *
 * 返回：{ ports: [{port, pid, proto}], ok: boolean }
 */
let listeningCache = { ts: 0, data: null }
async function listListeningPorts({ maxAgeMs = 5000 } = {}) {
  if (listeningCache.data && Date.now() - listeningCache.ts < maxAgeMs) {
    return listeningCache.data
  }
  if (process.platform !== 'win32') {
    return { ok: false, ports: [], reason: `当前平台 ${process.platform} 暂不支持读取监听表` }
  }
  const { execFile } = await import('node:child_process')
  const { promisify } = await import('node:util')
  const execFileP = promisify(execFile)
  let stdout = ''
  try {
    // -ano：全部连接 + 数字地址 + PID
    const r = await execFileP('netstat', ['-ano'], { timeout: 8000, windowsHide: true, maxBuffer: 8 * 1024 * 1024 })
    stdout = r.stdout || ''
  } catch (e) {
    return { ok: false, ports: [], reason: `netstat 执行失败：${e?.message || e}` }
  }
  const seen = new Map()
  for (const line of stdout.split(/\r?\n/)) {
    // TCP 行形如：  TCP    0.0.0.0:8000    0.0.0.0:0    LISTENING    1234
    if (!/^\s*TCP\s/i.test(line)) continue
    const cols = line.trim().split(/\s+/)
    if (cols.length < 4) continue
    if (String(cols[3]).toUpperCase() !== 'LISTENING') continue
    const local = cols[1] || ''
    const idx = local.lastIndexOf(':')
    if (idx < 0) continue
    const port = Number(local.slice(idx + 1))
    if (!Number.isInteger(port) || port <= 0) continue
    const pid = Number(cols[4] || 0) || null
    if (!seen.has(port)) seen.set(port, { port, pid, proto: 'tcp' })
  }
  const data = { ok: true, ports: [...seen.values()].sort((a, b) => a.port - b.port) }
  listeningCache = { ts: Date.now(), data }
  return data
}

/** 插件宿主（懒加载：只有首次取命令时才读插件目录）。 */
let host = null
async function ensureHost() {
  if (host) return host
  host = createHost({
    logger: (level, msg) => console.log(`[cordis-js][${level}] ${msg}`),
    deps: {
      core: {
        probePort, loadPorts, loadRegistry, resolvePath, REGISTRY_DIR,
        listListeningPorts,
      },
      cliBus: { locateCli, hasInfoSubcommand },
      readGateRuns: readGateBatches,
      runCli,
    },
  })
  // 加载内置插件：单个失败不阻断（宿主内部已 try/catch）
  const files = existsSync(PLUGIN_DIR)
    ? readdirSync(PLUGIN_DIR).filter((f) => f.endsWith('.mjs'))
    : []
  const mods = []
  for (const f of files) {
    try {
      // Windows 下 import() 的绝对路径必须转 file:// URL
      mods.push(await import(pathToFileURL(path.join(PLUGIN_DIR, f)).href))
    } catch (e) {
      host.errors.push({ plugin: f, error: e?.message || String(e) })
    }
  }
  await host.load(mods)
  return host
}

/** 注册 IPC。重复注册会抛错，故调用方须只调一次。 */
export function registerIpc() {
  ipcMain.handle('projects:list', () => {
    const { entries, problems } = loadRegistry(REGISTRY_DIR)
    return {
      total: entries.length,
      items: entries.map(compact),
      problems: (problems || []).map((p) => (typeof p === 'string' ? p : p.message || JSON.stringify(p))),
    }
  })

  ipcMain.handle('cli:run', async (_evt, { projectId, subcommand, extraArgs = [] }) => {
    if (!ALLOWED.has(subcommand)) {
      return { ok: false, reason: 'denied', message: `不支持的子命令：${subcommand}` }
    }
    const { entries } = loadRegistry(REGISTRY_DIR)
    const entry = entries.find((e) => e.id === projectId)
    if (!entry) return { ok: false, reason: 'not-found', message: `未知项目：${projectId}` }

    const abs = projectPath(entry)
    if (!abs) return { ok: false, reason: 'bad-path', message: '项目路径无法解析' }

    const args = [subcommand, ...extraArgs]
    // `info` 的既有契约是「无参数、stdout 直接是 JSON」（33+ 仓实测），
    // 不追加 --json —— 那会让 argparse 报 unrecognized arguments。
    const result = await runCli({
      projectPath: abs,
      args,
      expectJson: subcommand === 'info',
    })
    return {
      ok: result.ok,
      code: result.code,
      durationMs: result.durationMs,
      stdout: result.stdout,
      stderr: result.stderr,
      json: result.json,
      parseError: result.parseError,
      reason: result.reason,
      summary: result.ok ? '' : failureSummary(result),
    }
  })

  registerLifecycleIpc()
  registerPluginIpc()
}

/** 插件相关的 IPC：列命令 / 跑命令 / 列面板 */
function registerPluginIpc() {
  ipcMain.handle('plugins:state', async () => {
    const h = await ensureHost()
    return {
      commands: h.commands.map((c) => ({
        id: c.id, title: c.title, description: c.description, plugin: c.plugin,
      })),
      panels: h.panels.map((p) => ({
        id: p.id, slot: p.slot, title: p.title, html: p.html, plugin: p.plugin,
        dynamic: Boolean(p.render),
      })),
      errors: h.errors,
    }
  })

  ipcMain.handle('plugin:run', async (_evt, commandId) => {
    const h = await ensureHost()
    const cmd = h.commands.find((c) => c.id === commandId)
    if (!cmd) return { ok: false, message: `未知命令：${commandId}` }
    const started = Date.now()
    try {
      const r = await cmd.run()
      return { ...r, durationMs: Date.now() - started, commandId }
    } catch (e) {
      return { ok: false, message: e?.message || String(e), durationMs: Date.now() - started, commandId }
    }
  })

  /**
   * P3：取治理面板的当前数据（侧栏常驻视图）。
   *
   * 面板由插件的 `render()` 提供，返回**结构化数据**而非 HTML ——
   * 渲染层自己画，插件碰不到 DOM（也绕不开渲染层的 CSP）。
   * 单个面板渲染失败不影响其它面板（降级为一条错误条目）。
   */
  ipcMain.handle('panels:data', async (_evt, { slot } = {}) => {
    const h = await ensureHost()
    const targets = h.panels.filter((p) => !slot || p.slot === slot)
    const out = []
    for (const p of targets) {
      const base = { id: p.id, slot: p.slot, title: p.title, plugin: p.plugin }
      if (typeof p.render !== 'function') {
        out.push({ ...base, status: 'static', summary: '', rows: [], html: p.html })
        continue
      }
      const started = Date.now()
      try {
        const data = await p.render()
        out.push({
          ...base,
          status: data?.status || 'ok',
          summary: data?.summary || '',
          rows: Array.isArray(data?.rows) ? data.rows : [],
          ts: Date.now(),
          ms: Date.now() - started,
        })
      } catch (e) {
        out.push({
          ...base,
          status: 'error',
          summary: e?.message || String(e),
          rows: [],
          ts: Date.now(),
          ms: Date.now() - started,
        })
      }
    }
    return { panels: out }
  })
}

/** 冒烟脚本用：直接拿项目清单（不经 IPC）。 */
export function listProjects() {
  const { entries, problems } = loadRegistry(REGISTRY_DIR)
  return { total: entries.length, items: entries.map(compact), problems: problems || [] }
}

/**
 * 启停一律走 `@allin/core`（pid 表 / tasks.log / 终止梯都在那边），
 * console **不自己 spawn**、不自己记 pid —— 否则两边状态必然分裂（SPEC-205 §6）。
 */
export function registerLifecycleIpc() {
  ipcMain.handle('projects:running', () => ({ ids: runningIds() }))

  ipcMain.handle('project:start', (_evt, projectId) => {
    const { entries } = loadRegistry(REGISTRY_DIR)
    const entry = entries.find((e) => e.id === projectId)
    if (!entry) return { ok: false, reason: 'not-found', message: `未知项目：${projectId}` }
    try {
      const r = startEntry(entry)
      return { ok: r.ok !== false, pid: r.pid, reason: r.reason, id: projectId }
    } catch (e) {
      // core 会抛 INVALID_ENTRY / UNSAFE_COMMAND / PATH_ESCAPE —— 原样回传原因
      return { ok: false, reason: e.code || 'start-failed', message: e.message }
    }
  })

  ipcMain.handle('project:stop', async (_evt, projectId) => {
    const { entries } = loadRegistry(REGISTRY_DIR)
    const entry = entries.find((e) => e.id === projectId) || null
    try {
      const r = await stopEntry(projectId, entry)
      return { ok: r.ok !== false, reason: r.reason, id: projectId }
    } catch (e) {
      return { ok: false, reason: e.code || 'stop-failed', message: e.message }
    }
  })

  // 任务日志：只读 @allin/core 写的 tasks.log（JSONL），不在 console 侧另记一份
  ipcMain.handle('logs:tail', (_evt, { projectId, lines = 60 } = {}) => {
    const logFile = path.join(DATA_DIR, 'tasks.log')
    if (!existsSync(logFile)) {
      return { ok: true, entries: [], missing: true, path: logFile }
    }
    try {
      const entries = readFileSync(logFile, 'utf8')
        .split('\n')
        .filter(Boolean)
        .map((l) => { try { return JSON.parse(l) } catch { return null } })
        .filter(Boolean)
        .filter((r) => !projectId || r.project === projectId)
      return { ok: true, entries: entries.slice(-lines), path: logFile }
    } catch (e) {
      return { ok: false, message: e.message, path: logFile }
    }
  })
}

export { runCli, resolvePath }
