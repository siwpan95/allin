#!/usr/bin/env node
// @allin/cli —— allin-platform 命令行接口（ES 之于 Everything 的形态）。
// 分层纪律：
//   - 只读命令（list / search / status <id>）直连 registry 数据，门户未运行也可用；
//   - 启停（start / stop）直连 core——pid 持久化到 data/running.json，门户与
//     CLI 启动的项目互相可见、互相可停（谁启的谁才能停的割裂已消除）；
//   - 其余写命令（订阅 / shutdown 等）走门户 HTTP API（缓存与事务在门户层）。
// 端口发现：portal 启动时把实际端口写入 data/portal.port；本 CLI 读取后先以
// /api/status 探活兜底（进程被强杀时端口文件可能残留）。
import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { loadRegistry, probeEntry, startEntry, stopEntry, isRunning, runningInfo } from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.join(__dirname, '..', '..', '..')
const PLATFORM_ROOT = process.env.PLATFORM_ROOT || REPO_ROOT
const PORT_FILE = path.join(PLATFORM_ROOT, 'data', 'portal.port')
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(REPO_ROOT, 'registry', 'projects')

// ---------- 纯函数（导出供测试） ----------

/** 多关键词 AND 模糊匹配：命中 id/name/category/version/gameplay/note/publish.repo 任意拼接文本。 */
export function filterEntries(entries, query) {
  const terms = String(query || '').trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (!terms.length) return entries
  return entries.filter((e) => {
    const hay = [
      e.id, e.name, e.category, e.version,
      ...(e.gameplay || []), e.note || '',
      e.publish ? e.publish.repo : '',
    ].join(' ').toLowerCase()
    return terms.every((t) => hay.includes(t))
  })
}

/** 显示宽度（CJK 全角算 2 列，其余 1 列）——保证中文表格对齐。 */
export function displayWidth(s) {
  let w = 0
  for (const ch of String(s)) {
    const cp = ch.codePointAt(0)
    const cjk = (cp >= 0x2e80 && cp <= 0x9fff) ||
      (cp >= 0xf900 && cp <= 0xfaff) ||
      (cp >= 0xff00 && cp <= 0xff60) ||
      (cp >= 0x3000 && cp <= 0x303f) ||
      (cp >= 0xfe30 && cp <= 0xfe4f)
    w += cjk ? 2 : 1
  }
  return w
}

function padEnd(s, width) {
  return s + ' '.repeat(Math.max(0, width - displayWidth(s)))
}

/** 渲染对齐表格：表头 + 分隔线 + 数据行。 */
export function renderTable(headers, rows) {
  const widths = headers.map((_, i) =>
    Math.max(...[headers, ...rows].map((r) => displayWidth(String(r[i] ?? '')))))
  const line = (cells) => cells.map((c, i) => padEnd(String(c ?? ''), widths[i])).join('  ')
  return [line(headers), widths.map((w) => '-'.repeat(w)).join('  '), ...rows.map(line)].join('\n')
}

/** 读取门户端口文件；缺失/损坏返回 null。 */
export function readPortalPort() {
  try {
    const n = Number(fs.readFileSync(PORT_FILE, 'utf8').trim())
    return Number.isInteger(n) && n > 0 ? n : null
  } catch {
    return null
  }
}

// ---------- 门户 HTTP 客户端 ----------

function fail(msg) {
  console.error('错误: ' + msg)
  process.exit(1)
}

/** 探活门户并返回 base URL；未运行/超时返回 null。 */
async function portalBase(timeoutMs = 3000) {
  const port = readPortalPort()
  if (!port) return null
  const base = 'http://127.0.0.1:' + port
  try {
    const res = await fetch(base + '/api/status', { signal: AbortSignal.timeout(timeoutMs) })
    if (res.ok) return base
  } catch { /* 探活失败 = 未运行 */ }
  return null
}

async function api(pathname, method = 'GET') {
  const base = await portalBase()
  if (!base) {
    fail('门户未运行。先运行 start-platform.bat 或 allin open，再执行该命令。')
  }
  let res
  try {
    res = await fetch(base + pathname, { method, signal: AbortSignal.timeout(120000) })
  } catch (e) {
    fail('请求门户失败: ' + e.message)
  }
  const body = await res.json().catch(() => ({}))
  return { status: res.status, body }
}

// ---------- 命令实现 ----------

