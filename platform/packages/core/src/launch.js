// @allin/core — 子进程启停（子进程隔离）+ pid 持久化（running.json，跨进程可见可停）+ JSONL 任务日志（WorldLog 同构）。
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolvePath } from './registry.js'

const HERE = path.dirname(fileURLToPath(import.meta.url))

// 平台根（data/ 等运行时状态落点）：env PLATFORM_ROOT 优先；缺失时回退仓库根
// （2026-09-24 强化：G:\platform 绝对路径解绑——仓库克隆到任意目录即可跑，
//  运行时状态落在仓内 data/，已在 .gitignore）。
export const PLATFORM_ROOT = process.env.PLATFORM_ROOT || path.join(HERE, '..', '..', '..')
export const DATA_DIR = path.join(PLATFORM_ROOT, 'data')
const LOG_FILE = path.join(DATA_DIR, 'tasks.log')
// 日志轮转上限（2026-09-24 强化）：超过 5MB 归档为 .1（保留一代），杜绝长期运行无限增长
const LOG_MAX_BYTES = 5 * 1024 * 1024
// pid 登记表（跨进程启停的事实源）：{ <id>: { pid, startedAt, owner, command } }。
// 本进程内存 Map 是快路径；其他宿主（门户/CLI）登记的条目经 pidAlive 校验后
// 同样可见、可停。启动者进程退出后无人收 exit 事件 → 条目可能陈旧，读取侧
// 惰性清理（pid 已死即删）。
const RUNNING_FILE = path.join(DATA_DIR, 'running.json')

let seq = 0
const children = new Map() // id -> { child, startedAt }（仅本进程启动的）

function ensureData() {
  fs.mkdirSync(DATA_DIR, { recursive: true })
}

/** 超限归档：file → file.1（保留一代；轮转失败不阻塞记录——日志不能反噬主流程）。
 *  rename 前 fsync（2026-09-24 Phase 1，借 DSH「Windows JSONL durable publish」ADR）：
 *  确保已写入内容在归档切换前落盘，崩溃不产生丢一代边界的半截日志。 */
function rotateIfLarge(file, maxBytes = LOG_MAX_BYTES) {
  try {
    if (fs.existsSync(file) && fs.statSync(file).size > maxBytes) {
      const fd = fs.openSync(file, 'r+')
      try { fs.fsyncSync(fd) } finally { fs.closeSync(fd) }
      fs.rmSync(file + '.1', { force: true })
      fs.renameSync(file, file + '.1')
    }
  } catch { /* 轮转失败容错 */ }
}

/** 追加一条任务事件（与 WorldLog / crawl_hub tasks.log 同构：seq/ts/type/project/action/...）。 */
export function logTask(record) {
  ensureData()
  rotateIfLarge(LOG_FILE)
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

// ---------- running.json（pid 持久化） ----------

function readRunning() {
  try {
    return JSON.parse(fs.readFileSync(RUNNING_FILE, 'utf8')) || {}
  } catch {
    // 原子写备份（2026-09-24 强化）：主文件损坏/丢失时回退 .bak，杜绝整表清零
    try { return JSON.parse(fs.readFileSync(RUNNING_FILE + '.bak', 'utf8')) || {} } catch { return {} }
  }
}

function writeRunning(map) {
  ensureData()
  // 原子写（对齐 DSH「Windows durable publish」ADR）：temp 文件 + fsync + rename 原子替换，
  // 覆盖前把当前完好内容存 .bak——并发写/崩溃不再产生半截 JSON 或丢整表。
  // fsync 在 rename 前（Phase 1）：writeFileSync 只保证进页缓存，掉电场景 rename 可能
  // 指向空/半截 tmp；先 fsync 再 rename 才是 durable 语义（目录 fsync Windows 无 POSIX 等价，Node 层尽力）。
  try {
    const cur = fs.readFileSync(RUNNING_FILE, 'utf8')
    JSON.parse(cur)
    fs.writeFileSync(RUNNING_FILE + '.bak', cur, 'utf8')
  } catch { /* 主文件缺失/损坏：无可备份 */ }
  const tmp = RUNNING_FILE + '.' + process.pid + '.tmp'
  writeDurable(tmp, JSON.stringify(map, null, 2) + '\n')
  fs.renameSync(tmp, RUNNING_FILE)
}

/** durable 写：open → write → fsync → close（供 temp+rename 前置落盘）。 */
function writeDurable(file, data) {
  const fd = fs.openSync(file, 'w')
  try { fs.writeSync(fd, data); fs.fsyncSync(fd) } finally { fs.closeSync(fd) }
}

function upsertRunning(id, rec) {
  const map = readRunning()
  map[id] = rec
  writeRunning(map)
}

function removeRunning(id) {
  const map = readRunning()
  if (map[id] !== undefined) {
    delete map[id]
    writeRunning(map)
  }
}

/** pid 存活探测（跨平台；EPERM 视为存活——存在但不可信号）。 */
function pidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false
  try {
    process.kill(pid, 0)
    return true
  } catch (e) {
    return e.code === 'EPERM'
  }
}

