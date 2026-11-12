// publish_repos.mjs —— 发行仓远端写入编排器（执行层；默认 dry-run，逐项确认）
//
// 为什么单独一个脚本：discover_repos.mjs 是采集层，定位「默认只读、不写盘、不判红」。
// 远端建仓 / 首推 / 转公开属高风险动作（SPEC-001 铁律 3、SPEC-002「不分档，逐项确认」），
// 不能塞进采集层，也不能进 run_all_gates.sh 阻断链。本脚本只做编排 + 闸门 + 复验。
//
// 前置条件（2026-11-13 实测齐备）：
//   · discover_repos.mjs --json         → 三面对账，识别「已登记 / 远端不存在」候选
//   · tools/gitee_release.py            → create（幂等 SKIP）/ public / status，已沉淀
//                                        Gitee 两步建仓、PATCH 必带 name、JSON 正体等坑
//   · git credential fill               → 令牌同源（与 kernel/services/tools_service.py 一致），
//                                        不硬编码、不落盘、不回显
//   · origin 双 pushurl / check_repos.mjs → 推送通道与远端锚点验收
//
// 用法（在 platform/ 下运行，或任意 cwd）：
//   node scripts/publish_repos.mjs                     # 只生成远端写入计划（联网对账，dry-run）
//   node scripts/publish_repos.mjs --offline          # 离线看计划（禁止 --apply）
//   node scripts/publish_repos.mjs --json             # 机器可读计划
//   node scripts/publish_repos.mjs --apply --only <仓名> --confirm
//                                                    # 逐项确认后执行单个仓的远端写入
//   node scripts/publish_repos.mjs --rehearse --only <仓名> --confirm
//                                                    # 演练：闸门全齐但只核对前置件 + 打印命令链，零写操作
//   node scripts/publish_repos.mjs --selfcheck        # 离线守卫 / 计划自检（能红能绿，零远端副作用）
//
// 铁律 3 的机器化落地（四道闸门，缺一不可）：
//   ① --apply 必须配 --only <单个仓名> —— 拒绝批量、拒绝「把候选全建了」
//   ② 必须显式 --confirm —— 逐项确认，不靠「没说不行」推断放行
//   ③ 远端清单必须在线且可用（remote=ok）—— 离线/限流时盲写会建重复仓
//   ④ 必须能取到令牌；本地 origin 指向别处时拒绝覆盖（不破坏用户既有远端）
//
// 纪律：默认不写任何远端资产、不判红、不进门禁；执行序列每一步都留可复核输出，
// 最后用匿名视角复验（git ls-remote + GET /repos 看 private），不只看建仓响应。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import { loadRegistry, REPOS_ROOT, isTombstone } from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..', '..')
const PLATFORM = path.resolve(__dirname, '..')
const TOOL = path.join(ROOT, 'tools', 'gitee_release.py')
const DISCOVER = path.join(__dirname, 'discover_repos.mjs')

const args = process.argv.slice(2)
const flag = (n) => args.includes(n)
function option(n) {
  const i = args.indexOf(n)
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null
}

const OWNER = process.env.PLATFORM_GITEE_OWNER || 'siwpan'
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(PLATFORM, 'registry', 'projects')
const PYTHON = process.env.ALLIN_PYTHON || 'python'
const NAME_RX = /^[a-z0-9][a-z0-9._-]*$/i
const OWNER_RX = /^[a-z0-9][a-z0-9._-]*$/i

// ── 采集：完全复用 discover_repos 的对账结论，不重复实现差集 ────────────────
function collectReport(offline) {
  const r = spawnSync(process.execPath, [DISCOVER, '--json', ...(offline ? ['--offline'] : [])], {
    cwd: PLATFORM, encoding: 'utf8', timeout: 180000, env: process.env,
  })
  if (r.status !== 0) {
    throw new Error(`discover_repos 失败（exit ${r.status}）：${String(r.stderr || r.stdout).slice(0, 300)}`)
  }
  const out = String(r.stdout || '')
  const start = out.indexOf('{')
  const end = out.lastIndexOf('}')
  if (start < 0 || end < start) throw new Error('discover_repos 未返回 JSON 报告')
  return JSON.parse(out.slice(start, end + 1))
}

function registryEntries() {
  try {
    return loadRegistry(REGISTRY).entries
  } catch {
    return []
  }
}

