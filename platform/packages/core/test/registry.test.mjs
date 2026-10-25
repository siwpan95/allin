// registry 测试：必填字段 / 端口查表 / 归属核对（fail-loud）。
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadRegistry, validateEntry, loadPorts } from '../src/registry.js'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-reg-'))
fs.writeFileSync(path.join(tmp, 'good.yaml'), [
  'id: radio',
  'name: 电台',
  'category: media',
  'version: 1.0.0',
  'path: G:\\tools\\private-radio-stations',
  'port: 8000',
  'launch:',
  '  command: npm run radio',
].join('\n'))
fs.writeFileSync(path.join(tmp, 'badport.yaml'), [
  'id: ghost',
  'name: 幽灵服务',
  'category: tool',
  'version: 1.0.0',
  'path: G:\\tmp',
  'port: 1234',
  'launch:',
  '  command: python x.py',
].join('\n'))
fs.writeFileSync(path.join(tmp, 'missing.yaml'), [
  'id: no-launch',
  'name: 缺字段',
  'category: tool',
  'version: 1.0.0',
  'path: G:\\tmp',
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
  const base = { id: 'x', name: 'x', category: 'game', version: '1', path: 'G:\\x', launch: { command: 'x' } }
  const bad = validateEntry({ ...base, gameplay: ['survivor-割草'] }, ports)
  assert.ok(bad.some(e => e.includes('未登记')), '非法标签应报错')
  const notGame = validateEntry({ ...base, category: 'tool', gameplay: ['idle'] }, ports)
  assert.ok(notGame.some(e => e.includes('非 game')), '非 game 误标应报错')
  const good = validateEntry({ ...base, gameplay: ['idle', 'rpg'] }, ports)
  assert.deepEqual(good, [])
})

test('validateEntry: 端口归属核对（8000 = radio-panel 与 id radio 一致）', () => {
  const ports = loadPorts()
  const errs = validateEntry({
    id: 'radio', name: 'x', category: 'media', version: '1', path: 'G:\\x',
    port: 8000, launch: { command: 'npm run radio' },
  }, ports)
  assert.deepEqual(errs, [])
  const errs2 = validateEntry({
    id: 'video', name: 'x', category: 'media', version: '1', path: 'G:\\x',
    port: 8000, launch: { command: 'x' },
  }, ports)
  assert.ok(errs2.some(e => e.includes('不一致')))
})
