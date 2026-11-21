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
import { fileURLToPath } from 'node:url'
import { loadRegistry, PORTS_YAML, resolvePath } from '@allin/core'
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
}

/** 冒烟脚本用：直接拿项目清单（不经 IPC）。 */
export function listProjects() {
  const { entries, problems } = loadRegistry(REGISTRY_DIR)
  return { total: entries.length, items: entries.map(compact), problems: problems || [] }
}

export { runCli, resolvePath }
