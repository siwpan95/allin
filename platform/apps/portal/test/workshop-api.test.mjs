// workshop HTTP 集成测试（B2 闭环 · 2026-11-08 审查）。
//
// 目标：此前 POST /api/workshop/:id/(subscribe|unsubscribe|update|rollback) 这批
// 状态变更端点**零集成覆盖**（仅 workshop.test.mjs 测模块函数、不经 HTTP），
// 门户↔模块↔git 拼装缺陷漏测。本测试起真实 portal（PORT=0、tmp PLATFORM_ROOT），
// 通过 HTTP 驱动完整订阅生命周期，拦截拼装缺陷。
//
// 无网设计（与 api.test.mjs 同纪律：零第三方依赖、零盘符）：
//   ① 全局覆写 fetch → 桩掉 gitee API（fetchBranchCommitStatus 调的是全局 fetch）；
//   ② git insteadOf 把 https://gitee.com/local/bare.git 重写为本地 bare 仓
//      （写入 GIT_CONFIG_GLOBAL 指向的临时配置，绝不污染用户真实全局 gitconfig），
//      于是 subscribe/update 的真实 git clone/pull 全程离线跑通。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

// ---- 隔离环境 ----
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-ws-api-'))
process.env.PLATFORM_ROOT = tmp
process.env.PORT = '0'
// 2026-11-08：状态变更要令牌。测试用固定值，避免依赖临时文件读取时序。
process.env.ALLIN_PORTAL_TOKEN = 'portal-test-token'
const PORTAL_TOKEN = process.env.ALLIN_PORTAL_TOKEN
// 异机结构校验：registry 登记的 path 指向作者机器项目目录（本机不存在）；
// 测试只校验清单结构与订阅行为，不绑定具体机器。
process.env.PLATFORM_PATH_CHECK = 'absolute'

const regDir = path.join(tmp, 'registry', 'projects')
fs.mkdirSync(regDir, { recursive: true })
fs.writeFileSync(path.join(regDir, 'ws-demo.yaml'), [
  'id: ws-demo',
  'name: Workshop Demo',
  'category: tool',
  'version: 1.0.0',
  'path: repos/ws-demo',
  'launch:',
  '  command: echo placeholder',
  'publish:',
  '  repo: local/bare',
  '  branch: master',
].join('\n'), 'utf8')
process.env.PLATFORM_REGISTRY = regDir

// ---- 桩掉 gitee API（全局 fetch） ----
const FAKE_SHA = 'f'.repeat(40)
globalThis.fetch = async () => ({
  ok: true,
  json: async () => ({ commit: { sha: FAKE_SHA } }),
})

// ---- 本地 bare 仓 + insteadOf（临时 gitconfig，无机器污染） ----
const bare = path.join(tmp, 'ws-bare.git')
const gitconfig = path.join(tmp, 'gitconfig')
process.env.GIT_CONFIG_GLOBAL = gitconfig
const work = path.join(tmp, 'ws-work')
const git = (args) => execFileSync('git', args, { stdio: 'ignore' })
function initBareWithCommit() {
  fs.mkdirSync(work, { recursive: true })
  git(['init', '-q', work])
  git(['-C', work, 'config', 'user.email', 't@t'])
  git(['-C', work, 'config', 'user.name', 't'])
  fs.writeFileSync(path.join(work, 'README.md'), 'ws demo\n')
  git(['-C', work, 'add', '-A'])
  git(['-C', work, 'commit', '-qm', 'init'])
  git(['init', '--bare', '-q', bare])
  git(['-C', work, 'push', '-q', bare, 'master'])
}
function pushNewCommit() {
  fs.writeFileSync(path.join(work, 'v2.txt'), 'v2\n')
  git(['-C', work, 'add', '-A'])
  git(['-C', work, 'commit', '-qm', 'v2'])
  git(['-C', work, 'push', '-q', bare, 'master'])
}
initBareWithCommit()
git(['config', '--global', `url.${pathToFileURL(bare).href}.insteadOf`, 'https://gitee.com/local/bare.git'])

// ---- 起真实 portal ----
const { server } = await import('../src/index.js')
await new Promise((resolve) => server.once('listening', resolve))
const base = 'http://127.0.0.1:' + server.address().port

