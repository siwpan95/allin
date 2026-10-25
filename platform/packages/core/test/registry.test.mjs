// registry 测试：必填字段 / 端口查表 / 归属核对（fail-loud）。
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadRegistry, validateEntry, loadPorts } from '../src/registry.js'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-reg-'))
// 测试不绑定具体机器（2026-09-24 强化）：good 条目的 path 用必然存在的目录，
// path 存在性校验（默认 exists 模式）由「不存在的路径」负例单独覆盖。
// 2026-10-26 起 path **禁盘符**（去符盘铁律），故不再使用 os.tmpdir() 这类绝对路径，
// 改用仓内相对路径 `platform`（解析到治理仓根下，本机与 CI 都必然存在）。
const EXISTING_DIR = 'platform'
fs.writeFileSync(path.join(tmp, 'good.yaml'), [
  'id: radio',
  'name: 电台',
  'category: media',
  'version: 1.0.0',
  `path: ${EXISTING_DIR.replace(/\\/g, '\\\\')}`,
  'port: 8000',
  'launch:',
  '  command: npm run radio',
].join('\n'))
fs.writeFileSync(path.join(tmp, 'badport.yaml'), [
  'id: ghost',
  'name: 幽灵服务',
  'category: tool',
  'version: 1.0.0',
  'path: repos/no-such-repo',
  'port: 1234',
  'launch:',
  '  command: python x.py',
].join('\n'))
fs.writeFileSync(path.join(tmp, 'missing.yaml'), [
  'id: no-launch',
  'name: 缺字段',
  'category: tool',
  'version: 1.0.0',
  'path: repos/no-such-repo',
].join('\n'))

test('loadRegistry: 端口查表与必填字段 fail-loud', () => {
  const { entries, problems } = loadRegistry(tmp)
  assert.equal(entries.length, 3)
  assert.ok(problems.some(p => p.includes('badport') && p.includes('1234')))
  assert.ok(problems.some(p => p.includes('missing') && p.includes('launch.command')))
  const good = entries.find(e => e.id === 'radio')
  assert.ok(good._valid)
})

test('validateEntry: gameplay 受控枚举 fail-loud（非法标签/非 game 误标）', () => {
  const ports = loadPorts()
  const base = { id: 'x', name: 'x', category: 'game', version: '1', path: EXISTING_DIR, launch: { command: 'x' } }
  const bad = validateEntry({ ...base, gameplay: ['survivor-割草'] }, ports)
  assert.ok(bad.some(e => e.includes('未登记')), '非法标签应报错')
  const notGame = validateEntry({ ...base, category: 'tool', gameplay: ['idle'] }, ports)
  assert.ok(notGame.some(e => e.includes('非 game')), '非 game 误标应报错')
  const good = validateEntry({ ...base, gameplay: ['idle', 'rpg'] }, ports)
  assert.deepEqual(good, [])
  const noPath = validateEntry({ ...base, path: path.join(EXISTING_DIR, 'definitely-not-exists-' + Date.now()) }, ports)
  assert.ok(noPath.some(e => e.includes('不存在')), 'path 不存在应报错（2026-08-27 R4 新增存在性校验）')
})

test('validateEntry: 端口归属核对（8000 = radio 与 id radio 一致）', () => {
  const ports = loadPorts()
  const errs = validateEntry({
    id: 'radio', name: 'x', category: 'media', version: '1', path: EXISTING_DIR,
    port: 8000, launch: { command: 'npm run radio' },
  }, ports)
  assert.deepEqual(errs, [])
  const errs2 = validateEntry({
    id: 'video', name: 'x', category: 'media', version: '1', path: EXISTING_DIR,
    port: 8000, launch: { command: 'x' },
  }, ports)
  assert.ok(errs2.some(e => e.includes('不一致')))
})
