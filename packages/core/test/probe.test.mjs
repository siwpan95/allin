// probe 测试：真实本地 http server + 临时监听端口（真实现而非 mock，对齐 DSH 测试纪律）。
import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import http from 'node:http'
import net from 'node:net'

const { probePort, probeEntry, STARTING_GRACE_MS } = await import('../src/probe.js')

let server
let port
before(async () => {
  server = http.createServer((req, res) => { res.writeHead(200); res.end('ok') })
  await new Promise((r) => server.listen(0, '127.0.0.1', r))
  port = server.address().port
})
after(() => new Promise((r) => server.close(r)))

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer()
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)) })
    s.on('error', reject)
  })
}

test('probePort：监听中 → true；未监听 → false', async () => {
  assert.equal(await probePort(port, 500), true)
  assert.equal(await probePort(await freePort(), 300), false)
})

test('probeEntry：进程存活 + health 就绪 → via health-url', async () => {
  const entry = { id: 'x', health: { url: `http://127.0.0.1:${port}/` } }
  const r = await probeEntry(entry, true, Date.now())
  assert.deepEqual(r, { running: true, via: 'health-url' })
})

test('probeEntry：进程存活 + 宽限期内端口未就绪 → via starting（慢启动纪律）', async () => {
  const entry = { id: 'x', port: await freePort() }
  const r = await probeEntry(entry, true, Date.now())
  assert.deepEqual(r, { running: true, via: 'starting' })
})

test('probeEntry：宽限期外 → via process（不再拖慢启动宽限）', async () => {
  const entry = { id: 'x', port: await freePort() }
  const r = await probeEntry(entry, true, Date.now() - STARTING_GRACE_MS - 1000)
  assert.deepEqual(r, { running: true, via: 'process' })
})

test('probeEntry：无服务面 → process / no-probe', async () => {
  assert.deepEqual(await probeEntry({ id: 'x' }, true, Date.now()), { running: true, via: 'process' })
  assert.deepEqual(await probeEntry({ id: 'x' }, false, null), { running: false, via: 'no-probe' })
})