/** 仓名 → 条目：只认 path 落在发行区的活条目（墓碑 / 仓内条目一律不建远端）。 */
function indexEntries(entries) {
  const map = new Map()
  for (const e of entries) {
    const p = String(e.path || '')
    if (!p.startsWith('repos/')) continue
    if (isTombstone(e)) continue
    const name = String(e.publish?.repo || '').split('/').pop() || p.slice(6).split('/')[0] || e.id
    if (name) map.set(name.toLowerCase(), e)
  }
  return map
}

/**
 * 纯函数：由对账报告生成远端写入计划。
 * 只处理「已登记 + 远端不存在 + 非墓碑」；未登记先要 --apply 扫描登记，不先建远端
 * （否则远端仓没有 registry 锚点，check_repos 仍会判错位）。
 */
export function buildPlan(report, ctx, entries = registryEntries()) {
  const byName = indexEntries(entries)
  const candidates = []
  const skipped = []
  for (const raw of report.declared_missing_remote || []) {
    const name = String(raw).toLowerCase()
    if (!NAME_RX.test(name)) { skipped.push({ name, reason: '仓名非法' }); continue }
    const e = byName.get(name)
    if (!e) { skipped.push({ name, reason: 'registry 无对应活条目（墓碑 / 仓内条目 / 未登记）' }); continue }
    const rel = String(e.path || '').slice(6)
    if (!rel || rel.includes('..') || /^[a-z]:/i.test(rel)) {
      skipped.push({ name, reason: `path 不合法：${e.path}` }); continue
    }
    const localPath = path.join(ctx.reposRoot, rel)
    if (!fs.existsSync(path.join(localPath, '.git'))) {
      skipped.push({ name, reason: '本地无 .git，无法首推（remote-only 条目应走检出流程）' }); continue
    }
    candidates.push({
      name,
      owner: ctx.owner,
      target: `${ctx.owner}/${name}`,
      localPath,
      repo: String(e.publish?.repo || `${ctx.owner}/${name}`),
      branch: String(e.publish?.branch || 'master'),
      steps: ['create', 'origin', 'push', 'public', 'verify'],
      risk: 'high',
    })
  }
  const needsRegistrationFirst = [
    ...(report.local_only || []),
    ...((report.registration?.generated) || []),
  ].filter((v, i, a) => a.indexOf(v) === i).sort()
  return { candidates, skipped, needsRegistrationFirst }
}

// ── 闸门：铁律 3 的四道确认，全部纯函数，便于自检 ──────────────────────────
export function guardErrors(opts, report, plan) {
  const errs = []
  if (!opts.only) errs.push('--apply 必须配 --only <单个仓名>（逐项确认，禁止批量建仓）')
  else if (opts.only.includes(',') || opts.only.includes(' ')) errs.push('--only 只接受单个仓名')
  else if (!NAME_RX.test(opts.only)) errs.push(`--only 仓名非法：${opts.only}`)
  if (!opts.confirm) errs.push('--apply 必须配 --confirm（铁律 3：逐项确认后才做）')
  if (report.remote !== 'ok') errs.push(`远端清单不可用（remote=${report.remote}）：离线 / 限流时禁止写远端`)
  if (!OWNER_RX.test(opts.owner || '')) errs.push(`owner 非法：${opts.owner}`)
  if (!opts.token) errs.push('取不到 Gitee 令牌（GITEE_TOKEN 或 git credential fill）')
  if (opts.only && !plan.candidates.some((p) => p.name === opts.only.toLowerCase())) {
    errs.push(`--only ${opts.only} 不在远端写入候选集（零候选 / 已跳过 / 记错名字）`)
  }
  return errs
}

function getToken() {
  const env = (process.env.GITEE_TOKEN || '').trim()
  if (env) return env
  const r = spawnSync('git', ['credential', 'fill'], {
    input: 'protocol=https\nhost=gitee.com\n', encoding: 'utf8', timeout: 30000,
  })
  if (r.status !== 0) return null
  const line = String(r.stdout || '').split('\n').find((x) => x.startsWith('password='))
  return line ? line.slice('password='.length).trim() : null
}

// ── 执行：复用 gitee_release.py，不重写 Gitee API 调用 ─────────────────────
function run(cmd, cwd, env, timeout = 180000) {
  const r = spawnSync(cmd[0], cmd.slice(1), { cwd, encoding: 'utf8', env, timeout })
  if (r.status !== 0) {
    throw new Error(`${cmd.join(' ')} → exit ${r.status}：${String(r.stderr || r.stdout).slice(0, 400)}`)
  }
  return String(r.stdout || '').trim()
}

