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
//   node scripts/discover_repos.mjs --audit         # 本机全量扫描登记：跑满发行区，逐仓对账
//   node scripts/discover_repos.mjs --audit --snapshot  # 并落盘扫描快照（platform/registry/scan-snapshot.json）
//   node scripts/discover_repos.mjs --verify-snapshot   # 拿已落盘快照复跑对账，漂移即判红
//   node scripts/discover_repos.mjs --selfcheck     # 集合 / 探测 / 分类 / 审计自检（能红能绿）
//
// 纪律：默认不写盘、默认不判红；联网采集不进门禁阻断链 —— 离线北极星 +
// 「证据采集与门禁控制分离」（见 docs/记录/审计/组合做大做强战略研究_2026-10-31.md 第 6.1 节）。
// --apply 只写「新文件」，已存在的手抄条目一律跳过，绝不覆盖。
// 探测不到启动入口的仓不生成条目，列入 needs_manual_review —— 不伪造可直接入库的清单。
//
// --audit（2026-11-13 本机落地）：三面对账只答「有没有仓没登记」，答不了
// 「已登记的 145 份还与本机实况一致吗」。本机 138 仓里 131 份带 manual:true、
// 93 份带 verify —— 这些是扫描推不出的人工语义，必须作为**不可覆盖的保留层**。
// 因此审计只判机器可判定字段（id / path / publish.repo / publish.branch），
// 人工字段只登记清单、不比对、不改写。publish.branch 的判据是
// 「该分支在远端存在」而非「等于本机 HEAD」——workshop.js 拿它当发布分支去
// clone/fetch，radio / video 两条条目有意发布 3.0 / archived-video 分支。
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'
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
const AUDIT = flag('--audit')
const SNAPSHOT = flag('--snapshot')
const VERIFY_SNAPSHOT = flag('--verify-snapshot')
const SNAPSHOT_PATH = path.join(__dirname, '..', 'registry', 'scan-snapshot.json')
const API = 'https://gitee.com/api/v5'
const RETIRED_RX = /已归档|归档声明|不再维护|已退役|retired|archived/i

// 人工语义字段：扫描推不出（项目中文名、人工验收命令、玩法说明、状态…）。
// 审计只登记「有哪些」，绝不拿扫描值比对或改写 —— 138 份 manual / 93 份 verify
// 是历次实测沉淀，不是可以重新生成的模板。
const HUMAN_OWNED_FIELDS = [
  'name', 'category', 'version', 'manual', 'verify', 'gameplay',
  'note', 'status', 'order', 'port', 'stop', 'health', 'checkout',
]
// 机器可判定字段：扫描能拿到唯一客观值，不一致即漂移。
const MACHINE_FIELDS = ['id', 'path', 'publish.repo', 'publish.branch']

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

