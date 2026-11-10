// launch 启停测试：pid 持久化（running.json）跨进程可见/可停（PLATFORM_ROOT 隔离）。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn, spawnSync } from 'node:child_process'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-launch-'))
process.env.PLATFORM_ROOT = tmp

const { startEntry, stopEntry, isRunning, runningIds, buildSpawnPlan } = await import('../src/index.js')
const RUNNING = path.join(tmp, 'data', 'running.json')
// 2026-11-10 深度审计 P0-1：内联代码参数（node -e / bash -c / python -c）已被
// commandProblems 禁止 —— 这正是本次修复要堵的 RCE 入口。夹具改为落一个真实的
// 脚本文件，用 `node <file>` 启动，既不绕过校验、也不削弱启停行为的验证强度。
const SLEEPER_SCRIPT = path.join(tmp, 'sleeper.cjs')
fs.writeFileSync(SLEEPER_SCRIPT, 'setTimeout(function(){},60000)\n', 'utf8')
const SLEEPER = `node "${SLEEPER_SCRIPT}"`

function readRunning() {
  try { return JSON.parse(fs.readFileSync(RUNNING, 'utf8')) } catch { return {} }
}

function writeRunning(map) {
  fs.mkdirSync(path.dirname(RUNNING), { recursive: true })
  fs.writeFileSync(RUNNING, JSON.stringify(map), 'utf8')
}

function fakeEntry(id) {
  return { id, name: id, category: 'test', version: '1.0.0', path: os.tmpdir(), launch: { command: SLEEPER } }
}

function pidAlive(pid) {
  try { process.kill(pid, 0); return true } catch (e) { return e.code === 'EPERM' }
}

test('startEntry 落 running.json（pid/owner/command）且重复启动被拒', () => {
  const r = startEntry(fakeEntry('t1'), { owner: 'test' })
  assert.equal(r.ok, true)
  const m = readRunning()
  assert.equal(m.t1.pid, r.pid)
  assert.equal(m.t1.owner, 'test')
  assert.equal(m.t1.command, SLEEPER)
  assert.equal(isRunning('t1'), true)
  assert.ok(runningIds().includes('t1'))
  const again = startEntry(fakeEntry('t1'))
  assert.equal(again.reason, 'already-running')
})

test('外部登记条目：活 pid 可见、死 pid 惰性清理', () => {
  writeRunning({ ext1: { pid: process.pid, startedAt: Date.now(), owner: 'other' } })
  assert.equal(isRunning('ext1'), true) // 本测试进程 pid = 活
  assert.ok(runningIds().includes('ext1'))
  writeRunning({ ext1: { pid: 999999999, startedAt: Date.now(), owner: 'other' } })
  assert.equal(isRunning('ext1'), false) // 死 pid → false 且被清理
  assert.equal(readRunning().ext1, undefined)
})

test('stopEntry 可停止外部登记进程（跨进程树杀 + 条目清除）', async () => {
  const child = spawn('node', ['-e', 'setTimeout(()=>{},60000)'], { detached: true, stdio: 'ignore' })
  child.unref()
  writeRunning({ ext2: { pid: child.pid, startedAt: Date.now(), owner: 'other' } })
  assert.equal(isRunning('ext2'), true)
  const r = await stopEntry('ext2', null)
  assert.equal(r.ok, true)
  assert.equal(pidAlive(child.pid), false)
  assert.equal(readRunning().ext2, undefined)
  const r2 = await stopEntry('ext2', null)
  assert.equal(r2.reason, 'not-running')
})

test('子进程退出后 running.json 条目清除（exit 事件回弹）', async () => {
  const r = startEntry(fakeEntry('t2'), { owner: 'test' })
  // 跨平台杀进程：原实现只调用 Windows 的 taskkill，Linux CI 会 ENOENT 使用例失败。
  // B3 把 platform 测试接入 posix job 后这条必须可移植；POSIX 直接向 pid 发 SIGKILL。
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(r.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    try { process.kill(r.pid, 'SIGKILL') } catch { /* 子进程已退出 */ }
  }
  const deadline = Date.now() + 5000
  while (Date.now() < deadline && isRunning('t2')) await new Promise((res) => setTimeout(res, 100))
  assert.equal(isRunning('t2'), false)
  assert.equal(readRunning().t2, undefined)
})

test('running.json 损坏时回退 .bak（durable publish 纪律，Phase 1）', () => {
  // 两次正常写：第一次落 t3，第二次写 t4 时把 t3 存进 .bak
  startEntry(fakeEntry('t3'), { owner: 'test' })
  startEntry(fakeEntry('t4'), { owner: 'test' })
  // 主文件损坏（崩溃半截 JSON 模拟）
  fs.writeFileSync(RUNNING, '{ "t4": { broken', 'utf8')
  // 读侧应回退 .bak（= 上一次完好快照，含 t3）
  assert.equal(isRunning('t3'), true, '应从 .bak 恢复 t3')
  // 下一次写会以 .bak 为基底重建主文件（不丢 t3，也清掉损坏内容）
  startEntry(fakeEntry('t5'), { owner: 'test' })
  const m = readRunning()
  assert.ok(m.t3, '损坏后首次写不应丢 .bak 中的 t3')
  assert.ok(m.t5, '新条目正常登记')
})

after(async () => {
  for (const id of ['t1', 't2', 't3', 't4', 't5', 'ext1', 'ext2']) { try { await stopEntry(id, null) } catch { /* 已清 */ } }
  try { fs.rmSync(tmp, { recursive: true, force: true }) } catch { /* Windows 文件占用容错 */ }
})

// ── 2026-11-10 深度审计 P0-1 回归：执行层 shell 收敛 ──────────────────────────
test('S-1 回归：常规命令走 shell:false + 参数数组（命令与参数严格分离）', () => {
  const plan = buildSpawnPlan('python main.py --port 8080')
  assert.equal(plan.shell, false, '可执行文件形态不得经 shell')
  assert.equal(plan.file, 'python')
  assert.deepEqual(plan.args, ['main.py', '--port', '8080'])
})

test('S-1 回归：带引号路径参数不被引号破坏，且仍走无 shell 路径', () => {
  const plan = buildSpawnPlan('python "my script.py"')
  assert.equal(plan.shell, false)
  assert.deepEqual(plan.args, ['my script.py'])
})

test('S-1 回归：依赖 shell 关联的形态保留 shell，但危险内联载荷在准入层就被拒', () => {
  const bat = buildSpawnPlan('run.bat')
  assert.equal(bat.shell, true, '批处理依赖 shell 关联打开')
  assert.throws(() => buildSpawnPlan('bash -c id'), (e) => e.code === 'UNSAFE_COMMAND')
  assert.throws(() => buildSpawnPlan('node -e 1'), (e) => e.code === 'UNSAFE_COMMAND')
})

test('S-2 回归：startEntry 对越界 path fail-closed（绕过 loadRegistry 也拦得住）', () => {
  const escape = { ...fakeEntry('escape'), path: '../outside' }
  assert.throws(
    () => startEntry(escape, { owner: 'test' }),
    (e) => e.code === 'PATH_ESCAPE',
    'path 含 .. 必须在执行层被拒，而不是只靠 validateEntry',
  )
})