function rawPost(pathname, headers = {}, withToken = true) {
  const allHeaders = withToken ? { 'X-Allin-Token': PORTAL_TOKEN, ...headers } : headers
  return new Promise((resolve, reject) => {
    const req = http.request(base + pathname, { method: 'POST', headers: allHeaders }, (res) => {
      let body = ''
      res.on('data', (c) => { body += c })
      res.on('end', () => { try { resolve({ status: res.statusCode, json: body ? JSON.parse(body) : null }) } catch { resolve({ status: res.statusCode, json: null }) } })
    })
    req.on('error', reject)
    req.end()
  })
}
function getJson(pathname) {
  return new Promise((resolve, reject) => {
    const req = http.request(base + pathname, { method: 'GET' }, (res) => {
      let body = ''
      res.on('data', (c) => { body += c })
      res.on('end', () => { try { resolve({ status: res.statusCode, json: JSON.parse(body) }) } catch (e) { reject(e) } })
    })
    req.on('error', reject)
    req.end()
  })
}

test('POST subscribe → 200 且订阅态入册（真实 git clone 本地 bare 仓）', async () => {
  const r = await rawPost('/api/workshop/ws-demo/subscribe', { 'X-Allin-Local': '1' })
  assert.equal(r.status, 200, 'subscribe 应 200')
  assert.equal(r.json.ok, true, 'subscribe 应 ok:true')
  assert.match(String(r.json.commit || ''), /^[0-9a-f]{40}$/, 'commit 应为 40 位 sha')
  const cat = await getJson('/api/workshop')
  const item = cat.json.catalog.find((i) => i.id === 'ws-demo')
  assert.ok(item, 'catalog 应含 ws-demo')
  assert.equal(item.subscribed, true, '订阅后 subscribed 应为 true')
})

test('POST subscribe 缺本地标记头 → 403（CSRF 围栏对状态变更端点生效）', async () => {
  const r = await rawPost('/api/workshop/ws-demo/subscribe', {})
  assert.equal(r.status, 403, '无来源信号的 POST 必须 403')
})

test('令牌闸：只带 X-Allin-Local 不带令牌 → 403（同机不再即管理员）', async () => {
  const r = await rawPost('/api/workshop/ws-demo/subscribe', { 'X-Allin-Local': '1' }, false)
  assert.equal(r.status, 403, '无令牌的 POST 必须 403')
})

test('POST subscribe 未知 id → 404', async () => {
  const r = await rawPost('/api/workshop/nope/subscribe', { 'X-Allin-Local': '1' })
  assert.equal(r.status, 404, '未知 id 应 404')
})

test('GET /api/workshop 订阅项经 checkUpdate（fetch 桩）回填 updateAvailable 布尔', async () => {
  const cat = await getJson('/api/workshop')
  const item = cat.json.catalog.find((i) => i.id === 'ws-demo')
  assert.ok(item, 'catalog 应含 ws-demo')
  assert.equal(typeof item.updateAvailable, 'boolean', 'updateAvailable 应为布尔（fetch 桩生效）')
  assert.equal(item.updateAvailable, true, '本地 bare 仓 sha 与桩 sha 不同 → 应有更新可用')
  assert.equal(typeof item.checkError, 'object', 'checkError 字段应存在（网络故障显式回传，不伪装无更新）')
})

test('POST update → 200（真实 git pull 本地 bare 仓，提交推进）', async () => {
  pushNewCommit()
  const r = await rawPost('/api/workshop/ws-demo/update', { 'X-Allin-Local': '1' })
  assert.equal(r.status, 200, 'update 应 200')
  assert.equal(r.json.ok, true, 'update 应 ok:true')
  assert.equal(r.json.changed, true, '推送新提交后 update 应 changed:true（产生可回滚点）')
})

test('POST rollback → 200（回退到上一可回滚点）', async () => {
  const r = await rawPost('/api/workshop/ws-demo/rollback', { 'X-Allin-Local': '1' })
  assert.equal(r.status, 200, 'rollback 应 200')
  assert.equal(r.json.ok, true, 'rollback 应 ok:true')
  assert.match(String(r.json.commit || ''), /^[0-9a-f]{40}$/, 'rollback 后应回到历史提交 sha')
})

test('POST unsubscribe → 200 且订阅态清出（事务化：先停后删）', async () => {
  const r = await rawPost('/api/workshop/ws-demo/unsubscribe', { 'X-Allin-Local': '1' })
  assert.equal(r.status, 200, 'unsubscribe 应 200')
  assert.equal(r.json.ok, true, 'unsubscribe 应 ok:true')
  const cat = await getJson('/api/workshop')
  const item = cat.json.catalog.find((i) => i.id === 'ws-demo')
  assert.equal(item.subscribed, false, '退订后 subscribed 应为 false')
})

test('GET /api/workshop/audit → 审计流水为数组', async () => {
  const r = await getJson('/api/workshop/audit')
  assert.equal(r.status, 200)
  assert.ok(Array.isArray(r.json.audit), 'audit 应为数组')
})

after(() => server.close())