/** 远端 owner 的「仓名 → 默认分支」索引；列表接口一次拿全，避免逐仓限流。 */
async function remoteBranchIndex(owner) {
  const out = new Map()
  for (let page = 1; page <= 5; page++) {
    const url = `${API}/users/${owner}/repos?type=all&sort=full_name&per_page=100&page=${page}`
    const res = await fetch(url, {
      headers: { 'User-Agent': 'allin-repos-audit' },
      signal: AbortSignal.timeout(30000),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const batch = await res.json()
    if (!Array.isArray(batch) || batch.length === 0) break
    for (const r of batch) out.set(String(r.path).toLowerCase(), String(r.default_branch || 'master'))
    if (batch.length < 100) break
  }
  return out
}

/** 只对「登记分支 ≠ 默认分支」的少数条目精确查分支列表，带缓存。 */
const branchCache = new Map()
async function remoteBranches(repo) {
  if (branchCache.has(repo)) return branchCache.get(repo)
  try {
    const res = await fetch(`${API}/repos/${repo}/branches?per_page=100`, {
      headers: { 'User-Agent': 'allin-repos-audit' },
      signal: AbortSignal.timeout(30000),
    })
    if (!res.ok) { branchCache.set(repo, null); return null }
    const batch = await res.json()
    const names = Array.isArray(batch) ? new Set(batch.map((b) => String(b.name))) : null
    branchCache.set(repo, names)
    return names
  } catch {
    branchCache.set(repo, null)
    return null
  }
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

/**
 * 本机全量扫描登记的分层对账（纯函数部分）：只判机器字段，人工字段只登记。
 * 返回每个仓的扫描视角 + 漂移清单 + 保留层清单，供 --audit / --snapshot 使用。
 */
function auditRows(local, entries, remoteAvailable) {
  const rows = []
  const drift = []
  const humanOwned = []
  const byRepo = new Map()
  for (const e of entries) {
    if (!isIssuanceEntry(e)) continue
    const p = String(e.path || '')
    const first = p.replace(/^repos\//, '').split('/')[0].toLowerCase()
    if (!byRepo.has(first)) byRepo.set(first, [])
    byRepo.get(first).push(e)
  }
  for (const name of [...local].sort()) {
    const dir = path.join(REPOS_ROOT, name)
    const es = byRepo.get(name) || []
    const gi = gitInfo(dir)
    const launch = detectLaunch(dir)
    const human = new Set()
    for (const e of es) {
      for (const k of HUMAN_OWNED_FIELDS) if (e[k] !== undefined) human.add(k)
    }
    const machine = {
      id: es.map((e) => String(e.id || '')),
      path: es.map((e) => String(e.path || '')),
      'publish.repo': es.map((e) => String(e.publish?.repo || '')),
      'publish.branch': es.map((e) => String(e.publish?.branch || '')),
    }
    rows.push({
      name,
      entries: es.length,
      machine,
      human_owned: [...human].sort(),
      launch_probe: launch ? { command: launch.command, basis: launch.basis } : null,
      git_remote: gi.repo,
      local_head: gi.branch,
      declared: !es.length ? 'unregistered' : 'registered',
    })
    if (!es.length) continue
    // 机器字段②：publish.repo 必须与 git remote 同源（无 remote 时不判，避免误报）。
    if (gi.repo) {
      for (const e of es) {
        const declared = String(e.publish?.repo || '')
        if (declared && declared.toLowerCase() !== gi.repo.toLowerCase()) {
          drift.push({ name, field: 'publish.repo', declared, observed: gi.repo, reason: '登记仓名与 git remote 不符' })
        }
      }
    }
    // 机器字段③：publish.branch 必须是远端存在的分支（异步补判，见 auditBranches）。
    if (remoteAvailable) {
      for (const e of es) {
        const repo = String(e.publish?.repo || '')
        const declared = String(e.publish?.branch || '')
        // 缺省时 workshop.js 回退 master，按隐式 master 对账。
        const effective = declared || 'master'
        humanOwned.push({ name, id: String(e.id || ''), repo, branch: effective, implicit: !declared })
      }
    }
  }
  // 机器字段①（全局反向检查）：每条发行区条目的 path 首段必须对应一个本机目录。
  // 不能放在上面「按本地仓分组」的循环里 —— 那样 path 写错的条目会被分到
  // 错误名字的组，本机仓反而显示「未登记」，漂移永远抓不到（判据写了不跑）。
  // 墓碑 / checkout:remote-only 由 @allin/core 同源豁免，不算缺陷。
  for (const e of entries) {
    if (!isIssuanceEntry(e)) continue
    if (isTombstone(e) || skipLocalExistence(e)) continue
    const p = String(e.path || '')
    const first = p.replace(/^repos\//, '').split('/')[0].toLowerCase()
    if (!first || local.has(first)) continue
    drift.push({
      name: first, field: 'path', declared: p,
      observed: `本机发行区无 repos/${first}`,
      id: String(e.id || ''), reason: 'path 首段指向不存在的本机目录（非墓碑 / 非 remote-only）',
    })
  }
  return { rows, drift, humanOwned, byRepo }
}

/** 分支存在性补判：先比 default_branch，仅对不等项精确查 branches（带缓存）。 */
async function auditBranches(drift, humanOwned, defaults, remoteAvailable) {
  const verdicts = []
  if (!remoteAvailable) return verdicts
  for (const item of humanOwned) {
    const repoName = String(item.repo).split('/').pop()?.toLowerCase()
    if (!repoName || !defaults.has(repoName)) {
      verdicts.push({ ...item, verdict: 'skipped', reason: '远端无该仓' })
      continue
    }
    const def = defaults.get(repoName)
    if (item.branch === def) {
      verdicts.push({ ...item, verdict: 'default_branch' })
      continue
    }
    const names = await remoteBranches(item.repo)
    if (names === null) {
      verdicts.push({ ...item, verdict: 'unverifiable', reason: '分支列表不可得（不判红也不算通过）' })
      continue
    }
    if (names.has(item.branch)) {
      verdicts.push({ ...item, verdict: 'non_default_publish_branch', reason: '有意发布非默认分支，远端确实存在' })
      continue
    }
    verdicts.push({ ...item, verdict: 'missing', default_branch: def })
    drift.push({
      name: item.name, field: 'publish.branch', declared: item.branch,
      observed: `远端默认 ${def}`, default_branch: def,
      reason: item.implicit ? '未登记 branch，workshop.js 隐式回退 master，远端无该分支' : '登记的发布分支在远端不存在',
      id: item.id, repo: item.repo,
    })
  }
  return verdicts
}

/**
 * 快照指纹：只取**纯本地可判定**的机器字段，保证断网 / 远端限流时复跑可比。
 * 2026-11-13 实测教训：初版把 counts.branch_verdicts / drift（联网派生）算进指纹，
 * 远端 API 一抖 142→0 就假红「登记被改动」—— 把易变字段当不变量，等于给
 * 快照核对装了个随机报警器。联网派生结果仍写进快照作证据，但不进指纹。
 */
function snapshotFingerprint(payload) {
  const stable = {
    owner: payload.owner,
    repo_root: payload.repo_root,
    machine_fields: payload.machine_fields,
    rows: payload.rows.map((r) => ({
      name: r.name, entries: r.entries, machine: r.machine,
      git_remote: r.git_remote, declared: r.declared,
    })),
  }
  return crypto.createHash('sha256').update(JSON.stringify(stable)).digest('hex')
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
  // 全量审计：人工字段只登记不比对；机器字段漂移必须判出；指纹稳定可比。
  const entries = [
    { id: 'alpha', path: 'repos/alpha', manual: true, verify: { command: 'x' },
      publish: { repo: 'owner/alpha', branch: 'master' } },
    { id: 'alpha-extra', path: 'repos/alpha/remix', publish: { repo: 'owner/alpha', branch: 'main' } },
  ]
  const audit = auditRows(new Set(['alpha', 'beta']), entries, false)
  const alpha = audit.rows.find((r) => r.name === 'alpha')
  const beta = audit.rows.find((r) => r.name === 'beta')
  if (alpha?.human_owned.includes('manual') && alpha?.human_owned.includes('verify')) {
    console.log('[OK] 人工字段仅登记、不参与比对')
  } else { bad++; console.log('[BAD] 人工字段被当作机器字段') }
  if (beta?.declared === 'unregistered') console.log('[OK] 未登记仓进入扫描视角')
  else { bad++; console.log('[BAD] 未登记仓未被扫描覆盖') }
  if (audit.drift.length === 0) console.log('[OK] 一致条目不误判漂移')
  else { bad++; console.log('[BAD] 一致条目被误判：' + JSON.stringify(audit.drift)) }
  const broken = auditRows(new Set(['alpha']), [
    { id: 'alpha', path: 'repos/WRONG', publish: { repo: 'owner/other' } },
  ], false)
  if (broken.drift.some((d) => d.field === 'path')) console.log('[OK] path 首段漂移能判红')
  else { bad++; console.log('[BAD] path 首段漂移漏判') }
  const fp1 = snapshotFingerprint({ owner: 'x', repo_root: 'r', machine_fields: MACHINE_FIELDS,
    drift: [], counts: { local: 1 }, rows: [{ name: 'a', entries: 1, machine: {}, git_remote: '', declared: 'registered' }] })
  const fp2 = snapshotFingerprint({ owner: 'x', repo_root: 'r', machine_fields: MACHINE_FIELDS,
    drift: [], counts: { local: 1 }, rows: [{ name: 'a', entries: 1, machine: {}, git_remote: '', declared: 'registered' }] })
  if (fp1 === fp2) console.log('[OK] 快照指纹可复现')
  else { bad++; console.log('[BAD] 快照指纹不稳定') }
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

// ── --audit：本机全量扫描登记（跑满发行区，不只扫差集）────────────────────
let audit = null
if (AUDIT || SNAPSHOT || VERIFY_SNAPSHOT) {
  const { entries } = loadRegistry(REGISTRY)
  let defaults = new Map()
  if (remoteAvailable) {
    try { defaults = await remoteBranchIndex(OWNER) } catch { /* 索引不可得 ⇒ 分支判 unverifiable */ }
  }
  const scanned = auditRows(local, entries, remoteAvailable)
  const verdicts = await auditBranches(scanned.drift, scanned.humanOwned, defaults, remoteAvailable)
  const humanFieldCounts = {}
  for (const r of scanned.rows) {
    for (const k of r.human_owned) humanFieldCounts[k] = (humanFieldCounts[k] || 0) + 1
  }
  audit = {
    mode: 'full-scan',
    machine_fields: MACHINE_FIELDS,
    human_owned_fields: HUMAN_OWNED_FIELDS,
    policy: {
      machine: '机器字段与扫描值不一致 ⇒ 记 drift（--strict 可判红）',
      human: '人工语义字段只登记清单，绝不比对 / 覆盖 / 重新生成',
      branch: 'publish.branch 判据 = 远端是否存在该分支；非默认但存在 ⇒ 有意发布分支，不算漂移',
      implicit: '未登记 branch 时 workshop.js 隐式回退 master，按隐式值对账',
    },
    counts: {
      scanned_local_repos: scanned.rows.length,
      registered: scanned.rows.filter((r) => r.declared === 'registered').length,
      unregistered: scanned.rows.filter((r) => r.declared === 'unregistered').length,
      entries_audited: entries.filter(isIssuanceEntry).length,
      human_owned_entries: scanned.rows.filter((r) => r.human_owned.length).length,
      launch_probe_undetectable: scanned.rows.filter((r) => r.declared === 'registered' && !r.launch_probe).length,
      branch_verdicts: verdicts.length,
      branch_check_applicable: remoteAvailable,
      branch_check_skipped_reason: remoteAvailable ? null : '远端清单不可得 ⇒ 分支判据未运行（SKIP ≠ 通过，不算全绿）',
      drift: scanned.drift.length,
    },
    human_field_counts: humanFieldCounts,
    branch_verdicts: verdicts.filter((v) => v.verdict !== 'default_branch'),
    drift: scanned.drift.sort((a, b) => (a.name + a.field).localeCompare(b.name + b.field)),
    rows: scanned.rows,
  }
  report.audit = audit
}

if (SNAPSHOT && audit) {
  const payload = {
    generated_at: new Date().toISOString(),
    owner: OWNER,
    repo_root: path.relative(path.resolve(__dirname, '..', '..'), REPOS_ROOT).replace(/\\/g, '/'),
    machine: os.hostname(),
    remote: report.remote,
    machine_fields: MACHINE_FIELDS,
    human_owned_fields: HUMAN_OWNED_FIELDS,
    counts: audit.counts,
    coverage: {
      local_machine_fields: `${audit.counts.scanned_local_repos}/${audit.counts.scanned_local_repos} 仓（纯本地，不依赖网络）`,
      human_owned_inventory: `${audit.counts.human_owned_entries} 仓的人工字段清单已登记`,
      branch_verdicts: audit.counts.branch_check_applicable
        ? `${audit.counts.branch_verdicts} 条分支判据已运行`
        : `未运行：${audit.counts.branch_check_skipped_reason}`,
      note: '远端不可用时本快照仍可用于本机机器字段核对；分支判据缺失不算通过，待远端恢复后重跑 --snapshot 补齐。',
    },
    human_field_counts: audit.human_field_counts,
    branch_verdicts: audit.branch_verdicts,
    drift: audit.drift,
    rows: audit.rows,
    policy: audit.policy,
  }
  payload.fingerprint = snapshotFingerprint(payload)
  fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(payload, null, 2) + '\n', 'utf8')
  audit.snapshot = { path: path.relative(path.resolve(__dirname, '..', '..'), SNAPSHOT_PATH).replace(/\\/g, '/'), fingerprint: payload.fingerprint }
}

if (VERIFY_SNAPSHOT) {
  if (!fs.existsSync(SNAPSHOT_PATH)) {
    report.snapshot_verify = { ok: false, reason: '快照不存在，先跑 --audit --snapshot' }
  } else {
    const saved = JSON.parse(fs.readFileSync(SNAPSHOT_PATH, 'utf8'))
    const fresh = snapshotFingerprint(saved)
    const current = audit ? snapshotFingerprint({
      owner: OWNER,
      repo_root: saved.repo_root,
      machine_fields: MACHINE_FIELDS,
      rows: audit.rows,
    }) : null
    report.snapshot_verify = {
      ok: fresh === saved.fingerprint && (current === null || current === saved.fingerprint),
      saved_fingerprint: saved.fingerprint,
      recomputed_from_saved: fresh,
      recomputed_from_current_scan: current,
      reason: fresh !== saved.fingerprint ? '快照文件被改动（指纹不符）'
        : current !== null && current !== saved.fingerprint ? '本机实况与快照不一致（登记被改动，需重扫）' : '一致',
    }
  }
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
  if (audit) {
    console.log(`-- 全量扫描登记（跑满本机 ${audit.counts.scanned_local_repos} 仓）--`)
    console.log(`   已登记 ${audit.counts.registered} / 未登记 ${audit.counts.unregistered} / ` +
      `审计条目 ${audit.counts.entries_audited} / 含人工字段 ${audit.counts.human_owned_entries}`)
    console.log(`   人工字段分布: ` + Object.entries(audit.human_field_counts)
      .sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k}=${v}`).join(', '))
    console.log(`   入口探测不到（保留人工 launch.command）: ${audit.counts.launch_probe_undetectable}`)
    console.log(`   机器字段漂移: ${audit.counts.drift}`)
    for (const d of audit.drift) {
      console.log(`     [DRIFT] ${d.name}/${d.field}: 登记=${d.declared} 实况=${d.observed} — ${d.reason}`)
    }
    for (const v of audit.branch_verdicts) {
      console.log(`     [分支] ${v.id || v.name} ${v.branch} ⇒ ${v.verdict}${v.reason ? '（' + v.reason + '）' : ''}`)
    }
    if (audit.snapshot) console.log(`   快照: ${audit.snapshot.path}  fingerprint=${audit.snapshot.fingerprint.slice(0, 16)}…`)
  }
  if (report.snapshot_verify) {
    console.log(`-- 快照复验: ${report.snapshot_verify.ok ? 'OK' : 'FAIL'} — ${report.snapshot_verify.reason}`)
  }
}

if (flag('--draft')) {
  if (!generated.length) console.log('# 无可生成条目')
  for (const g of generated) console.log(`# --- ${g.name}.yaml ---\n${g.yaml}`)
}

// 默认只报告不判红；--strict 供人工 / CI 显式选用（不接进 run_all_gates.sh）。
// --audit --strict 把机器字段漂移计入；--verify-snapshot 不一致必须判红（快照核对是判据）。
const diffs = localOnly.length + missingRemote.length + remoteUndeclared.length +
  (audit ? audit.drift.length : 0)
const snapshotBroken = report.snapshot_verify && !report.snapshot_verify.ok
process.exit((flag('--strict') && diffs > 0) || snapshotBroken ? 1 : 0)
