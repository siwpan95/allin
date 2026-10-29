// @allin/portal —— 平台前台 :9000（零依赖纯 Node http，自 @relay/portal 升级）。
// 三个页签：库 Library（启停/状态）/ 工坊 Workshop（订阅）/ 引擎 Engine（allin_engine dump-profile）。
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync, spawn, execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'
import {
  loadRegistry,
  startEntry,
  stopEntry,
  isRunning,
  runningInfo,
  shutdownAll,
  probeEntry,
  listWorkshop,
  subscribe,
  unsubscribe,
  update,
  rollback,
  auditWorkshop,
  checkUpdate,
  DATA_DIR,
  resolvePath,
} from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PUBLIC = path.join(__dirname, '..', 'public')
const PLATFORM = path.join(__dirname, '..', '..', '..')
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(PLATFORM, 'registry', 'projects')
// allin_engine 引擎视图：外部项目目录不进仓（聚合不融合）——env 未配置时引擎页报「未配置」
// 而不是指向某台机器的硬编码路径（2026-09-24 强化：仓库区 repos/ 解绑，盘符随机器）。
const ENGINE_CWD = process.env.PLATFORM_ALLIN_ENGINE_CWD || null
const port = process.env.PORT !== undefined ? Number(process.env.PORT) : 9000

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
}

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(body))
}

function loopbackOnly(req, res) {
  const remote = req.socket.remoteAddress || ''
  const ok = remote === '127.0.0.1' || remote === '::1' || remote === '::ffff:127.0.0.1'
  if (!ok) { res.writeHead(403); res.end('forbidden'); return false }
  return true
}

// Host 头围栏（2026-09-24 Phase 1，借 DSH api-request-trust 纪律）：
// 防 DNS rebinding——恶意页面可把自有域名解析到 127.0.0.1，浏览器随后会带上
// 该域名的 Host 头发本机请求，socket 仍是回环（loopbackOnly 放行）但 Host 不是；
// 非「127.0.0.1 / localhost / [::1]（任意端口）」的 Host 一律 403。
// 只允许字面量回环主机名，不接受可配置白名单（单机形态无此需求，少一个误配面）。
const LOOPBACK_HOST = /^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$/i
function hostAllowed(req) {
  return LOOPBACK_HOST.test(String(req.headers.host || ''))
}

function readBody(req, maxBytes = 64 * 1024) {
  return new Promise((resolve) => {
    let data = ''
    let overflow = false
    req.on('data', (c) => {
      if (overflow) return
      data += c
      if (data.length > maxBytes) { overflow = true; data = ''; req.destroy() }
    })
    req.on('end', () => { if (!overflow) { try { resolve(data ? JSON.parse(data) : {}) } catch { resolve({}) } } })
    req.on('close', () => { if (overflow) resolve({}) })
  })
}

// allin_engine 装配视图（CLI 调用，缓存 30s；2026-09-24 强化：execFile 异步化，
// 不再 spawnSync 阻塞事件循环——引擎慢/挂死时门户其余 API 照常响应）
//
// 命名（2026-09-24 对齐 PyPI，权威口径）：
//   分发名 allin-engine ｜ 导入名 allin_engine ｜ PyPI https://pypi.org/project/allin-engine/
//   `alloy` 是被放弃的旧名——PyPI 上该名属他人（Sam Gammon @ Elide），不可再用；
//   引擎目录已由 `alloy/` 改为 `allin_engine/`（commit 72c1d63），故此处不再引用 alloy。
const execFileP = promisify(execFile)
let engineCache = { at: 0, payload: null }
const workshopCache = new Map()
async function runEngine(python, args) {
  try {
    const { stdout, stderr } = await execFileP(python, args, { cwd: ENGINE_CWD, encoding: 'utf8', timeout: 60000, shell: true })
    return { status: 0, stdout, stderr }
  } catch (e) {
    return { status: e.code ?? 1, stdout: e.stdout || '', stderr: e.stderr || String(e.message) }
  }
}
async function engineReport() {
  if (Date.now() - engineCache.at < 30000 && engineCache.payload) return engineCache.payload
  if (!ENGINE_CWD || !fs.existsSync(ENGINE_CWD)) {
    engineCache = { at: Date.now(), payload: { ok: false, error: '引擎未配置：设置 PLATFORM_ALLIN_ENGINE_CWD 指向 an-engine 项目目录后再试' } }
    return engineCache.payload
  }
  const python = process.env.PLATFORM_PYTHON || 'python'
  const r = await runEngine(python, ['-m', 'allin_engine', 'dump-profile', '--json'])
  const presets = await runEngine(python, ['-c',
    'import json; from allin_engine.core.profiles import PROFILES; print(json.dumps(list(PROFILES)))'])
  if (r.status !== 0) {
    engineCache = { at: Date.now(), payload: { ok: false, error: (r.stderr || 'allin_engine CLI 不可用').slice(-500) } }
  } else {
    try {
      engineCache = { at: Date.now(), payload: {
        ok: true,
        profile: JSON.parse(r.stdout),
        presets: presets.status === 0 ? JSON.parse(presets.stdout) : [],
      } }
    } catch {
      engineCache = { at: Date.now(), payload: { ok: false, error: 'dump-profile 输出解析失败' } }
    }
  }
  return engineCache.payload
}

