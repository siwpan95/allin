// @allin/core — 项目注册表：platform.yaml 加载 / 校验 / 端口查表（fail-loud）。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PLATFORM_DIR = path.join(HERE, '..', '..', '..')          // platform/（本 submodule 根）
const ALLIN_ROOT = path.join(HERE, '..', '..', '..', '..')      // 治理仓根 allin/（2026-10-26 并入后 platform 不再是仓根）

// 端口唯一事实源（机器可读版）：与 端口分配表.md 同步维护。
// 解析顺序（2026-09-24 强化：仓库可移植）：env PLATFORM_PORTS（外部端口分配表）优先；
// 缺失时回退仓内默认 registry/ports.yaml（重建自 registry/projects/*.yaml 的 port 字段，
// 新增端口仍须先查外部端口分配表再登记，仓内默认只保证查表自洽）。
export const PORTS_YAML = process.env.PLATFORM_PORTS || path.join(PLATFORM_DIR, 'registry', 'ports.yaml')

// path 存在性校验模式（fail-loud 的环境边界，2026-09-24 强化）：
//  - 'exists'（默认）：path 必须存在于本机——author 机器与生产环境保持原纪律；
//  - 'absolute'：仅校验绝对路径——CI / 异机跑测试用（登记的 path 指向本机外部的
//    项目目录，天然不存在；跳过存在性但保留形状校验，不让测试绑定具体机器）。
// ⚠️ **惰性读取**（2026-11-01 修复，勿改回 module 级 const）：
// 原先写作 `export const PATH_CHECK = ...`，模块一旦被 import 时就把模式锁死，
// 连测试都切不动 ⇒ `PLATFORM_PATH_CHECK=absolute npm test` 下「path 不存在应报错」
// 类断言集体失去前提而红。该缺陷 2026-09-24 专题记录里已写明，README 却仍推荐这条异机命令。
export function pathCheckMode() {
  const explicit = process.env.PLATFORM_PATH_CHECK
  if (explicit === 'absolute' || explicit === 'exists') return explicit
  // 2026-11-10 换机可移植整改：此前固定 'exists' ⇒ 换机（无同级 repos/ 发布区）
  // 时 145 条清单全部报「path 不存在」，把形状校验淹掉。现在按「发布区是否真的存在」
  // 自动选：有发布区才要求路径存在，否则退到形状校验（absolute）。
  //
  // M-7（2026-11-10）：自动检测结果只依赖 REPOS_ROOT 目录 + env，与 entry 无关，
  // 却被 validateEntry 逐条调用（145 条 × 137 仓 ≈ 2 万次 statSync）。按
  // 「env + 发布区目录签名」memoize：签名变化（发布区增删仓库）自动失效，
  // invalidateRegistryCache() 可显式清空。显式 env 分支仍即时返回，不入缓存。
  const key = `${String(explicit || '')}|${reposRootSignature()}`
  if (pathCheckCache && pathCheckCache.key === key) return pathCheckCache.mode
  const mode = detectPathCheckMode()
  pathCheckCache = { key, mode }
  return mode
}

// ── path 去符盘（2026-10-26 三仓整合 + repos 约定）───────────────────────────
// 清单里的 path 一律**禁止盘符**（铁律 5 / SPEC-006 机器与路径约定）：写相对于「发布区根」的
// POSIX 相对路径，形如 `repos/lab`。理由：盘符路径会随机器漂移，换机后全部失效。
// 发布区根 = env `PLATFORM_REPOS_ROOT`，缺省取 **治理仓的同级 `repos/` 目录**
// （约定：`allin/` 与 `repos/` 并立，见仓根 README「三仓整合」待办）。
// 工作区根 = 治理仓的上一级（allin/ 与 repos/ 在此并立）；发布区根 = 其下的 repos/。
const WORKSPACE_ROOT = path.join(ALLIN_ROOT, '..')
export const REPOS_ROOT = process.env.PLATFORM_REPOS_ROOT || path.join(WORKSPACE_ROOT, 'repos')

// C-03（2026-11-08 深度审核 P1 · 2026-11-10 收尾）：registry 解析唯一入口。
// loadRegistry / validateEntry / loadPorts / resolvePath / commandProblems 全部集中于此；
// 其他模块（portal / website / kernel）只读 portal.port / running.json 等产物，不自行解析 registry。
const RX_DRIVE = /^[A-Za-z]:[\\/]/

