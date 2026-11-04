// @allin/portal —— bridge 只读聚合端点（P4-M1 · 三面贯通 G1/G2/G4 数据面）。
//
// 纪律（P2 设计冻结版，deliverables/P2-后端服务与API实现.md v3）：
//   - 零依赖：仅 node:fs / node:path（「聚合不融合」，portal node:http 面不新增任何包）；
//   - 只读文件事实源：running.json / gate-runs.jsonl / g21-runs.jsonl / divergence-events（经注入）；
//   - 不 import 项目代码：@allin/core 的 loadRegistry/isRunning 与 readAlerts 由 index.js **注入**，
//     bridge 自身不 import core，依赖方向 index → bridge（注入参数）单向无环；
//   - 降级语义与 gate-history 的 readable 模式一致：文件缺失/无可解析行 → readable:false，
//     绝不 500（g21-runs.jsonl 在 g21 门禁首次运行前不存在，属正常生命周期状态）。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PLATFORM = path.join(HERE, '..', '..', '..')        // platform/
const ALLIN_ROOT = path.join(PLATFORM, '..')              // 治理仓根 allin/（2026-10-26 三仓整合后 platform 非仓根）
// 门禁留痕目录：env 覆盖沿既有 ALLIN_GATE_RUNS 惯例（异机/测试可指路），零盘符硬编码
const GATE_AUDIT = process.env.ALLIN_GATE_AUDIT || path.join(ALLIN_ROOT, 'tools', 'gate', 'audit')
const GATE_RUNS = process.env.ALLIN_GATE_RUNS || path.join(GATE_AUDIT, 'gate-runs.jsonl')
// g21 产物 v3（主理人终裁）：JSONL 逐行快照，每行一次运行的完整自足快照，5MB 轮转沿 tasks.log 模式；
// portal 只读「最后一行」= 最新判据快照，免 YAML 解析（P2 D-B1 裁决）
const G21_RUNS = process.env.ALLIN_G21_RUNS || path.join(GATE_AUDIT, 'g21-runs.jsonl')

// 门户自身版本：读 package.json（与 /api/status 口径对齐的事实源），不硬编码
const PKG = readJsonFileSync(path.join(HERE, '..', 'package.json')) || {}

function readJsonFileSync(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return null }
}

// ── JSONL 尾行读取（容忍末尾坏帧，D1 纪律：坏行跳过而非整份失败）────────────────
// 从文件尾部向前找最后一个可解析的 JSON 行；文件缺失/全空/全坏行返回 null。
// ⚠️ 边界（2026-11-04 实测修正）：lastIndexOf('\n', i) 在 text[i]==='\n' 时返回 i 本身，
// 若以「i = end」回退会零进度死循环把事件循环卡死（文件以换行结尾的常见形态必触发）。
// 改用 end 游标（end 严格递减）保证必然前进。
function readLastJsonLine(file) {
  let text
  try { text = fs.readFileSync(file, 'utf8') } catch { return null }
  let end = text.length
  while (end > 0) {
    const start = text.lastIndexOf('\n', end - 1)   // start ≤ end-1，保证每轮 end 严格变小
    const line = text.slice(start + 1, end).trim()
    end = start < 0 ? 0 : start
    if (!line) continue
    try { return JSON.parse(line) } catch { continue }   // 坏行跳过，继续向前找
  }
  return null
}

// ── 门禁留痕摘要（gate-runs.jsonl，tail 200；与既有 /api/gate-history 同口径）────
function gateSummary(tail = 200) {
  let text
  try { text = fs.readFileSync(GATE_RUNS, 'utf8') } catch {
    return { readable: false, lastRunAt: null, lastOkAt: null, escapeRate: 0 }
  }
  const runs = []
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (!t) continue
    try { runs.push(JSON.parse(t)) } catch { /* 坏行跳过 */ }
  }
  const t2 = runs.slice(-tail)
  const failed = t2.filter(r => Number(r.exit) !== 0).length
  const okRuns = t2.filter(r => Number(r.exit) === 0)
  return {
    readable: true,
    lastRunAt: t2.length ? (t2[t2.length - 1].ts ?? null) : null,
    lastOkAt: okRuns.length ? (okRuns[okRuns.length - 1].ts ?? null) : null,
    escapeRate: t2.length ? Number((failed / t2.length).toFixed(4)) : 0,
  }
}