async function libraryPayload() {
  const { entries, problems } = loadRegistry(REGISTRY)
  // 并行探测：慢启动服务的宽限期探测会拉长单条耗时，串行会随条目数堆叠
  const items = await Promise.all(entries.map(async (e) => {
    const info = runningInfo(e.id)
    const probe = await probeEntry(e, Boolean(info), info ? info.startedAt : null)
    return {
      id: e.id, name: e.name, category: e.category, version: e.version,
      gameplay: e.gameplay || [],
      note: e.note || null, order: e.order ?? null,
      port: e.port ?? null, path: e.path, manual: Boolean(e.manual), valid: e._valid,
      running: probe.running, via: probe.via,
      publish: e.publish ? e.publish.repo || null : null,
    }
  }))
  return { items, problems }
}

// E5 分歧事件订阅链路（订阅方）：聚合各登记项目 data/divergence-events.jsonl 的最近事件
// （registry 的 path 即事件源路径；缺失/损坏文件跳过；按 ts 倒序，封顶 100 条）。
function readAlerts() {
  const { entries } = loadRegistry(REGISTRY)
  const alerts = []
  for (const e of entries) {
    const f = path.join(resolvePath(e.path), 'data', 'divergence-events.jsonl')
    if (!fs.existsSync(f)) continue
    try {
      const lines = fs.readFileSync(f, 'utf8').trim().split('\n').slice(-20)
      for (const line of lines) {
        if (!line.trim()) continue
        try { alerts.push({ project: e.id, ...JSON.parse(line) }) } catch { /* 坏帧跳过（D1 纪律） */ }
      }
    } catch { /* 读取失败跳过该项目 */ }
  }
  alerts.sort((a, b) => String(b.ts).localeCompare(String(a.ts)))
  return alerts.slice(0, 100)
}

