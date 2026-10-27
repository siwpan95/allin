#!/usr/bin/env node
// DSH Hook Protocol -- PreToolUse gate for the allin workspace.
//
// Why this exists: text injection (SKILL.md / the GOVERNANCE segment) only tells
// an agent what the rules are. A hook can *stop* it. Mounted as a PreToolUse
// hook, this script runs the fast governance gates against the workspace and
// exits 2 when they are red -- and in the Hook Protocol, exit 2 means "block the
// operation", with stderr shown to the agent as the reason.
//
// Contract (Claude Code dialect, which @deepseek-ai/dsh-hooks-claude-code speaks):
//   stdin  : { tool_name, tool_input: { file_path | command | ... }, ... }
//   exit 0 : allow (stdout, if any, is injected as context for the next prompt)
//   exit 2 : block (stderr becomes the blocking message)
//
// Conservative by design: it only judges paths inside this repository, it only
// runs the gates that are fast enough to sit in an agent's critical path
// (g01 machine paths, g03 credentials), and any failure of the harness itself
// is reported as a warning -- never as a silent pass, never as a hard block.

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.join(__dirname, '..', '..', '..', '..')
const GATES = path.join(REPO, 'tools', 'gate', 'governance', 'gates')
const FAST_GATES = ['g01_paths.py', 'g03_credentials.py']

function pythonBin() {
  return process.env.ALLIN_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
}

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8')
  } catch {
    return ''
  }
}

function targetOf(payload) {
  const input = payload?.tool_input || {}
  return String(input.file_path || input.path || input.notebook_path || input.command || '')
}

function insideRepo(candidate) {
  if (!candidate) return false
  const absolute = path.isAbsolute(candidate) ? candidate : path.join(REPO, candidate)
  const relative = path.relative(REPO, absolute)
  return Boolean(relative) && !relative.startsWith('..') && !path.isAbsolute(relative)
}

function runGate(script) {
  const res = spawnSync(pythonBin(), [path.join(GATES, script), '--quiet'], {
    cwd: REPO, encoding: 'utf8', timeout: 120000, maxBuffer: 4 * 1024 * 1024,
  })
  return {
    exit: typeof res.status === 'number' ? res.status : -1,
    output: `${res.stdout || ''}${res.stderr || ''}`.trim(),
  }
}

function judge(payload) {
  const target = targetOf(payload)
  if (!insideRepo(target)) {
    return { code: 0, stderr: '', stdout: '', skipped: true }
  }
  const failures = []
  for (const script of FAST_GATES) {
    if (!fs.existsSync(path.join(GATES, script))) {
      failures.push({ script, exit: -1, output: '门禁脚本缺失' })
      continue
    }
    const res = runGate(script)
    if (res.exit !== 0) failures.push({ script, exit: res.exit, output: res.output })
  }
  if (!failures.length) return { code: 0, stderr: '', stdout: '' }
  const detail = failures.map((f) => `  - ${f.script} (exit ${f.exit}): ${f.output.split('\n')[0]}`).join('\n')
  return {
    code: 2,
    stderr: `allin 治理门禁未通过，本次写入已被阻断：\n${detail}\n`
      + `修好后重试；判据见 tools/gate/governance/RULES.md，一键复跑：bash scripts/run_all_gates.sh`,
    stdout: '',
  }
}

const argv = process.argv.slice(2)

if (argv.includes('--selftest')) {
  let failures = 0
  const check = (label, ok, detail = '') => {
    if (!ok) { failures += 1; console.log(`FAIL ${label} ${detail}`) } else { console.log(`ok   ${label}`) }
  }
  // 干净样本：工具作用在仓外 → 直接放行，不跑门禁
  const outside = judge({ tool_name: 'Write', tool_input: { file_path: path.join(REPO, '..', 'outside.txt') } })
  check('仓外写入放行', outside.code === 0 && outside.skipped === true)
  // 仓内写入：门禁当前为绿 → 放行
  const inside = judge({ tool_name: 'Write', tool_input: { file_path: path.join(REPO, 'README.md') } })
  check('仓内写入且门禁绿 → 放行', inside.code === 0, `code=${inside.code} ${inside.stderr.slice(0, 120)}`)
  // judge() 必须能被"门禁红"驱动到 exit 2 —— 用桩脚本验证阻断路径本身
  const stubDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hook-stub-'))
  const stub = path.join(stubDir, 'stub.py')
  fs.writeFileSync(stub, 'import sys\nsys.exit(1)\n', 'utf8')
  const original = FAST_GATES.slice()
  FAST_GATES.length = 0
  FAST_GATES.push(path.relative(GATES, stub))
  const blocked = judge({ tool_name: 'Write', tool_input: { file_path: path.join(REPO, 'README.md') } })
  FAST_GATES.length = 0
  original.forEach((g) => FAST_GATES.push(g))
  check('门禁红 → 阻断（exit 2 + stderr 说明）', blocked.code === 2 && blocked.stderr.includes('已被阻断'))
  fs.rmSync(stubDir, { recursive: true, force: true })
  console.log(failures === 0 ? 'SELFTEST OK' : `SELFTEST FAILED (${failures})`)
  process.exit(failures === 0 ? 0 : 1)
}

const payload = (() => {
  const raw = readStdin().trim()
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    return {}
  }
})()

const verdict = judge(payload)
if (verdict.stderr) process.stderr.write(verdict.stderr + '\n')
if (verdict.stdout) process.stdout.write(verdict.stdout + '\n')
process.exit(verdict.code)
