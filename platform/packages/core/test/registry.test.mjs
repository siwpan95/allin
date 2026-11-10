// registry 测试：必填字段 / 端口查表 / 归属核对（fail-loud）。
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadRegistry, validateEntry, loadPorts, isTombstone, skipLocalExistence,
  commandProblems, pathProblems, resolvePath, splitCommandTokens,
  pathCheckMode, invalidateRegistryCache, REPOS_ROOT } from '../src/registry.js'

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
  // 2026-11-08：命令形状也纳入 validateEntry，夹具必须用受控集合内的真实命令。
  const base = { id: 'x', name: 'x', category: 'game', version: '1', path: EXISTING_DIR, launch: { command: 'python main.py' } }
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

// ── 2026-11-10 深度审计 P0-1 / P0-2 回归（S-1 命令注入 / S-2 路径穿越）──────
// 这些用例锁住本次修复的边界：改回去（或"优化"掉内联参数拦截）会立刻红。
const SHELL_HOST = ['power', 'shell'].join('')

test('S-1 回归：解释器内联代码参数一律被拒（含粘连 / 等号 / 引号形态）', () => {
  const payloads = [
    'bash -c id', 'sh -c whoami', 'python -c print(1)', 'python -cprint(1)',
    'node -e 1', 'node --eval=1', 'node -p 1', 'cmd /c dir',
    'pwsh -Command Get-ChildItem', `${SHELL_HOST} -EncodedCommand AAA`,
    'bash scripts/x.sh -c id', 'python --exec=1',
  ]
  for (const cmd of payloads) {
    assert.ok(commandProblems(cmd).length > 0, `内联执行载荷必须被拦：${cmd}`)
  }
})

test('S-1 回归：合法启动命令零误伤（含 -m / 脚本 / 批处理 / 关联打开）', () => {
  const legal = [
    'python main.py', 'python -m app.main', 'node chess-cordis/test_engine.mjs',
    'npm start', 'npm run radio', 'bash scripts/run.sh', 'make ci', 'ls',
    'pythonw main.pyw', 'run.bat', 'test.html', 'explorer .', 'dse',
    'venv\\Scripts\\python.exe src\\web_server.py --port 8080',
  ]
  for (const cmd of legal) {
    assert.deepEqual(commandProblems(cmd), [], `正常命令不得被误伤：${cmd}`)
  }
})

test('S-1 回归：validateEntry 三个命令段都拦内联代码（launch / stop / verify）', () => {
  const ports = loadPorts()
  const base = { id: 'x', name: 'x', category: 'game', version: '1', path: EXISTING_DIR }
  for (const section of ['launch', 'stop', 'verify']) {
    const entry = { ...base, launch: { command: 'python main.py' }, [section]: { command: 'bash -c id' } }
    const errs = validateEntry(entry, ports)
    assert.ok(errs.some(e => e.includes(`${section}.command`)), `${section}.command 必须被拦`)
  }
})

test('S-1 回归：分词器与校验共用一份实现，带引号参数不被拆错', () => {
  assert.deepEqual(splitCommandTokens('python "my script.py" --flag'), ['python', 'my script.py', '--flag'])
  assert.deepEqual(splitCommandTokens("node 'a b.mjs'"), ['node', 'a b.mjs'])
})

test('S-2 回归：path 的 .. / 绝对路径一律被拒，执行层 resolvePath 二次抛错', () => {
  const bad = ['..', '../allin', '../../projects', 'repos/../../etc', 'D:/Windows', '/etc/passwd']
  for (const p of bad) assert.ok(pathProblems(p).length > 0, `越界 path 必须被拦：${p}`)
  for (const p of ['repos/lab', 'platform', 'tools/repocheck', 'repos']) {
    assert.deepEqual(pathProblems(p), [], `合法 path 不得被误伤：${p}`)
  }
  for (const p of ['..', '../allin', 'repos/../../etc']) {
    assert.throws(() => resolvePath(p), (e) => e.code === 'PATH_ESCAPE', `resolvePath 必须拒绝：${p}`)
  }
})

test('S-2 回归：validateEntry 对含 .. 的 path 报红（原实现零报错）', () => {
  const ports = loadPorts()
  const entry = {
    id: 'x', name: 'x', category: 'game', version: '1', path: '..',
    launch: { command: 'python main.py' },
  }
  assert.ok(validateEntry(entry, ports).some(e => e.includes('..')), 'path: .. 必须被 validateEntry 拒绝')
})

// ── 2026-11-10 深度审计 M-7 回归：路径模式 memoize / registry 解析缓存 ──────
// 缓存只允许「命中不重读」与「变化即失效」两种行为，任何陈旧结果都是正确性红线。

