// gitee 测试：fetch 打桩（不触网）——验证「网络故障 ≠ 无更新」的错误区分。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'

const { fetchBranchCommitStatus, fetchBranchCommit } = await import('../src/gitee.js')
const realFetch = globalThis.fetch
after(() => { globalThis.fetch = realFetch })

test('fetchBranchCommitStatus 成功 → { ok, commit }', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ commit: { sha: 'abc123def' } }) })
  const r = await fetchBranchCommitStatus('siwpan/x', 'master')
  assert.deepEqual(r, { ok: true, commit: 'abc123def' })
})

test('HTTP 非 200 → ok:false + error（不再伪装成 null/无更新）', async () => {
  globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) })
  const r = await fetchBranchCommitStatus('siwpan/x', 'nope')
  assert.equal(r.ok, false)
  assert.ok(r.error.includes('404'))
})

test('网络异常（fetch 抛错/超时）→ ok:false，不抛异常', async () => {
  globalThis.fetch = async () => { throw new Error('connect timeout') }
  const r = await fetchBranchCommitStatus('siwpan/x', 'master')
  assert.equal(r.ok, false)
  assert.ok(r.error.includes('connect timeout'))
})

test('响应缺 commit.sha → ok:false', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({}) })
  const r = await fetchBranchCommitStatus('siwpan/x', 'master')
  assert.equal(r.ok, false)
  assert.ok(r.error.includes('commit.sha'))
})

test('fetchBranchCommit 兼容封装：成功返回 sha / 失败返回 null', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ commit: { sha: 'deadbeef' } }) })
  assert.equal(await fetchBranchCommit('siwpan/x', 'master'), 'deadbeef')
  globalThis.fetch = async () => { throw new Error('down') }
  assert.equal(await fetchBranchCommit('siwpan/x', 'master'), null)
})
