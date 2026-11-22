/**
 * 内置插件：端口体检 / 端口占用
 *
 * 读 `ports.yaml` 的登记项，逐个探活，报告「登记的没起来」与「起来了但没登记」。
 * 依赖只从 ctx.deps 取（core），不碰 fs / net / child_process。
 *
 * 两种消费方式（同一份探测逻辑）：
 *   · 命令面板 `port.health`（P2）
 *   · 侧栏常驻面板 `governance.ports`（P3）
 */
export const name = 'port-health'

/**
 * 探测全部 active 登记端口。
 *
 * ⚠ 端口占用需要「实际在监听的端口」全集，而 core 只提供 `probePort`
 *   （给定端口问「通不通」）—— 不能反推「哪些端口被占」：
 *   对 65535 个端口逐个探测要 14 小时，不可行。
 *   ⇒ 端口占用由宿主注入 `listListeningPorts()`（读系统 netstat）提供；
 *   本插件没有该能力时，端口占用视图降级为「未接入」，**不假装**。
 */
export async function probeAll(core) {
  const { loadPorts } = core
  // loadPorts() 返回的是 Map<port, entry>（不是数组，也不是 {ports:[]}）——
  // 实测按 .ports 取会永远得到 0 条，端口体检就成了摆设。
  const ports = loadPorts()
  const items = [...ports.values()].filter((p) => p.status === 'active')
  const rows = []
  for (const p of items) {
    let alive = false
    try {
      alive = await core.probePort(p.port, { timeoutMs: 800 })
    } catch {
      alive = false
    }
    rows.push({ port: p.port, service: p.service, alive })
  }
  return rows
}

export function apply(ctx) {
  const { core } = ctx.deps

  ctx.console.command({
    id: 'port.health',
    title: '端口体检',
    description: '对 ports.yaml 里 active 的服务逐个探活，列出未响应的登记项',
    plugin: name,
    async run() {
      const rows = await probeAll(core)
      const down = rows.filter((r) => !r.alive)
      return {
        ok: down.length === 0,
        summary: down.length
          ? `${down.length}/${rows.length} 个登记端口未响应`
          : `全部 ${rows.length} 个登记端口正常`,
        detail: rows,
      }
    },
  })

  // P3：侧栏常驻视图
  ctx.console.panel({
    id: 'governance.ports',
    slot: 'sidebar',
    title: '端口占用',
    plugin: name,
    async render() {
      const rows = await probeAll(core)
      const alive = rows.filter((r) => r.alive)
      const down = rows.filter((r) => !r.alive)

      // 端口占用：实际监听但 registry 没登记的端口 —— **治理价值最高，排最前**
      const listening = typeof core.listListeningPorts === 'function'
        ? await core.listListeningPorts()
        : null
      const stray = []
      if (listening && Array.isArray(listening.ports)) {
        const registered = new Set(rows.map((r) => Number(r.port)))
        for (const p of listening.ports) {
          if (!registered.has(Number(p.port))) stray.push(p)
        }
      }

      const out = []
      if (stray.length) {
        // 24 个端口全列出来会把卡片撑得很高。列前 12 个，其余折叠计数 ——
        // 但**计数必须给出**，否则「还有多少」这个信息就丢了。
        const shown = stray.slice(0, 12)
        out.push({
          label: '未登记的监听端口',
          value: shown.map((p) => p.port).join(' ') + (stray.length > 12 ? ` …共 ${stray.length} 个` : ''),
          tone: 'warn',
          wrap: true,
        })
      }
      // 登记端口里在监听的
      for (const r of alive) {
        out.push({ label: `${r.port} ${r.service || ''}`.trim(), value: '监听中', tone: 'ok' })
      }
      // 未监听的登记端口（最多列 5 条）
      for (const r of down.slice(0, 5)) {
        out.push({ label: `${r.port} ${r.service || ''}`.trim(), value: '未响应', tone: 'dim' })
      }
      if (down.length > 5) {
        out.push({ label: '其余未响应', value: `${down.length - 5} 个`, tone: 'dim' })
      }

      return {
        status: down.length ? 'warn' : 'ok',
        summary: `${alive.length}/${rows.length} 个登记端口在监听`
          + (stray.length ? `（另有 ${stray.length} 个未登记）` : ''),
        rows: out,
      }
    },
  })
}
