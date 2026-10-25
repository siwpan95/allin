// @allin/core — 子进程启停（子进程隔离）+ JSONL 任务日志（WorldLog 同构）。
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

export const PLATFORM_ROOT = process.env.PLATFORM_ROOT || 'G:\\platform'
export const DATA_DIR = path.join(PLATFORM_ROOT, 'data')
const LOG_FILE = path.join(DATA_DIR, 'tasks.log')

let seq = 0
const children = new Map() // id -> { child, startedAt }

function ensureData() {
  fs.mkdirSync(DATA_DIR, { recursive: true })
}

/** 追加一条任务事件（与 WorldLog / crawl_hub tasks.log 同构：seq/ts/type/project/action/...）。 */
export function logTask(record) {
  ensureData()
  seq += 1
  const line = JSON.stringify({
    seq,
    ts: new Date().toISOString(),
    type: 'task',
    ...record,
  })
  fs.appendFileSync(LOG_FILE, line + '\n')
  return line
}

export function isRunning(id) {
  const rec = children.get(id)
  return Boolean(rec && rec.child.exitCode === null && rec.child.signalCode === null)
}

export function runningIds() {
  return [...children.keys()].filter(isRunning)
}

/** 启动清单条目（子进程隔离：shell 执行 launch.command，cwd = entry.path）。 */
export function startEntry(entry, options = {}) {
  if (entry._valid === false) {
    const err = new Error(`清单未通过校验（${entry._file}），拒绝启动`)
    err.code = 'INVALID_ENTRY'
    throw err
  }
  if (isRunning(entry.id)) {
    return { ok: false, reason: 'already-running', id: entry.id }
  }
  const startedAt = Date.now()
  const child = spawn(entry.launch.command, {
    shell: true,
    cwd: entry.path,
    detached: true,
    stdio: 'ignore',
  })
  child.on('exit', (code, signal) => {
    logTask({
      project: entry.id,
      action: 'exit',
      exit_code: code,
      signal: signal || undefined,
      duration_ms: Date.now() - startedAt,
    })
    children.delete(entry.id)
  })
  child.on('error', (e) => {
    logTask({ project: entry.id, action: 'error', error: String(e.message) })
    children.delete(entry.id)
  })
  children.set(entry.id, { child, startedAt })
  logTask({ project: entry.id, action: 'launch', command: entry.launch.command, path: entry.path })
  child.unref()
  return { ok: true, id: entry.id, pid: child.pid }
}

/** 停止：Windows 用 taskkill 树杀（连同子进程）；其余平台发 SIGTERM。 */
export function stopEntry(id) {
  const rec = children.get(id)
  if (!rec || !isRunning(id)) {
    return { ok: false, reason: 'not-running', id }
  }
  const pid = rec.child.pid
  const startedAt = rec.startedAt
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    try { rec.child.kill('SIGTERM') } catch { /* 已退出 */ }
  }
  logTask({ project: id, action: 'stop', pid, duration_ms: Date.now() - startedAt })
  children.delete(id)
  return { ok: true, id }
}