const server = http.createServer(async (req, res) => {
  // Host 围栏在最前：GET 读取面（/api/library 含全盘路径信息）同样受保护，
  // 不止写操作的 loopbackOnly（2026-09-24 Phase 1）
  if (!hostAllowed(req)) { res.writeHead(403); return res.end('forbidden') }
  const url = new URL(req.url, 'http://x')
  const p = url.pathname

  if (p === '/api/status' && req.method === 'GET') {
    return json(res, 200, { version: '0.1.0', uptime: Math.round(process.uptime()), platform: 'allin-platform', port })
  }
  if (p === '/api/library' && req.method === 'GET') {
    return json(res, 200, await libraryPayload())
  }
  const startM = p.match(/^\/api\/library\/([a-z0-9-]+)\/start$/)
  if (startM && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    const { entries } = loadRegistry(REGISTRY)
    const entry = entries.find(e => e.id === startM[1])
    if (!entry) return json(res, 404, { error: 'unknown id' })
    try {
      return json(res, 200, startEntry(entry, { owner: 'portal' }))
    } catch (e) {
      return json(res, 400, { error: String(e.message) })
    }
  }
  const stopM = p.match(/^\/api\/library\/([a-z0-9-]+)\/stop$/)
  if (stopM && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    const { entries } = loadRegistry(REGISTRY)
    const entry = entries.find(e => e.id === stopM[1])
    // dispose 纪律：优先优雅停止（entry.stop.command），缺省回退树杀（异步，不阻塞事件循环）
    return json(res, 200, await stopEntry(stopM[1], entry || null))
  }
  const alertsM = p.match(/^\/api\/alerts$/)
  if (alertsM && req.method === 'GET') {
    return json(res, 200, { alerts: readAlerts() })
  }
  // 门禁执行留痕（P0-2）：scripts/run_all_gates.sh 每次执行落一行 JSONL，
  // 这里把它读出来，供「逃逸率 / 证据新鲜度」在界面上看得见。
  if (p === '/api/gate-history' && req.method === 'GET') {
    const trail = process.env.ALLIN_GATE_RUNS
      || path.join(PLATFORM, '..', 'tools', 'gate', 'audit', 'gate-runs.jsonl')
    const runs = []
    let readable = true
    try {
      for (const line of fs.readFileSync(trail, 'utf8').split('\n')) {
        const text = line.trim()
        if (!text) continue
        try { runs.push(JSON.parse(text)) } catch { /* 坏行跳过，不整体失败 */ }
      }
    } catch { readable = false }
    const tail = runs.slice(-200)
    const failed = tail.filter(r => Number(r.exit) !== 0).length
    const okRuns = tail.filter(r => Number(r.exit) === 0)
    return json(res, 200, {
      trail,
      readable,
      runs: tail,
      summary: {
        total: runs.length,
        inTail: tail.length,
        failed,
        escapeRate: tail.length ? Number((failed / tail.length).toFixed(4)) : 0,
        lastRunAt: tail.length ? tail[tail.length - 1].ts : null,
        lastOkAt: okRuns.length ? okRuns[okRuns.length - 1].ts : null
      }
    })
  }
  if (p === '/api/workshop' && req.method === 'GET') {
    const { entries } = loadRegistry(REGISTRY)
    const base = listWorkshop(entries)
    // 订阅项比对发布面最新提交（60s 缓存，避免前端 5s 刷新打满 gitee API）
    for (const item of base.catalog) {
      if (!item.subscribed) continue
      const entry = entries.find(e => e.id === item.id)
      const cache = workshopCache.get(item.id)
      if (cache && Date.now() - cache.at < 60000) {
        item.updateAvailable = cache.updateAvailable
        item.pendingCommit = cache.pendingCommit
        item.checkError = cache.checkError || null
        continue
      }
      const ck = await checkUpdate(item.id, entry)
      workshopCache.set(item.id, { at: Date.now(), updateAvailable: ck.updateAvailable, pendingCommit: ck.latest, checkError: ck.checkError || null })
      item.updateAvailable = ck.updateAvailable
      item.pendingCommit = ck.latest
      item.checkError = ck.checkError || null
    }
    return json(res, 200, base)
  }
  const subM = p.match(/^\/api\/workshop\/([a-z0-9-]+)\/(subscribe|unsubscribe|update|rollback)$/)
  if (subM && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    const { entries } = loadRegistry(REGISTRY)
    const entry = entries.find(e => e.id === subM[1])
    if (!entry) return json(res, 404, { error: 'unknown id' })
    let result
    if (subM[2] === 'subscribe') result = await subscribe(entry.id, entry)
    else if (subM[2] === 'unsubscribe') {
      // 事务化装配（dispose 纪律）：退订 = 先停（优雅/树杀）再删，杜绝「删了还在跑」的孤儿进程
      if (isRunning(entry.id)) await stopEntry(entry.id, entry)
      result = unsubscribe(entry.id)
    }
    else if (subM[2] === 'update') result = await update(entry.id, entry)
    else result = rollback(entry.id)
    return json(res, result.ok ? 200 : 400, result)
  }
  if (p === '/api/workshop/audit' && req.method === 'GET') {
    return json(res, 200, { audit: auditWorkshop() })
  }
  if (p === '/workshop/catalog' && req.method === 'GET') {
    const { entries } = loadRegistry(REGISTRY)
    // HTML 转义（2026-09-24 强化）：registry yaml 虽是本地可信数据，但服务端拼 HTML
    // 一律转义（对齐自身 XSS 纪律，防 yaml 字段引入特殊字符破页）
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
    const rows = entries.filter(e => e.publish && e.publish.repo).map(e => {
      const branch = e.publish.branch || 'master'
      const url = `https://gitee.com/${e.publish.repo.split('/').map(encodeURIComponent).join('/')}/tree/${encodeURIComponent(branch)}`
      return `<tr><td>${esc(e.name)}</td><td>${esc(e.category)}</td><td>v${esc(e.version)}</td><td><a href="${url}" target="_blank">${esc(e.publish.repo)} #${esc(branch)}</a></td></tr>`
    }).join('')
    const html = `<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><title>工坊目录 · allin-platform</title>` +
      `<style>body{background:#10141a;color:#d8dee9;font-family:"Microsoft YaHei",sans-serif;max-width:900px;margin:30px auto;padding:0 20px}` +
      `table{border-collapse:collapse;width:100%}td,th{border:1px solid #263142;padding:8px 12px;text-align:left}a{color:#7fd0ff}</style></head>` +
      `<body><h1>工坊目录（静态页 · 全部公开 MIT）</h1><p>共 ${rows.length} 个插件/项目发布面；订阅/更新/回滚请回平台工坊页。</p>` +
      `<table><tr><th>名称</th><th>分类</th><th>版本</th><th>发布面（gitee）</th></tr>${rows}</table></body></html>`
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    return res.end(html)
  }
  if (p === '/api/engine' && req.method === 'GET') {
    return json(res, 200, await engineReport())
  }
  if (p === '/api/shutdown' && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    await shutdownAll()
    json(res, 200, { ok: true })
    return setTimeout(() => process.exit(0), 150)
  }

  // 静态文件（同 @relay/portal 纪律）
  let fp = p === '/' ? '/index.html' : p
  const abs = path.join(PUBLIC, path.normalize(fp).replace(/^(\.\.[/\\])+/, ''))
  // 前缀校验用「路径分隔符边界」而非裸字符串前缀（2026-09-24 强化）：
  // 裸 startsWith(PUBLIC) 会放行 public-evil 这类同级前缀目录
  if ((!abs.startsWith(PUBLIC + path.sep) && abs !== PUBLIC) || !fs.existsSync(abs) || fs.statSync(abs).isDirectory()) {
    res.writeHead(404)
    return res.end('not found')
  }
  res.setHeader('Content-Type', MIME[path.extname(abs)] || 'application/octet-stream')
  fs.createReadStream(abs).pipe(res)
})

