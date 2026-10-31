/**
 * Run the governance gates of this distribution repository.
 *
 * The gates themselves are Python programs under `governance/gates/`, because
 * their first implementations came from a PowerShell/Python governance toolbox
 * and one judgment must not exist twice in two languages. This dispatcher owns
 * the parts that are repository plumbing rather than judgment:
 *
 * - **interpreter discovery that fails loudly.** A gate that cannot find an
 *   interpreter must stop the run with a named cause; skipping quietly would
 *   turn a whole class of checks into decoration.
 * - **one aggregate entry point** (`pnpm run check:governance`) so the gates
 *   are listed, runnable one by one, and self-checkable.
 * - **exit-code aggregation** over the shared vocabulary: 0 clean, 1 blocking,
 *   2 usage error, 3 environment error. The worst outcome wins.
 *
 * Usage:
 *   tsx governance/run.ts                     # every registered gate
 *   tsx governance/run.ts --list              # ids, tiers, and covered rules
 *   tsx governance/run.ts --only g01-paths    # a subset, comma separated
 *   tsx governance/run.ts --tier P0,P1        # every gate at these tiers that can
 *                                             # run offline (context != push)
 *   tsx governance/run.ts --selfcheck-all     # prove every gate still detects
 *   tsx governance/run.ts -- <args>           # forwarded to each gate
 *
 * `--tier` exists because a hand-maintained subset list drifts: every new gate
 * had to be added to `check:precommit` by hand, and twice it was not, so the
 * pre-commit stage silently stopped running the newest checks. Tier and context
 * live in `registry.json` -- the same file that already declares the gate.
 */

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname, '..')
const REGISTRY_PATH = resolve(import.meta.dirname, 'registry.json')

/** Exit-code vocabulary shared by every governance gate. */
const EXIT_OK = 0
const EXIT_BLOCKING = 1
const EXIT_USAGE = 2
const EXIT_ENV = 3

const MINIMUM_PYTHON = [3, 9] as const

/**
 * 本机在 registry 的 `platforms` 词汇里的代号。
 *
 * registry 用 *文件内* 的稳定词汇（`nt` / `posix`），而不是 Node 的
 * `process.platform`（`win32` / `linux` / `darwin`）—— 因为前者是写在
 * JSON 里的契约数据，换 Node 版本不会变。这里只做一次映射。
 */
const HOST_PLATFORM = process.platform === 'win32' ? 'nt' : 'posix'

/**
 * 平台不匹配的门禁在本机**不适用**，必须跳过（记为 SKIPPED），而不是跑它。
 *
 * 起因（2026-10-31 真实 CI 事故，两次踩到同一个根因的两面）：
 *   `g20-facts` 在 registry 里声明 `platforms: ["nt"]`（它判 Windows 本机
 *   磁盘路径的存在性声称）。但本调度器**从不读 platforms 字段** —— 它只是
 *   在 interface 里声明了一下就再没用过。于是 Linux CI 上照样调起 g20，
 *   g20 自己判 `sys.platform != "win32"` 后打一行 ENV ERROR 并 exit 3，
 *   聚合器把 3 当失败 ⇒ 「19/20 clean; failed: g20-facts」⇒ 整条流水线红。
 *
 *   而真实结论只是「这道门禁在 Linux 上不适用」。把「不适用」报成「失败」，
 *   与把「跳过」报成「通过」是同一种病：结论与事实不符。
 *
 * 口径（与门禁契约「SKIP ≠ 通过」一致）：平台不匹配 → 不调起、记 SKIPPED、
 * 在汇总行里单列。这样 Linux 的诚实结论是「19 clean + 1 skipped (platform)」。
 *
 * ⚠ 与 `--only` 的关系：显式点名（`--only g20-facts`）时**不跳过**，
 * 因为那时用户的意图就是「我就要在这台机器上试它」，跳过会掩盖真实报错。
 */
function onHostPlatform(gate: GateEntry): boolean {
  const platforms = gate.platforms
  if (!Array.isArray(platforms) || platforms.length === 0) return true
  return platforms.includes(HOST_PLATFORM)
}

interface Interpreter {
  command: string
  prefix: string[]
  version: string
}

interface GateEntry {
  id: string
  title: string
  script: string
  tier: string
  rules: string[]
  platforms: string[]
  requires: string[]
  baseline: string | null
  selfcheck: boolean
  /**
   * Where the gate may run. `local` (default) works offline against the working
   * tree; `push` needs authoritative remote evidence (`git ls-remote`). Tier
   * selection keeps `push` gates out so a pre-commit run never fails on a
   * missing network.
   */
  context?: string
  /**
   * True when the gate consults state outside the repository (the active DSH
   * profile). The aggregate passes `--no-profile` to exactly these gates, so a
   * repository-only run never reads the host's deployment; `g00-meta` checks the
   * declaration against the gate's own `--help`, so it cannot go stale.
   */
  profileProbe?: boolean
}

