// registry 测试：必填字段 / 端口查表 / 归属核对（fail-loud）。
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadRegistry, validateEntry, loadPorts, isTombstone, skipLocalExistence } from '../src/registry.js'

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

// ── 存在性相关断言必须**显式钉住模式**（2026-11-01）───────────────────────────
// pathCheckMode() 现为惰性读取 env ⇒ 结果随 ambient 变。不钉住就会出现典型的「一边绿一边红」：
// 本机默认 exists 全绿，CI/异机 `PLATFORM_PATH_CHECK=absolute npm test` 却整片失去前提。
// （该缺陷 2026-09-24 专题记录已写明，README 却仍推荐这条异机命令 —— 本次一并修好。）
function withMode(mode, fn) {
  const saved = process.env.PLATFORM_PATH_CHECK
  if (mode === 'absolute') process.env.PLATFORM_PATH_CHECK = 'absolute'
  else delete process.env.PLATFORM_PATH_CHECK
  try {
    return fn()
  } finally {
    if (saved === undefined) delete process.env.PLATFORM_PATH_CHECK
    else process.env.PLATFORM_PATH_CHECK = saved
  }
}

test('validateEntry: gameplay 受控枚举 fail-loud（非法标签/非 game 误标）', () => {
  const ports = loadPorts()
  const base = { id: 'x', name: 'x', category: 'game', version: '1', path: EXISTING_DIR, launch: { command: 'x' } }
  const bad = validateEntry({ ...base, gameplay: ['survivor-割草'] }, ports)
  assert.ok(bad.some(e => e.includes('未登记')), '非法标签应报错')
  const notGame = validateEntry({ ...base, category: 'tool', gameplay: ['idle'] }, ports)
  assert.ok(notGame.some(e => e.includes('非 game')), '非 game 误标应报错')
  const good = validateEntry({ ...base, gameplay: ['idle', 'rpg'] }, ports)
  assert.deepEqual(good, [])
  const noPath = withMode('exists', () =>
    validateEntry({ ...base, path: path.join(EXISTING_DIR, 'definitely-not-exists-' + Date.now()) }, ports))
  assert.ok(noPath.some(e => e.includes('不存在')),
            'path 不存在应报错（2026-08-27 R4 新增存在性校验；须在 exists 模式下判）')
})

test('validateEntry: 墓碑条目豁免 path 存在性，但形状校验不放（2026-11-01）', () => {
  const ports = loadPorts()
  const tomb = {
    id: 'calc', name: 'x', category: 'tool', version: '1',
    path: 'repos/no-such-repo', status: 'archived', manual: true, launch: { command: 'python main.py' },
  }
  // ① 已归档：工作树按治理流程移出 repos/ ⇒ 不再要求本机存在
  assert.deepEqual(withMode('exists', () => validateEntry(tomb, ports)), [], 'archived 条目应豁免存在性')
  assert.deepEqual(withMode('exists', () => validateEntry({ ...tomb, status: 'retired' }, ports)), [],
                   'retired 同属墓碑')
  // ② 活性条目照旧 fail-loud（防止豁免范围被无意放大）
  const active = withMode('exists', () => validateEntry({ ...tomb, status: 'active' }, ports))
  assert.ok(active.some(e => e.includes('不存在')), '活性条目仍须报错')
  assert.ok(withMode('exists', () => validateEntry({ ...tomb, status: undefined }, ports))
              .some(e => e.includes('不存在')), '无 status 默认按活性处理')
  // ③ 豁免不放宽形状纪律：盘符依旧 fail-loud
  const drive = validateEntry({ ...tomb, path: 'G:\\repos\\calc' }, ports)
  assert.ok(drive.some(e => e.includes('盘符')), '墓碑也不许写盘符')
  // ④ absolute（异机降级口）下两种条目都不做存在性 —— 显式钉住，避免将来漂成两边说不清
  assert.deepEqual(withMode('absolute', () => validateEntry(tomb, ports)), [])
  const absActive = withMode('absolute', () => validateEntry({ ...tomb, status: 'active' }, ports))
  assert.ok(!absActive.some(e => e.includes('不存在')), 'absolute 模式不校验存在性（异机降级口）')
  assert.ok(absActive.every(e => !e.includes('盘符')), '但形态合法仍应全通过')
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

// ── 2026-11-07：全局清单 vs 本机检出集（remote-only 只豁免存在性）──────────
// registry 是全局清单，各机检出集不同；本机缺检出 ≠ 治理缺陷。但豁免必须**窄**：
// 去掉声明要能重新报「path 不存在」，禁盘符等形状校验一条都不许跟着放宽。
test('skipLocalExistence: remote-only 只豁免存在性，形状校验照旧', () => {
  const ports = loadPorts()
  const remoteOnly = {
    id: 'write-agent', name: 'x', category: 'ai', version: '1',
    path: 'repos/no-such-checkout', checkout: 'remote-only',
    launch: { command: 'python -m app.main' },
  }
  assert.ok(isTombstone({ status: 'archived' }), '墓碑判定仍有效')
  assert.ok(!isTombstone(remoteOnly), 'remote-only 不是墓碑：活跃但在别机')
  assert.ok(skipLocalExistence(remoteOnly))
  assert.ok(!skipLocalExistence({ ...remoteOnly, checkout: undefined }), '未声明则照旧 fail-loud')
  assert.deepEqual(withMode('exists', () => validateEntry(remoteOnly, ports)), [],
    '显式声明后豁免 path 存在性')
  assert.ok(withMode('exists', () => validateEntry({ ...remoteOnly, checkout: undefined }, ports))
    .some(e => e.includes('不存在')), '去掉声明必须重新报 path 不存在')
  assert.ok(withMode('exists', () => validateEntry({ ...remoteOnly, path: 'G:\\repos\\x' }, ports))
    .some(e => e.includes('盘符')), '豁免不等于放行：禁盘符形状校验照旧')
})