function gitee(sub, p, ctx, token) {
  // 全局参数必须写在子命令之前（gitee_release.py 的 argparse 约定）。
  return run([ctx.python, ctx.tool, '--owner', ctx.owner, '--name', p.name,
    '--repo', p.localPath, sub], ctx.root, { ...process.env, GITEE_TOKEN: token })
}

/** 本地 origin：无则 add，已指向目标则跳过，指向别处则拒绝覆盖（不破坏既有远端）。 */
export function ensureOrigin(p) {
  const cur = spawnSync('git', ['-C', p.localPath, 'remote', 'get-url', 'origin'], { encoding: 'utf8' })
  const url = cur.status === 0 ? String(cur.stdout).trim() : ''
  const want = `https://gitee.com/${p.owner}/${p.name}.git`
  if (!url) {
    run(['git', '-C', p.localPath, 'remote', 'add', 'origin', want], p.localPath, process.env)
    return `origin 已添加：${want}`
  }
  if (url.replace(/\.git$/, '').toLowerCase() === want.replace(/\.git$/, '').toLowerCase()) {
    return `origin 已指向目标，跳过：${url}`
  }
  throw new Error(`本地 origin 指向别处，拒绝覆盖：${url}（目标 ${want}）；请人工确认后再试`)
}

async function verifyAnonymous(p) {
  const ls = spawnSync('git', ['ls-remote', `https://gitee.com/${p.owner}/${p.name}.git`, 'HEAD'], {
    encoding: 'utf8', timeout: 60000,
  })
  if (ls.status !== 0) throw new Error(`匿名 git ls-remote 失败：${String(ls.stderr).slice(0, 200)}`)
  const res = await fetch(`https://gitee.com/api/v5/repos/${p.owner}/${p.name}`, {
    headers: { 'User-Agent': 'allin-repos-publish' }, signal: AbortSignal.timeout(30000),
  })
  if (!res.ok) throw new Error(`匿名 GET /repos 返回 HTTP ${res.status}`)
  const d = await res.json()
  if (d.private) throw new Error('远端仓仍为 private（转公开未生效）')
  return `匿名复验通过：ls-remote exit 0 / private=false / full_name=${d.full_name}`
}

/** 演练：证明「前置条件齐备」而不产生任何远端副作用；令牌只报可用，绝不回显。 */
export function rehearsal(p, ctx, opts) {
  const cur = spawnSync('git', ['-C', p.localPath, 'remote', 'get-url', 'origin'], { encoding: 'utf8' })
  const origin = cur.status === 0 ? String(cur.stdout).trim() : ''
  const want = `https://gitee.com/${p.owner}/${p.name}.git`
  const norm = (u) => u.replace(/\.git$/, '').toLowerCase()
  return {
    executed: false,
    checks: {
      gitee_release_tool: fs.existsSync(ctx.tool),
      python_interpreter: ctx.python,
      local_git_worktree: fs.existsSync(path.join(p.localPath, '.git')),
      token_available: !!opts.token,
      token_value_omitted: true,
      registry_anchor: p.repo,
    },
    origin_current: origin || '(无 origin)',
    origin_action: !origin ? 'add' : (norm(origin) === norm(want) ? 'skip' : 'REFUSE（指向别处，拒绝覆盖）'),
    command_chain: [
      `${ctx.python} tools/gitee_release.py --owner ${ctx.owner} --name ${p.name} --repo <local> create`,
      `git -C <local> remote add origin ${want}（或 skip / 拒绝覆盖）`,
      `git -C <local> push -u origin ${p.branch}（unrelated 时按铁律 4 merge，不强推）`,
      `${ctx.python} tools/gitee_release.py --owner ${ctx.owner} --name ${p.name} --repo <local> public`,
      `匿名复验：git ls-remote + GET /repos/${ctx.owner}/${p.name} 看 private=false`,
    ],
  }
}

