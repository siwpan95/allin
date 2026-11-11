// harness.mjs — 编排 harness 入口：黄金值用例 + 共识/分歧 + 退出码绑定。
// 对齐 lab/chess-cordis/src/harness.mjs（GOLDEN_POSITIONS / analyzeDivergence / formatReport）；
// lab 仓落点盘符随机器，按仓名定位而非盘符。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mountPort } from './port.mjs'
import { register, disposeAll, runCmd, analyzeDivergence, snapshot } from './registry.mjs'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const MANIFEST = JSON.parse(fs.readFileSync(path.join(ROOT, 'harness', 'manifest.json'), 'utf8'))
const resolve = (s) => (s || '')
  .replaceAll('{root}', ROOT)
  .replaceAll('{node}', MANIFEST.runtime?.node || 'node')
  .replaceAll('{python}', MANIFEST.runtime?.python || 'python')

// 2026-11-08 深度审核 A4：manifest 固定探活 :9000，而平台已改为 PORT=0
// 并写端口发现文件 data/portal.port。固定端口会让「门户不在线」成为常态，
// 配合 informational 用例忽略 errors ⇒ harness 恒报全绿。这里改为优先读
// 实际绑定端口，环境变量 PLATFORM_PORTAL_URL 可显式覆盖。
// R-01（2026-11-10 收尾）：harness 面端口发现读取。口径：读 portFile → parseInt → port>0 → URL；
// env PLATFORM_PORTAL_URL 可显式覆盖（回退 manifest 声明失败时须计入 failures，不得恒绿）。
// 与 website（1-65535 + 三态降级）/ kernel（仅存在性）/ cli（探活兜底）有意差异，不可强行统一。
function probeTarget(c) {
  if (process.env.PLATFORM_PORTAL_URL) return process.env.PLATFORM_PORTAL_URL
  try {
    const raw = fs.readFileSync(path.join(ROOT, 'data', 'portal.port'), 'utf8').trim()
    const port = Number.parseInt(raw, 10)
    if (Number.isInteger(port) && port > 0) return `http://127.0.0.1:${port}/`
  } catch { /* 无端口发现文件：回退 manifest 声明，且失败必须计入 failures */ }
  return c.target
}

// 挂载组件（组合即数据：enabled:false = 运行时下架，对齐 cordis.yml 语义）
for (const c of MANIFEST.components) {
  if (c.enabled === false) continue
  if (c.kind === 'subprocess') {
    mountPort({ id: c.id, kind: c.kind, cmd: resolve(c.cmd), args: (c.args || []).map(resolve), cwd: resolve(c.cwd || '{root}'), timeout: c.timeout ?? 15000 })
  } else if (c.kind === 'probe') {
    register(c.id, {
      kind: 'probe', alive: () => true, ready: () => true,
      call: async () => {
        // S2（2026-11-11）：严格区分「门户离线」与「门户不健康」。
        //  · 无 HTTP 响应（连接被拒 / 端口无监听 / 超时）⇒ 离线，informational，
        //    返回 manifest 声明的 offlineValue，不进 errors、不计 failures。
        //    spec.md 的 health 用例本来就写「离线不判失败」，旧实现把它报成
        //    DIVERGENCE DETECTED，语义过重且把「门户没起」伪装成分歧。
        //  · 有响应但非 200 / marker 缺失 ⇒ 不健康，throw ⇒ error ⇒ failures++。
        //    这条路径绝不能被上面的离线分支吞掉，否则在线故障会恒绿。
        let r
        try {
          r = await fetch(probeTarget(c), { signal: AbortSignal.timeout(c.timeout ?? 5000) })
        } catch {
          return c.offlineValue ?? 'OFFLINE'
        }
        const body = await r.text()
        if (r.status !== 200) throw new Error('status ' + r.status)
        if (c.marker && !body.includes(c.marker)) throw new Error('marker missing: ' + c.marker)
        return r.status
      },
    })
  }
}

// 黄金值用例（单一真相源 = spec.md；expected:null = informational 用例；
// expectDiverged:[] = informational 用例的预期分歧名单，超出预期同样失败）
const CASES = [
  { name: 'registry-audit', cmd: 'check', participants: ['platform-gate'], expected: 0, expectConsensus: true },
  { name: 'registry-count', cmd: 'count', participants: ['platform-gate'], expected: null, expectConsensus: false, expectDiverged: [] },
  { name: 'portal-health', cmd: 'health', participants: ['portal-probe'], expected: null, expectConsensus: false, expectDiverged: [] },
]

