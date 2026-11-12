// discover_repos.mjs —— 发行仓扫描登记 / 三面对账（采集层；默认只读，--apply 才写盘）。
//
// 为什么需要它：registry/projects/*.yaml 原本靠手抄维护 145 份。换机部署 allin 后
// repos/ 内容可能完全不同，手抄清单会与实况全量错位；check_repos.mjs 只答
// 「已有锚点对不对」，答不了「到底有哪些仓该被登记」。本脚本把登记动作变成扫描：
// 本地发行区 / registry 声明 / 远端 owner 三方差集 → 探测仓内真实入口 →
// 生成**可直接通过 validateEntry 的完整条目**，显式 --apply 才落盘。
//
// 借鉴（仅公开文档中的概念，未复制代码 / 配置片段 / 引入依赖，见 SPEC-203）：
//   · Backstage GitHub Discovery —— discovery 优于手工登记
//   · Argo CD SCM Provider Generator —— 从 SCM 组织自动发现仓
//   · Renovate autodiscover —— 账号可访问集合 = 发现域，用 filter 收窄
//
// 用法（在 platform/ 下运行，或任意 cwd 均可）：
//   node scripts/discover_repos.mjs                  # 三面对账 + 登记预览（远端需网络）
//   node scripts/discover_repos.mjs --offline       # 仅本地 + registry
//   node scripts/discover_repos.mjs --json          # 机器可读输出
//   node scripts/discover_repos.mjs --apply         # 扫描登记：把候选写成 registry YAML
//   node scripts/discover_repos.mjs --draft         # --apply 的 dry-run 预览（兼容旧用法）
//   node scripts/discover_repos.mjs --strict        # 存在差异时 exit 1（供人工 / CI 选用）
//   node scripts/discover_repos.mjs --selfcheck     # 集合 / 探测 / 分类自检（能红能绿）
//
// 纪律：默认不写盘、默认不判红；联网采集不进门禁阻断链 —— 离线北极星 +
// 「证据采集与门禁控制分离」（见 docs/记录/审计/组合做大做强战略研究_2026-10-31.md 第 6.1 节）。
// --apply 只写「新文件」，已存在的手抄条目一律跳过，绝不覆盖。
// 探测不到启动入口的仓不生成条目，列入 needs_manual_review —— 不伪造可直接入库的清单。
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { loadRegistry, REPOS_ROOT, isTombstone, skipLocalExistence } from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const flag = (n) => args.includes(n)
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(__dirname, '..', 'registry', 'projects')
const OWNER = process.env.PLATFORM_GITEE_OWNER || 'siwpan'
const OFFLINE = flag('--offline') || process.env.PLATFORM_REPOS_OFFLINE === '1'
const APPLY = flag('--apply')
const API = 'https://gitee.com/api/v5'
const RETIRED_RX = /已归档|归档声明|不再维护|已退役|retired|archived/i

const diffSets = (a, b) => [...a].filter((x) => !b.has(x)).sort()

/** 本地发行区：只认「一仓一目录 + 含 .git」，对齐 SPEC-006 第 3 节。 */
function localRepos(root) {
  const out = new Set()
  if (!fs.existsSync(root)) return out
  for (const e of fs.readdirSync(root, { withFileTypes: true })) {
    if (!e.isDirectory()) continue
    if (fs.existsSync(path.join(root, e.name, '.git'))) out.add(e.name.toLowerCase())
  }
  return out
}