/** 读取并惰性清理：pid 已死的条目（启动者退出后遗留）直接删除。 */
function liveRunning() {
  const map = readRunning()
  let changed = false
  for (const [id, rec] of Object.entries(map)) {
    if (!pidAlive(rec && rec.pid)) {
      delete map[id]
      changed = true
    }
  }
  if (changed) writeRunning(map)
  return map
}

// ---------- 启停 ----------

/** 本进程内存快路径（不动 running.json）。 */
function ownRunning(id) {
  const rec = children.get(id)
  return Boolean(rec && rec.child.exitCode === null && rec.child.signalCode === null)
}

export function isRunning(id) {
  if (ownRunning(id)) return true
  const ext = liveRunning()[id]
  return Boolean(ext && pidAlive(ext.pid))
}

export function runningIds() {
  const ids = new Set([...children.keys()].filter(ownRunning))
  for (const [id, rec] of Object.entries(liveRunning())) {
    if (pidAlive(rec.pid)) ids.add(id)
  }
  return [...ids]
}

/** 运行中条目的登记信息（跨进程）：{ pid, startedAt }；未运行返回 null。
 *  供探测层判断"启动宽限期"（慢启动服务在端口就绪前显示启动中）。 */
export function runningInfo(id) {
  const own = children.get(id)
  if (own && ownRunning(id)) return { pid: own.child.pid, startedAt: own.startedAt }
  const ext = liveRunning()[id]
  if (ext && pidAlive(ext.pid)) return { pid: ext.pid, startedAt: ext.startedAt }
  return null
}

/**
 * 启动命令预处理：npm 类命令经 npm.cmd 批处理垫片启动时，Windows 下 detached
 * 会让该批处理卡死在 CALL node 之前（实测 2026-08-28：detached + ignore/pipe
 * 均卡死、attached 正常，导致"运行中"为卡死空壳）。改为由当前 node 直启
 * npm-cli.js，绕开批处理垫片，同时保留 detached 的控制台隔离（关闭门户窗口
 * 不连坐项目进程）。npm-cli.js 缺失（无内置 npm 的 node）时回退原命令。
 */
function prepareCommand(command) {
  const text = String(command).trim()
  const m = /^npm(?:\s+(.*))?$/.exec(text)
  if (!m) return text
  const npmCli = path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js')
  if (!fs.existsSync(npmCli)) return text
  const args = m[1] || ''
  return `"${process.execPath}" "${npmCli}"${args ? ' ' + args : ''}`
}

