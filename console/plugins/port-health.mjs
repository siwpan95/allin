/**
 * 内置插件：端口体检
 *
 * 读 `ports.yaml` 的登记项，逐个探活，报告「登记的没起来」与「起来了但没登记」。
 * 依赖只从 ctx.deps 取（core），不碰 fs / net / child_process。
 */
export const name = 'port-health'


export function apply(ctx) {
  const { core } = ctx.deps

  ctx.console.command({
    id: 'port.health',
    title: '端口体检',
    description: '对 ports.yaml 里 active 的服务逐个探活，列出未响应的登记项',
    plugin: name,
    async run() {
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
}
