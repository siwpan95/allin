#!/usr/bin/env node
// allin MCP server -- the governance surface as callable tools.
//
// Transport: JSON-RPC 2.0 over stdio (one message per line), which is what
// `@deepseek-ai/dsh-mcp-client` and every other MCP client can spawn directly.
//
// Design rules, none of them optional:
//   * read-only by default -- six of the seven tools only read;
//   * the one write tool needs an explicit `confirm: true` and writes outside
//     `docs/` (a file dropped into `docs/` without an INDEX.md registration
//     would trip the D1 contract on the very next gate run), and every accepted
//     write is appended to `tools/gate/audit/mcp-actions.jsonl`;
//   * paths are derived from this file's location, never hard-coded to a drive;
//   * a tool that cannot do its work returns `isError: true` with a reason --
//     never an empty success.

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.join(__dirname, '..', '..', '..', '..')
const GOVERNANCE = path.join(REPO, 'tools', 'gate', 'governance')
const REGISTRY_DIR = path.join(REPO, 'platform', 'registry', 'projects')
const AUDIT_DIR = path.join(REPO, 'tools', 'gate', 'audit')

const PROTOCOL = '2025-06-18'
const SERVER_INFO = { name: 'allin-governance', version: '0.1.0' }
const DEFAULT_TIMEOUT_MS = 120000

// ---------------------------------------------------------------- helpers

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch {
    return null
  }
}

function readLines(file) {
  try {
    return fs.readFileSync(file, 'utf8').split('\n')
  } catch {
    return []
  }
}

function pythonBin() {
  return process.env.ALLIN_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
}

function run(cmd, args, { timeout = DEFAULT_TIMEOUT_MS, cwd = REPO } = {}) {
  const started = Date.now()
  const res = spawnSync(cmd, args, { cwd, timeout, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 })
  const ms = Date.now() - started
  const out = `${res.stdout || ''}${res.stderr || ''}`
  return {
    exit: typeof res.status === 'number' ? res.status : (res.error ? -1 : 0),
    ms,
    error: res.error ? String(res.error.message || res.error) : null,
    output: out,
    tail: out.trim().split('\n').slice(-25).join('\n'),
  }
}

function parseEntry(text) {
  const pick = (re) => {
    const m = text.match(re)
    return m ? m[1].trim() : null
  }
  return {
    id: pick(/^id:\s*(\S+)\s*$/m),
    name: pick(/^name:\s*(.+)\s*$/m),
    category: pick(/^category:\s*(\S+)\s*$/m),
    path: pick(/^path:\s*(\S+)\s*$/m),
    status: pick(/^status:\s*(\S+)\s*$/m),
  }
}

function listEntries() {
  let files = []
  try {
    files = fs.readdirSync(REGISTRY_DIR).filter((f) => f.endsWith('.yaml'))
  } catch {
    return []
  }
  return files.map((f) => {
    const text = fs.readFileSync(path.join(REGISTRY_DIR, f), 'utf8').replace(/^﻿/, '')
    return { ...parseEntry(text), file: f }
  })
}

// ---------------------------------------------------------------- tools