// ── 命令形状校验（2026-11-08 深度审核 P1 · 2026-11-10 深度审计 P0-1 补强）──
// launch/stop/verify 的 command 会被 launch.js 交给 shell 执行。
// 此前 validateEntry 只判字段存在 —— 能写一份 yaml 就等同拿到任意命令执行入口。
// 这里把命令钉成「单个程序调用 + 参数」的形状：禁止 shell 控制符、路径穿越、
// 首词不在受控集合。白名单已对本仓 145 份清单做过零误伤核验。
//
// ⚠️ 2026-11-10 深度审计 S-1：只禁 shell 元字符**不够**。首词白名单里含
// bash / sh / python / node / cmd / powershell 等解释器，而 `-c` / `-e` / `/c`
// 这类「内联代码」参数不是元字符 —— 实测 `bash -c id`、`python -c ...` 曾全部
// 被 commandProblems 放行，随后经 spawn({shell:true}) 真正执行任意代码。
// ⇒ 增加「解释器 + 内联执行 flag」判定。放行合法 flag（如 `python -m app.main`、
// `node --version`、`bash scripts/run.sh`），避免把正常启动命令误伤。
const COMMAND_FORBIDDEN = /[;&|<>`$]|\r|\n/
const COMMAND_TRAVERSAL = /(^|[\\/])\.\.([\\/]|$)/
const COMMAND_HEAD = /^(?:python|python3|pythonw|py|node|npm|npx|dse|ls|dir|echo|git|cmd|powershell|pwsh|bash|sh|robocopy|make|explorer|start)(?:\.exe)?(?:\s|$)/i
const COMMAND_FILE_HEAD = /^[A-Za-z0-9_.-]+\.(?:bat|cmd|html|exe)(?:\s|$)/i
const COMMAND_REL_EXE = /^(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+\.exe(?:\s|$)/i

// 能「把一段字符串当代码执行」的宿主程序。命中这些首词时，参数面必须更严。
const INLINE_EXEC_HOST = /^(?:python|python3|pythonw|py|node|bash|sh|cmd|powershell|pwsh)(?:\.exe)?$/i
// 内联执行 flag：单独出现（-c / -e /c）、带等号（--eval=...）、或粘连值（-ccode）。
// Python 支持 `-cCODE`（无空格）形态，故粘连形式也必须拦。
const INLINE_EXEC_FLAG = /^(?:-c|-e|-p|\/c|\/k|--eval|--print|--command|-command|-encodedcommand|-enc|--exec|--execute)$/i
const INLINE_EXEC_ATTACHED = /^(?:-(?:c|e|p)\S|\/c\S|\/k\S|--(?:eval|print|command|exec|execute)=|-encodedcommand=)/i

/** 把命令串按 shell 词法拆成 token（支持单/双引号）。
 *  校验与执行**共用同一个分词器**，避免两处实现各自漂移。 */
export function splitCommandTokens(s) {
  const out = []
  let cur = ''
  let quote = null
  for (const ch of s) {
    if (quote) {
      if (ch === quote) quote = null
      else cur += ch
    } else if (ch === '"' || ch === "'") {
      quote = ch
    } else if (/\s/.test(ch)) {
      if (cur) { out.push(cur); cur = '' }
    } else {
      cur += ch
    }
  }
  if (cur) out.push(cur)
  return out
}

export function commandProblems(cmd) {
  if (typeof cmd !== 'string' || !cmd.trim()) return ['命令为空']
  const s = cmd.trim()
  if (COMMAND_FORBIDDEN.test(s)) return ['含 shell 控制符（; & | < > ` $ 或换行）']
  if (COMMAND_TRAVERSAL.test(s)) return ['路径含 ..（禁止越出项目目录）']
  const tokens = splitCommandTokens(s)
  const head = tokens[0] || ''
  if (INLINE_EXEC_HOST.test(head)) {
    const bad = tokens.slice(1).find((t) => INLINE_EXEC_FLAG.test(t) || INLINE_EXEC_ATTACHED.test(t))
    if (bad) return [`解释器内联代码参数被禁止（${head} ${bad}）：能写 yaml 不等于能执行任意代码`]
  }
  if (!(COMMAND_HEAD.test(s) || COMMAND_FILE_HEAD.test(s) || COMMAND_REL_EXE.test(s))) {
    return [`首词不在受控命令集合：${s.split(/\s/)[0]}`]
  }
  return []
}

