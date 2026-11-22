/**
 * 内置插件：registry 审计
 *
 * 审的是**登记本身的质量**，不是项目代码：
 *   · 条目总数 / 无效条目（core 已跑过 validateEntry，problems 里就是结果）
 *   · 重复 id
 *   · CLI 接入覆盖率（有 info 子命令才算接入）
 *   · 分类分布（找出「unclassified」堆积）
 *
 * 与门禁 g17 的分工：g17 是**门禁判据**（阻断），本插件是**常驻视图**
 * （随时可看，不阻断）。两者读的是同一份 registry，不重复造解析逻辑 ——
 * 条目与 problems 一律由宿主的 core.loadRegistry 提供。
 *
 * 依赖只从 ctx.deps 取（core + cli-bus 的静态探测），不碰 fs。
 */
export const name = 'registry-audit'

export function apply(ctx) {
  const { core, cliBus } = ctx.deps

  async function audit() {
    if (!core || typeof core.loadRegistry !== 'function') {
      return { ok: false, summary: '宿主未注入 core.loadRegistry' }
    }
    const { entries, problems } = core.loadRegistry(core.REGISTRY_DIR)
    const total = entries.length
    const invalid = entries.filter((e) => e._valid === false)

    // CLI 接入覆盖：有 info 子命令才算「已接入」（只看 cli.py 存在会虚高）
    let withInfo = 0
    let cliOnly = 0
    if (cliBus && typeof cliBus.hasInfoSubcommand === 'function') {
      for (const e of entries) {
        let abs
        try { abs = core.resolvePath(e.path) } catch { continue }
        const cli = cliBus.locateCli(abs)
        if (!cli) continue
        if (cliBus.hasInfoSubcommand(cli)) withInfo += 1
        else cliOnly += 1
      }
    }

    // 分类分布：unclassified 堆积是登记质量的一个信号
    const byCategory = new Map()
    for (const e of entries) {
      const c = e.category || 'unclassified'
      byCategory.set(c, (byCategory.get(c) || 0) + 1)
    }
    const unclassified = byCategory.get('unclassified') || 0

    return {
      ok: true,
      total,
      invalid,
      problems: problems || [],
      withInfo,
      cliOnly,
      byCategory,
      unclassified,
    }
  }

  ctx.console.command({
    id: 'registry.audit',
    title: 'registry 审计',
    description: '审计登记条目的质量：无效条目、重复 id、CLI 接入覆盖、分类分布',
    plugin: name,
    async run() {
      const a = await audit()
      if (!a.ok) return { ok: false, summary: a.summary }
      const issues = a.invalid.length + a.problems.length
      return {
        ok: issues === 0,
        summary: issues
          ? `${a.total} 条登记中 ${a.invalid.length} 条无效、${a.problems.length} 条问题`
          : `${a.total} 条登记全部通过校验`,
        detail: [
          ...a.problems.slice(0, 10),
          ...a.invalid.slice(0, 10).map((e) => `${e.id}: 清单校验未通过`),
        ],
      }
    },
  })

  // P3：侧栏常驻视图
  ctx.console.panel({
    id: 'governance.registry',
    slot: 'sidebar',
    title: 'registry 审计',
    plugin: name,
    async render() {
      const a = await audit()
      if (!a.ok) return { status: 'error', summary: a.summary, rows: [] }

      const rows = []
      rows.push({ label: '登记条目', value: String(a.total), tone: 'dim' })
      if (a.invalid.length) {
        rows.push({ label: '校验未通过', value: `${a.invalid.length} 条`, tone: 'bad' })
      }
      if (a.problems.length) {
        rows.push({ label: '清单问题', value: `${a.problems.length} 条`, tone: 'bad' })
      }
      if (a.cliOnly) {
        rows.push({ label: '有 CLI 无 info', value: `${a.cliOnly} 个`, tone: 'warn' })
      }
      if (a.unclassified) {
        rows.push({ label: '未分类', value: `${a.unclassified} 条`, tone: 'warn' })
      }
      const pct = a.total ? Math.round((a.withInfo / a.total) * 100) : 0
      rows.push({ label: 'CLI 接入', value: `${a.withInfo}/${a.total}（${pct}%）`, tone: 'dim' })

      // 分类 top3 —— 让「登记结构」一眼可见
      const top = [...a.byCategory.entries()]
        .sort((x, y) => y[1] - x[1])
        .slice(0, 3)
        .map(([c, n]) => `${c} ${n}`)
      if (top.length) {
        rows.push({ label: '主要分类', value: top.join(' · '), tone: 'dim' })
      }

      const bad = a.invalid.length + a.problems.length
      return {
        status: bad ? 'bad' : 'ok',
        summary: bad ? `${bad} 项待处理` : '全部通过校验',
        rows,
      }
    },
  })
}
