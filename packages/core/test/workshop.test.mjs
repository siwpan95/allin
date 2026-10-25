// workshop P3.5 测试：真实 git 订阅(clone)/更新(pull)/回滚(checkout)/退订(删除副本)。
// 用本地 bare 仓做发布面（gitUrl 注入），fetcher 用假实现。
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-ws-'))
process.env.PLATFORM_ROOT = tmp

function git(args, cwd) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
}
function commitFile(content, msg, push = true) {
  fs.writeFileSync(path.join(src, 'code.txt'), content + '\n')
  git(['add', 'code.txt'], src)
  git(['commit', '-qm', msg], src)
  if (push) git(['push', '-q', remote, 'master'], src)
  return git(['rev-parse', 'HEAD'], src)
}

const src = path.join(tmp, 'src')
fs.mkdirSync(src)
git(['init', '-q', '-b', 'master'], src)
git(['config', 'user.name', 't'], src)
git(['config', 'user.email', 't@t'], src)
commitFile('v1', 'v1', false)
commitFile('v2', 'v2', false)
const v3 = commitFile('v3', 'v3', false)
const remote = path.join(tmp, 'remote.git')
git(['clone', '-q', '--bare', src, remote], tmp)

git(['remote', 'add', 'origin', remote], src)
git(['push', '-q', '-u', 'origin', 'master'], src)

const entry = {
  id: 'radio', name: '电台', category: 'media', version: '4.0.0',
  publish: { repo: 'siwpan/x', branch: 'master' },
}

const ws = await import('../src/workshop.js')
const { listWorkshop, subscribe, update, rollback, unsubscribe, auditWorkshop, COPIES_DIR } = ws

const opts = { gitUrl: remote, fetcher: async () => 'fffffff' }

test('订阅 = clone 到 workshop-copies 并记录提交', async () => {
  const r = await subscribe('radio', entry, opts)
  assert.equal(r.ok, true)
  assert.equal(r.commit, v3)
  assert.ok(fs.existsSync(path.join(COPIES_DIR, 'radio', '.git')))
  assert.equal(fs.readFileSync(path.join(COPIES_DIR, 'radio', 'code.txt'), 'utf8').trim(), 'v3')
})

test('更新 = 真实 git pull，旧提交入 history', async () => {
  const v4 = commitFile('v4', 'v4')
  const r = await update('radio', entry, opts)
  assert.equal(r.ok, true)
  assert.equal(r.changed, true)
  assert.equal(r.commit, v4)
  assert.equal(fs.readFileSync(path.join(COPIES_DIR, 'radio', 'code.txt'), 'utf8').trim(), 'v4')
  const ws2 = listWorkshop([entry])
  assert.equal(ws2.catalog[0].history.length, 1)
  assert.equal(ws2.catalog[0].history[0].commit, v3)
})

test('回滚 = checkout 历史提交，副本内容回退', () => {
  const r = rollback('radio')
  assert.equal(r.ok, true)
  assert.equal(r.commit, v3)
  assert.equal(fs.readFileSync(path.join(COPIES_DIR, 'radio', 'code.txt'), 'utf8').trim(), 'v3')
  const r2 = rollback('radio')
  assert.equal(r2.reason, 'no-history')
})

test('退订 = 删除副本 + 审计流水完整', () => {
  assert.equal(unsubscribe('radio').ok, true)
  assert.ok(!fs.existsSync(path.join(COPIES_DIR, 'radio')))
  const actions = auditWorkshop(20).map(a => a.action)
  for (const a of ['workshop-subscribe', 'workshop-update', 'workshop-rollback', 'workshop-unsubscribe']) {
    assert.ok(actions.includes(a), 'missing ' + a)
  }
})

// 2026-09-24 强化：多级回滚链 + 浅克隆对象缺失时的 unshallow 兜底
test('多级回滚链（radio2：v9→v8→v7 全程可达）', async () => {
  const e2 = { ...entry, id: 'radio2' }
  commitFile('v5', 'v5'); commitFile('v6', 'v6')
  const v7 = commitFile('v7', 'v7')
  const s = await subscribe('radio2', e2, opts)
  assert.equal(s.commit, v7)
  const v8 = commitFile('v8', 'v8')
  assert.equal((await update('radio2', e2, opts)).commit, v8)
  const v9 = commitFile('v9', 'v9')
  assert.equal((await update('radio2', e2, opts)).commit, v9)
  const rb1 = rollback('radio2')
  assert.equal(rb1.commit, v8)
  const rb2 = rollback('radio2')
  assert.equal(rb2.commit, v7)
  assert.equal(fs.readFileSync(path.join(COPIES_DIR, 'radio2', 'code.txt'), 'utf8').trim(), 'v7')
})

test('浅克隆对象缺失时 unshallow 兜底（陈旧 history 指向克隆前提交）', async () => {
  git(['config', 'uploadpack.allowAnySHA1InWant', 'true'], remote)
  const v5 = git(['rev-parse', 'master~4'], src) // v5：不在 radio2 浅克隆对象库（HEAD=v9）
  const stateFile = path.join(tmp, 'data', 'workshop.json')
  const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'))
  state.subscriptions.radio2.history = [{ commit: v5, version: '5.0.0', at: new Date().toISOString() }]
  fs.writeFileSync(stateFile, JSON.stringify(state))
  const rb = rollback('radio2')
  assert.equal(rb.ok, true, '回滚应经 unshallow 兜底成功: ' + (rb.error || ''))
  assert.equal(rb.commit, v5)
  assert.equal(fs.readFileSync(path.join(COPIES_DIR, 'radio2', 'code.txt'), 'utf8').trim(), 'v5')
  assert.equal(unsubscribe('radio2').ok, true)
})