function loadEntries() {
  const { entries, problems } = loadRegistry(REGISTRY)
  if (problems.length) console.error('警告 注册表问题: ' + problems.join('; '))
  return entries
}

async function libraryRows(entries) {
  const probes = await Promise.all(entries.map((e) => {
    const info = runningInfo(e.id)
    return probeEntry(e, Boolean(info), info ? info.startedAt : null)
  }))
  return entries.map((e, i) => [
    e.id, e.name, e.category, 'v' + e.version,
    probes[i].running ? (probes[i].via === 'starting' ? '启动中' : '运行中') : '-', probes[i].via,
  ])
}

async function cmdList() {
  const entries = loadEntries()
  console.log(renderTable(['ID', '名称', '分类', '版本', '状态', '探测'], await libraryRows(entries)))
  console.log('\n共 ' + entries.length + ' 个登记项目')
}

async function cmdSearch(args) {
  if (!args.length) fail('用法: allin search <关键词> [...]（多个关键词为 AND 匹配）')
  const entries = filterEntries(loadEntries(), args.join(' '))
  if (!entries.length) {
    console.log('没有匹配 "' + args.join(' ') + '" 的项目')
    return
  }
  console.log(renderTable(['ID', '名称', '分类', '版本', '状态', '探测'], await libraryRows(entries)))
  console.log('\n匹配 ' + entries.length + ' 个项目')
}

async function cmdStatus(args) {
  if (!args.length) {
    const base = await portalBase()
    if (!base) {
      console.log('门户: 未运行（allin open 可启动门户并打开浏览器）')
      return
    }
    const { body } = await api('/api/status')
    console.log('门户: ' + base + '/')
    console.log(renderTable(['字段', '值'], [
      ['版本', body.version], ['运行秒数', body.uptime], ['平台', body.platform],
    ]))
    return
  }
  const id = args[0]
  const entry = loadEntries().find((e) => e.id === id)
  if (!entry) fail('未知项目 id: ' + id + '（allin search <关键词> 可检索）')
  const info = runningInfo(entry.id)
  const probe = await probeEntry(entry, Boolean(info), info ? info.startedAt : null)
  const runState = probe.running ? (probe.via === 'starting' ? '启动中' : '运行中 (' + probe.via + ')') : '停止 (' + probe.via + ')'
  console.log(renderTable(['字段', '值'], [
    ['ID', entry.id], ['名称', entry.name], ['分类', entry.category],
    ['版本', 'v' + entry.version], ['路径', entry.path],
    ['端口', entry.port ?? '-'], ['标签', (entry.gameplay || []).join(', ') || '-'],
    ['备注', entry.note || '-'],
    ['发布面', entry.publish ? entry.publish.repo + ' #' + (entry.publish.branch || 'master') : '-'],
    ['manual', entry.manual ? '是' : '否'],
    ['运行状态', runState],
  ]))
}

function needId(args, usage) {
  if (!args.length) fail('用法: ' + usage)
  return args[0]
}

function findEntry(id) {
  const entry = loadEntries().find((e) => e.id === id)
  if (!entry) fail('未知项目 id: ' + id + '（allin search <关键词> 可检索）')
  return entry
}

async function cmdStart(args) {
  const id = needId(args, 'allin start <id>')
  const entry = findEntry(id)
  try {
    const r = startEntry(entry, { owner: 'cli' })
    if (r.ok) console.log('已启动 ' + id + ' (pid ' + r.pid + ')')
    else if (r.reason === 'already-running') console.log(id + ' 已在运行')
    else fail('启动失败: ' + JSON.stringify(r))
  } catch (e) {
    fail('启动失败: ' + e.message)
  }
}

async function cmdStop(args) {
  const id = needId(args, 'allin stop <id>')
  const entry = loadEntries().find((e) => e.id === id) || null
  const r = await stopEntry(id, entry)
  if (r.ok) console.log('已停止 ' + id + (r.graceful ? '（优雅停止）' : '（树杀）'))
  else if (r.reason === 'not-running') console.log(id + ' 未在运行')
  else fail('停止失败: ' + JSON.stringify(r))
}

async function cmdWorkshop() {
  const { body } = await api('/api/workshop')
  const rows = (body.catalog || []).map((i) => [
    i.id, i.name, i.category, 'v' + i.version,
    i.subscribed ? '已订阅' : '-', i.updateAvailable ? '可更新' : '-',
    i.copyExists ? '有' : '-',
  ])
  console.log(renderTable(['ID', '名称', '分类', '版本', '订阅', '更新', '副本'], rows))
}