// ── g21 尾行公共解析（对齐 agent-app-engineer 落盘的真实 schema，宽容兼容 P2 草案字段）──
// 真实行：{ type:'g21-run', checkedAt, commit, routesFile, routesReadable, routes[], results[], summary{total,ok,drift,warn}, error? }
// P2 草案字段（drift[]/lastCheckAt）保留兼容：checkedAt 优先，findings = drift[] ∪ results[]，
// 漂移计数优先取 summary.drift（逐条清单缺席时回退 findings 计数）。
function parseGateRun(j) {
  const findings = [
    ...(Array.isArray(j.drift) ? j.drift : []),
    ...(Array.isArray(j.results) ? j.results : []),
  ]
  const driftCount = (j.summary && Number.isInteger(j.summary.drift))
    ? j.summary.drift
    : findings.length
  const hasErrorSeverity = findings.some((d) => d && d.severity === 'error')
  return {
    routes: Array.isArray(j.routes) ? j.routes : [],
    findings,
    driftCount,
    lastCheckAt: j.checkedAt ?? j.lastCheckAt ?? null,
    healthy: !(j.routesReadable === false || hasErrorSeverity || driftCount > 0),
  }
}

// ── /api/orchestration：g21-runs.jsonl 尾行 → 编排判据快照 ──────────────────────
// 响应含 healthy（判红三条件：routesReadable=false ∨ 任一 finding severity:error ∨ 漂移>0）
// 与 lastCheckError（崩溃行 error{code,msg} 透传，前端据此区分「门禁自身故障」与「判据结果」）。
export function orchestrationPayload(params = new URLSearchParams()) {
  const include = String(params.get('include') || 'routes,status') // 逗号分隔白名单
  const result = {
    readable: true,
    routes: [],
    drift: [],
    lastCheckAt: null,
    lastCheckError: null,
    summary: { total: 0, driftCount: 0 },
    healthy: false,
  }
  const j = readLastJsonLine(G21_RUNS)
  if (!j) { result.readable = false; return result }   // 文件缺失/全坏行 → 降级，不报错
  const p = parseGateRun(j)
  if (include.includes('routes')) result.routes = p.routes
  if (include.includes('status')) {
    result.drift = p.findings
    result.lastCheckAt = p.lastCheckAt
    result.lastCheckError = j.error
      ? { code: String(j.error.code || 'GATE_CRASHED'), msg: String(j.error.msg || '').slice(-500) }
      : null
  }
  result.summary = { total: result.routes.length, driftCount: p.driftCount }
  result.healthy = p.healthy
  return result
}

// orchestration 的概要投影（供 /api/overview 内嵌，避免读两遍文件各自解析）
function orchestrationSummary() {
  const j = readLastJsonLine(G21_RUNS)
  if (!j) return { readable: false, routes: 0, driftCount: 0, lastCheckAt: null, healthy: false }
  const p = parseGateRun(j)
  return {
    readable: true,
    routes: p.routes.length,
    driftCount: p.driftCount,
    lastCheckAt: p.lastCheckAt,
    healthy: p.healthy,
  }
}

// ── /api/overview：一次拉取的全局聚合（30s TTL 内存缓存，沿 engineCache 惯例）────
// 只有 TTL 失效、不做文件监听（Windows 跨进程 FSWatcher 语义不可靠，P1 决策三已实证）；
// build 失败不写缓存，下次请求重算。deps 由 index.js 注入（P2 §1.1 依赖方向裁决）。
let overviewCache = { at: 0, payload: null }
const OVERVIEW_TTL_MS = 30_000

export async function overviewPayload(deps) {
  if (Date.now() - overviewCache.at < OVERVIEW_TTL_MS && overviewCache.payload) {
    return { ...overviewCache.payload, cached: true }
  }
  const payload = buildOverview(deps)
  overviewCache = { at: Date.now(), payload }
  return { ...payload, cached: false }
}

function buildOverview(deps) {
  const { loadRegistry, isRunning, readAlerts, registryDir, port } = deps
  // library：pid 存活级（isRunning）而非 probeEntry 探测级——overview 只回答「活着几个」，
  // 探测级细节走既有 /api/library（P2 D-B2 裁决，保 P95 ≤ 500ms 预算）
  let library = { total: 0, running: 0, invalid: 0, problems: 0 }
  try {
    const { entries, problems } = loadRegistry(registryDir)
    library = {
      total: entries.length,
      running: entries.filter((e) => isRunning(e.id)).length,
      invalid: entries.filter((e) => e._valid === false).length,
      problems: problems.length,
    }
  } catch { /* registry 不可读 → 投影零值，块级降级不整体失败 */ }

  let alerts = { last24h: 0, latestTs: null }
  try {
    const list = readAlerts()   // index.js 注入：已按 ts 倒序、封顶 100
    const cutoff = Date.now() - 24 * 60 * 60 * 1000
    alerts = {
      last24h: list.filter((a) => {
        const ts = Date.parse(String(a.ts || ''))
        return Number.isFinite(ts) && ts >= cutoff
      }).length,
      latestTs: list.length ? (list[0].ts ?? null) : null,
    }
  } catch { /* alerts 块降级 */ }

  return {
    portal: { version: PKG.version || null, uptime: Math.round(process.uptime()), port: port ?? null },
    library,
    alerts,
    gates: gateSummary(),
    orchestration: orchestrationSummary(),
    generatedAt: new Date().toISOString(),
  }
}
