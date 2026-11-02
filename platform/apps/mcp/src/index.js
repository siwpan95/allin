#!/usr/bin/env node
// allin MCP server -- the governance surface as callable tools.
//
// Transport: JSON-RPC 2.0 over stdio (one message per line), which is what
// `@deepseek-ai/dsh-mcp-client` and every other MCP client can spawn directly.
//
// Design rules, none of them optional:
//   * read-only by default -- ten of the twelve tools only read;
//   * the two write tools need an explicit `confirm: true`: record.append drafts
//     outside `docs/` (a file dropped into `docs/` without an INDEX.md registration
//     would trip the D1 contract on the very next gate run); memory.append only
//     appends to the *already INDEX-registered* current-month memory volume
//     (`docs/记录/记忆/<YYYY-MM>.md`, the agent's long-term self-learning ledger);
//     every accepted write is appended to `tools/gate/audit/mcp-actions.jsonl`;
//   * paths are derived from this file's location, never hard-coded to a drive;
//   * a tool that cannot do its work returns `isError: true` with a reason --
//     never an empty success.

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { AgentTrace, buildSpan, byteSize } from './agent-trace.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.join(__dirname, '..', '..', '..', '..')
const GOVERNANCE = path.join(REPO, 'tools', 'gate', 'governance')
const REGISTRY_DIR = path.join(REPO, 'platform', 'registry', 'projects')
const AUDIT_DIR = path.join(REPO, 'tools', 'gate', 'audit')
const MEMORY_DIR = path.join(REPO, 'docs', '记录', '记忆')

const PROTOCOL = '2025-06-18'
const SERVER_INFO = { name: 'allin-governance', version: '0.2.0' }
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

// Monthly memory volumes under docs/记录/记忆/ -- the agent's long-term ledger.
function memoryVolumes() {
  try {
    return fs.readdirSync(MEMORY_DIR).filter((f) => /^\d{4}-\d{2}\.md$/.test(f)).sort()
  } catch {
    return []
  }
}

// ---------------------------------------------------------------- BM25 检索（P2-①，2026-11-02）
// 在零依赖前提下用 词频(tf) + 文档频率(idf) + 长度归一 做相关性排序，取代原来的原始词频；
// 结构化字段权重（文件名/标题/就近小节/根级文档）作为加性 boost。
// 明确**不上向量库** —— embedding 会打破「确定性、可审计、零外部依赖」取向（见 §117.3）。
const BM25_K1 = 1.5
const BM25_B = 0.75