// ── path 边界校验（2026-11-10 深度审计 S-2 / CWE-22）─────────────────────────
// 此前 validateEntry 只用 RX_DRIVE 禁盘符，**完全没有 `..` 检查** —— 实测
// `path: ".."` / `"../allin"` / `"../../projects"` 全部零报错通过，resolvePath("..")
// 解析到 D:\projects（仓外），随后被用作 spawn 的 cwd 与门户读取文件的目录。
// ⇒ 清单准入层拒绝一切越界形状；执行层（resolvePath）再做一次防线。
const RX_POSIX_ABS = /^\//
const RX_DOT_SEGMENT = /(^|[\\/])\.\.([\\/]|$)/

/**
 * 清单里 path 的形状校验。
 * @param {string} p
 * @param {{allowAbsolute?: boolean}} opts allowAbsolute 供程序内部构造的 entry
 *   使用（如测试夹具用 os.tmpdir() 作 cwd）；**清单准入必须用缺省的 false**。
 */
export function pathProblems(p, opts = {}) {
  if (typeof p !== 'string' || !p.trim()) return ['path 为空']
  const s = p.trim().replace(/\\/g, '/')
  if (RX_DOT_SEGMENT.test(s)) return [`path 含 .. 越界段（CWE-22）：${p}`]
  if (!opts.allowAbsolute && (RX_DRIVE.test(p) || RX_POSIX_ABS.test(s))) {
    return [`path 禁止盘符 / 绝对路径（去符盘铁律，应写 repos/<仓名>）: ${p}`]
  }
  return []
}

/** 只有落在允许根之内的路径才可用于启动 cwd / 文件读取。 */
export function isPathContained(p) {
  if (typeof p !== 'string' || !p.trim()) return false
  const s = p.trim().replace(/\\/g, '/')
  if (RX_DOT_SEGMENT.test(s)) return false
  const abs = path.resolve(p)
  const bases = [path.resolve(ALLIN_ROOT), path.resolve(WORKSPACE_ROOT), path.resolve(REPOS_ROOT)]
  return bases.some((base) => abs === base || abs.startsWith(base + path.sep))
}

/**
 * 把清单里的 path 解析成绝对路径 —— **唯一入口**，所有消费点（启动 cwd / 门户读写 / 存在性校验）
 * 都必须走这里，避免各模块各自拼接后各自漂移。
 * 解析规则（先明确、后执行，不含「找不到就瞎试」的隐式魔法）：
 *   - 绝对路径 → 原样返回（仍被准入校验拦截：盘符一律不许写进清单）
 *   - `repos/...`  → 工作区根（allin 的上一级）之下，即 `<工作区根>/repos/<仓名>`
 *   - 其它相对值  → 治理仓根 ALLIN_ROOT 之下（仓内条目，如平台自身的 `platform`）
 */
export function resolvePath(p) {
  if (!p) return p
  if (path.isAbsolute(p)) return p
  // 2026-11-10 深度审计 S-2 执行层二次防御：即便调用方绕过 validateEntry
  // 直接构造 entry，`..` 也不得把 cwd / 文件读取目标带出仓根。
  if (RX_DOT_SEGMENT.test(p.replace(/\\/g, '/'))) {
    const err = new Error(`path 含 .. 越界段，拒绝解析（CWE-22）：${p}`)
    err.code = 'PATH_ESCAPE'
    throw err
  }
  return (p === 'repos' || p.startsWith('repos/'))
    ? path.resolve(WORKSPACE_ROOT, p)
    : path.resolve(ALLIN_ROOT, p)
}

export function loadPorts(portsPath = PORTS_YAML) {
  const text = fs.readFileSync(portsPath, 'utf8')
  const doc = yaml.load(text)
  const ports = new Map()
  for (const p of doc.ports || []) ports.set(Number(p.port), p)
  return ports
}

const REQUIRED = ['id', 'name', 'category', 'version']

// gameplay 受控枚举（2026-08-25 拍板：新标签先在此登记，杜绝同玩法不同名）
export const KNOWN_GAMEPLAY = [
  'arcade', 'survivor', 'driving', 'roulette', 'snake', 'idle', 'rpg', 'card',
  'fishing', 'mahjong', 'building', 'moba', 'puzzle', 'sports', 'music',
  'visual-novel', 'sim', 'chess', 'go', 'text', 'shooting',
]

