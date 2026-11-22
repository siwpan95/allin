/**
 * 内置插件：门禁红项
 *
 * 读门禁留痕（`tools/gate/audit/gate-runs.jsonl`），把最近一次各门禁的
 * 通过/失败摆出来 —— 免得每次都去翻 JSONL。
 *
 * 两种消费方式（同一份数据）：
 *   · 命令面板 `gate.reds`（P2）
 *   · 侧栏常驻面板 `governance.gates`（P3）
 *
 * ⚠ 批次完整性（2026-11-22 实测踩到）：
 *   留痕按 `batch` 分组，但**批次会被中断**——跑批中途 Ctrl-C 会留下一个
 *   只有 30 道门禁的残缺批次（正常是 48 道）。若直接取「最后一批」，
 *   一个被打断的批次会被当成「门禁全绿」，是**假绿**。
 *   ⇒ 取批次时按「门禁数最多的那个」为准（成熟批次），并把残缺批次单独报出，
 *     让它可见而不是被静默吞掉。
 */
export const name = 'gate-reds'

/**
 * 从批次列表里挑出「成熟批次」——即**可作为门禁现状依据**的那一批。
 *
 * ⚠ 两次踩坑才定下这个判据（2026-11-22）：
 *
 * 坑一：直接取「最后一批」。跑批中途 Ctrl-C 会留下**残缺批次**
 *   （实测 30 道，正常 48 道）。残缺批次没有失败项，会被当成「全绿」——**假绿**。
 *
 * 坑二：取「门禁数最多的批次」。门禁是逐次新增的，**历史批次的门禁数天然更多**
 *   （实测 2026-11-11 那批 50 道 vs 现在 48 道），于是永远选到最老的一批，
 *   报出的是**几周前的红项**，与当下无关。
 *
 * ⇒ 正确判据：门禁数在近若干批里会稳定在一个值（当前是 48），取这个「规模」
 *   的**最新**一批。实现上取最近 N 批的门禁数众数作为「应有规模」，
 *   再从后往前找第一个门禁数等于该规模的批次。众数比 max/min 都稳。
 */
export function pickMatureBatch(batches, { lookback = 12 } = {}) {
  if (!batches.length) return null
  const recent = batches.slice(-lookback)
  // 众数（门禁数 → 出现次数）
  const counts = new Map()
  for (const b of recent) {
    const n = (b.gates || []).length
    counts.set(n, (counts.get(n) || 0) + 1)
  }
  let expected = 0
  let bestFreq = 0
  for (const [n, freq] of counts) {
    // 门禁数大者优先（同等频次下取更大的规模，避免被少数小批次带偏）
    if (freq > bestFreq || (freq === bestFreq && n > expected)) {
      expected = n
      bestFreq = freq
    }
  }
  if (!expected) return batches[batches.length - 1]
  // 从后往前找第一个门禁数等于「应有规模」的批次
  for (let i = batches.length - 1; i >= 0; i -= 1) {
    const n = (batches[i].gates || []).length
    if (n === expected) return batches[i]
  }
  return batches[batches.length - 1]
}

/** 汇总一批门禁的通过/失败情况。 */
export function summarizeBatch(batch) {
  const gates = (batch && batch.gates) || []
  const failed = gates.filter((g) => g.exit !== 0 && !g.skipped)
  const skipped = gates.filter((g) => g.skipped)
  return {
    batch: batch?.batch || '',
    ts: batch?.ts || '',
    total: gates.length,
    failed: failed.length,
    skipped: skipped.length,
    failedList: failed.map((g) => ({ label: g.label, exit: g.exit })),
  }
}

/** 把门禁留痕里的绝对路径命令压成可读短名（如 g03-credentials）。 */
function shortLabel(label) {
  const m = String(label).match(/g\d{2}[-_][a-z0-9_-]+/i)
  if (m) return m[0].replace(/_/g, '-')
  const parts = String(label).split(/[\\/]/).filter(Boolean)
  return parts[parts.length - 1] || String(label)
}

export function apply(ctx) {
  const { readGateRuns } = ctx.deps

  async function collect() {
    if (typeof readGateRuns !== 'function') {
      return { ok: false, summary: '宿主未注入 readGateRuns，无法读留痕', empty: true }
    }
    const batches = await readGateRuns()
    if (!batches.length) {
      return { ok: true, summary: '暂无门禁留痕（先跑一次 scripts/run_all_gates.sh）', empty: true }
    }
    const mature = pickMatureBatch(batches)
    const sum = summarizeBatch(mature)
    const last = batches[batches.length - 1]
    const lastCount = (last.gates || []).length
    // 残缺批次单独提示 —— 让人知道「最新一次跑批没跑完」，而不是误以为已全绿。
    // 判据用「应有规模」（成熟批次的门禁数）：最新批次门禁数少于它就是没跑完。
    const partial = lastCount < sum.total
      ? { batch: last.batch, count: lastCount, total: sum.total }
      : null
    return { ok: sum.failed === 0, summary: '', batches, sum, partial }
  }

  ctx.console.command({
    id: 'gate.reds',
    title: '门禁红项',
    description: '列出最近一次门禁运行中未通过的项目',
    plugin: name,
    async run() {
      const r = await collect()
      if (r.empty) return { ok: true, summary: r.summary }
      const s = r.sum
      const summary = s.failed
        ? `成熟批次（${s.batch}）有 ${s.failed} 道门禁未通过（共 ${s.total} 道）`
        : `成熟批次（${s.batch}）${s.total} 道门禁全绿`
      return {
        ok: s.failed === 0,
        summary: r.partial
          ? `${summary}；⚠ 最新批次 ${r.partial.batch} 仅 ${r.partial.count}/${r.partial.total} 道（跑批被中断）`
          : summary,
        detail: s.failedList,
      }
    },
  })

  // P3：侧栏常驻视图
  ctx.console.panel({
    id: 'governance.gates',
    slot: 'sidebar',
    title: '门禁红项',
    plugin: name,
    async render() {
      const r = await collect()
      if (r.empty) {
        return { status: r.summary ? 'error' : 'unknown', summary: r.summary, rows: [] }
      }
      const s = r.sum
      const rows = s.failedList.slice(0, 8).map((g) => ({
        label: shortLabel(g.label),
        value: `exit ${g.exit}`,
        tone: 'bad',
      }))
      if (r.partial) {
        rows.push({
          label: '最新批次未跑完',
          value: `${r.partial.count}/${r.partial.total} 道`,
          tone: 'warn',
        })
      }
      if (!rows.length) {
        rows.push({ label: '成熟批次', value: `${s.total} 道全绿`, tone: 'ok' })
      }
      return {
        status: s.failed ? 'bad' : (r.partial ? 'warn' : 'ok'),
        summary: s.failed
          ? `${s.failed} 道未通过 / 共 ${s.total} 道`
          : `${s.total} 道全绿`,
        rows,
      }
    },
  })
}
