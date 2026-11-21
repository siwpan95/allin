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
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { loadRegistry, PORTS_YAML, resolvePath, startEntry, stopEntry, runningIds, DATA_DIR } from '@allin/core'
import { locateCli, hasInfoSubcommand, runCli, failureSummary } from '@allin/cli-bus'

const HERE = path.dirname(fileURLToPath(import.meta.url))
export const UI_INDEX = path.join(HERE, '..', 'ui', 'index.html')
export const PRELOAD = path.join(HERE, 'preload.cjs')

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