const report = []
let failures = 0
const events = []
for (const c of CASES) {
  const all = await runCmd(c.cmd, c.payload || {})
  const sub = all.filter((r) => c.participants.includes(r.id))
  const errors = sub.filter((r) => !r.ok)
  const { consensus, diverged } = analyzeDivergence(sub)
  const match = c.expected === null ? true : (consensus !== null && JSON.stringify(consensus) === JSON.stringify(c.expected))
  if (c.expectConsensus && (diverged.length || errors.length || !match)) failures++
  // E4 eval-invariant：informational 用例声明预期分歧名单，超出预期 = 真失败。
  // 2026-11-08 深度审核 A4：组件全部报错时 analyzeDivergence 得到
  // consensus=null / diverged=[]，与 expectDiverged:[] 恰好相等 ⇒ 旧逻辑把
  // 「一个组件都没跑起来」判成全绿。errors 必须独立计入 failures。
  if (!c.expectConsensus && Array.isArray(c.expectDiverged)) {
    const got = [...diverged].sort().join(',')
    const want = [...c.expectDiverged].sort().join(',')
    if (got !== want || errors.length) failures++
  }
  if (diverged.length || errors.length || (c.expected !== null && !match)) {
    events.push({ type: 'divergence', case: c.name, consensus, expected: c.expected, expectDiverged: c.expectDiverged ?? null, diverged, errors: errors.map((r) => r.id + ':' + r.error) })
  }
  report.push({ c, sub, consensus, diverged, errors, match })
}

const lines = []
lines.push('=== ' + "allin-platform" + ' harness: golden cases ===')
lines.push('components: ' + snapshot().map((s) => s.id + (s.alive ? '' : '(dead)')).join(' '))
for (const { c, sub, consensus, diverged, errors, match } of report) {
  const status = match && !diverged.length && !errors.length ? 'PASS' : 'FAIL'
  const vals = sub.map((r) => r.id + '=' + (r.ok ? JSON.stringify(r.value) : 'ERR(' + r.error + ')') + '/' + r.ms + 'ms').join('  ')
  lines.push('[' + status + '] ' + c.name + '  expected=' + JSON.stringify(c.expected) + '  consensus=' + JSON.stringify(consensus) + '  ' + vals)
  if (diverged.length) lines.push('        diverged: ' + diverged.join(', '))
  if (errors.length) lines.push('        errors: ' + errors.map((r) => r.id + ': ' + r.error).join(' | '))
}

// E5 分歧事件订阅链路：异常事件以 JSON-lines 追加到 sink，供 CI/上层订阅与告警
if (events.length) {
  const sink = process.env.DIVERGENCE_EVENT_FILE || path.join(ROOT, 'data', 'divergence-events.jsonl')
  fs.mkdirSync(path.dirname(sink), { recursive: true })
  // 轮转（2026-09-24 强化）：超 5MB 归档为 .1，与 tasks.log 同款纪律
  try {
    if (fs.existsSync(sink) && fs.statSync(sink).size > 5 * 1024 * 1024) {
      fs.rmSync(sink + '.1', { force: true })
      fs.renameSync(sink, sink + '.1')
    }
  } catch { /* 轮转失败不阻塞记录 */ }
  const stream = fs.createWriteStream(sink, { flags: 'a' })
  for (const e of events) {
    stream.write(JSON.stringify({ ts: new Date().toISOString(), ...e, components: snapshot().map((s) => ({ id: s.id, alive: s.alive })) }) + '\n')
  }
  await new Promise((resolve, reject) => stream.end((err) => (err ? reject(err) : resolve())))
  lines.push('divergence-events: ' + events.length + ' appended -> ' + sink)
}
lines.push(failures === 0 ? 'OVERALL: ALL GOLDEN VALUES MATCH' : 'OVERALL: DIVERGENCE DETECTED (' + failures + ')')
console.log(lines.join('\n'))

// 退出码绑定（E6）：全绿 = exit 0；任何分歧/报错 = exit 1
await disposeAll()
process.exit(failures === 0 ? 0 : 1)
