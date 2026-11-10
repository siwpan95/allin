// @allin/core — 子进程启停（子进程隔离）+ pid 持久化（running.json，跨进程可见可停）+ JSONL 任务日志（WorldLog 同构）。
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolvePath, commandProblems, pathProblems, splitCommandTokens } from './registry.js'

const HERE = path.dirname(fileURLToPath(import.meta.url))

// 平台根（data/ 等运行时状态落点）：env PLATFORM_ROOT 优先；缺失时回退仓库根
// （2026-09-24 强化：platform/ 绝对路径解绑（盘符随机器）——仓库克隆到任意目录即可跑，
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
  // 原子写统一走 writeAtomically（R-05 收敛，2026-11-10）：temp 文件 + fsync + rename 原子替换，
  // 覆盖前把当前完好内容存 .bak——并发写/崩溃不再产生半截 JSON 或丢整表。
  // （此前 writeRunning 内联了一份 temp+fsync+rename，与 writeDurable 同语义但各写一遍。）
  writeAtomically(RUNNING_FILE, JSON.stringify(map, null, 2) + '\n', { backup: true })
}

/** 原子写（R-05 收敛，2026-11-10）：temp 文件 + fsync + rename，可选 .bak 回退。
 * 供所有需要 durable 落盘的状态文件（running.json / workshop.json / portal.port / portal.token）复用，
 * 避免各处重实现 temp+fsync+rename 且口径不一致（此前 workshop / portal 漏了 fsync 或 .bak）。
 * @param {boolean} [opts.backup] 覆盖前把当前完好内容存 .bak（崩溃可回退整表）
 * @param {number}  [opts.mode]   创建/落盘权限位（默认不显式设，沿用 umask；令牌类传 0o600） */
export function writeAtomically(file, data, { backup = false, mode } = {}) {
  const tmp = file + '.' + process.pid + '.tmp'
  writeDurable(tmp, data, mode)
  if (backup) {
    try {
      const cur = fs.readFileSync(file, 'utf8')
      JSON.parse(cur)
      fs.writeFileSync(file + '.bak', cur, 'utf8')
    } catch { /* 主文件缺失/损坏：无可备份 */ }
  }
  fs.renameSync(tmp, file)
}