const TOOLS = [
  {
    name: 'gate.list',
    description: '列出 allin 治理门禁（id / title / tier / 是否有基线）',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'gate.run',
    description: '跑一个门禁（gate 指定 id）或整套聚合（all=true）。返回退出码与输出尾部。',
    inputSchema: {
      type: 'object',
      properties: {
        gate: { type: 'string', description: '门禁 id，例如 g01-paths' },
        all: { type: 'boolean', description: 'true 时跑 npm run check:governance 整套' },
        timeoutMs: { type: 'number' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'registry.query',
    description: '按 id / category 查询项目注册表，返回条目摘要',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string' },
        category: { type: 'string' },
        limit: { type: 'number' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'registry.verify',
    description: '无头验证登记项目（可限定 only/category/limit）。耗时操作，默认 limit 20。',
    inputSchema: {
      type: 'object',
      properties: {
        only: { type: 'string', description: '只验一个 id' },
        category: { type: 'string' },
        limit: { type: 'number' },
        timeoutMs: { type: 'number' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'docs.search',
    description: '在文档枢纽里全文检索（不含 md/ 历史树），返回 file:line:片段',
    inputSchema: {
      type: 'object',
      properties: { query: { type: 'string' }, limit: { type: 'number' } },
      required: ['query'],
      additionalProperties: false,
    },
  },
  {
    name: 'project.status',
    description: '单个项目的登记信息 + 本地克隆的最后提交天数 + 上次验证结论',
    inputSchema: {
      type: 'object',
      properties: { id: { type: 'string' } },
      required: ['id'],
      additionalProperties: false,
    },
  },
  {
    name: 'record.append',
    description: '起草一份治理记录（写到 audit/mcp-drafts/，不直接进 docs/，避免触发 D1 未登记）。需要 confirm=true。',
    inputSchema: {
      type: 'object',
      properties: {
        title: { type: 'string' },
        body: { type: 'string' },
        confirm: { type: 'boolean' },
      },
      required: ['title', 'body'],
      additionalProperties: false,
    },
  },
]

function callTool(name, args) {
  const a = args || {}
  switch (name) {
    case 'gate.list': {
      const registry = readJson(path.join(GOVERNANCE, 'registry.json'))
      if (!registry) return { isError: true, text: 'registry.json 不可读' }
      const gates = (registry.gates || []).map((g) => ({
        id: g.id, title: g.title, tier: g.tier, baseline: g.baseline || null,
      }))
      return { text: JSON.stringify({ count: gates.length, gates }, null, 2) }
    }
    case 'gate.run': {
      if (a.all === true) {
        const res = run(process.platform === 'win32' ? 'npm.cmd' : 'npm',
          ['run', 'check:governance'], { timeout: a.timeoutMs || 300000 })
        const clean = (res.output.match(/(\d+)\/(\d+) gate\(s\) clean/) || [])[0] || null
        return { text: JSON.stringify({ exit: res.exit, ms: res.ms, cleanSummary: clean, tail: res.tail }, null, 2) }
      }
      if (!a.gate) return { isError: true, text: '需要 gate 或 all=true' }
      const registry = readJson(path.join(GOVERNANCE, 'registry.json'))
      const entry = (registry?.gates || []).find((g) => g.id === a.gate)
      if (!entry) return { isError: true, text: `未登记的门禁 id：${a.gate}` }
      const script = path.join(REPO, 'tools', 'gate', entry.script)
      const res = run(pythonBin(), [script, '--quiet'], { timeout: a.timeoutMs || DEFAULT_TIMEOUT_MS })
      return { text: JSON.stringify({ gate: a.gate, exit: res.exit, ms: res.ms, output: res.tail }, null, 2) }
    }
    case 'registry.query': {
      let entries = listEntries()
      if (a.id) entries = entries.filter((e) => e.id === a.id)
      if (a.category) entries = entries.filter((e) => e.category === a.category)
      const limit = Math.min(a.limit || 20, 200)
      return { text: JSON.stringify({ total: entries.length, entries: entries.slice(0, limit) }, null, 2) }
    }
    case 'registry.verify': {
      const args = ['--workers', '8']
      if (a.only) args.push('--only', a.only)
      if (a.category) args.push('--category', a.category)
      args.push('--limit', String(a.limit || 20))
      const res = run(pythonBin(), [path.join(REPO, 'tools', 'verify_projects.py'), ...args],
        { timeout: a.timeoutMs || 600000 })
      return { text: JSON.stringify({ exit: res.exit, ms: res.ms, tail: res.tail }, null, 2) }
    }
    case 'docs.search': {
      const docs = path.join(REPO, 'docs')
      const hits = []
      const walk = (dir) => {
        for (const name of fs.readdirSync(dir, { withFileTypes: true })) {
          if (name.name === 'md') continue
          const full = path.join(dir, name.name)
          if (name.isDirectory()) { walk(full); continue }
          if (!name.name.endsWith('.md')) continue
          const lines = readLines(full)
          lines.forEach((line, i) => {
            if (line.includes(a.query)) {
              hits.push({ file: path.relative(REPO, full).replace(/\\/g, '/'), line: i + 1, snippet: line.trim().slice(0, 160) })
            }
          })
          if (hits.length >= Math.min(a.limit || 20, 100)) return
        }
      }
      try { walk(docs) } catch (e) { return { isError: true, text: String(e.message) } }
      return { text: JSON.stringify({ query: a.query, hits: hits.slice(0, Math.min(a.limit || 20, 100)) }, null, 2) }
    }
    case 'project.status': {
      const entry = listEntries().find((e) => e.id === a.id)
      if (!entry) return { isError: true, text: `registry 里没有 id：${a.id}` }
      let days = null
      const clone = entry.path ? path.join(REPO, '..', path.basename(entry.path)) : null
      if (clone && fs.existsSync(path.join(clone, '.git'))) {
        const res = run('git', ['log', '-1', '--format=%ct'], { cwd: clone, timeout: 20000 })
        const stamp = Number(String(res.output).trim().split('\n')[0])
        if (Number.isFinite(stamp) && stamp > 0) days = Math.floor((Date.now() / 1000 - stamp) / 86400)
      }
      const report = readJson(path.join(AUDIT_DIR, 'projects_verify.json'))
      const found = report?.results
        ? report.results.find((r) => r.id === a.id || r.project === a.id)
        : null
      return {
        text: JSON.stringify({
          id: entry.id, name: entry.name, category: entry.category,
          path: entry.path, declaredStatus: entry.status || null,
          localClone: Boolean(clone && fs.existsSync(path.join(clone || '', '.git'))),
          daysSinceLastCommit: days,
          lastVerify: found || null,
        }, null, 2),
      }
    }
    case 'record.append': {
      if (a.confirm !== true) {
        return { isError: true, text: '该工具会写文件：请带 confirm=true 再调用一次' }
      }
      const date = new Date().toISOString().slice(0, 10)
      const slug = String(a.title).replace(/[^\w一-龥-]+/g, '-').slice(0, 60)
      const drafts = path.join(AUDIT_DIR, 'mcp-drafts')
      fs.mkdirSync(drafts, { recursive: true })
      const file = path.join(drafts, `${slug}_${date}.md`)
      const body = `> **本文是 ${date} 的一次性记录，不作为约束。**\n\n# ${a.title}\n\n${a.body}\n`
      fs.writeFileSync(file, body, 'utf8')
      fs.appendFileSync(path.join(AUDIT_DIR, 'mcp-actions.jsonl'),
        JSON.stringify({ ts: new Date().toISOString(), tool: name, file: path.relative(REPO, file) }) + '\n', 'utf8')
      return { text: JSON.stringify({ written: path.relative(REPO, file).replace(/\\/g, '/'),
        note: '草稿落在 audit/mcp-drafts/（不进 docs/）；要成为正式记录须由人移入 docs/记录/ 并在 INDEX.md 登记' }, null, 2) }
    }
    default:
      return { isError: true, text: `unknown tool: ${name}` }
  }
}

// ---------------------------------------------------------------- JSON-RPC

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n')
}

function handle(msg) {
  const { id, method, params } = msg || {}
  if (method === 'initialize') {
    return send({
      jsonrpc: '2.0', id,
      result: { protocolVersion: params?.protocolVersion || PROTOCOL, capabilities: { tools: {} }, serverInfo: SERVER_INFO },
    })
  }
  if (method === 'notifications/initialized' || method === 'initialized') return
  if (method === 'ping') return send({ jsonrpc: '2.0', id, result: {} })
  if (method === 'tools/list') return send({ jsonrpc: '2.0', id, result: { tools: TOOLS } })
  if (method === 'tools/call') {
    const name = params?.name
    let result
    try {
      result = callTool(name, params?.arguments || {})
    } catch (e) {
      result = { isError: true, text: String(e && e.message ? e.message : e) }
    }
    return send({
      jsonrpc: '2.0', id,
      result: {
        content: [{ type: 'text', text: result.text || '' }],
        isError: Boolean(result.isError),
      },
    })
  }
  if (typeof id !== 'undefined') {
    send({ jsonrpc: '2.0', id, error: { code: -32601, message: `method not found: ${method}` } })
  }
}

// ---------------------------------------------------------------- entry

const argv = process.argv.slice(2)

if (argv.includes('--selftest')) {
  // Scripted session: exactly what a client does, so the server can prove itself.
  let failures = 0
  const check = (label, ok, detail = '') => {
    if (!ok) { failures += 1; console.log(`FAIL ${label} ${detail}`) } else { console.log(`ok   ${label}`) }
  }
  const captured = []
  // 自检期间把响应截获下来，不污染 stdout
  const origWrite = process.stdout.write.bind(process.stdout)
  process.stdout.write = (chunk) => { captured.push(String(chunk)); return true }
  handle({ id: 1, method: 'initialize', params: { protocolVersion: PROTOCOL } })
  handle({ id: 2, method: 'tools/list' })
  handle({ id: 3, method: 'tools/call', params: { name: 'gate.list', arguments: {} } })
  handle({ id: 4, method: 'tools/call', params: { name: 'registry.query', arguments: { id: 'allin' } } })
  handle({ id: 5, method: 'tools/call', params: { name: 'docs.search', arguments: { query: '门禁', limit: 3 } } })
  handle({ id: 6, method: 'tools/call', params: { name: 'record.append', arguments: { title: 't', body: 'b' } } })
  handle({ id: 7, method: 'tools/call', params: { name: 'nope', arguments: {} } })
  process.stdout.write = origWrite
  const msgs = captured.map((c) => JSON.parse(c.trim()))
  check('initialize 返回 protocolVersion', msgs[0]?.result?.protocolVersion === PROTOCOL)
  check('tools/list 返回 7 个工具', msgs[1]?.result?.tools?.length === 7, `got ${msgs[1]?.result?.tools?.length}`)
  check('gate.list 返回门禁清单', (msgs[2]?.result?.content?.[0]?.text || '').includes('"gates"'))
  check('registry.query 返回结构', (msgs[3]?.result?.content?.[0]?.text || '').includes('"total"'))
  check('docs.search 命中', (msgs[4]?.result?.content?.[0]?.text || '').includes('hits'))
  check('record.append 未确认即拒绝', msgs[5]?.result?.isError === true)
  check('未知工具报 isError', msgs[6]?.result?.isError === true)
  console.log(failures === 0 ? 'SELFTEST OK' : `SELFTEST FAILED (${failures})`)
  process.exit(failures === 0 ? 0 : 1)
}

if (argv.includes('--list-tools')) {
  console.log(JSON.stringify(TOOLS.map((t) => ({ name: t.name, description: t.description })), null, 2))
  process.exit(0)
}

let buffer = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', (chunk) => {
  buffer += chunk
  let index
  while ((index = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, index).trim()
    buffer = buffer.slice(index + 1)
    if (!line) continue
    try {
      handle(JSON.parse(line))
    } catch (e) {
      send({ jsonrpc: '2.0', id: null, error: { code: -32700, message: `parse error: ${e.message}` } })
    }
  }
})
process.stdin.on('end', () => process.exit(0))
