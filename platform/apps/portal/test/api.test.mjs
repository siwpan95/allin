// portal API 测试：临时端口启动真实服务，验证三个页签的数据面。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import http from 'node:http'
import net from 'node:net'
import { fileURLToPath } from 'node:url'

// 隔离数据目录（launch 日志不落真实 data/）
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-api-'))
process.env.PLATFORM_ROOT = tmp
process.env.PORT = '0'
// 异机结构校验：登记的 path 指向作者机器的项目目录（本机不存在），
// 测试只校验清单结构与端口查表（PLATFORM_PATH_CHECK=absolute），不绑定具体机器。
process.env.PLATFORM_PATH_CHECK = 'absolute'

const { server } = await import('../src/index.js')
await new Promise((resolve) => server.once('listening', resolve))
const base = 'http://127.0.0.1:' + server.address().port

test('GET /api/status', async () => {
  const res = await fetch(base + '/api/status')
  const body = await res.json()
  assert.equal(body.platform, 'allin-platform')
})

// Phase 1（2026-09-24）：Host 头围栏——防 DNS rebinding 打穿 loopbackOnly。
// undici fetch 禁止设置 Host 头，故用原生 http.request 指定伪造 Host。
function rawGet(pathname, hostHeader) {
  return new Promise((resolve, reject) => {
    const req = http.request(base + pathname, { headers: { host: hostHeader }, method: 'GET' }, (res) => {
      res.resume()
      res.on('end', () => resolve(res.statusCode))
    })
    req.on('error', reject)
    req.end()
  })
}

test('Host 围栏：回环 Host（127.0.0.1 / localhost / [::1]）放行', async () => {
  assert.equal(await rawGet('/api/status', '127.0.0.1:' + server.address().port), 200)
  assert.equal(await rawGet('/api/status', 'localhost:9999'), 200)
  assert.equal(await rawGet('/api/status', '[::1]:8888'), 200)
})

test('Host 围栏：攻击域名 / 空 Host → 403（DNS rebinding 防护）', async () => {
  assert.equal(await rawGet('/api/status', 'evil.example.com'), 403)
  assert.equal(await rawGet('/api/status', 'attacker.rebind.local:80'), 403)
  assert.equal(await rawGet('/api/library', 'evil.example.com'), 403, 'GET 读取面同样受保护')
  // HTTP/1.0 无 Host 头（Node http.request 会自动补 Host，须 raw socket 实测）
  assert.equal(await rawRequest10('/api/status'), 403, '缺 Host 头一律拒绝')
})

function rawRequest10(pathname) {
  return new Promise((resolve, reject) => {
    const sock = net.connect(server.address().port, '127.0.0.1', () => {
      sock.write(`GET ${pathname} HTTP/1.0\r\n\r\n`)
    })
    let head = ''
    sock.on('data', (c) => { head += c; sock.end() })
    sock.on('end', () => resolve(Number((/^HTTP\/1\.[01] (\d{3})/.exec(head) || [])[1])))
    sock.on('error', reject)
  })
}

test('GET /api/library 数量与 registry yaml 文件数一致（problems 为空）', async () => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()
  // 数量断言跟随 estate（2026-09-24 强化：不再写死 95——收编新项目忘同步测试的教训）
  const yamlCount = fs.readdirSync(path.join(__dirnameOf(), '..', '..', '..', 'registry', 'projects'))
    .filter(f => f.endsWith('.yaml') || f.endsWith('.yml')).length
  assert.equal(body.items.length, yamlCount)
  const ids = body.items.map(i => i.id)
  for (const id of ['radio', 'video', 'portal', 'crawl-hub', 'audio-pipeline', 'audio-separator', 'mixer', 'allin-engine', 'dwarf-scrolls', 'pywallpaper', 'cellular', 'shikonghuaban', 'bee', 'jotunnslayer', 'novel', 'video-generator', 'station', 'remix', 'cordis-snake', 'repocheck', 'bloodmusic', 'webcopier', 'arcade', 'idle', 'stay', 'pq-multiverse', 'life-reset', 'endless-highway', 'russia', 'txtlegend', 'darksouls', 'kard', 'loly', 'hell-below', 'moba-battle', 'carimara', 'd20']) {
    assert.ok(ids.includes(id), 'missing ' + id)
  }
  assert.deepEqual(body.problems, [])
})

function __dirnameOf() {
  return path.dirname(fileURLToPath(import.meta.url))
}

test('GET /api/library 挂机族子视图数据（order/note 回填）', async () => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()
  const idle = body.items.filter(i => (i.gameplay || []).includes('idle')).sort((a, b) => a.order - b.order)
  // estate 增长（2026-09-24 强化）：不写死数量，只约束 order 连续递增 + note 全回填
  assert.ok(idle.length >= 5, 'idle 族应至少 5 个')
  assert.deepEqual(idle.map(i => i.order), Array.from({ length: idle.length }, (_, k) => k + 1))
  assert.ok(idle.every(i => typeof i.note === 'string' && i.note.length > 0))
})

test('GET /api/library 返回 gameplay 标签（受控枚举回填）', async () => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()
  const arcade = body.items.find(i => i.id === 'arcade')
  assert.deepEqual(arcade.gameplay, ['arcade'])
  const idle = body.items.find(i => i.id === 'idle')
  assert.deepEqual(idle.gameplay, ['idle'])
})

test('GET /api/workshop 目录 = 有 publish 的项目（无订阅 → 不触发 gitee 网络）', async () => {
  const res = await fetch(base + '/api/workshop')
  const body = await res.json()
  assert.ok(body.catalog.length >= 20)
  assert.ok(body.catalog.every(i => !i.subscribed || i.subscribedAt))
})

test('GET /workshop/catalog 静态目录页（HTML）', async () => {
  const res = await fetch(base + '/workshop/catalog')
  const text = await res.text()
  assert.ok(res.headers.get('content-type').includes('text/html'))
  assert.ok(text.includes('工坊目录'))
  assert.ok(text.includes('gitee.com/siwpan/'))
})

test('GET /api/workshop/audit 审计流水', async () => {
  const res = await fetch(base + '/api/workshop/audit')
  const body = await res.json()
  assert.ok(Array.isArray(body.audit))
})

test('GET /api/alerts E5 订阅视图（聚合分歧事件，无事件时为空数组）', async () => {
  const res = await fetch(base + '/api/alerts')
  const body = await res.json()
  assert.ok(Array.isArray(body.alerts))
})

test('POST 启动未知项目 → 404', async () => {
  const res = await fetch(base + '/api/library/nope/start', { method: 'POST' })
  assert.equal(res.status, 404)
})

after(() => server.close())
