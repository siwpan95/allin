/**
 * @allin/cli-bus —— console 与项目之间的**唯一**总线（SPEC-205 §C1）
 *
 * 设计纪律：
 *   · 只认 `<仓根>/cli.py` | `cli.mjs` | `cli.js`，不猜别的入口；
 *   · 一律子进程调用，**绝不 import 项目代码**（承 SPEC-203 子进程隔离铁律）；
 *   · stdout 必须是纯 JSON（`--json` 场景）——夹带 banner 即判协议违约，不尝试"宽容解析"；
 *   · 超时视为失败并强杀，不留下孤儿进程；
 *   · 退出码只有三态：0 成功 / 1 业务失败 / 2 用法错误（其他码记录但按失败处理）。
 */
import { spawn } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'

/** 项目 CLI 的文件名优先级。 */
const CLI_NAMES = ['cli.py', 'cli.mjs', 'cli.js']

/** Python 解释器：允许 env 覆盖（与 allin 其他工具一致，不写死盘符）。 */
const PYTHON = process.env.ALLIN_PYTHON || 'python'

/** 默认超时：info/version 这类只读命令 30s 足够；launch 由调用方放宽。 */
export const DEFAULT_TIMEOUT_MS = 30_000

/**
 * 定位项目的 CLI 入口。
 * @param {string} projectPath 项目绝对路径
 * @returns {string|null} CLI 绝对路径；无则 null
 */
export function locateCli(projectPath) {
  if (!projectPath) return null
  for (const name of CLI_NAMES) {
    const candidate = path.join(projectPath, name)
    if (existsSync(candidate)) return candidate
  }
  return null
}

/**
 * 静态探测该 CLI 是否实现了 `info` 子命令。
 *
 * 为什么不能只看文件存在：实测 bloodmusic 的 cli.py 只有 `batch/preview/list/gui/pool`，
 * audio-pipeline 只有 `doctor/run/stage-a…` —— 都是早期 CLI，没有 `info`。
 * 只按文件存在打标会把它们算成"已接入"，UI 上点一下才报错，体验更差。
 *
 * 这里只做静态判断（读源码找 add_parser("info")），不跑进程 —— 148 个项目逐个跑
 * `--help` 要几十秒，P0 用不起。误判方向可接受：宁可漏标（用户点了会看到明确报错），
 * 不可错标（让人以为能跑）。
 *
 * @param {string|null} cliPath
 * @returns {boolean}
 */