/** durable 写：open → write → fsync → close（供 temp+rename 前置落盘）。 */
export function writeDurable(file, data, mode) {
  const fd = fs.openSync(file, 'w', mode)
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

/** pid 存活探测（跨平台；EPERM 视为存活——存在但不可信号）。
 *
 * 语义约定（R-02 2026-11-10 功能内聚整改）：本函数与
 * kernel/services/status_service.py:_pid_alive 必须为**同一语义**，否则 portal 与 kernel
 * 对同一 pid 给出不同「存活」结论。约定：pid 非法/≤0 → false；可发 signal-0（含 EPERM
 * 无权限）→ true；不存在(ESRCH/ENOENT)或异常 → false。改动此处须同步 Python 侧。
 */
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
 * 启动命令预处理 —— 2026-11-10 深度审计 P0-1 重构。
 *
 * 原实现把整条命令字符串交给 `spawn(..., {shell:true})`。即便 commandProblems 禁了
 * shell 元字符，shell 仍是多余的一层解释器：解释器内联参数、shell 内建命令、
 * 关联打开都经它，攻击面无法收敛（OWASP OS Command Injection Defense Cheat Sheet：
 * 「Avoid running sh -c, cmd.exe or powershell.exe with untrusted input」）。
 *
 * 现在按命令形态分流：
 *   - 「可执行文件 + 参数」（python/node/npm/bash/git/make/... 及 *.exe）
 *     → `spawn(file, args, {shell:false})`，命令与参数严格分离，元字符无解释层；
 *   - 依赖 shell 关联 / 内建的少数形态（*.bat / *.cmd / *.html / start / dir）
 *     → 保留 `shell:true`，但它们已通过 commandProblems 的严格形状白名单。
 *
 * npm 沿用既有垫片修正（2026-08-28 实测）：detached 下 npm.cmd 批处理会卡死，
 * 改由当前 node 直启 npm-cli.js —— 数组化后路径含空格也无需再加引号。
 */
const NO_SHELL_HEAD = /^(?:python|python3|pythonw|py|node|npm|npx|bash|sh|git|make|ls|echo|dse|robocopy|explorer)(?:\.exe)?$/i

export function buildSpawnPlan(command) {
  const problems = commandProblems(command)
  if (problems.length) {
    const err = new Error(`命令未通过形状校验：${problems.join('; ')}`)
    err.code = 'UNSAFE_COMMAND'
    throw err
  }
  const tokens = splitCommandTokens(String(command).trim())
  const head = tokens[0]
  const rest = tokens.slice(1)
  if (/^npm$/i.test(head)) {
    const npmCli = path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js')
    if (fs.existsSync(npmCli)) return { file: process.execPath, args: [npmCli, ...rest], shell: false }
  }
  if (NO_SHELL_HEAD.test(head) || /\.exe$/i.test(head)) {
    return { file: head, args: rest, shell: false }
  }
  return { command: String(command).trim(), args: [], shell: true }
}

/** 统一执行计划：所有 spawn 都必须经此，避免某个调用点漏掉 shell 收敛。 */
function spawnFromPlan(plan, options) {
  const opts = { ...options, shell: plan.shell }
  return plan.shell
    ? spawn(plan.command, opts)
    : spawn(plan.file, plan.args, opts)
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
  // fail-closed：即便调用方绕过 loadRegistry 直接构造 entry，也不执行不安全的命令。
  const startProblems = commandProblems(entry.launch && entry.launch.command)
  if (startProblems.length) {
    const err = new Error(`启动命令未通过形状校验（${entry._file || entry.id}）：${startProblems.join('; ')}`)
    err.code = 'UNSAFE_COMMAND'
    throw err
  }
  // 2026-11-10 深度审计 S-2 执行层二次防御：path 也不得越界（allowAbsolute 是给
  // 程序内部构造的临时 entry 用的，如测试夹具用 os.tmpdir() 当 cwd）。
  const pathErrs = pathProblems(entry.path, { allowAbsolute: true })
  if (pathErrs.length) {
    const err = new Error(`启动路径未通过形状校验（${entry._file || entry.id}）：${pathErrs.join('; ')}`)
    err.code = 'PATH_ESCAPE'
    throw err
  }
  const startedAt = Date.now()
  const child = spawnFromPlan(buildSpawnPlan(entry.launch.command), {
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
  if (stopCmd && commandProblems(stopCmd).length === 0 && pathProblems(entry.path || '', { allowAbsolute: true }).length === 0) {
    usedGraceful = true
    // 优雅停止：等待 stop 命令退出（graceMs 封顶杀之），不阻塞事件循环
    await new Promise((resolve) => {
      let g
      try {
        g = spawnFromPlan(buildSpawnPlan(stopCmd), {
          cwd: (entry.path && resolvePath(entry.path)) || process.cwd(), stdio: 'ignore',
        })
      } catch (e) {
        // 2026-11-10：命令/路径校验异常不得让 stopEntry 变成 unhandled rejection。
        logTask({ project: id, action: 'stop-graceful-error', error: String(e.message) })
        usedGraceful = false
        resolve()
        return
      }
      const t = setTimeout(() => { try { g.kill() } catch { /* 已退出 */ } resolve() }, graceMs)
      g.on('exit', () => { clearTimeout(t); resolve() })
      g.on('error', () => { clearTimeout(t); resolve() })
    })
    // 给 exit 事件留出异步回弹窗口（settleMs，50ms 步进），再决定是否升级强杀
    const deadline = Date.now() + settleMs
    while (Date.now() < deadline && isRunning(id)) await sleep(50)
  } else if (stopCmd) {
    // 不安全的停止命令绝不执行；留痕后直接走下面的强杀路径，不静默吞掉。
    logTask({ project: id, action: 'stop-command-rejected', reason: 'unsafe command shape' })
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