/** 远端 owner 的仓集合：匿名只读，与 check_repos.mjs 同一口径（type=all）。 */
async function remoteRepos(owner) {
  const out = new Set()
  for (let page = 1; page <= 5; page++) {
    const url = `${API}/users/${owner}/repos?type=all&sort=full_name&per_page=100&page=${page}`
    const res = await fetch(url, {
      headers: { 'User-Agent': 'allin-repos-discovery' },
      signal: AbortSignal.timeout(30000),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const batch = await res.json()
    if (!Array.isArray(batch) || batch.length === 0) break
    for (const r of batch) out.add(String(r.path).toLowerCase())
    if (batch.length < 100) break
  }
  return out
}

/** 只有 path 落在发行区的条目才参与三面对账；仓内条目（如 platform）单列。 */
const isIssuanceEntry = (e) => String(e.path || '').startsWith('repos/')

/** registry 声明：仓名取 publish.repo 末段，回退 path 末段，再回退 id。 */
function declaredRepos(dir) {
  const { entries } = loadRegistry(dir)
  const out = new Set()          // 发行区条目（参与本地/远端差集）
  const allNames = new Set()     // 全部条目的仓名（含治理仓自身，用于远端对账）
  const internal = []
  const detail = []
  for (const e of entries) {
    const fromPublish = String(e.publish?.repo || '').split('/').pop()
    const fromPath = String(e.path || '').replace(/^repos\//, '').split('/')[0]
    const name = (fromPublish || fromPath || e.id || '').toLowerCase()
    if (name) allNames.add(name)
    // 仓内条目（如 portal.yaml，path: platform，publish.repo: siwpan/allin）：
    // 不进发行区差集，但它的远端仓名仍算「已声明」，否则治理仓自身会被误报未登记。
    if (!isIssuanceEntry(e)) {
      internal.push({ id: e.id, path: String(e.path || ''), publish: String(e.publish?.repo || '') })
      continue
    }
    if (!name) continue
    out.add(name)
    detail.push({
      id: e.id,
      name,
      publish: String(e.publish?.repo || ''),
      tombstone: isTombstone(e),
      skipLocal: skipLocalExistence(e),
    })
  }
  return { out, allNames, detail, entriesCount: entries.length, internal }
}

/** 归档残留：远端已无该仓（或离线）+ README / 最后一次提交含归档声明。 */
function retiredReason(dir, name, remoteAvailable) {
  if (remoteAvailable && remoteHas(name)) return null
  const readme = ['README.md', 'README.en.md', 'README.zh.md']
    .map((f) => path.join(dir, f))
    .filter((f) => fs.existsSync(f))
    .map((f) => { try { return fs.readFileSync(f, 'utf8').slice(0, 4000) } catch { return '' } })
    .join('\n')
  let head = ''
  try {
    head = spawnSync('git', ['-C', dir, 'log', '-1', '--format=%s'], { encoding: 'utf8' }).stdout || ''
  } catch { /* 非 git 仓不算归档残留 */ }
  if (RETIRED_RX.test(readme)) return 'README 含归档/退役声明'
  if (RETIRED_RX.test(head)) return `末次提交含归档声明：${head.trim().slice(0, 80)}`
  return null
}

let remoteSetRef = new Set()
const remoteHas = (n) => remoteSetRef.has(n.toLowerCase())

/** 探测真实启动入口；返回 null 表示无法判定（绝不猜命令）。 */
function detectLaunch(dir) {
  const has = (f) => fs.existsSync(path.join(dir, f))
  if (has('main.py')) return { command: 'python main.py', basis: 'main.py' }
  if (has('app.py')) return { command: 'python app.py', basis: 'app.py' }
  if (has('package.json')) {
    try {
      const pkg = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8'))
      if (pkg.scripts && pkg.scripts.start) return { command: 'npm start', basis: 'package.json scripts.start' }
    } catch { /* 损坏的 package.json 不作为依据 */ }
  }
  if (has('index.js')) return { command: 'node index.js', basis: 'index.js' }
  if (has('run.bat')) return { command: 'run.bat', basis: 'run.bat' }
  return null
}

function gitInfo(dir) {
  const out = { repo: '', branch: 'master' }
  try {
    const url = (spawnSync('git', ['-C', dir, 'remote', 'get-url', 'origin'], { encoding: 'utf8' }).stdout || '').trim()
    const m = url.match(/(?:gitee\.com|github\.com)[/:]([^/]+)\/([^/]+?)(?:\.git)?$/i)
    if (m) out.repo = `${m[1]}/${m[2]}`
    const br = (spawnSync('git', ['-C', dir, 'symbolic-ref', '--short', 'HEAD'], { encoding: 'utf8' }).stdout || '').trim()
    if (br) out.branch = br
  } catch { /* 用默认值 */ }
  return out
}

function displayName(dir, fallback) {
  for (const f of ['README.md', 'README.en.md']) {
    const p = path.join(dir, f)
    if (!fs.existsSync(p)) continue
    try {
      const first = fs.readFileSync(p, 'utf8').split('\n').find((x) => x.startsWith('# '))
      if (first) return first.replace(/^#\s+/, '').trim().slice(0, 80)
    } catch { /* 回退目录名 */ }
  }
  return fallback
}

/** 生成完整可入库 YAML：所有字段来自实际扫描，探测不到入口的仓不生成。 */
function buildEntryYaml(name, localSet, remoteSet) {
  const isLocal = localSet.has(name)
  if (!isLocal) return null // 只有远端、无本地目录 ⇒ 无法探测入口，交由人工
  const dir = path.join(REPOS_ROOT, name)
  const launch = detectLaunch(dir)
  if (!launch) return null
  const gi = gitInfo(dir)
  const publishRepo = gi.repo || `${OWNER}/${name}`
  const q = (s) => JSON.stringify(String(s))
  return [
    `id: ${name}`,
    `name: ${q(displayName(dir, name))}`,
    'category: unclassified',
    'version: 0.0.0',
    `path: repos/${name}`,
    `checkout: ${isLocal ? 'local' : 'remote-only'}`,
    `note: ${q(`scan-generated by discover_repos.mjs; launch 来自 ${launch.basis} 探测；publish 来自 git remote`)}`,
    'launch:',
    `  command: ${q(launch.command)}`,
    'publish:',
    `  repo: ${publishRepo}`,
    `  branch: ${gi.branch}`,
    '',
  ].join('\n')
}

function selfcheck() {
  const local = new Set(['alpha', 'beta'])
  const declared = new Set(['alpha', 'gamma'])
  const remote = new Set(['alpha', 'gamma', 'delta'])
  const cases = [
    ['local_only', diffSets(local, declared).join(','), 'beta'],
    ['declared_missing_local', diffSets(declared, local).join(','), 'gamma'],
    ['remote_undeclared', diffSets(remote, declared).join(','), 'delta'],
  ]
  let bad = 0
  for (const [n, got, want] of cases) {
    if (got !== want) { bad++; console.log(`[BAD] ${n}: ${got} != ${want}`) }
    else console.log(`[OK] ${n}: ${got}`)
  }
  const strict = diffSets(local, declared).length + diffSets(remote, declared).length > 0
  const clean = diffSets(new Set(['alpha']), new Set(['alpha'])).length === 0
  if (!strict) { bad++; console.log('[BAD] strict 未判出差异') } else console.log('[OK] strict 能红')
  if (!clean) { bad++; console.log('[BAD] 一致集合被误判') } else console.log('[OK] 一致集合能绿')
  // 仓内条目分流：portal.yaml（path: platform）不得进发行仓集合
  if (isIssuanceEntry({ path: 'platform' })) { bad++; console.log('[BAD] 仓内条目被误判为发行仓') }
  else console.log('[OK] 仓内条目分流')
  if (!isIssuanceEntry({ path: 'repos/alpha' })) { bad++; console.log('[BAD] 发行仓条目被漏掉') }
  else console.log('[OK] 发行仓条目保留')
  // 入口探测：能绿（有 main.py）也要能红（无入口不猜）
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'discover-selfcheck-'))
  try {
    fs.writeFileSync(path.join(tmp, 'main.py'), '')
    const ok = detectLaunch(tmp)?.command === 'python main.py'
    if (!ok) { bad++; console.log('[BAD] main.py 入口探测失败') } else console.log('[OK] main.py 入口探测')
    fs.rmSync(path.join(tmp, 'main.py'))
    const none = detectLaunch(tmp) === null
    if (!none) { bad++; console.log('[BAD] 无入口时伪造了命令') } else console.log('[OK] 无入口不伪造')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
  console.log(bad ? `SELFCHECK FAIL (${bad})` : 'SELFCHECK OK')
  return bad ? 1 : 0
}

if (flag('--selfcheck')) process.exit(selfcheck())

let remote = new Set()
let remoteError = null
if (!OFFLINE) {
  try {
    remote = await remoteRepos(OWNER)
  } catch (e) {
    remoteError = e.message
  }
}
remoteSetRef = remote
const remoteAvailable = !OFFLINE && !remoteError && remote.size > 0

const local = localRepos(REPOS_ROOT)
const { out: declared, allNames, detail, entriesCount, internal } = declaredRepos(REGISTRY)

const rawLocalOnly = diffSets(local, declared)
const retiredLocal = []
const localOnly = []
for (const name of rawLocalOnly) {
  const reason = retiredReason(path.join(REPOS_ROOT, name), name, remoteAvailable)
  if (reason) retiredLocal.push({ name, reason })
  else localOnly.push(name)
}
const missingLocal = diffSets(declared, local)
const remoteUndeclared = remoteAvailable ? diffSets(remote, allNames) : []
const nonTombstone = new Set(detail.filter((d) => !d.tombstone).map((d) => d.name))
const missingRemote = remoteAvailable ? diffSets(nonTombstone, remote) : []
const excused = detail.filter((d) => d.skipLocal && missingLocal.includes(d.name)).length

// ── 扫描登记：候选 → 完整 YAML；--apply 才写盘 ──────────────────────────────
const candidates = [...new Set([...localOnly, ...remoteUndeclared])].sort()
const generated = []
const needsManual = []
for (const name of candidates) {
  const yaml = buildEntryYaml(name, local, remote)
  if (!yaml) {
    needsManual.push({ name, reason: local.has(name) ? '仓内无可判定启动入口' : '仅远端存在，无本地目录可探测' })
    continue
  }
  generated.push({ name, yaml })
}

let written = 0
let skipped = 0
if (APPLY) {
  fs.mkdirSync(REGISTRY, { recursive: true })
  for (const g of generated) {
    const target = path.join(REGISTRY, `${g.name}.yaml`)
    if (fs.existsSync(target)) { skipped++; continue }
    fs.writeFileSync(target, g.yaml, 'utf8')
    written++
  }
}

const report = {
  owner: OWNER,
  registry: REGISTRY,
  reposRoot: REPOS_ROOT,
  remote: OFFLINE ? 'offline' : (remoteError ? `error: ${remoteError}` : 'ok'),
  apply: APPLY,
  counts: {
    local: local.size,
    entries: entriesCount,
    uniqueNames: declared.size,
    internalEntries: internal.length,
    remote: remote.size,
  },
  local_only: localOnly,
  retired_local: retiredLocal,
  declared_missing_local: missingLocal,
  declared_missing_local_excused: excused,
  declared_missing_local_unexcused: missingLocal.length - excused,
  declared_missing_remote: missingRemote,
  remote_undeclared: remoteUndeclared,
  registration: {
    generated: generated.map((g) => g.name),
    needs_manual_review: needsManual,
    written,
    skipped_existing: skipped,
  },
}

if (flag('--json')) {
  console.log(JSON.stringify(report, null, 2))
} else {
  console.log('== 发行仓三面对账 / 扫描登记（默认只读） ==')
  console.log(`owner=${report.owner}  registry=${REGISTRY}`)
  console.log(`reposRoot=${REPOS_ROOT}  remote=${report.remote}  apply=${APPLY}`)
  console.log(`local=${local.size} entries=${entriesCount} uniqueNames=${declared.size} internal=${internal.length} remote=${remote.size}`)
  for (const [k, v] of [
    ['local_only（本地有 / 未登记）', localOnly],
    ['declared_missing_local（已声明 / 本机未检出）', missingLocal],
    ['declared_missing_remote（已声明 / 远端不存在，非墓碑）', missingRemote],
    ['remote_undeclared（远端有 / 未登记）', remoteUndeclared],
  ]) {
    console.log(`-- ${k}: ${v.length}`)
    if (v.length) console.log('   ' + v.slice(0, 20).join(', ') + (v.length > 20 ? ' …' : ''))
  }
  console.log(`-- retired_local（归档残留 / 不登记）: ${retiredLocal.length}`)
  for (const r of retiredLocal) console.log(`   ${r.name}: ${r.reason}`)
  console.log(`注：本机未检出中 ${excused} 条为墓碑 / checkout:remote-only 豁免；仓内条目 ${internal.length} 条不进差集。`)
  console.log(`-- 扫描登记：可生成 ${generated.length} 条 / 需人工 ${needsManual.length} 条` +
    (APPLY ? ` / 已写入 ${written} 条 / 跳过已存在 ${skipped} 条` : '（dry-run，加 --apply 写盘）'))
  for (const n of needsManual) console.log(`   需人工 ${n.name}: ${n.reason}`)
}

if (flag('--draft')) {
  if (!generated.length) console.log('# 无可生成条目')
  for (const g of generated) console.log(`# --- ${g.name}.yaml ---\n${g.yaml}`)
}

// 默认只报告不判红；--strict 供人工 / CI 显式选用（不接进 run_all_gates.sh）。
const diffs = localOnly.length + missingRemote.length + remoteUndeclared.length
process.exit(flag('--strict') && diffs > 0 ? 1 : 0)