async function execPlan(p, ctx, token) {
  const log = []
  log.push(`[create] ${gitee('create', p, ctx, token).split('\n')[0]}`)
  log.push(`[origin] ${ensureOrigin(p)}`)
  // auto_init=false ⇒ 远端为空仓，正常首推；若遇 unrelated histories，按铁律 4
  // 用 merge --allow-unrelated-histories，绝不强推（强推会抹掉远端首个提交）。
  const push = spawnSync('git', ['-C', p.localPath, 'push', '-u', 'origin', p.branch], {
    encoding: 'utf8', timeout: 300000,
  })
  if (push.status !== 0) {
    const msg = String(push.stderr || push.stdout)
    if (/unrelated|non-fast-forward|rejected/i.test(msg)) {
      log.push('[push] 检测到远端非空/历史不相关：按铁律 4 走 merge，不强推')
      run(['git', '-C', p.localPath, 'pull', '--allow-unrelated-histories', 'origin', p.branch, '--no-edit'],
        p.localPath, process.env, 300000)
      run(['git', '-C', p.localPath, 'push', '-u', 'origin', p.branch], p.localPath, process.env, 300000)
    } else {
      throw new Error(`首推失败：${msg.slice(0, 400)}`)
    }
  } else {
    log.push(`[push] 首推 ${p.branch} 成功`)
  }
  log.push(`[public] ${gitee('public', p, ctx, token).split('\n')[0]}`)
  log.push(`[verify] ${await verifyAnonymous(p)}`)
  return log
}