async function workshopAction(args, action, usage) {
  const id = needId(args, usage)
  const { status, body } = await api('/api/workshop/' + id + '/' + action, 'POST')
  if (status === 404) fail('未知项目 id: ' + id)
  if (!body.ok) fail(action + ' 失败: ' + (body.error || JSON.stringify(body)))
  console.log(action + ' ' + id + ' 完成')
}

async function cmdSub(args) { await workshopAction(args, 'subscribe', 'allin sub <id>') }
async function cmdUnsub(args) { await workshopAction(args, 'unsubscribe', 'allin unsub <id>') }
async function cmdUpdate(args) { await workshopAction(args, 'update', 'allin update <id>') }
async function cmdRollback(args) { await workshopAction(args, 'rollback', 'allin rollback <id>') }

async function cmdAlerts() {
  const { body } = await api('/api/alerts')
  const alerts = body.alerts || []
  if (!alerts.length) return console.log('无分歧事件')
  const rows = alerts.map((a) => [
    a.ts || '-', a.project || '-', a.case || '-',
    String(a.consensus ?? '-'), String(a.errors ? a.errors.length : 0),
  ])
  console.log(renderTable(['时间', '项目', '用例', '共识', '错误数'], rows))
}

async function cmdEngine() {
  const { body } = await api('/api/engine')
  if (!body.ok) return console.log('引擎报告失败: ' + String(body.error || '?').slice(0, 300))
  console.log('allin_engine profile: ' + JSON.stringify(body.profile).slice(0, 400))
  console.log('presets: ' + (body.presets || []).join(', '))
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function cmdOpen() {
  let base = await portalBase()
  if (!base) {
    console.log('门户未运行，正在启动（start-platform.bat；首次运行可能需要安装依赖）...')
    const child = spawn('cmd', ['/c', 'start-platform.bat'], {
      cwd: PLATFORM_ROOT, detached: true, stdio: 'ignore',
    })
    child.unref()
    for (let i = 0; i < 90 && !base; i++) {
      await sleep(1000)
      base = await portalBase(1000)
    }
  }
  if (!base) fail('门户 90 秒内未就绪：请手动运行 start-platform.bat 查看输出。')
  spawn('cmd', ['/c', 'start', '', base + '/'], { detached: true, stdio: 'ignore' }).unref()
  console.log('门户: ' + base + '/')
}

async function cmdShutdown() {
  await api('/api/shutdown', 'POST')
  console.log('门户已停止，端口已释放')
}

function cmdHelp() {
  console.log(`allin —— allin-platform 命令行接口（门户未运行时只读命令仍可用）

用法: allin <命令> [参数]

只读（直连 registry，无需门户）:
  list | ls                   列出全部登记项目与运行状态
  search <关键词> [...]        多关键词 AND 模糊搜索（id/名称/分类/标签/备注）
  status [id]                 无 id 看门户状态；有 id 看项目详情

启停（直连 core，pid 持久化到 data/running.json，无需门户）:
  start <id> | stop <id>      启动 / 停止登记项目（门户与 CLI 互相可见可停）

门户操作（需要门户运行，未运行时会提示）:
  workshop                    工坊订阅面
  sub <id> | unsub <id>       订阅 / 退订
  update <id> | rollback <id> 更新 / 回滚
  alerts                      E5 分歧事件
  engine                      allin_engine 引擎报告
  open                        打开门户浏览器（未运行则先启动门户）
  shutdown                    停止门户并释放端口`)
}

const COMMANDS = {
  list: cmdList, ls: cmdList, search: cmdSearch, status: cmdStatus,
  start: cmdStart, stop: cmdStop, workshop: cmdWorkshop,
  sub: cmdSub, unsub: cmdUnsub, update: cmdUpdate, rollback: cmdRollback,
  alerts: cmdAlerts, engine: cmdEngine, open: cmdOpen, shutdown: cmdShutdown,
  help: cmdHelp,
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
if (isMain) {
  const [cmd, ...args] = process.argv.slice(2)
  const fn = COMMANDS[cmd]
  if (!fn) {
    if (cmd) console.error('未知命令: ' + cmd + '\n')
    cmdHelp()
    process.exit(cmd ? 1 : 0)
  }
  await fn(args)
}