export function hasInfoSubcommand(cliPath) {
  if (!cliPath) return false
  try {
    const src = readFileSync(cliPath, 'utf8')
    // argparse / commander / 手写分发三种常见形态
    return /add_parser\(\s*['"]info['"]/.test(src)
      || /\.command\(\s*['"]info['"]/.test(src)
      || /case\s+['"]info['"]/.test(src)
      || /['"]info['"]\s*:\s*(cmd|command|run)/.test(src)
  } catch {
    return false
  }
}

/**
 * 算出该用什么跑 CLI。
 * `.py` → python；`.mjs`/`.js` → 复用 Electron 自带的 Node（ELECTRON_RUN_AS_NODE），
 * 避免假设系统 PATH 里一定有 node。
 */
function buildPlan(cliPath) {
  const ext = path.extname(cliPath).toLowerCase()
  if (ext === '.py') {
    return { command: PYTHON, argsPrefix: [], env: {} }
  }
  return {
    command: process.execPath,
    argsPrefix: [],
    env: { ELECTRON_RUN_AS_NODE: '1' },
  }
}

/**
 * 调用项目 CLI。
 *
 * @param {object} opts
 * @param {string} opts.projectPath 项目绝对路径（作为 cwd）
 * @param {string[]} opts.args 子命令与参数，如 ['info']
 * @param {number} [opts.timeoutMs]
 * @param {boolean} [opts.expectJson] 是否要求 stdout 为 JSON（`info` 用）。
 *   注意：既有 33+ 个项目的 `info` **默认就输出 JSON**，不接受 `--json` 参数
 *   （实测 shikonghuaban：加 --json 会 argparse 报 unrecognized arguments）。
 *   所以这里用显式选项而非在 args 里塞参数 —— 契约贴着既成事实走。
 * @returns {Promise<{ok:boolean, code:number|null, stdout:string, stderr:string,
 *                    durationMs:number, timedOut:boolean, reason?:string, json?:any,
 *                    parseError?:string}>}
 */
export function runCli({
  projectPath, args = [], timeoutMs = DEFAULT_TIMEOUT_MS, expectJson = false,
}) {
  const cli = locateCli(projectPath)
  if (!cli) {
    return Promise.resolve({
      ok: false, code: null, stdout: '', stderr: '', durationMs: 0,
      timedOut: false, reason: 'no-cli',
    })
  }

  const plan = buildPlan(cli)
  const started = Date.now()

  return new Promise((resolve) => {
    let child
    try {
      child = spawn(plan.command, [cli, ...args], {
        cwd: projectPath,
        env: { ...process.env, ...plan.env, PYTHONIOENCODING: 'utf-8' },
        shell: false,
        windowsHide: true,
      })
    } catch (e) {
      resolve({
        ok: false, code: null, stdout: '', stderr: String(e && e.message),
        durationMs: Date.now() - started, timedOut: false, reason: 'spawn-failed',
      })
      return
    }

    let stdout = ''
    let stderr = ''
    let timedOut = false

    const timer = setTimeout(() => {
      timedOut = true
      try { child.kill('SIGKILL') } catch { /* 已退出 */ }
    }, timeoutMs)

    child.stdout.on('data', (d) => { stdout += d.toString('utf8') })
    child.stderr.on('data', (d) => { stderr += d.toString('utf8') })

    child.on('error', (e) => {
      clearTimeout(timer)
      resolve({
        ok: false, code: null, stdout, stderr: stderr + String(e && e.message),
        durationMs: Date.now() - started, timedOut, reason: 'spawn-error',
      })
    })

    child.on('close', (code) => {
      clearTimeout(timer)
      const result = {
        ok: code === 0 && !timedOut,
        code,
        stdout,
        stderr,
        durationMs: Date.now() - started,
        timedOut,
      }
      if (timedOut) result.reason = 'timeout'
      // 只有调用方明确要 JSON 时才解析 —— 避免把人类可读输出误当协议
      if (expectJson) {
        const parsed = tryParseJson(stdout)
        if (parsed.ok) result.json = parsed.value
        else result.parseError = parsed.error
      }
      resolve(result)
    })
  })
}

/**
 * 严格 JSON 解析：先整体解析，失败再尝试剥离尾部噪声一次。
 * 不成功就如实报错 —— 不用正则去"猜"一个 JSON 出来（那会把协议违约藏起来）。
 */
function tryParseJson(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return { ok: false, error: 'stdout 为空' }
  try {
    return { ok: true, value: JSON.parse(trimmed) }
  } catch (e1) {
    // 退一步：取第一个 '{' 到最后一个 '}' —— 仅当首尾确实包着一个对象时才用
    const start = trimmed.indexOf('{')
    const end = trimmed.lastIndexOf('}')
    if (start >= 0 && end > start) {
      try {
        return { ok: true, value: JSON.parse(trimmed.slice(start, end + 1)), stitched: true }
      } catch {
        /* 落回原始错误 */
      }
    }
    return { ok: false, error: String(e1 && e1.message) }
  }
}

/** 人类可读的失败摘要（UI 用，取 stderr 末 n 行）。 */
export function failureSummary(result, lines = 20) {
  if (!result) return '（无结果）'
  if (result.reason === 'no-cli') return '该项目尚未提供 cli.py / cli.mjs（见 SPEC-205 §C1 B3 批次）'
  if (result.reason === 'timeout') return `调用超时（>${Math.round(result.durationMs / 1000)}s）`
  const tail = (result.stderr || '').trim().split('\n').slice(-lines).join('\n')
  return tail || `退出码 ${result.code}`
}
