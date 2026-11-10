// @allin/portal —— 平台前台（PORT 指定端口，默认 0 = OS 临时端口；零依赖纯 Node http，自 @relay/portal 升级）。
// 端口口径以 docs/事实源/ports.yaml 为准：9000 已退役为「仅手动可选」，不再是默认值（审计 §六第二阶段）。
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
  writeAtomically,
} from '@allin/core'
import { overviewPayload, orchestrationPayload } from './bridge.js'
import { createTokenGate } from './auth.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
// 令牌在服务启动期确定；index.html 注入与 CLI/website 读文件都取同一份。
const gate = createTokenGate(DATA_DIR)
const PUBLIC = path.join(__dirname, '..', 'public')
const PLATFORM = path.join(__dirname, '..', '..', '..')
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(PLATFORM, 'registry', 'projects')
// allin_engine 引擎视图：外部项目目录不进仓（聚合不融合）——env 未配置时引擎页报「未配置」
// 而不是指向某台机器的硬编码路径（2026-09-24 强化：仓库区 repos/ 解绑，盘符随机器）。
const ENGINE_CWD = process.env.PLATFORM_ALLIN_ENGINE_CWD || null
// 配置端口：默认 0（OS 临时端口），对齐 docs/事实源/ports.yaml「9000 退役、按需临时端口」口径。
// 显式 PORT=9000 仍可手动占固定端口（仅手动可选），但默认不再常驻。
const port = process.env.PORT !== undefined ? Number(process.env.PORT) : 0
// 实际绑定端口（listen 后回填）：PORT=0 时配置端口恒为 0，与实际端口不同。
// /api/status 与 bridge overview 都只报 boundPort（实际值），报配置端口会让消费方误判
// （2026-11-04 实测修正；2026-11-11 第二阶段把 /api/status 口径一并对齐）。
let boundPort = port

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

