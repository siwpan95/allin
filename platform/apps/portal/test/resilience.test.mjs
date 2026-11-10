// 2026-11-10 深度审计 H-1 回归：坏数据不得让 portal 进程整体下线。
//
// 原缺陷：http.createServer(async (req,res)=>{...}) 的 async handler 抛错不会被
// Node 捕获 ⇒ unhandled rejection ⇒ Node ≥15 默认 throw ⇒ 进程 exit 1。
//
// 触发链的选取（实测踩坑，勿改回去）：
//   ✗ 损坏的 registry/projects/*.yaml **不会**让 handler 抛错 —— loadRegistry()
//     对单文件 YAML 解析失败是设计好的 fail-soft（push 进 problems 后 continue），
//     拿它当夹具只会得到 200，测不到 wrapper；
//   ✓ loadRegistry() 首行 loadPorts() 里 `yaml.load(text)` 无 try/catch，损坏的
//     PLATFORM_PORTS 会真抛 YAMLException，经 libraryPayload() → requestHandler()
//     冒泡，正好覆盖「async handler 内任意抛错」这一通用兜底路径。
//
// 断言：① /api/library 拿到 500 且不回显 stack；② 紧接着 /api/status 仍 200 ——
// 证明进程活着，才是「门户没有被一条坏数据打挂」的直接证据；
// ③ H-1 原始触发点 `port: not-a-number` → probePort(NaN) 单独回归，不再抛
// ERR_SOCKET_BAD_PORT（该同步异常曾在 Promise.all 里升级为进程级拒绝）。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-resilience-'))
process.env.PLATFORM_ROOT = tmp
process.env.PORT = '0'
process.env.ALLIN_PORTAL_TOKEN = 'portal-test-token'
process.env.PLATFORM_PATH_CHECK = 'absolute'

// registry 目录保持干净（空目录即可），坏数据放在端口表这一条真实会抛的路径上。
const emptyRegistry = path.join(tmp, 'registry')
fs.mkdirSync(emptyRegistry, { recursive: true })
process.env.PLATFORM_REGISTRY = emptyRegistry
const badPorts = path.join(tmp, 'ports.yaml')
fs.writeFileSync(badPorts, 'ports: [ { port: [unclosed\n  bad: : :\n', 'utf8')
process.env.PLATFORM_PORTS = badPorts

const { server } = await import('../src/index.js')
await new Promise((resolve) => server.once('listening', resolve))
const base = 'http://127.0.0.1:' + server.address().port

test('H-1 回归：handler 抛错被兜成 500，不产生未捕获拒绝', async () => {
  const res = await fetch(base + '/api/library')
  assert.equal(res.status, 500, 'handler 异常必须转成 500 响应')
  const body = await res.json().catch(() => ({}))
  assert.equal(body.error, 'internal_error')
  assert.ok(!JSON.stringify(body).includes('stack'), '不得回显堆栈')
})

test('H-1 回归：异常之后进程仍存活，/api/status 仍可用', async () => {
  const res = await fetch(base + '/api/status')
  assert.equal(res.status, 200, '进程必须还活着')
  const body = await res.json()
  assert.equal(body.platform, 'allin-platform')
})

test('H-1 回归：坏端口数据不再让 probePort 抛 ERR_SOCKET_BAD_PORT', async () => {
  const { probePort } = await import('@allin/core')
  for (const bad of [NaN, 'not-a-number', -1, 70000, undefined]) {
    assert.equal(await probePort(bad, 50), false, `probePort(${String(bad)}) 必须安全降级为 false`)
  }
})

after(async () => {
  await new Promise((resolve) => server.close(resolve))
  try { fs.rmSync(tmp, { recursive: true, force: true }) } catch { /* Windows 占用容错 */ }
})