interface GateOutcome {
  gate: GateEntry
  code: number
}

/** Probe one interpreter candidate for a usable Python 3.9+ version. */
function probe(command: string, prefix: string[]): Interpreter | undefined {
  const result = spawnSync(command, [...prefix, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], {
    encoding: 'utf8',
  })
  if (result.error !== undefined || result.status !== 0) return undefined
  const version = (result.stdout ?? '').trim()
  const parts = version.split('.')
  const major = Number.parseInt(parts[0] ?? '', 10)
  const minor = Number.parseInt(parts[1] ?? '', 10)
  if (Number.isNaN(major) || Number.isNaN(minor)) return undefined
  const [wantedMajor, wantedMinor] = MINIMUM_PYTHON
  const usable = major > wantedMajor || (major === wantedMajor && minor >= wantedMinor)
  return usable ? { command, prefix, version } : undefined
}

/**
 * Find the interpreter that runs the gates, or stop with a named cause.
 * @see governance/RULES.md -- the fail-loud clause of the gate contract
 */
/**
 * Interpreters inside the repository's own virtualenv, when it exists.
 *
 * The venv is the only dependency set the repository pins itself (it carries
 * PyYAML, which `g18-exceptions` needs to parse the exception ledger), so it is
 * the one candidate that yields the same verdict on every machine. Probing it
 * before the PATH keeps "same commit, green here, red there" from coming back:
 * the discovery order below otherwise lands on whatever `python3` the host
 * happens to provide -- a trimmed build without PyYAML makes `g18` report a
 * false blocker, and the run then contradicts the commit message.
 */
function venvInterpreters(): Array<{ command: string; prefix: string[] }> {
  const venv = resolve(ROOT, '..', '..', '.venv')
  return [
    { command: resolve(venv, 'Scripts', 'python.exe'), prefix: [] },
    { command: resolve(venv, 'bin', 'python'), prefix: [] },
  ]
}

function discoverInterpreter(): Interpreter {
  const override = process.env.DSH_GOVERNANCE_PYTHON
  const candidates: Array<{ command: string; prefix: string[] }> = [
    ...(override === undefined || override === '' ? [] : [{ command: override, prefix: [] }]),
    ...venvInterpreters(),
    { command: 'python3', prefix: [] },
    { command: 'python', prefix: [] },
    { command: 'py', prefix: ['-3'] },
  ]
  for (const candidate of candidates) {
    const found = probe(candidate.command, candidate.prefix)
    if (found !== undefined) return found
  }
  throw new Error(
    'governance: no Python 3.9+ interpreter found; install python3 or set DSH_GOVERNANCE_PYTHON to its path',
  )
}

/** Read the gate registry, failing loudly on a malformed or empty file. */
function readRegistry(): GateEntry[] {
  const raw = JSON.parse(readFileSync(REGISTRY_PATH, 'utf8')) as { gates?: GateEntry[] }
  const gates = raw.gates
  if (!Array.isArray(gates) || gates.length === 0) {
    throw new Error(`governance: ${REGISTRY_PATH} declares no gates`)
  }
  return gates
}

interface Options {
  list: boolean
  only: string[] | undefined
  tier: string[] | undefined
  selfcheckAll: boolean
  quiet: boolean
  noProfile: boolean
  forwarded: string[]
}

/** Parse the dispatcher's own flags; everything after `--` belongs to the gates. */
function parseArguments(argv: string[]): Options {
  const separator = argv.indexOf('--')
  const own = separator === -1 ? argv : argv.slice(0, separator)
  const forwarded = separator === -1 ? [] : argv.slice(separator + 1)
  const options: Options = {
    list: false, only: undefined, tier: undefined, selfcheckAll: false, quiet: false,
    noProfile: false, forwarded,
  }
  for (let index = 0; index < own.length; index += 1) {
    const argument = own[index]
    if (argument === '--list') options.list = true
    else if (argument === '--selfcheck-all') options.selfcheckAll = true
    else if (argument === '--quiet') options.quiet = true
    else if (argument === '--no-profile') options.noProfile = true
    else if (argument === '--only') {
      const value = own[index + 1]
      if (value === undefined) throw new Error('governance: --only needs a comma-separated gate list')
      options.only = value.split(',').map(entry => entry.trim()).filter(entry => entry !== '')
      index += 1
    } else if (argument === '--tier') {
      const value = own[index + 1]
      if (value === undefined) throw new Error('governance: --tier needs a comma-separated tier list')
      options.tier = value.split(',').map(entry => entry.trim()).filter(entry => entry !== '')
      index += 1
    } else {
      throw new Error(`governance: unknown argument ${JSON.stringify(argument)}; see the usage block in run.ts`)
    }
  }
  return options
}

