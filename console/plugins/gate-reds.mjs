/**
 * 内置插件：门禁红项
 *
 * 读门禁留痕（`tools/gate/audit/gate-runs.jsonl` 之类），把最近一次各门禁的
 * 通过/失败摆到命令面板里 —— 免得每次都去翻 JSONL。
 *
 * 依赖只从 ctx.deps 取；文件读取由宿主注入的 `readGateRuns` 完成（插件不碰 fs）。
 */
export const name = 'gate-reds'


export function apply(ctx) {
  const { readGateRuns } = ctx.deps

  ctx.console.command({
    id: 'gate.reds',
    title: '门禁红项',
    description: '列出最近一次门禁运行中未通过的项目',
    plugin: name,
    async run() {
      if (typeof readGateRuns !== 'function') {
        return { ok: false, summary: '宿主未注入 readGateRuns，无法读留痕' }
      }
      // 宿主返回按 batch 分组后的批次数组（每批一次全量门禁跑）
      const batches = await readGateRuns()
      if (!batches.length) {
        return { ok: true, summary: '暂无门禁留痕（先跑一次 scripts/run_all_gates.sh）' }
      }
      const latest = batches[batches.length - 1]
      const failed = (latest.gates || []).filter((g) => g.exit !== 0 && !g.skipped)
      return {
        ok: failed.length === 0,
        summary: failed.length
          ? `最近一批（${latest.batch}）有 ${failed.length} 道门禁未通过（共 ${latest.gates.length} 道）`
          : `最近一批（${latest.batch}）${latest.gates.length} 道门禁全绿`,
        detail: failed.map((g) => ({ label: g.label, exit: g.exit })),
      }
    },
  })
}