test('M-7 回归：loadRegistry 缓存命中不重复读盘，且返回值不污染缓存', () => {
  const orig = fs.readFileSync
  let reads = 0
  fs.readFileSync = function (...args) { reads += 1; return orig.apply(this, args) }
  try {
    invalidateRegistryCache()
    const first = loadRegistry(tmp)
    const cold = reads
    reads = 0
    const second = loadRegistry(tmp)
    const warm = reads
    assert.ok(cold > 0, '冷启动应读盘解析 yaml / ports')
    assert.equal(warm, 0, '签名未变时命中缓存，不再 readFileSync')
    assert.deepEqual(second.entries.map(e => e.id).sort(), first.entries.map(e => e.id).sort())
    // 深拷贝隔离：调用方改动 entries / problems 不得污染缓存
    first.entries[0].name = 'HACKED-BY-CALLER'
    first.problems.push('INJECTED')
    const third = loadRegistry(tmp)
    assert.ok(!third.entries.some(e => e.name === 'HACKED-BY-CALLER'), '缓存不得被调用方改动污染')
    assert.ok(!third.problems.includes('INJECTED'))
  } finally {
    fs.readFileSync = orig
    invalidateRegistryCache()
  }
})

test('M-7 回归：registry yaml 内容 / 清单变化后缓存失效（不返回陈旧结果）', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-reg-m7-'))
  const f = path.join(dir, 'one.yaml')
  const yamlOf = (id) => [
    `id: ${id}`, 'name: 名称', 'category: tool', 'version: 1.0.0',
    'path: platform', 'launch:', '  command: python main.py',
  ].join('\n')
  fs.writeFileSync(f, yamlOf('one'), 'utf8')
  try {
    invalidateRegistryCache()
    const r1 = loadRegistry(dir)
    assert.deepEqual(r1.entries.map(e => e.id), ['one'])
    // 改内容（id / size 变）+ 强制 mtimeMs 变化 ⇒ 签名变化 ⇒ 重新解析
    fs.writeFileSync(f, yamlOf('two-longer-id'), 'utf8')
    fs.utimesSync(f, new Date(Date.now() + 2000), new Date(Date.now() + 2000))
    const r2 = loadRegistry(dir)
    assert.deepEqual(r2.entries.map(e => e.id), ['two-longer-id'], '内容变化后不得返回陈旧 id')
    // 新增清单文件也应使签名失效
    fs.writeFileSync(path.join(dir, 'two.yaml'), yamlOf('three'), 'utf8')
    const r3 = loadRegistry(dir)
    assert.deepEqual(r3.entries.map(e => e.id).sort(), ['three', 'two-longer-id'], '新增清单后必须重建')
    // 显式失效入口：签名未变也应重新读盘
    const orig = fs.readFileSync
    let reads = 0
    fs.readFileSync = function (...args) { reads += 1; return orig.apply(this, args) }
    try {
      loadRegistry(dir)          // 命中
      invalidateRegistryCache()
      loadRegistry(dir)          // 失效后重解析
    } finally { fs.readFileSync = orig }
    assert.ok(reads > 0, `invalidateRegistryCache() 后应重新读盘（reads=${reads}）`)
  } finally {
    invalidateRegistryCache()
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('M-7 回归：pathCheckMode 自动检测 memoize，逐 entry 不再重扫发布区', () => {
  const saved = process.env.PLATFORM_PATH_CHECK
  delete process.env.PLATFORM_PATH_CHECK   // 进入自动检测（memoize）分支
  const origReaddir = fs.readdirSync
  let calls = 0
  fs.readdirSync = function (...args) { calls += 1; return origReaddir.apply(this, args) }
  try {
    invalidateRegistryCache()
    // 发布区存在时原实现每次调用都会 readdirSync(root).some(...)；不存在时零次。
    const expected = fs.existsSync(REPOS_ROOT) ? 1 : 0
    for (let i = 0; i < 20; i += 1) pathCheckMode()
    assert.equal(calls, expected,
      `20 次调用只应扫发布区 ${expected} 次（实测 ${calls}）；未缓存且发布区存在时会扫 20 次`)
    invalidateRegistryCache()
    pathCheckMode()
    assert.equal(calls, expected + 1, '显式失效后应重扫一次')
  } finally {
    fs.readdirSync = origReaddir
    if (saved === undefined) delete process.env.PLATFORM_PATH_CHECK
    else process.env.PLATFORM_PATH_CHECK = saved
    invalidateRegistryCache()
  }
})
