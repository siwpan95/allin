// @allin/portal —— 平台前台 :9000（零依赖纯 Node http，自 @relay/portal 升级）。
// 三个页签：库 Library（启停/状态）/ 工坊 Workshop（订阅）/ 引擎 Engine（alloy dump-profile）。
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  loadRegistry,
  startEntry,
  stopEntry,
  isRunning,
  probeEntry,
  listWorkshop,
  subscribe,
  unsubscribe,
  update,
  rollback,
  auditWorkshop,
  checkUpdate,
} from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PUBLIC = path.join(__dirname, '..', 'public')
const PLATFORM = path.join(__dirname, '..', '..', '..')
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(PLATFORM, 'registry', 'projects')
const ALLOY_CWD = process.env.PLATFORM_ALLOY_CWD || 'G:\\games'
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

function readBody(req) {
  return new Promise((resolve) => {
    let data = ''
    req.on('data', (c) => { data += c })
    req.on('end', () => { try { resolve(data ? JSON.parse(data) : {}) } catch { resolve({}) } })
  })
}

// alloy 装配视图（CLI 调用，缓存 30s）
let engineCache = { at: 0, payload: null }
const workshopCache = new Map()
function engineReport() {
  if (Date.now() - engineCache.at < 30000 && engineCache.payload) return engineCache.payload
  const python = process.env.PLATFORM_PYTHON || 'python'
  const r = spawnSync(python, ['-m', 'alloy', 'dump-profile', '--json'], {
    cwd: ALLOY_CWD, encoding: 'utf8', timeout: 60000,
  })
  const presets = spawnSync(python, ['-c',
    'import json; from alloy.core.profiles import PROFILES; print(json.dumps(list(PROFILES)))'], {
    cwd: ALLOY_CWD, encoding: 'utf8', timeout: 60000,
  })
  if (r.status !== 0) {
    engineCache = { at: Date.now(), payload: { ok: false, error: (r.stderr || 'alloy CLI 不可用').slice(-500) } }
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
  const items = []
  for (const e of entries) {
    const running = isRunning(e.id)
    const probe = await probeEntry(e, running)
    items.push({
      id: e.id, name: e.name, category: e.category, version: e.version,
      gameplay: e.gameplay || [],
      note: e.note || null, order: e.order ?? null,
      port: e.port ?? null, path: e.path, manual: Boolean(e.manual), valid: e._valid,
      running: probe.running, via: probe.via,
      publish: e.publish ? e.publish.repo || null : null,
    })
  }
  return { items, problems }
}

const server = http.createServer(async (req, res) => {
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
      return json(res, 200, startEntry(entry))
    } catch (e) {
      return json(res, 400, { error: String(e.message) })
    }
  }
  const stopM = p.match(/^\/api\/library\/([a-z0-9-]+)\/stop$/)
  if (stopM && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    return json(res, 200, stopEntry(stopM[1]))
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
        continue
      }
      const ck = await checkUpdate(item.id, entry)
      workshopCache.set(item.id, { at: Date.now(), updateAvailable: ck.updateAvailable, pendingCommit: ck.latest })
      item.updateAvailable = ck.updateAvailable
      item.pendingCommit = ck.latest
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
    else if (subM[2] === 'unsubscribe') result = unsubscribe(entry.id)
    else if (subM[2] === 'update') result = await update(entry.id, entry)
    else result = rollback(entry.id)
    return json(res, result.ok ? 200 : 400, result)
  }
  if (p === '/api/workshop/audit' && req.method === 'GET') {
    return json(res, 200, { audit: auditWorkshop() })
  }
  if (p === '/workshop/catalog' && req.method === 'GET') {
    const { entries } = loadRegistry(REGISTRY)
    const rows = entries.filter(e => e.publish && e.publish.repo).map(e => {
      const branch = e.publish.branch || 'master'
      const url = `https://gitee.com/${e.publish.repo}/tree/${branch}`
      return `<tr><td>${e.name}</td><td>${e.category}</td><td>v${e.version}</td><td><a href="${url}" target="_blank">${e.publish.repo} #${branch}</a></td></tr>`
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
    return json(res, 200, engineReport())
  }
  if (p === '/api/shutdown' && req.method === 'POST') {
    if (!loopbackOnly(req, res)) return
    json(res, 200, { ok: true })
    return setTimeout(() => process.exit(0), 150)
  }

  // 静态文件（同 @relay/portal 纪律）
  let fp = p === '/' ? '/index.html' : p
  const abs = path.join(PUBLIC, path.normalize(fp).replace(/^(\.\.[/\\])+/, ''))
  if (!abs.startsWith(PUBLIC) || !fs.existsSync(abs) || fs.statSync(abs).isDirectory()) {
    res.writeHead(404)
    return res.end('not found')
  }
  res.setHeader('Content-Type', MIME[path.extname(abs)] || 'application/octet-stream')
  fs.createReadStream(abs).pipe(res)
})

server.listen(port, '0.0.0.0', () => {
  console.log('[allin-platform portal] http://localhost:' + port)
})

export { server }
