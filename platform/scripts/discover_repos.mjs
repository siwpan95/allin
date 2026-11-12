// discover_repos.mjs —— 发行仓发现 / 三面对账（采集层，默认只读、不进阻断链）。
//
// 为什么需要它：registry/projects/*.yaml 是「当前这一套发行仓」的声明态清单。
// 换机部署 allin 后 repos/ 内容可能完全不同，手维护的清单会与实况全量错位；
// check_repos.mjs 只答「已有锚点对不对」，答不了「到底有哪些仓该被登记」。
// 本脚本补上发现这一步：本地发行区 / registry 声明 / 远端 owner 三方差集。
//
// 借鉴（仅公开文档中的概念，未复制代码 / 配置片段 / 引入依赖，见 SPEC-203）：
//   · Backstage GitHub Discovery —— discovery 优于手工登记
//   · Argo CD SCM Provider Generator —— 从 SCM 组织自动发现仓
//   · Renovate autodiscover —— 账号可访问集合 = 发现域，用 filter 收窄
//
// 用法（在 platform/ 下运行，或任意 cwd 均可）：
//   node scripts/discover_repos.mjs                  # 三面对账（远端需网络）
//   node scripts/discover_repos.mjs --offline       # 仅本地 + registry
//   node scripts/discover_repos.mjs --json          # 机器可读输出
//   node scripts/discover_repos.mjs --draft         # 输出待补登记草稿到 stdout（不写盘）
//   node scripts/discover_repos.mjs --strict        # 存在差异时 exit 1（供人工 / CI 选用）
//   node scripts/discover_repos.mjs --selfcheck     # 集合运算自检（能红能绿）
//
// 纪律：默认不写盘、默认不判红；联网采集不进门禁阻断链 —— 离线北极星 +
// 「证据采集与门禁控制分离」（见 docs/记录/审计/组合做大做强战略研究_2026-10-31.md §6.1）。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadRegistry, REPOS_ROOT, isTombstone, skipLocalExistence } from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const flag = (n) => args.includes(n)
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(__dirname, '..', 'registry', 'projects')
const OWNER = process.env.PLATFORM_GITEE_OWNER || 'siwpan'
const OFFLINE = flag('--offline') || process.env.PLATFORM_REPOS_OFFLINE === '1'
const API = 'https://gitee.com/api/v5'

const diffSets = (a, b) => [...a].filter((x) => !b.has(x)).sort()

/** 本地发行区：只认「一仓一目录 + 含 .git」，对齐 SPEC-006 §3。 */
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

/** registry 声明：仓名取 publish.repo 末段，回退 path 末段，再回退 id。 */
function declaredRepos(dir) {
  const { entries } = loadRegistry(dir)
  const out = new Set()
  const detail = []
  for (const e of entries) {
    const fromPublish = String(e.publish?.repo || '').split('/').pop()
    const fromPath = String(e.path || '').replace(/^repos\//, '').split('/')[0]
    const name = (fromPublish || fromPath || e.id || '').toLowerCase()
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
  return { out, detail }
}

/** 草稿只给「最小可登记形状」，缺的 launch/stop/health 必须人工补，绝不伪造可直接入库的条目。 */
function draftYaml(names, owner, localSet) {
  const lines = []
  lines.push('# registry 草稿（discover_repos.mjs 生成，仅 stdout，不写盘）')
  lines.push('# ⚠ 以下条目缺 launch/stop/health，直接入库会被 validateEntry 判红；')
  lines.push('#   请人工补齐后逐个复核，再放进 PLATFORM_REGISTRY 指向的目录。')
  for (const name of names) {
    lines.push(`# --- ${name}.yaml ---`)
    lines.push(`id: ${name}`)
    lines.push(`name: ${name}`)
    lines.push('category: 未分类')
    lines.push('version: 0.0.0')
    lines.push(`path: repos/${name}`)
    lines.push(`checkout: ${localSet.has(name) ? 'local' : 'remote-only'}`)
    lines.push('launch:')
    lines.push('  command: ""')
    lines.push('publish:')
    lines.push(`  repo: ${owner}/${name}`)
    lines.push('  branch: master')
    lines.push('')
  }
  return lines.join('\n')
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
  // 能红：strict 口径必须把差异判出来；能绿：三方完全一致时严格口径应放行
  const strict = diffSets(local, declared).length + diffSets(remote, declared).length > 0
  const clean = diffSets(new Set(['alpha']), new Set(['alpha'])).length === 0
  if (!strict) { bad++; console.log('[BAD] strict 未判出差异') } else console.log('[OK] strict 能红')
  if (!clean) { bad++; console.log('[BAD] 一致集合被误判') } else console.log('[OK] 一致集合能绿')
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

const local = localRepos(REPOS_ROOT)
const { out: declared, detail } = declaredRepos(REGISTRY)

const localOnly = diffSets(local, declared)
const missingLocal = diffSets(declared, local)
const remoteUndeclared = OFFLINE || remoteError ? [] : diffSets(remote, declared)
const nonTombstone = new Set(detail.filter((d) => !d.tombstone).map((d) => d.name))
const missingRemote = OFFLINE || remoteError ? [] : diffSets(nonTombstone, remote)
const excused = detail.filter((d) => d.skipLocal && missingLocal.includes(d.name)).length

const report = {
  owner: OWNER,
  registry: REGISTRY,
  reposRoot: REPOS_ROOT,
  remote: OFFLINE ? 'offline' : (remoteError ? `error: ${remoteError}` : 'ok'),
  counts: { local: local.size, declared: declared.size, remote: remote.size },
  local_only: localOnly,
  declared_missing_local: missingLocal,
  declared_missing_local_excused: excused,
  declared_missing_remote: missingRemote,
  remote_undeclared: remoteUndeclared,
}

if (flag('--json')) {
  console.log(JSON.stringify(report, null, 2))
} else {
  console.log('== 发行仓三面对账（采集层 / 默认只读） ==')
  console.log(`owner=${report.owner}  registry=${REGISTRY}`)
  console.log(`reposRoot=${REPOS_ROOT}  remote=${report.remote}`)
  console.log(`local=${local.size} declared=${declared.size} remote=${remote.size}`)
  for (const [k, v] of [
    ['local_only（本地有 / 未登记）', localOnly],
    ['declared_missing_local（已声明 / 本机未检出）', missingLocal],
    ['declared_missing_remote（已声明 / 远端不存在，非墓碑）', missingRemote],
    ['remote_undeclared（远端有 / 未登记）', remoteUndeclared],
  ]) {
    console.log(`-- ${k}: ${v.length}`)
    if (v.length) console.log('   ' + v.slice(0, 20).join(', ') + (v.length > 20 ? ' …' : ''))
  }
  console.log(`注：本机未检出中有 ${excused} 条为墓碑 / checkout:remote-only 显式豁免。`)
}

if (flag('--draft')) {
  const names = [...new Set([...localOnly, ...remoteUndeclared])].sort()
  if (!names.length) console.log('# 无待补登记项')
  else console.log(draftYaml(names, OWNER, local))
}

// 默认只报告不判红；--strict 供人工 / CI 显式选用（不接进 run_all_gates.sh）。
const diffs = localOnly.length + missingRemote.length + remoteUndeclared.length
process.exit(flag('--strict') && diffs > 0 ? 1 : 0)
