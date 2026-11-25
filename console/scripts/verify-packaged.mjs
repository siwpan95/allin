/**
 * 打包产物运行验证（P4 核心判据）
 *
 * 为什么必须真跑：electron-builder 的成功日志**不代表**产物能用。
 * 实测坑：`@allin/core` 是符号链接到仓外，它声明的 `js-yaml` 不被收集进
 * asar —— 打包阶段只报一行 `cannot find path for dependency`（不阻断），
 * 而运行时 `import yaml from 'js-yaml'` 直接崩，表现为「装得上、打不开」。
 *
 * 为什么用**文件**而不是 stdout：Windows GUI 子系统的进程（electron.exe /
 * 「allin console.exe」）不继承控制台句柄，stdout 会直接丢失 ——
 * 实测退出码 0 但一个字节都没打印。⇒ 探针结果写文件，由外部读取。
 *
 * 判据：探针文件里 registry 的条数**必须等于仓内源清单**（`platform/registry/projects/*.yaml` 的份数）。
 *   （2026-11-25 改：原判据是「≥ 100（预期 148）」，与 `verify-package.mjs` 同一类魔数缺陷 ——
 *    门槛与真实条数脱钩，且**判不到最该判的那类**：产物落后于源。详见下方第 4 段。）
 *
 * 用法：node scripts/verify-packaged.mjs
 */
import path from 'node:path'
import { spawn } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const UNPACKED = path.join(HERE, '..', 'dist', 'win-unpacked')
const EXE = path.join(UNPACKED, 'allin console.exe')
const PROBE_OUT = path.join(UNPACKED, 'probe-out.txt')

function log(m) { console.log(`[packaged] ${m}`) }

if (!existsSync(EXE)) {
  console.error(`[packaged] ✗ 产物不存在：${EXE}`)
  process.exit(1)
}
try { rmSync(PROBE_OUT, { force: true }) } catch { /* 无所谓 */ }

// ⚠ env 构造有坑：ELECTRON_RUN_AS_NODE 必须**彻底删除**。
//   设成空字符串 ≠ 未设置 —— Electron 收到非 undefined 的值就以纯 Node 模式跑，
//   主进程代码根本不执行（表现为退出码 0、什么也没干）。
//   这正是本机宿主进程注入的那个变量的坑（P3 已在 start-console.bat 里处理过）。
const childEnv = { ...process.env }
delete childEnv.ELECTRON_RUN_AS_NODE
childEnv.ALLIN_CONSOLE_PROBE = '1'
childEnv.ALLIN_CONSOLE_PROBE_OUT = PROBE_OUT

const child = spawn(EXE, [], {
  cwd: UNPACKED,
  env: childEnv,
  stdio: 'ignore',
  detached: false,
})

const timeout = setTimeout(() => {
  child.kill()
  console.error('[packaged] ✗ 探针超时（40s）')
  if (existsSync(PROBE_OUT)) {
    console.error(`探针文件内容：\n${readFileSync(PROBE_OUT, 'utf8')}`)
  }
  process.exit(1)
}, 40_000)

child.on('exit', (code) => {
  clearTimeout(timeout)
  log(`退出码 ${code}`)

  // electron.exe 会 fork 出多个子进程；主进程退出后子进程可能还持有 exe 句柄，
  // 导致下一次打包报「open 'allin console.exe' failed」。这里主动清一遍。
  if (process.platform === 'win32') {
    try {
      spawn('taskkill', ['/F', '/IM', 'allin console.exe', '/T'], { stdio: 'ignore' })
    } catch { /* 无所谓 */ }
  }

  if (!existsSync(PROBE_OUT)) {
    // 探针文件没出来：先看是不是写到了别处（cwd / TEMP），再判定失败。
    console.error('[packaged] ✗ 主进程没有写出探针文件（可能崩在 import 阶段）')
    console.error(`  期望路径：${PROBE_OUT}`)
    console.error(`  cwd      ：${UNPACKED}`)
    const alt = path.join(process.cwd(), 'probe-out.txt')
    if (existsSync(alt)) {
      console.error(`  但在 cwd 找到了：${alt}`)
      console.error(readFileSync(alt, 'utf8'))
    }
    process.exit(1)
  }
  const text = readFileSync(PROBE_OUT, 'utf8')
  log(`探针输出：\n${text.trim()}`)

  const m = text.match(/registry=(\d+)/)
  if (!m) {
    console.error('[packaged] ✗ 探针没有输出 registry 条数')
    process.exit(1)
  }
  const n = Number(m[1])
  // 「对源对账」取代魔数阈值（2026-11-25）。为什么非改不可：
  //   旧判据 `n >= 100` 在注册表 83 条时恒假红、涨过 100 后又恒真绿；
  //   而它**判不到**"产物落后于源"这一类 —— 本机实测产物里 148 条、源清单 83 条，
  //   旧判据面对 148 只说"通过"。运行时读到的条数必须与源清单**相等**，多一条少一条都红。
  const SOURCE_REG = path.join(HERE, '..', '..', 'platform', 'registry', 'projects')
  const declared = existsSync(SOURCE_REG)
    ? readdirSync(SOURCE_REG).filter((f) => f.endsWith('.yaml')).length
    : -1
  if (declared < 0) {
    console.error(`[packaged] ✗ 源清单读不到：${SOURCE_REG} —— 对账缺基准，不能判通过`)
    process.exit(1)
  }
  if (n !== declared) {
    const how = n < declared
      ? `少 ${declared - n} 条（产物落后于源，需重新打包）`
      : `多 ${n - declared} 条（产物里还留着已删除的条目）`
    console.error(`[packaged] ✗ registry 运行时读到 ${n} 条 ≠ 源清单 ${declared} 条 —— ${how}`)
    process.exit(1)
  }
  log(`registry 条数 = ${n}（与源清单 ${declared} 条一致）`)
  log('打包产物运行验证通过')
  process.exit(0)
})