// ── 自检：离线、零远端副作用、能红也能绿 ───────────────────────────────────
function selfcheck() {
  let bad = 0
  const ok = (c, msg) => { if (c) console.log(`[OK] ${msg}`); else { bad++; console.log(`[BAD] ${msg}`) } }
  const ctx = { owner: 'fakeowner', reposRoot: '/tmp/fake-repos' }
  const report = {
    remote: 'ok',
    declared_missing_remote: ['alpha', 'beta', 'tomb'],
    local_only: ['gamma'],
    registration: { generated: ['gamma'] },
  }
  const entries = [
    { id: 'alpha', path: 'repos/alpha', publish: { repo: 'fakeowner/alpha', branch: 'master' } },
    { id: 'beta', path: 'repos/beta', publish: { repo: 'fakeowner/beta', branch: 'main' } },
    { id: 'tomb', path: 'repos/tomb', status: 'archived', publish: { repo: 'fakeowner/tomb' } },
    { id: 'portal', path: 'platform', publish: { repo: 'fakeowner/allin' } },
  ]
  // 计划生成（不依赖真实文件系统：候选须含 .git，这里用一个临时假仓）
  const tmp = fs.mkdtempSync(path.join(process.env.TEMP || '.', 'publish-selfcheck-'))
  try {
    fs.mkdirSync(path.join(tmp, 'alpha'), { recursive: true })
    fs.mkdirSync(path.join(tmp, 'alpha', '.git'), { recursive: true })
    fs.mkdirSync(path.join(tmp, 'beta'), { recursive: true })
    fs.mkdirSync(path.join(tmp, 'beta', '.git'), { recursive: true })
    const plan = buildPlan(report, { ...ctx, reposRoot: tmp }, entries)
    ok(plan.candidates.length === 2, '两仓候选生成')
    ok(plan.candidates[0].steps.join(',') === 'create,origin,push,public,verify', '执行序列完整')
    ok(plan.candidates[1].branch === 'main', 'branch 取条目真值')
    ok(plan.needsRegistrationFirst.join(',') === 'gamma', '未登记仓先扫描登记，不先建远端')
    ok(plan.skipped.some((s) => s.name === 'tomb'), '墓碑跳过')

    const base = { only: 'alpha', confirm: true, owner: 'fakeowner', token: 'x' }
    ok(guardErrors(base, report, plan).length === 0, '四道闸门齐全 ⇒ 放行')
    ok(guardErrors({ ...base, only: null }, report, plan).some((e) => e.includes('--only')), '缺 --only 判红')
    ok(guardErrors({ ...base, only: 'alpha,beta' }, report, plan).some((e) => e.includes('单个仓名')), '批量建仓判红')
    ok(guardErrors({ ...base, confirm: false }, report, plan).some((e) => e.includes('--confirm')), '缺 --confirm 判红')
    ok(guardErrors(base, { ...report, remote: 'offline' }, plan).some((e) => e.includes('离线')), '离线禁写判红')
    ok(guardErrors({ ...base, token: '' }, report, plan).some((e) => e.includes('令牌')), '缺令牌判红')
    ok(guardErrors({ ...base, owner: 'bad/owner' }, report, plan).some((e) => e.includes('owner')), '非法 owner 判红')
    ok(guardErrors({ ...base, only: 'ghost' }, report, plan).some((e) => e.includes('候选集')), '非候选仓判红')
    // 零候选时计划为空、闸门自然拦住任何 --apply
    const empty = buildPlan({ ...report, declared_missing_remote: [] }, { ...ctx, reposRoot: tmp }, entries)
    ok(empty.candidates.length === 0, '零候选 ⇒ 空计划')
    ok(guardErrors(base, report, empty).some((e) => e.includes('候选集')), '零候选时 --apply 被拦')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
  console.log(bad ? `PUBLISH_SELFCHECK FAIL (${bad})` : 'PUBLISH_SELFCHECK OK')
  return bad ? 1 : 0
}

async function main() {
if (flag('--selfcheck')) return selfcheck()

const ctx = {
  owner: OWNER,
  reposRoot: REPOS_ROOT,
  root: ROOT,
  tool: TOOL,
  python: PYTHON,
}

let report
try {
  report = collectReport(flag('--offline'))
} catch (e) {
  console.error(`[publish:repos] 采集失败：${e.message}`)
  process.exit(1)
}

const plan = buildPlan(report, ctx)
const APPLY = flag('--apply')
const REHEARSE = flag('--rehearse')
const ACTIVE = APPLY || REHEARSE
const opts = {
  only: option('--only'),
  confirm: flag('--confirm'),
  owner: OWNER,
  token: ACTIVE ? getToken() : null,
}
const errs = ACTIVE ? guardErrors(opts, report, plan) : []

const out = {
  owner: OWNER,
  registry: REGISTRY,
  reposRoot: REPOS_ROOT,
  remote: report.remote,
  mode: REHEARSE ? 'rehearse' : (APPLY ? 'apply' : 'dry-run'),
  gate: ACTIVE ? (errs.length ? 'blocked' : 'allowed') : 'dry-run',
  gate_errors: errs,
  plan,
}

let execLog = null
if (ACTIVE && errs.length === 0) {
  const p = plan.candidates.find((x) => x.name === opts.only.toLowerCase())
  if (REHEARSE) {
    out.rehearsal = rehearsal(p, ctx, opts)
  } else {
    try {
      execLog = await execPlan(p, ctx, opts.token)
      out.executed = { name: p.name, target: p.target, log: execLog }
    } catch (e) {
      out.executed = { name: p.name, target: p.target, error: e.message, partial: execLog }
      out.gate = 'failed'
    }
  }
}

if (flag('--json')) {
  console.log(JSON.stringify(out, null, 2))
} else {
  console.log('== 发行仓远端写入编排（默认 dry-run，高风险动作逐项确认） ==')
  console.log(`owner=${OWNER}  remote=${report.remote}  mode=${out.mode}  gate=${out.gate}`)
  console.log(`候选 ${plan.candidates.length} 个 / 跳过 ${plan.skipped.length} 个 / ` +
    `需先扫描登记 ${plan.needsRegistrationFirst.length} 个`)
  for (const p of plan.candidates) {
    console.log(`  - ${p.name} → ${p.target} (${p.branch})  steps=${p.steps.join('→')}  risk=${p.risk}`)
  }
  for (const s of plan.skipped) console.log(`  [跳过] ${s.name}: ${s.reason}`)
  if (plan.needsRegistrationFirst.length) {
    console.log(`  [先登记] ${plan.needsRegistrationFirst.join(', ')}：先跑 discover_repos.mjs --apply，` +
      `再生成远端写入计划（不建无锚点的远端仓）`)
  }
  for (const e of errs) console.log(`  [闸门] ${e}`)
  if (out.rehearsal) {
    console.log('  -- 演练（零写操作）--')
    for (const [k, v] of Object.entries(out.rehearsal.checks)) console.log(`     ${k}: ${v}`)
    console.log(`     origin 现状: ${out.rehearsal.origin_current} ⇒ ${out.rehearsal.origin_action}`)
    for (const c of out.rehearsal.command_chain) console.log(`     > ${c}`)
    console.log(`     executed=${out.rehearsal.executed}`)
  }
  if (execLog) for (const l of execLog) console.log(`  ${l}`)
  if (out.executed?.error) console.log(`  [执行失败] ${out.executed.error}`)
  if (!ACTIVE) console.log('提示：要执行需 --apply --only <仓名> --confirm；演练用 --rehearse；当前组合通常零候选。')
}

// 默认不判红；显式 --apply / --rehearse 时闸门拦截或执行失败必须非 0（能红能绿）。
// 不接门禁阻断链：脚本本身不在 run_all_gates.sh 内，退出码只服务于显式调用方。
return ACTIVE && (errs.length || out.gate === 'failed') ? 1 : 0
}

// 被 import 时只提供 buildPlan / guardErrors 纯函数，不采集、不执行、不写远端。
const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href
if (isMain) process.exit(await main())