// 状态变更围栏（2026-11-04 工程审查 P0 + 2026-11-08 深度审核 P1）：
// Host 围栏挡的是 DNS rebinding，挡不住 CSRF，更挡不住「本机任意进程直接发包」。
// 因此所有非 GET/HEAD 请求统一在这里过**两道闸**，而不是逐个端点挂：
//   A) 令牌闸：必须带 X-Allin-Token，值与启动期生成的 portal.token 相等。
//      此前只靠 `X-Allin-Local: 1` 这个无凭证标记 ⇒ 同机即管理员（可 shutdown）。
//      令牌由服务写入 data/portal.token（0600）并经 index.html 注入前端，
//      CLI / website 代理读同一文件；跨站页面既读不到文件也无法伪造该头
//      （自定义头触发 CORS 预检，本服务不返回任何 CORS 响应头）。
//   B) 来源闸：CLI/脚本显式带 X-Allin-Local: 1；或浏览器同源请求满足
//      Sec-Fetch-Site ∈ {same-origin, none} 且 Origin == http://<Host>。
//      二者皆不具备的裸请求一律拒绝（无来源信号 = 不可判定，按 g10 大声拒绝）。
function stateChangeAllowed(req, res) {
  // 拒绝前先消费掉请求体，否则 socket 上残留未读数据会让客户端收到 ECONNRESET，
  // 掩盖了「403」这个真实结论（也避免连接异常被误读成服务故障）。
  const deny = (reason) => {
    req.resume()
    res.writeHead(403)
    res.end(`forbidden (${reason})`)
    return false
  }
  if (!gate.valid(req)) return deny('missing or invalid portal token')
  if (req.headers['x-allin-local'] === '1') return true
  const site = String(req.headers['sec-fetch-site'] || '').toLowerCase()
  if (site && site !== 'same-origin' && site !== 'none') return deny('cross-site')
  const origin = String(req.headers.origin || '')
  if (origin && origin !== `http://${String(req.headers.host || '')}`) return deny('origin')
  if (!site && !origin) return deny('missing source signal')
  return true
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
    const { stdout, stderr } = await execFileP(python, args, { cwd: ENGINE_CWD, encoding: 'utf8', timeout: 60000 })
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

// 2026-11-10 深度审计 H-1：请求处理抽成独立 async 函数，由下面的 wrapper 统一兜底。
// 原写法 `http.createServer(async (req,res)=>{...})` 的抛错**不会被 Node 捕获**：
// async 函数 throw = Promise rejection，Node ≥15 默认 --unhandled-rejections=throw
// ⇒ 整个 portal 进程 exit 1。实测一条 `port: not-a-number` 的 registry 数据就能
// 经 probePort → Promise.all → libraryPayload 打挂门户。
async function requestHandler(req, res) {
  // Host 围栏在最前：GET 读取面（/api/library 含全盘路径信息）同样受保护，
  // 不止写操作的 loopbackOnly（2026-09-24 Phase 1）
  if (!hostAllowed(req)) { res.writeHead(403); return res.end('forbidden') }
  // 状态变更统一过来源围栏（GET/HEAD 读取面不受影响，Host 围栏仍覆盖它们）
  if (req.method !== 'GET' && req.method !== 'HEAD' && !stateChangeAllowed(req, res)) return
  const url = new URL(req.url, 'http://x')
  const p = url.pathname

  if (p === '/api/status' && req.method === 'GET') {
    return json(res, 200, { version: '0.1.0', uptime: Math.round(process.uptime()), platform: 'allin-platform', boundPort })
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
      // E-01（2026-11-10 功能内聚整改）：core 抛的是带 err.code 的结构化错误
      // （INVALID_ENTRY / UNSAFE_COMMAND），这里必须保留 code 跨接缝存活，否则下游
      // （CLI / website / MCP）无法区分「清单非法」与「命令不安全」。
      const code = (e && e.code) || 'START_FAILED'
      return json(res, 400, { error: String(e.message), code })
    }
  }
  const stopM = p.match(/^\/api\/library\/([a-z0-9-]+)\/stop$/)
  if (stopM && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    const { entries } = loadRegistry(REGISTRY)
    const entry = entries.find(e => e.id === stopM[1])
    // dispose 纪律：优先优雅停止（entry.stop.command），缺省回退树杀（异步，不阻塞事件循环）
    // 2026-11-04 P2 修复（F-020）：stopEntry 内部 logTask / removeRunning 可能抛，
    // 未捕获会让整个 async handler 变成 unhandled rejection ⇒ 详情页 500。
    try {
      return json(res, 200, await stopEntry(stopM[1], entry || null))
    } catch (e) {
      // E-01：保留上游 code（STOP_FAILED / UNSAFE_COMMAND 等），供 website 侧透传。
      const code = (e && e.code) || 'STOP_FAILED'
      return json(res, 200, { ok: false, reason: 'stop-failed', code, error: String((e && e.message) || e) })
    }
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
    // SKIP 单列：仅 `skipped === true` 才算 SKIP；旧留痕无该字段按真跑兼容回放。
    // SKIP 不计入 failed / escapeRate / lastOkAt；runs 仍返回全部行（含 SKIP）供界面查看。
    const real = tail.filter(r => r.skipped !== true)
    const failed = real.filter(r => Number(r.exit) !== 0).length
    const okRuns = real.filter(r => Number(r.exit) === 0)
    return json(res, 200, {
      trail,
      readable,
      runs: tail,
      summary: {
        total: runs.length,
        inTail: tail.length,
        failed,
        skipped: tail.length - real.length,
        escapeRate: real.length ? Number((failed / real.length).toFixed(4)) : 0,
        lastRunAt: tail.length ? tail[tail.length - 1].ts : null,
        lastOkAt: okRuns.length ? okRuns[okRuns.length - 1].ts : null
      }
    })
  }
  // ── bridge 只读聚合（P4-M1 · 三面贯通 G1/G2/G4 数据面）────────────────────────
  // Host 围栏已在最顶端全局生效；两个只读端点额外过 loopbackOnly（P2 §5 S1 收紧口径）。
  // deps 注入：bridge 不 import core，依赖方向 index → bridge 单向无环（P2 §1.1）。
  if (p === '/api/overview' && req.method === 'GET') {
    if (!loopbackOnly(req, res)) return
    return json(res, 200, await overviewPayload({ loadRegistry, isRunning, readAlerts, registryDir: REGISTRY, boundPort }))
  }
  if (p === '/api/orchestration' && req.method === 'GET') {
    if (!loopbackOnly(req, res)) return
    return json(res, 200, orchestrationPayload(url.searchParams))
  }

  if (p === '/api/workshop' && req.method === 'GET') {
    const { entries } = loadRegistry(REGISTRY)
    const base = listWorkshop(entries)
    // 订阅项比对发布面最新提交（60s 缓存，避免前端 5s 刷新打满 gitee API）。
    // M-7：与 libraryPayload()(:166) 对齐改 Promise.all 并发——串行时总延迟 = Σ 各订阅延迟。
    // 每条任务内部 try/catch 就地降级：checkUpdate 用 checkError 表达网络故障；未来若它
    // 真抛异常，也只让该条带 checkError 降级，不让单条订阅把整个接口变成 500（与 H-1 同向）。
    await Promise.all(base.catalog.map(async (item) => {
      if (!item.subscribed) return
      const entry = entries.find(e => e.id === item.id)
      const cache = workshopCache.get(item.id)
      if (cache && Date.now() - cache.at < 60000) {
        item.updateAvailable = cache.updateAvailable
        item.pendingCommit = cache.pendingCommit
        item.checkError = cache.checkError || null
        return
      }
      let ck
      try {
        ck = await checkUpdate(item.id, entry)
      } catch (e) {
        ck = { updateAvailable: false, latest: null, checkError: String((e && e.message) || e) }
      }
      workshopCache.set(item.id, { at: Date.now(), updateAvailable: ck.updateAvailable, pendingCommit: ck.latest, checkError: ck.checkError || null })
      item.updateAvailable = ck.updateAvailable
      item.pendingCommit = ck.latest
      item.checkError = ck.checkError || null
    }))
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
  // 2026-11-08 深度审核：字符串前缀挡不住 public/ 下的符号链接 / junction，
  // 解析真实路径后再校验一次边界。
  let publicReal = PUBLIC
  try { publicReal = fs.realpathSync(PUBLIC) } catch { /* 保持原值 */ }
  let real
  try { real = fs.realpathSync(abs) } catch { res.writeHead(404); return res.end('not found') }
  if (!real.startsWith(publicReal + path.sep) && real !== publicReal) {
    res.writeHead(404)
    return res.end('not found')
  }
  // 令牌只注入服务自身渲染的首页；禁止缓存，避免带令牌的 HTML 落进共享缓存。
  if (path.basename(abs) === 'index.html') {
    const html = fs.readFileSync(abs, 'utf8').replace('__ALLIN_PORTAL_TOKEN__', gate.token)
    res.setHeader('Content-Type', MIME['.html'])
    res.setHeader('Cache-Control', 'no-store')
    return res.end(html)
  }
  res.setHeader('Content-Type', MIME[path.extname(abs)] || 'application/octet-stream')
  fs.createReadStream(abs).pipe(res)
}

/** 统一兜底：任何同步 throw 或 Promise rejection 都转成 500 响应，不让进程退出。
 *  返回体只带错误类型与稳定提示，不回显堆栈/内部路径（避免信息泄露）。 */
function failLoudResponse(req, res, err) {
  console.error(`[portal] 未处理异常 ${req.method} ${req.url}: ${err && err.stack ? err.stack : err}`)
  if (res.headersSent) { try { res.end() } catch { /* 连接已断 */ } return }
  try {
    res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({ error: 'internal_error', hint: '见服务端日志' }))
  } catch { /* 连接已断 */ }
}