server.listen(port, '127.0.0.1', () => {
  const actual = server.address().port
  // 端口发现（CLI/宿主用）：实际端口写入 data/portal.port，进程退出时删除；
  // 被强杀时文件可能残留，消费方须以 /api/status 探活兜底。
  const PORT_FILE = path.join(DATA_DIR, 'portal.port')
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true })
    fs.writeFileSync(PORT_FILE, String(actual), 'utf8')
    process.on('exit', () => { try { fs.rmSync(PORT_FILE, { force: true }) } catch { /* 已不在 */ } })
  } catch (e) {
    console.error('[portal] 端口文件写入失败: ' + e.message)
  }
  // 按需启动（DSH 同款形态）：PORT=0 时打印实际绑定端口，供启动器/宿主发现；不再常驻 9000
  console.log('[allin-platform portal] http://127.0.0.1:' + actual + '/')
  if (process.env.PORTAL_AUTO_OPEN === '1') {
    // 自动打开默认浏览器（Windows）；测试（PLATFORM_ROOT 隔离）与手动模式不触发
    try {
      const cp = spawnSync('cmd', ['/c', 'start', '', 'http://127.0.0.1:' + actual + '/'], { stdio: 'ignore' })
      if (cp.error) console.error('[portal] auto-open failed: ' + cp.error.message)
    } catch (e) {}
  }
})

export { server }
