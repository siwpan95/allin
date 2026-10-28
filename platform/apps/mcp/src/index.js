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
  {
    name: 'gate.history',
    description: '汇总门禁执行留痕（gate-runs.jsonl）：总次数 / 失败次数 / 各标签最近一次退出码 / 最近 N 条',
    inputSchema: {
      type: 'object',
      properties: { limit: { type: 'number', description: '最近条数，默认 20' } },
      additionalProperties: false,
    },
  },
  {
    name: 'metrics.snapshot',
    description: '跑 gate_metrics.py --json：逃逸率 / 证据新鲜度 / 例外燃尽 / 门禁性能预算（只读，不落趋势文件）',
    inputSchema: {
      type: 'object',
      properties: { timeoutMs: { type: 'number' } },
      additionalProperties: false,
    },
  },
  {
    name: 'exceptions.list',
    description: '读治理例外台账（exceptions.yml）：每条 id / kind / gate / status / expires，附 open / closed 计数',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'memory.read',
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
    description: '记忆晋升看板（只读）：按 tag 统计有效条目数，把「同 tag ≥ 阈值条且未晋升」的列为固化成专项 skill 的候选，附建议流程',
    inputSchema: {
      type: 'object',
      properties: { threshold: { type: 'number', description: '晋升阈值，默认 3（2–10）' } },
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
      if (!a.gate) return { isError: true, text: '需要 gate 或 all=true' }
      const registry = readJson(path.join(GOVERNANCE, 'registry.json'))
      const entry = (registry?.gates || []).find((g) => g.id === a.gate)
      if (!entry) return { isError: true, text: `未登记的门禁 id：${a.gate}` }
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
      const q = String(a.query || '')
      if (!q) return { isError: true, text: 'query 不能为空' }
      const cap = Math.min(a.limit || 20, 100)
      let skippedNonText = 0
      // 零依赖重排：没有 embedding，就用「命中次数 + 标题/就近小节/文件名加权」排序，
      // 取代原来「按遍历顺序取前 N 条」——那样排在前面的常常只是碰巧先被读到的文件。
      const scored = []
      const walk = (dir) => {
        for (const name of fs.readdirSync(dir, { withFileTypes: true })) {
          if (name.name === 'md') continue
          const full = path.join(dir, name.name)
          if (name.isDirectory()) { walk(full); continue }
          // 只索引 Markdown：PDF / 表格 / 扫描件等二进制一律跳过并如实计数 ——
          // 专用解析引擎（如 RAGflow DeepDoc）与本机零依赖原则冲突，明确不做，
          // 所以**必须把跳过量报出来**，避免 agent 误以为「搜过但没结果」。
          if (!name.name.endsWith('.md')) { skippedNonText += 1; continue }
          const rel = path.relative(REPO, full).replace(/\\/g, '/')
          const nameBonus = name.name.includes(q) ? 2 : 0
          const rootBonus = rel.split('/').length === 2 ? 0.5 : 0
          const lines = readLines(full)
          let heading = ''
          lines.forEach((line, i) => {
            const trimmed = line.trim()
            if (trimmed.startsWith('#')) { heading = trimmed.replace(/^#+\s*/, ''); return }
            if (!line.includes(q)) return
            let score = line.split(q).length - 1
            if (trimmed.startsWith('#')) score += 3
            if (heading && heading.includes(q)) score += 2
            score += nameBonus + rootBonus
            scored.push({
              score, file: rel, line: i + 1,
              section: heading || null,
              snippet: trimmed.slice(0, 160),
            })
          })
        }
      }
      try { walk(docs) } catch (e) { return { isError: true, text: String(e.message) } }
      scored.sort((x, y) => (y.score - x.score) || x.file.localeCompare(y.file) || (x.line - y.line))
      return {
        text: JSON.stringify({
          query: q,
          matched: scored.length,
          ranked: true,
          scoring: '命中次数 + 标题×3 + 就近小节含词×2 + 文件名含词×2 + 根级文档×0.5',
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
    case 'gate.history': {
      const rows = readLines(path.join(AUDIT_DIR, 'gate-runs.jsonl'))
        .filter((l) => l.trim())
        .map((l) => { try { return JSON.parse(l) } catch { return null } })
        .filter(Boolean)
      if (!rows.length) return { isError: true, text: '留痕为空：先跑一次 bash scripts/run_all_gates.sh 再来' }
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
      if (res.exit !== 0) return { isError: true, text: `gate_metrics --json 退出码 ${res.exit}\n${res.tail}` }
      return { text: res.output.trim() || res.tail }
    }
    case 'exceptions.list': {
      let text
      try {
        text = fs.readFileSync(path.join(GOVERNANCE, 'exceptions.yml'), 'utf8')
      } catch {
        return { isError: true, text: 'exceptions.yml 不可读' }
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
      if (!entries.length) return { isError: true, text: 'exceptions.yml 里没有解析到任何 EX-### 条目' }
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
      if (!volumes.length) return { isError: true, text: '记忆目录为空：docs/记录/记忆/ 下还没有月卷' }
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
        return { isError: true, text: '该工具会写文件：请带 confirm=true 再调用一次' }
      }
      const entry = String(a.entry || '').trim()
      if (!entry) return { isError: true, text: 'entry 不能为空' }
      if (entry.length > 2000) return { isError: true, text: `entry 过长（${entry.length} > 2000 字），拆成多条` }
      const layer = a.layer === '永久' ? '永久' : '临时'
      if (a.layer && a.layer !== '临时' && a.layer !== '永久') {
        return { isError: true, text: `layer 只能是 临时 或 永久（收到「${a.layer}」）` }
      }
      const now = new Date()
      const target = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}.md`
      if (!memoryVolumes().includes(target)) {
        return { isError: true, text: `当月卷 ${target} 不存在：开新卷属治理动作，先创建文件并在 docs/INDEX.md §4 登记（D1/D8 会核对），再调用本工具` }
      }
      const indexText = fs.readFileSync(path.join(REPO, 'docs', 'INDEX.md'), 'utf8')
      if (!indexText.includes(`记录/记忆/${target}`)) {
        return { isError: true, text: `当月卷 ${target} 尚未登记进 docs/INDEX.md（D1 会打红）；先登记再写入` }
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
      if (!volumes.length) return { isError: true, text: '记忆目录为空：docs/记录/记忆/ 下还没有月卷' }
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
      return { isError: true, text: `unknown tool: ${name}` }
  }
}

// 追加写工具共用的审计落痕（mcp-actions.jsonl）。
function auditWrite(tool, file) {
  fs.appendFileSync(path.join(AUDIT_DIR, 'mcp-actions.jsonl'),
    JSON.stringify({ ts: new Date().toISOString(), tool, file: path.relative(REPO, file) }) + '\n', 'utf8')
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
  check('gate.list 返回门禁清单', textOf(2).includes('"gates"'))
  check('registry.query 返回结构', textOf(3).includes('"total"'))
  check('docs.search 命中', textOf(4).includes('hits'))
  check('record.append 未确认即拒绝', msgs[5]?.result?.isError === true)
  check('未知工具报 isError', msgs[6]?.result?.isError === true)
  check('gate.history 返回留痕汇总', textOf(7).includes('"total"') || textOf(7).includes('留痕为空'))
  check('exceptions.list 返回例外台账', textOf(8).includes('EX-'))
  check('memory.read 召回月卷', textOf(9).includes('volumes') || textOf(9).includes('记忆目录为空'))
  check('memory.append 未确认即拒绝', msgs[10]?.result?.isError === true)
  check('memory.promotable 返回晋升看板', textOf(11).includes('promotable'))
  check('memory.append 拒绝非法 layer', msgs[12]?.result?.isError === true)
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