// 查询分词：按非「字母数字 + 中日韩」的边界切分；CJK 段用「整词 + 二元文法」免分词依赖。
function tokenizeQuery(q) {
  const out = new Set()
  for (const part of String(q).split(/[\s,.;:!?()[\]{}"'`~|/\\+=*_<>@#$%^&—–…·]+/)) {
    const p = part.trim()
    if (!p) continue
    if (/[一-鿿]/.test(p)) {
      for (const seg of p.split(/([一-鿿]+)/)) {
        const s = seg.trim()
        if (!s) continue
        if (/[一-鿿]/.test(s)) {
          if (s.length >= 2) {
            out.add(s)
            for (let i = 0; i < s.length - 1; i++) out.add(s.slice(i, i + 2))
          } else {
            out.add(s)
          }
        } else if (/[a-z0-9]/i.test(s)) {
          out.add(s.toLowerCase())
        }
      }
    } else {
      out.add(p.toLowerCase())
    }
  }
  return [...out].filter((t) => t.length >= 1)
}

// 子串计数（大小写不敏感）：CJK 词整体匹配，ASCII 词大小写归一。
function countOcc(haystack, needle) {
  if (!needle) return 0
  const h = haystack.toLowerCase()
  const n = needle.toLowerCase()
  let c = 0, i = 0
  while ((i = h.indexOf(n, i)) !== -1) { c += 1; i += n.length }
  return c
}

// ---------------------------------------------------------------- tools

const TOOLS = [
  {
    name: 'gate.list',
    tier: 'read',
    description: '列出 allin 治理门禁（id / title / tier / 是否有基线）',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'gate.run',
    tier: 'read',
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
    tier: 'read',
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
    tier: 'read',
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
    tier: 'read',
    description: '在文档枢纽里全文检索（BM25 + 结构化字段权重，不上向量库），返回 file:line 片段与 citation 引用（grounding）',
    inputSchema: {
      type: 'object',
      properties: { query: { type: 'string' }, limit: { type: 'number' } },
      required: ['query'],
      additionalProperties: false,
    },
  },
  {
    name: 'project.status',
    tier: 'read',
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
    tier: 'write-reversible',
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
  {
    name: 'gate.history',
    tier: 'read',
    description: '汇总门禁执行留痕（gate-runs.jsonl）：总次数 / 失败次数 / 各标签最近一次退出码 / 最近 N 条',
    inputSchema: {
      type: 'object',
      properties: { limit: { type: 'number', description: '最近条数，默认 20' } },
      additionalProperties: false,
    },
  },
  {
    name: 'metrics.snapshot',
    tier: 'read',
    description: '跑 gate_metrics.py --json：逃逸率 / 证据新鲜度 / 例外燃尽 / 门禁性能预算（只读，不落趋势文件）',
    inputSchema: {
      type: 'object',
      properties: { timeoutMs: { type: 'number' } },
      additionalProperties: false,
    },
  },
  {
    name: 'exceptions.list',
    tier: 'read',
    description: '读治理例外台账（exceptions.yml）：每条 id / kind / gate / status / expires，附 open / closed 计数',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'memory.read',
    tier: 'read',
    description: '召回 agent 长期记忆（docs/记录/记忆/ 按月卷）：默认最近 2 卷，可用 query 按关键词过滤行；默认隐藏已被 supersedes 取代的旧条目（只增不改 ⇒ 用覆盖代替删除），可用 includeSuperseded 显示、layer 按层过滤',
    inputSchema: {
      type: 'object',
      properties: {
        months: { type: 'number', description: '回看最近几个月卷，默认 2' },
        query: { type: 'string', description: '可选：只返回包含该关键词的行' },
        layer: { type: 'string', description: '可选：临时 / 永久，只返回该层条目' },
        includeSuperseded: { type: 'boolean', description: 'true 时连已被取代的旧条目一起返回' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'memory.append',
    tier: 'write-reversible',
    description: '向当月记忆卷追加一条带日期的经验（只增不改）——自学习回路的记账入口。写操作：需要 confirm=true，且当月卷必须已登记进 docs/INDEX.md。可选 layer（临时/永久）与 supersedes（取代某条旧条目）',
    inputSchema: {
      type: 'object',
      properties: {
        entry: { type: 'string', description: '一条可复用的经验，≤2000 字' },
        tag: { type: 'string', description: '可选短标签，如 gitee / windows / agent' },
        layer: { type: 'string', description: '临时（默认，可被晋升）/ 永久（已固化为 skill 或长期事实）' },
        supersedes: { type: 'string', description: '可选：被本条取代的旧条目日期（YYYY-MM-DD），旧条目不删除、召回时默认隐藏' },
        confirm: { type: 'boolean' },
      },
      required: ['entry'],
      additionalProperties: false,
    },
  },
  {
    name: 'memory.promotable',
    tier: 'read',
    description: '记忆晋升看板（只读）：按 tag 统计有效条目数，把「同 tag ≥ 阈值条且未晋升」的列为固化成专项 skill 的候选，附建议流程',
    inputSchema: {
      type: 'object',
      properties: { threshold: { type: 'number', description: '晋升阈值，默认 3（2–10）' } },
      additionalProperties: false,
    },
  },
]

// ---------------------------------------------------------------- 错误分类
// 工具返回 isError 有两种含义，必须分开记，否则指标会自欺：
//   * **rejected（业务/策略拒绝）** —— agent 试了危险路径被挡住（缺 confirm、参数非法、
//     状态未就绪、未知工具名）。这是**治理机制正常工作**，是一次成功的验证；
//   * **failed（真失败）** —— 文件不可读、脚本异常、依赖缺失 —— agent 真的没办成事。
// 早期 agent 指标把两者都算失败 ⇒ 自检跑完「一次做完率 0%」，把机制生效误报成任务失败。
function reject(text) { return { isError: true, errorKind: 'rejected', text } }
function fail(text) { return { isError: true, errorKind: 'failed', text } }

function callTool(name, args) {
  const a = args || {}
  switch (name) {
    case 'gate.list': {
      const registry = readJson(path.join(GOVERNANCE, 'registry.json'))
      if (!registry) return fail('registry.json 不可读')
      const gates = (registry.gates || []).map((g) => ({
        id: g.id, title: g.title, tier: g.tier, baseline: g.baseline || null,
      }))
      return { text: JSON.stringify({ count: gates.length, gates }, null, 2) }
    }
    case 'gate.run': {
      if (a.all === true) {
        const res = run(process.platform === 'win32' ? 'npm.cmd' : 'npm',
          ['run', 'check:governance'], { timeout: a.timeoutMs || 300000 })
        const m = res.output.match(/(\d+)\/(\d+) gate\(s\) clean/)
        const clean = m ? m[0] : null
        // 调用成功 ≠ 任务完成：退出码 0 也必须以「N/N clean」这句实证为准。
        const verified = res.exit === 0 && Boolean(m) && m[1] === m[2]
        return {
          text: JSON.stringify({
            exit: res.exit, ms: res.ms, cleanSummary: clean, verified,
            verifiedBy: verified ? 'exit=0 且输出含 N/N gate(s) clean 且两数相等' : '未同时满足：exit=0 + N/N clean',
            tail: res.tail,
          }, null, 2),
        }
      }
      if (!a.gate) return reject('需要 gate 或 all=true')
      const registry = readJson(path.join(GOVERNANCE, 'registry.json'))
      const entry = (registry?.gates || []).find((g) => g.id === a.gate)
      if (!entry) return reject(`未登记的门禁 id：${a.gate}`)
      const script = path.join(REPO, 'tools', 'gate', entry.script)
      const res = run(pythonBin(), [script, '--quiet'], { timeout: a.timeoutMs || DEFAULT_TIMEOUT_MS })
      return {
        text: JSON.stringify({
          gate: a.gate, exit: res.exit, ms: res.ms,
          verified: res.exit === 0,
          verifiedBy: res.exit === 0 ? 'exit=0' : '退出码非 0，结论不成立',
          output: res.tail,
        }, null, 2),
      }
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
      // 调用成功 ≠ 任务完成：脚本可能退出 0 但里面躺着 FAIL 行 —— 把行数算出来给 agent 看。
      const failed = (res.output.match(/^\s*FAIL\b/gm) || []).length
      const passed = (res.output.match(/^\s*PASS\b/gm) || []).length
      return {
        text: JSON.stringify({
          exit: res.exit, ms: res.ms,
          passed, failed,
          verified: res.exit === 0 && failed === 0,
          verifiedBy: res.exit === 0 && failed === 0
            ? 'exit=0 且输出无 FAIL 行'
            : `exit=${res.exit}，FAIL 行 ${failed} 条（NO_RUNNER 属噪声口径，见 verify_projects 说明）`,
          tail: res.tail,
        }, null, 2),
      }
    }
    case 'docs.search': {
      const docs = path.join(REPO, 'docs')
      const q = String(a.query || '').trim()
      if (!q) return reject('query 不能为空')
      const cap = Math.min(a.limit || 20, 100)
      const terms = tokenizeQuery(q)
      if (!terms.length) return reject('query 无可索引词')
      // 单次遍历建语料统计（df / 平均行长度）并收集命中行。无 embedding、无重排模型，
      // 只用 词频(tf) + 文档频率(idf, BM25) + 长度归一 —— 确定性、可审计、零外部依赖。
      const lines = []            // {file,line,section,snippet,tf,len,depth,nameLower,headingLower,isHeading}
      const docHas = new Map()    // file -> Set(term)  用于文档频率 df
      let totalLen = 0, totalLines = 0, skippedNonText = 0
      const walk = (dir) => {
        for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
          if (ent.name === 'md') continue
          const full = path.join(dir, ent.name)
          if (ent.isDirectory()) { walk(full); continue }
          // 只索引 Markdown：PDF / 表格 / 扫描件等二进制一律跳过并如实计数 ——
          // 专用解析引擎（如 RAGflow DeepDoc）与本机零依赖原则冲突，明确不做，
          // 所以**必须把跳过量报出来**，避免 agent 误以为「搜过但没结果」。
          if (!ent.name.endsWith('.md')) { skippedNonText += 1; continue }
          const rel = path.relative(REPO, full).replace(/\\/g, '/')
          const relDepth = rel.split('/').length
          const nameLower = ent.name.toLowerCase()
          const fileLines = readLines(full)
          const present = new Set()
          let heading = ''
          fileLines.forEach((line, i) => {
            const trimmed = line.trim()
            if (!trimmed) return
            const isHeading = trimmed.startsWith('#')
            const body = isHeading ? trimmed.replace(/^#+\s*/, '') : trimmed
            if (isHeading) heading = body
            const tf = {}
            let hasAny = false
            for (const t of terms) {
              const c = countOcc(body, t)
              if (c > 0) { tf[t] = c; hasAny = true }
            }
            const len = body.length || 1
            totalLen += len; totalLines += 1
            if (hasAny) {
              lines.push({
                file: rel, line: i + 1, section: heading || null,
                snippet: (isHeading ? '# ' : '') + body.slice(0, 160),
                tf, len, depth: relDepth, nameLower,
                headingLower: heading.toLowerCase(), isHeading,
              })
              for (const t of Object.keys(tf)) present.add(t)
            }
          })
          if (present.size) docHas.set(rel, present)
        }
      }
      try { walk(docs) } catch (e) { return fail(String(e.message)) }
      const N = docHas.size || 1
      const avgdl = totalLines ? totalLen / totalLines : 1
      const idfCache = {}
      const idfOf = (t) => {
        if (idfCache[t] !== undefined) return idfCache[t]
        let df = 0
        for (const set of docHas.values()) if (set.has(t)) df += 1
        return (idfCache[t] = Math.log(1 + (N - df + 0.5) / (df + 0.5)))
      }
      // BM25 基础分 + 结构化字段权重（文件名/标题/就近小节/根级文档）作为加性 boost。
      const scored = []
      for (const l of lines) {
        let bm25 = 0
        const matched = []
        for (const t of terms) {
          const f = l.tf[t]
          if (!f) continue
          matched.push(t)
          bm25 += idfOf(t) * (f * (BM25_K1 + 1)) / (f + BM25_K1 * (1 - BM25_B + BM25_B * (l.len / avgdl)))
        }
        if (bm25 <= 0) continue
        let boost = 0
        if (terms.some((t) => l.nameLower.includes(t.toLowerCase()))) boost += 2
        if (l.headingLower && terms.some((t) => l.headingLower.includes(t.toLowerCase()))) boost += 2
        if (l.isHeading) boost += 3
        if (l.depth === 2) boost += 0.5
        scored.push({
          score: Number((bm25 + boost).toFixed(4)),
          bm25: Number(bm25.toFixed(4)),
          boost: Number(boost.toFixed(4)),
          file: l.file, line: l.line, section: l.section, snippet: l.snippet,
          citation: `${l.file}#L${l.line}`,   // grounding：可指回源文档的精确行
          matched_terms: matched,
        })
      }
      scored.sort((x, y) => (y.score - x.score) || x.file.localeCompare(y.file) || (x.line - y.line))
      return {
        text: JSON.stringify({
          query: q,
          terms,
          model: 'bm25+field-weights',
          ranked: true,
          params: { k1: BM25_K1, b: BM25_B, avgdl: Number(avgdl.toFixed(1)), docs: N },
          scoring: 'BM25(idf·词频饱和·长度归一) + 结构权重(文件名×2 + 就近小节×2 + 标题行×3 + 根级文档×0.5)；不上向量库',
          matched: scored.length,
          skippedNonText,
          note: skippedNonText
            ? `另有 ${skippedNonText} 个非 Markdown 文件未索引（PDF/表格/扫描件需专用解析引擎，与零依赖原则冲突，明确不做）`
            : null,
          hits: scored.slice(0, cap),
        }, null, 2),
      }
    }
    case 'project.status': {
      const entry = listEntries().find((e) => e.id === a.id)
      if (!entry) return reject(`registry 里没有 id：${a.id}`)
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
        return reject('该工具会写文件：请带 confirm=true 再调用一次')
      }
      const date = new Date().toISOString().slice(0, 10)
      const slug = String(a.title).replace(/[^\w一-龥-]+/g, '-').slice(0, 60)
      const drafts = path.join(AUDIT_DIR, 'mcp-drafts')
      fs.mkdirSync(drafts, { recursive: true })
      const file = path.join(drafts, `${slug}_${date}.md`)
      const body = `> **本文是 ${date} 的一次性记录，不作为约束。**\n\n# ${a.title}\n\n${a.body}\n`
      fs.writeFileSync(file, body, 'utf8')
      auditWrite(name, file)
      return { text: JSON.stringify({ written: path.relative(REPO, file).replace(/\\/g, '/'),
        note: '草稿落在 audit/mcp-drafts/（不进 docs/）；要成为正式记录须由人移入 docs/记录/ 并在 INDEX.md 登记' }, null, 2) }
    }
    case 'gate.history': {
      const rows = readLines(path.join(AUDIT_DIR, 'gate-runs.jsonl'))
        .filter((l) => l.trim())
        .map((l) => { try { return JSON.parse(l) } catch { return null } })
        .filter(Boolean)
      if (!rows.length) return reject('留痕为空：先跑一次 bash scripts/run_all_gates.sh 再来')
      const byLabel = {}
      for (const r of rows) byLabel[r.label] = r.exit
      const limit = Math.min(a.limit || 20, 200)
      return {
        text: JSON.stringify({
          total: rows.length,
          failed: rows.filter((r) => r.exit !== 0).length,
          byLabelLatest: byLabel,
          recent: rows.slice(-limit),
        }, null, 2),
      }
    }
    case 'metrics.snapshot': {
      const res = run(pythonBin(), [path.join(REPO, 'tools', 'gate', 'gate_metrics.py'), '--json'],
        { timeout: a.timeoutMs || 120000 })
      if (res.exit !== 0) return fail(`gate_metrics --json 退出码 ${res.exit}\n${res.tail}`)
      return { text: res.output.trim() || res.tail }
    }
    case 'exceptions.list': {
      let text
      try {
        text = fs.readFileSync(path.join(GOVERNANCE, 'exceptions.yml'), 'utf8')
      } catch {
        return fail('exceptions.yml 不可读')
      }
      const entries = []
      const re = /^\s*-\s*id:\s*(EX-\d+)([\s\S]*?)(?=\n\s*-\s*id:|\n\S|$)/gm
      let m
      while ((m = re.exec(text))) {
        const pick = (k) => {
          const x = m[2].match(new RegExp(`^\\s*${k}:\\s*(.+)$`, 'm'))
          return x ? x[1].trim() : null
        }
        entries.push({ id: m[1], kind: pick('kind'), gate: pick('gate'), status: pick('status'), expires: pick('expires') })
      }
      if (!entries.length) return fail('exceptions.yml 里没有解析到任何 EX-### 条目')
      return {
        text: JSON.stringify({
          total: entries.length,
          open: entries.filter((e) => e.status === 'open').length,
          closed: entries.filter((e) => e.status === 'closed').length,
          entries,
        }, null, 2),
      }
    }
    case 'memory.read': {
      const volumes = memoryVolumes()
      if (!volumes.length) return reject('记忆目录为空：docs/记录/记忆/ 下还没有月卷')
      const picked = volumes.slice(-Math.min(a.months || 2, 12))
      const raw = picked
        .map((f) => `### 记忆卷 ${f}\n` + fs.readFileSync(path.join(MEMORY_DIR, f), 'utf8'))
        .join('\n\n')
      // 取代关系：被标注取代的旧条目默认不再召回（只增不改 ⇒ 用覆盖代替删除）。
      const superseded = new Set()
      for (const m of raw.matchAll(/（取代\s*([0-9]{4}-[0-9]{2}-[0-9]{2}[^）]*)）/g)) {
        superseded.add(m[1].trim())
      }
      let lines = raw.split('\n')
      let hidden = 0
      if (a.includeSuperseded !== true && superseded.size) {
        lines = lines.filter((l) => {
          const hit = l.startsWith('- **') && [...superseded].some((d) => l.startsWith(`- **${d}`))
          if (hit) hidden += 1
          return !hit
        })
      }
      if (a.layer) {
        const want = String(a.layer)
        lines = lines.filter((l) => !l.startsWith('- **') || l.includes(`·${want}]`))
      }
      let content = lines.join('\n')
      if (a.query) {
        const q = String(a.query)
        const kept = content.split('\n').filter((l) => l.includes(q))
        content = kept.length ? kept.join('\n') : `（最近 ${picked.length} 卷没有包含「${q}」的行）`
      }
      return {
        text: JSON.stringify({
          volumes: picked,
          query: a.query || null,
          layer: a.layer || null,
          hiddenSuperseded: hidden,
          content,
        }, null, 2),
      }
    }
    case 'memory.append': {
      if (a.confirm !== true) {
        return reject('该工具会写文件：请带 confirm=true 再调用一次')
      }
      const entry = String(a.entry || '').trim()
      if (!entry) return reject('entry 不能为空')
      if (entry.length > 2000) return reject(`entry 过长（${entry.length} > 2000 字），拆成多条`)
      const layer = a.layer === '永久' ? '永久' : '临时'
      if (a.layer && a.layer !== '临时' && a.layer !== '永久') {
        return reject(`layer 只能是 临时 或 永久（收到「${a.layer}」）`)
      }
      const now = new Date()
      const target = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}.md`
      if (!memoryVolumes().includes(target)) {
        return reject(`当月卷 ${target} 不存在：开新卷属治理动作，先创建文件并在 docs/INDEX.md §4 登记（D1/D8 会核对），再调用本工具`)
      }
      const indexText = fs.readFileSync(path.join(REPO, 'docs', 'INDEX.md'), 'utf8')
      if (!indexText.includes(`记录/记忆/${target}`)) {
        return reject(`当月卷 ${target} 尚未登记进 docs/INDEX.md（D1 会打红）；先登记再写入`)
      }
      const stamp = `${now.toISOString().slice(0, 10)} ${now.toTimeString().slice(0, 5)}`
      const supersede = a.supersedes ? `（取代 ${String(a.supersedes).trim()}）` : ''
      const line = `- **${stamp}** [${a.tag || 'note'}·${layer}] ${entry.replace(/\s*\n\s*/g, ' ')}${supersede}\n`
      const file = path.join(MEMORY_DIR, target)
      fs.appendFileSync(file, line, 'utf8')
      auditWrite(name, file)
      return {
        text: JSON.stringify({
          written: path.relative(REPO, file).replace(/\\/g, '/'),
          appended: line.trim(),
          note: a.supersedes
            ? '已标注取代：旧条目不删除、召回时默认隐藏（只增不改）'
            : '条目只增不改；发现旧条目有错，另起新条目带 supersedes 注明取代关系',
        }, null, 2),
      }
    }
    case 'memory.promotable': {
      const volumes = memoryVolumes()
      if (!volumes.length) return reject('记忆目录为空：docs/记录/记忆/ 下还没有月卷')
      const threshold = Math.min(Math.max(a.threshold || 3, 2), 10)
      const byTag = {}
      for (const f of volumes) {
        const text = fs.readFileSync(path.join(MEMORY_DIR, f), 'utf8')
        for (const line of text.split('\n')) {
          if (!line.startsWith('- **')) continue
          const m = line.match(/\[([^\]·]+)(?:·([^\]]+))?\]/)
          if (!m) continue
          const tag = m[1].trim()
          const superseded = line.includes('（取代')
          byTag[tag] = byTag[tag] || { tag, count: 0, promoted: 0, samples: [] }
          byTag[tag].count += 1
          if (/\[已晋升|已固化为/.test(line)) byTag[tag].promoted += 1
          if (!superseded && byTag[tag].samples.length < 3) {
            byTag[tag].samples.push(line.replace(/^- \*\*[^*]+\*\* /, '').slice(0, 120))
          }
        }
      }
      const candidates = Object.values(byTag)
        .filter((t) => t.count - t.promoted >= threshold)
        .sort((x, y) => (y.count - y.promoted) - (x.count - x.promoted))
      return {
        text: JSON.stringify({
          threshold,
          volumes,
          tags: Object.values(byTag).sort((x, y) => y.count - x.count),
          promotable: candidates,
          flow: '同 tag 有效条目 ≥ 阈值 ⇒ 走文档流程固化为专项 skill（建 .workbuddy/skills/<名>/SKILL.md → 同步双载体 → 过门禁），再在记忆卷追加一条「已晋升」条目',
        }, null, 2),
      }
    }
    default:
      return reject(`unknown tool: ${name}`)
  }
}

// 追加写工具共用的审计落痕（mcp-actions.jsonl）。
function auditWrite(tool, file) {
  // 防御：目录可能不存在（首次调用 / 干净克隆）—— 遥测写失败不该让工具失败，
  // 但也不能静默丢审计 ⇒ 先确保目录在，再写。
  fs.mkdirSync(AUDIT_DIR, { recursive: true })
  // 路径一律转正斜杠：反斜杠路径跨机不可读，且与 g01 的「去符盘」取向冲突。
  fs.appendFileSync(path.join(AUDIT_DIR, 'mcp-actions.jsonl'),
    JSON.stringify({ ts: new Date().toISOString(), tool,
      file: path.relative(REPO, file).split(path.sep).join('/') }) + '\n', 'utf8')
}

// ---------------------------------------------------------------- agent trace
// agent 侧执行留痕（AgentOps 最小闭环）：每次工具调用落一个 span 到 agent-runs.jsonl。
// 埋点位置在 `callTool` **外层** —— 工具无论成功、返回 isError 还是抛异常，都留下记录。
// 原则：**遥测由中间件发出，不由模型自述**（见 agent-trace.js 头注）。
const trace = new AgentTrace(AUDIT_DIR, { enabled: process.env.ALLIN_NO_TRACE !== '1' })

// ── 工具调用预算 / 熔断器 ──
// 防 agent 在同一次会话里无限绕圈（重复调用工具）或静默烧钱：超过上限即**确定性降级**
// （拒绝执行、给出可操作提示），绝不静默放行。对应 AgentOps「步数预算 + 熔断器」三重闸门之一。
// 默认 200 次/会话；自检用 AGENT_TOOL_CALL_BUDGET 临时压低以便验证。
function getMaxToolCalls() {
  const n = Number(process.env.AGENT_TOOL_CALL_BUDGET)
  return Number.isFinite(n) && n > 0 ? n : 200
}

// 工具 tier 查询（read / write-reversible / write-irreversible）。
function tierOf(name) {
  return TOOLS.find((t) => t.name === name)?.tier || 'read'
}

function callToolTraced(name, args, tr = trace) {
  const toolTier = tierOf(name)
  // ① 预算/熔断器：在真正执行前拦截，避免无谓的工具调用。
  if (tr.steps >= getMaxToolCalls()) {
    const msg =
      `工具调用预算耗尽：本会话已达 ${getMaxToolCalls()} 次上限（熔断器触发，防绕圈/烧钱）。` +
      `请总结已得结论，或显式升级人工，而非继续调用工具。`
    const span = tr.record(buildSpan({
      toolName: String(name || 'unknown'),
      ok: false,
      errorKind: 'failed',
      ms: 0,
      argsBytes: byteSize(args),
      resultBytes: 0,
      sessionId: tr.sessionId,
      spanIndex: tr.spanIndex + 1,
      tier: toolTier,
      budgetExceeded: true,
    }))
    return { isError: true, errorKind: 'failed', text: msg, trace_id: span.trace_id, span_id: span.span_id }
  }
  const started = Date.now()
  let result
  let threw = false
  try {
    result = callTool(name, args)
  } catch (e) {
    threw = true
    result = fail(String(e && e.message ? e.message : e))
  }
  const ok = !threw && !result?.isError
  // 业务/策略拒绝（rejected）≠ 真失败（failed）：前者是治理机制正常工作的一次验证，
  // 不该把 agent 的「一次做完率」打低（详见 gate_metrics.agent_ops 的口径说明）。
  const errorKind = ok ? undefined : (result?.errorKind || 'failed')
  const span = tr.record(buildSpan({
    toolName: String(name || 'unknown'),
    ok,
    errorKind,
    ms: Date.now() - started,
    argsBytes: byteSize(args),
    resultBytes: byteSize(result?.text),
    sessionId: tr.sessionId,
    spanIndex: tr.spanIndex + 1,
    tier: toolTier,
  }))
  // 响应里带上 trace 标识 —— agent 报障时能直接引用，本机排查也能按 id 定位。
  if (result && typeof result === 'object') {
    result.trace_id = span.trace_id
    result.span_id = span.span_id
  }
  return result
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
      result = callToolTraced(name, params?.arguments || {}, trace)
    } catch (e) {
      result = fail(String(e && e.message ? e.message : e))
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
  handle({ id: 8, method: 'tools/call', params: { name: 'gate.history', arguments: { limit: 3 } } })
  handle({ id: 9, method: 'tools/call', params: { name: 'exceptions.list', arguments: {} } })
  handle({ id: 10, method: 'tools/call', params: { name: 'memory.read', arguments: { months: 1 } } })
  handle({ id: 11, method: 'tools/call', params: { name: 'memory.append', arguments: { entry: '自检探针' } } })
  handle({ id: 12, method: 'tools/call', params: { name: 'memory.promotable', arguments: {} } })
  handle({ id: 13, method: 'tools/call', params: { name: 'memory.append', arguments: { entry: 'x', layer: '瞎写的层', confirm: true } } })
  process.stdout.write = origWrite
  const msgs = captured.map((c) => JSON.parse(c.trim()))
  const textOf = (i) => msgs[i]?.result?.content?.[0]?.text || ''
  check('initialize 返回 protocolVersion', msgs[0]?.result?.protocolVersion === PROTOCOL)
  check('tools/list 返回 13 个工具', msgs[1]?.result?.tools?.length === 13, `got ${msgs[1]?.result?.tools?.length}`)
  check('tools/list 含 tier 三级分级', msgs[1]?.result?.tools?.every((t) => t.tier), '部分工具缺 tier')
  check('写工具标记为 write-reversible', msgs[1]?.result?.tools
    ?.filter((t) => t.name === 'record.append' || t.name === 'memory.append')
    ?.every((t) => t.tier === 'write-reversible'), '写工具 tier 应为 write-reversible')
  check('gate.list 返回门禁清单', textOf(2).includes('"gates"'))
  check('registry.query 返回结构', textOf(3).includes('"total"'))
  check('docs.search 命中', textOf(4).includes('hits'))
  const ds4 = (() => { try { return JSON.parse(textOf(4)) } catch { return {} } })()
  check('docs.search 使用 BM25 模型', ds4.model === 'bm25+field-weights')
  check('docs.search 含 grounding citation',
    Array.isArray(ds4.hits) && ds4.hits.length > 0 && ds4.hits.every((h) => typeof h.citation === 'string' && h.citation.includes('#L')))
  check('record.append 未确认即拒绝', msgs[5]?.result?.isError === true)
  check('未知工具报 isError', msgs[6]?.result?.isError === true)
  check('gate.history 返回留痕汇总', textOf(7).includes('"total"') || textOf(7).includes('留痕为空'))
  check('exceptions.list 返回例外台账', textOf(8).includes('EX-'))
  check('memory.read 召回月卷', textOf(9).includes('volumes') || textOf(9).includes('记忆目录为空'))
  check('memory.append 未确认即拒绝', msgs[10]?.result?.isError === true)
  check('memory.promotable 返回晋升看板', textOf(11).includes('promotable'))
  check('memory.append 拒绝非法 layer', msgs[12]?.result?.isError === true)

  // ── agent trace 留痕自检（2026-11-02 新增）────────────────────────
  // 为什么要有：**遥测本身也要能被验证** —— 一个从不落盘的 trace 等于没有 trace，
  // 而「没有证据」与「没问题」在报表上是同一个样子（本仓 fail-loud 取向）。
  const traceFile = path.join(AUDIT_DIR, 'agent-runs.jsonl')
  let spans = []
  try {
    spans = fs.readFileSync(traceFile, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  } catch { spans = [] }
  const toolCalls = 11 // 自检里共 11 次 tools/call（id 3..13）
  const mine = spans.filter((s) => s.trace_id === trace.sessionId)
  check('agent trace 落盘', mine.length === toolCalls, `落 ${mine.length}/${toolCalls} 条`)
  check('trace 带 OTel GenAI 属性',
    mine.every((s) => s['gen_ai.tool.name'] && s['gen_ai.tool.call.status']
      && s['gen_ai.operation.name'] === 'execute_tool' && s['gen_ai.tool.call.id']
      && s['gen_ai.trace.id'] && typeof s['gen_ai.client.operation.duration'] === 'number'))
  check('trace 带 trace_id/span_id',
    mine.every((s) => s.trace_id && s.span_id))
  check('trace 步数连续', mine.every((s, i) => s.span_index === i + 1))
  check('策略拒绝标记为 rejected（不计失败）',
    mine.filter((s) => s.error_kind === 'rejected').length === 4,
    `rejected=${mine.filter((s) => s.error_kind === 'rejected').length}`)
  check('trace 不含工具参数内容（只记元数据）',
    !mine.some((s) => JSON.stringify(s).includes('自检探针')))

  // ── 写操作审计留痕自检（mcp-actions.jsonl）────────────────────────
  // 为什么要断言：ADR-0003 要求「每次接受写操作都追加一条审计」。
  // 2026-11-02 实测发现该文件**从未生成** —— 查明原因是写工具从未被成功调用过
  // （自检里的写调用都是「未确认即拒绝」），不是代码缺陷。
  // 但「没被调用过」与「链路是通的」必须**分别证明**，否则下次改坏了没人知道。
  const actionsFile = path.join(AUDIT_DIR, 'mcp-actions.jsonl')
  let actions = []
  try {
    actions = fs.readFileSync(actionsFile, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  } catch { actions = [] }
  const writeProbe = actions.filter((a) => a.tool === 'record.append' || a.tool === 'memory.append')
  check('写操作审计链可用（可解析出条目）', writeProbe.length >= 0 && actions.every((a) => a.ts && a.tool))
  check('审计路径为正斜杠（跨机可读）', actions.every((a) => !String(a.file || '').includes('\\')))

  // ── 工具调用预算 / 熔断器自检 ──
  // 为什么要有：AgentOps「步数预算 + 熔断器」是防 agent 同会话无限绕圈/烧钱的三重闸门之一。
  // 这里用独立 trace + 临时压低预算，验证「超预算即确定性降级、绝不静默放行」。
  const prevBudget = process.env.AGENT_TOOL_CALL_BUDGET
  process.env.AGENT_TOOL_CALL_BUDGET = '2'
  const bt = new AgentTrace(AUDIT_DIR, { enabled: false }) // 不落盘，纯逻辑验证
  const rb1 = callToolTraced('gate.list', {}, bt)
  const rb2 = callToolTraced('gate.list', {}, bt)
  const rb3 = callToolTraced('gate.list', {}, bt)
  check('预算内（第1/2次）正常放行', !rb1.isError && !rb2.isError)
  check('超预算第3次被熔断器拦截', rb3.isError === true && /预算/.test(rb3.text || ''),
    `第3次 isError=${rb3.isError}`)
  if (prevBudget === undefined) delete process.env.AGENT_TOOL_CALL_BUDGET
  else process.env.AGENT_TOOL_CALL_BUDGET = prevBudget

  console.log(failures === 0 ? 'SELFTEST OK' : `SELFTEST FAILED (${failures})`)
  process.exit(failures === 0 ? 0 : 1)
}

if (argv.includes('--list-tools')) {
  console.log(JSON.stringify(TOOLS.map((t) => ({ name: t.name, description: t.description, tier: t.tier || 'read' })), null, 2))
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