/** 启动清单条目（子进程隔离：shell 执行 launch.command，cwd = entry.path；
 *  pid 落 running.json 供跨进程停止：门户/CLI 启动的项目互相可见、互相可停）。 */
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
  const child = spawn(prepareCommand(entry.launch.command), {
    shell: true,
    cwd: resolvePath(entry.path),
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
    removeRunning(entry.id)
  })
  child.on('error', (e) => {
    logTask({ project: entry.id, action: 'error', error: String(e.message) })
    children.delete(entry.id)
    removeRunning(entry.id)
  })
  children.set(entry.id, { child, startedAt })
  upsertRunning(entry.id, {
    pid: child.pid,
    startedAt,
    owner: options.owner || 'host',
    command: entry.launch.command,
  })
  logTask({ project: entry.id, action: 'launch', command: entry.launch.command, path: entry.path, owner: options.owner || 'host' })
  child.unref()
  return { ok: true, id: entry.id, pid: child.pid }
}

/** 停止：优先优雅停止（entry.stop.command），超时/仍存活则回退 Windows taskkill 树杀（连同子进程）；其余平台发 SIGTERM。
 *  跨进程：pid 取自本进程 children 或 running.json——任何宿主（门户/CLI）都能停任何宿主启动的项目。
 *  dispose 纪律（2026-08-27）：launch 必须可逆——每次停止都在 tasks.log 留下 stop-graceful/stop-force/stop 记录。
 *  2026-09-24 强化（对齐 DSH 终止梯纪律）：改为 async——优雅停止 spawn + await exit
 *  （graceMs 封顶）+ settle 回弹窗口，不再 spawnSync/Atomics.wait 阻塞事件循环；
 *  停止慢服务期间门户/CLI 照常响应。 */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function stopEntry(id, entry = null, options = {}) {
  const graceMs = options.graceMs ?? 15000
  const settleMs = options.settleMs ?? 2000
  const own = children.get(id)
  let pid
  let startedAt
  if (own && ownRunning(id)) {
    pid = own.child.pid
    startedAt = own.startedAt
  } else {
    const ext = liveRunning()[id]
    if (!ext || !pidAlive(ext.pid)) {
      return { ok: false, reason: 'not-running', id }
    }
    pid = ext.pid
    startedAt = ext.startedAt
  }
  const stopCmd = entry && entry.stop && typeof entry.stop.command === 'string' ? entry.stop.command : null
  let usedGraceful = false
  if (stopCmd) {
    usedGraceful = true
    // 优雅停止：等待 stop 命令退出（graceMs 封顶杀之），不阻塞事件循环
    await new Promise((resolve) => {
      const g = spawn(stopCmd, { shell: true, cwd: (entry.path && resolvePath(entry.path)) || process.cwd(), stdio: 'ignore' })
      const t = setTimeout(() => { try { g.kill() } catch { /* 已退出 */ } resolve() }, graceMs)
      g.on('exit', () => { clearTimeout(t); resolve() })
      g.on('error', () => { clearTimeout(t); resolve() })
    })
    // 给 exit 事件留出异步回弹窗口（settleMs，50ms 步进），再决定是否升级强杀
    const deadline = Date.now() + settleMs
    while (Date.now() < deadline && isRunning(id)) await sleep(50)
  }
  const forced = usedGraceful && isRunning(id)
  if (!stopCmd || forced) {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' })
    } else {
      try { process.kill(pid, 'SIGTERM') } catch { /* 已退出 */ }
    }
  }
  logTask({ project: id, action: usedGraceful ? (forced ? 'stop-force' : 'stop-graceful') : 'stop', pid, duration_ms: Date.now() - (startedAt || Date.now()), stop_command: stopCmd || undefined })
  children.delete(id)
  removeRunning(id)
  return { ok: true, id, graceful: usedGraceful }
}

/** 平台退出前回收本进程启动的子进程（事务化装配：启动过的必须可逆）。
 *  只停自己启动的（children）；其他宿主（CLI 等）登记的条目不动，由其宿主或显式 stopEntry 负责。 */
export async function shutdownAll() {
  for (const id of [...children.keys()]) {
    if (!ownRunning(id)) continue
    try { await stopEntry(id, null) } catch { /* 容错：退出路径不清空失败 */ }
  }
}