// ── 墓碑条目（tombstone）豁免 path 存在性（2026-11-01 拍板）─────────────────
// 为什么要有这条：`status: archived/retired` 的条目按治理流程**已经把工作树移出 repos/**
// 归入仓外归档区（远端也多已删除），典型如 calculator（2026-10-29 收拢进 arcade，
// 原树入 archive/calculator-retired-20261029，Gitee/GitHub 双端 404）。此时再要求
// 「path 必须存在于本机」，等于逼我们必须删掉这份「撤退记录」才能绿灯 —— 语义冲突。
// ⇒ 墓碑条目豁免**存在性**，但形状校验一个不放（仍然必须写 path、仍然禁盘符），
//   避免豁免退化成「随便写」。活性条目（无 status / status: active）照旧 fail-loud。
//
// 2026-11-07 增量：`checkout: remote-only` —— registry 是**全局清单**，各机检出集不同
// （如 write-agent 在 @DESKTOP-8RSV60V 新建并推送，@SIWPAN 本机尚未检出）。
// 「本机没这个目录」不等于「治理缺陷」；显式声明后同样只豁免存在性，形状校验照旧。
// 与墓碑同族但语义不同：墓碑 = 已撤退，remote-only = 活跃但在别机。
const TOMBSTONE_STATUS = new Set(['archived', 'retired'])

export function isTombstone(entry) {
  return TOMBSTONE_STATUS.has(String(entry.status ?? '').trim().toLowerCase())
}

/** 是否豁免 path 存在性校验（形状校验一律不放）。 */
export function skipLocalExistence(entry) {
  return isTombstone(entry) || String(entry.checkout ?? '').trim().toLowerCase() === 'remote-only'
}

/**
 * 校验单条清单：必填字段、id 形状、launch.command、端口查表 + 归属核对。
 * @returns {string[]} 问题列表（空 = 通过）
 */
export function validateEntry(entry, ports) {
  const errors = []
  for (const k of REQUIRED) {
    if (entry[k] === undefined || entry[k] === null || entry[k] === '') errors.push(`missing required field: ${k}`)
  }
  if (entry.id && !/^[a-z0-9][a-z0-9-]*$/.test(entry.id)) errors.push(`bad id: ${entry.id}`)
  if (!entry.path) errors.push('missing path（去符盘纪律：repos/<仓名>）')
  else {
    // 2026-11-10 深度审计 S-2：盘符检查之外补 `..` 越界与 POSIX 绝对路径。
    const pathErrs = pathProblems(entry.path)
    for (const problem of pathErrs) errors.push(`path ${problem}`)
    if (!pathErrs.length && pathCheckMode() === 'exists' && !skipLocalExistence(entry) && !fs.existsSync(resolvePath(entry.path))) {
      errors.push(`path 不存在: ${entry.path} → 解析为 ${resolvePath(entry.path)}`)
    }
  }
  if (!entry.launch || !entry.launch.command) errors.push('missing launch.command')
  // 命令形状：不能只判「字段存在」，否则一份 yaml 就是任意命令执行入口。
  for (const section of ['launch', 'stop', 'verify']) {
    const node = entry[section]
    const cmd = node && node.command
    if (typeof cmd === 'string' && cmd.trim()) {
      for (const problem of commandProblems(cmd)) errors.push(`${section}.command ${problem}`)
    }
  }
  if (entry.gameplay !== undefined) {
    if (!Array.isArray(entry.gameplay)) {
      errors.push('gameplay 必须为数组')
    } else {
      for (const g of entry.gameplay) {
        if (!KNOWN_GAMEPLAY.includes(g)) {
          errors.push(`gameplay 标签未登记: ${g}（受控枚举，先在 KNOWN_GAMEPLAY 登记）`)
        }
      }
    }
    if (entry.category !== 'game') {
      errors.push('非 game 类项目不应填写 gameplay 标签')
    }
  }
  if (entry.port !== undefined && entry.port !== null) {
    const p = Number(entry.port)
    if (!ports.has(p)) {
      errors.push(`port ${entry.port} 未在 ports.yaml 登记（统一端口纪律：先查表再填）`)
    } else {
      const svc = String(ports.get(p).service || '')
      if (!svc.includes(entry.id)) errors.push(`port ${entry.port} 登记服务 ${svc} 与 id ${entry.id} 不一致`)
    }
  }
  return errors
}

