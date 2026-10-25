// portal API 测试：临时端口启动真实服务，验证三个页签的数据面。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// 隔离数据目录（launch 日志不落真实 G:\\platform\\data）
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-api-'))
process.env.PLATFORM_ROOT = tmp
process.env.PORT = '0'

const { server } = await import('../src/index.js')
await new Promise((resolve) => server.once('listening', resolve))
const base = 'http://127.0.0.1:' + server.address().port

test('GET /api/status', async () => {
  const res = await fetch(base + '/api/status')
  const body = await res.json()
  assert.equal(body.platform, 'allin-platform')
})

test('GET /api/library 返回 95 个登记项目（73 + 收编 22）', async () => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()
  assert.equal(body.items.length, 95)
  const ids = body.items.map(i => i.id)
  for (const id of ['radio', 'video', 'portal', 'crawl-hub', 'audio-pipeline', 'audio-separator', 'mixer', 'alloy', 'dwarf-scrolls', 'pywallpaper', 'cellular', 'shikonghuaban', 'bee', 'jotunnslayer', 'novel', 'video-generator', 'station', 'remix', 'cordis-snake', 'repocheck', 'bloodmusic', 'webcopier', 'arcade', 'idle', 'stay', 'pq-multiverse', 'life-reset', 'endless-highway', 'russia', 'txtlegend', 'darksouls', 'kard', 'loly', 'hell-below', 'moba-battle', 'carimara', 'd20']) {
    assert.ok(ids.includes(id), 'missing ' + id)
  }
  assert.deepEqual(body.problems, [])
})

test('GET /api/library 挂机族子视图数据（order/note 回填）', async () => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()
  const idle = body.items.filter(i => (i.gameplay || []).includes('idle')).sort((a, b) => a.order - b.order)
  assert.equal(idle.length, 5)
  assert.deepEqual(idle.map(i => i.order), [1, 2, 3, 4, 5])
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

test('POST 启动未知项目 → 404', async () => {
  const res = await fetch(base + '/api/library/nope/start', { method: 'POST' })
  assert.equal(res.status, 404)
})

after(() => server.close())