/**
 * Choose which gates run. `--only` wins when given; otherwise `--tier` selects
 * by the tier declared in `registry.json`, skipping gates whose context is not
 * `local` so an offline pre-commit run cannot fail on a missing remote.
 */
function selectGates(registry: GateEntry[], options: Options): GateEntry[] {
  if (options.only !== undefined) {
    return registry.filter(gate => options.only?.includes(gate.id) === true)
  }
  if (options.tier !== undefined) {
    return registry.filter(
      gate => options.tier?.includes(gate.tier) === true && (gate.context ?? 'local') === 'local',
    )
  }
  return registry
}

/** Run one gate as a child process, streaming its output to the caller. */
function runGate(gate: GateEntry, interpreter: Interpreter, args: string[]): GateOutcome {
  const script = resolve(ROOT, gate.script)
  const result = spawnSync(interpreter.command, [...interpreter.prefix, script, ...args], {
    cwd: ROOT,
    stdio: 'inherit',
  })
  if (result.error !== undefined) throw result.error
  return { gate, code: result.status ?? EXIT_ENV }
}

/** Collapse per-gate outcomes into the shared exit-code vocabulary. */
function aggregate(outcomes: GateOutcome[]): number {
  let worst = EXIT_OK
  for (const outcome of outcomes) {
    if (outcome.code === EXIT_ENV) return EXIT_ENV
    if (outcome.code === EXIT_USAGE) worst = Math.max(worst, EXIT_USAGE)
    else if (outcome.code !== EXIT_OK) worst = Math.max(worst, EXIT_BLOCKING)
  }
  return worst
}

function main(argv: string[]): number {
  const options = parseArguments(argv)
  const registry = readRegistry()
  const selected = selectGates(registry, options)
  if (selected.length === 0) {
    const asked = options.only ?? options.tier ?? []
    console.error(`governance: no registered gate matches ${JSON.stringify(asked)}`)
    return EXIT_USAGE
  }
  if (options.list) {
    for (const gate of registry) {
      console.log(`${gate.id}\t${gate.tier}\t${gate.rules.join(',')}\t${gate.title}`)
    }
    return EXIT_OK
  }

  const interpreter = discoverInterpreter()
  // `--no-profile` reaches only the gates that declare they read the host profile,
  // so a repository-only aggregate never touches the deployment and never breaks a
  // gate that has no such switch.
  const profileGates = options.noProfile
    ? selected.filter(gate => gate.profileProbe === true)
    : []
  if (!options.quiet) {
    console.log(`governance: python ${interpreter.version} via ${interpreter.command}; `
      + `${selected.length} gate(s)${options.selfcheckAll ? ' in self-check mode' : ''}`
      + (options.noProfile
        ? `; repository-only (--no-profile forwarded to ${profileGates.length} profile-reading gate(s))`
        : ''))
  }
  const outcomes: GateOutcome[] = []
  // 平台不匹配的门禁：不调起、记 SKIPPED（见 onHostPlatform 的说明）。
  // `--only` 显式点名时不跳过 —— 用户点名的意图就是「我就要试它」。
  const platformSkipped: GateEntry[] = []
  for (const gate of selected) {
    if (options.only === undefined && !onHostPlatform(gate)) {
      platformSkipped.push(gate)
      continue
    }
    const args = options.selfcheckAll
      ? ['--selfcheck']
      : [...options.forwarded, ...(profileGates.includes(gate) ? ['--no-profile'] : [])]
    const outcome = runGate(gate, interpreter, args)
    outcomes.push(outcome)
    if (!options.quiet) {
      console.log(`governance: ${gate.id} -> exit ${outcome.code}`)
    }
  }
  const failed = outcomes.filter(outcome => outcome.code !== EXIT_OK)
  console.log(`governance: ${outcomes.length - failed.length}/${outcomes.length} gate(s) clean`
    + (failed.length === 0 ? '' : `; failed: ${failed.map(outcome => outcome.gate.id).join(', ')}`))
  if (platformSkipped.length > 0) {
    // 单独一行，且明写 SKIPPED (not a pass) —— 不让「跳过的」混进「干净的」分子里。
    console.log(`governance: SKIPPED (not a pass) on ${HOST_PLATFORM}: `
      + platformSkipped.map(gate => `${gate.id} (declares ${gate.platforms.join('|')})`).join(', '))
  }
  // 「一个都没跑」不等于「一个都没问题」。若所有选中的门禁都因平台被跳过，
  // 此时退出 0 就是在用「没验」冒充「验过」—— 判环境错误，让调用方看见。
  if (outcomes.length === 0 && platformSkipped.length > 0) {
    console.error(`governance: every selected gate is inapplicable on ${HOST_PLATFORM}; nothing was judged`)
    return EXIT_ENV
  }
  return aggregate(outcomes)
}

try {
  process.exitCode = main(process.argv.slice(2))
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = EXIT_ENV
}