// ── M-7 缓存基础设施（2026-11-10 深度审计）─────────────────────────────────
// loadRegistry 在单次门户请求里被多个端点重复调用（6 处），每次全量
// readFileSync + yaml.load 145 份清单。改为「签名命中即复用」：签名覆盖 dir 下
// 每份 yaml 的 (文件名, mtimeMs, size)、ports.yaml 的 (mtimeMs, size)、
// pathCheckMode 判定与发布区目录签名 —— 任一变化即重新解析，绝不返回陈旧结果。
// 返回值每次深拷贝，调用方改动不会污染缓存（行为与「每次重解析」完全一致）。
let pathCheckCache = null                 // { key, mode }（pathCheckMode 用）
const registryCache = new Map()          // dir -> { sig, result }

function reposRootSignature() {
  try {
    const st = fs.statSync(REPOS_ROOT)
    return `${st.mtimeMs}:${st.size}`
  } catch { return 'missing' }
}

function detectPathCheckMode() {
  try {
    const root = REPOS_ROOT
    if (fs.existsSync(root)) {
      const hasRepo = fs.readdirSync(root).some((name) => {
        try { return fs.statSync(path.join(root, name)).isDirectory() } catch { return false }
      })
      if (hasRepo) return 'exists'
    }
  } catch { /* 读不到发布区：按形状校验继续，不硬失败 */ }
  return 'absolute'
}

/** 显式失效入口（测试 / 文件批量变更后调用）：清空 pathCheckMode 与 loadRegistry 两级缓存。 */
export function invalidateRegistryCache() {
  pathCheckCache = null
  registryCache.clear()
}

function portFileSignature() {
  try {
    const st = fs.statSync(PORTS_YAML)
    return `${st.mtimeMs}:${st.size}`
  } catch { return 'missing' }
}

function registrySignature(dir) {
  const parts = [
    `env:${String(process.env.PLATFORM_PATH_CHECK || '')}`,
    `mode:${pathCheckMode()}`,
    `root:${reposRootSignature()}`,
    `ports:${portFileSignature()}`,
  ]
  let files = []
  try {
    files = fs.readdirSync(dir).filter(f => f.endsWith('.yaml') || f.endsWith('.yml')).sort()
  } catch (e) {
    parts.push(`dir-unreadable:${e.message}`)
    return parts.join('|')
  }
  for (const f of files) {
    try {
      const st = fs.statSync(path.join(dir, f))
      parts.push(`${f}:${st.mtimeMs}:${st.size}`)
    } catch {
      parts.push(`${f}:missing`)
    }
  }
  return parts.join('|')
}

function cloneRegistryResult(r) {
  // structuredClone 保留 Map（ports）与 Date（YAML 时间戳），且不共享引用。
  return structuredClone(r)
}

/**
 * 加载注册表目录（全部 *.yaml），返回 { entries, problems }。
 * 校验失败不阻塞加载：条目带 _valid=false，problems 供 --check fail-loud。
 */
export function loadRegistry(dir) {
  const sig = registrySignature(dir)
  const hit = registryCache.get(dir)
  if (hit && hit.sig === sig) return cloneRegistryResult(hit.result)
  // 解析失败（如 ports.yaml 损坏）原样抛出，且不写缓存 —— 保持 fail-loud 语义不变。
  const result = loadRegistryUncached(dir)
  registryCache.set(dir, { sig, result })
  return cloneRegistryResult(result)
}

function loadRegistryUncached(dir) {
  const ports = loadPorts()
  const entries = []
  const problems = []
  let files = []
  try {
    files = fs.readdirSync(dir).filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))
  } catch (e) {
    problems.push(`registry dir 不可读: ${dir} (${e.message})`)
    return { entries, problems }
  }
  for (const f of files.sort()) {
    let entry
    try {
      entry = yaml.load(fs.readFileSync(path.join(dir, f), 'utf8'))
    } catch (e) {
      problems.push(`${f}: YAML 解析失败: ${e.message}`)
      continue
    }
    if (!entry || typeof entry !== 'object') { problems.push(`${f}: 空清单`); continue }
    const errs = validateEntry(entry, ports)
    if (errs.length) problems.push(`${f}: ${errs.join('; ')}`)
    entries.push({ ...entry, _file: f, _valid: errs.length === 0 })
  }
  const seen = new Set()
  for (const e of entries) {
    if (seen.has(e.id)) problems.push(`duplicate id: ${e.id}`)
    seen.add(e.id)
  }
  return { entries, problems, ports }
}
