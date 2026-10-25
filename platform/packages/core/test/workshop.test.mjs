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