const server = http.createServer((req, res) => {
  // 用 Promise.resolve() 把同步 throw 也纳入同一个 catch（不等 microtask 之外的缝隙）。
  Promise.resolve()
    .then(() => requestHandler(req, res))
    .catch((err) => failLoudResponse(req, res, err))
})

// 末位安全网：请求 handler 之外（定时器 / 后台任务 / 第三方库）的未处理拒绝。
// 只记录后退出，**不吞** —— Node 官方语义下继续跑会留下状态不确定的进程。
// 由 supervisor / 启动器重启一个干净实例比带病运行安全。
process.on('unhandledRejection', (reason) => {
  console.error('[portal] FATAL unhandledRejection: ' + (reason && reason.stack ? reason.stack : reason))
  process.exit(1)
})

// 2026-11-08 深度审核：此前无 body / 头部超时，慢请求可占连接至 Node 默认 5 分钟。
server.requestTimeout = 30_000
server.headersTimeout = 10_000
server.keepAliveTimeout = 5_000

server.listen(port, '127.0.0.1', () => {
  const actual = server.address().port
  boundPort = actual
  // 端口发现（CLI/宿主用）：实际端口写入 data/portal.port，进程退出时删除；
  // 被强杀时文件可能残留，消费方须以 /api/status 探活兜底。
  const PORT_FILE = path.join(DATA_DIR, 'portal.port')
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true })
    // R-05 收敛（2026-11-10）：改原子写（temp+fsync+rename），不再裸 writeFileSync；
    // 此前直接 writeFileSync 违反 AGENTS.md 第 5 条 durable 语义（崩溃可能半截）。
    writeAtomically(PORT_FILE, String(actual))
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
