/**
 * 插件宿主的独立验证（不经 Electron）—— 快速确认 cordis-js 与内置插件可用。
 * 用法：node scripts/verify-plugins.mjs
 */
import path from 'node:path'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createHost } from '@allin/cordis-js'
import { probePort, loadPorts, PLATFORM_ROOT } from '@allin/core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PLUGIN_DIR = path.join(HERE, '..', 'plugins')
const GATE_RUNS = path.join(PLATFORM_ROOT, '..', 'tools', 'gate', 'audit', 'gate-runs.jsonl')

function readGateBatches() {
  if (!existsSync(GATE_RUNS)) return []
  const byBatch = new Map()
  for (const line of readFileSync(GATE_RUNS, 'utf8').split('\n')) {
    if (!line.trim()) continue
    let row
    try { row = JSON.parse(line) } catch { continue }
    if (!row.batch) continue
    if (!byBatch.has(row.batch)) byBatch.set(row.batch, { batch: row.batch, ts: row.ts, gates: [] })
    byBatch.get(row.batch).gates.push({ label: row.label, exit: row.exit, skipped: Boolean(row.skipped) })
  }
  return [...byBatch.values()].sort((a, b) => String(a.ts).localeCompare(String(b.ts)))
}

const host = createHost({
  logger: (lv, msg) => console.log(`  [${lv}] ${msg}`),
  deps: { core: { probePort, loadPorts }, readGateRuns: readGateBatches },
})

const files = readdirSync(PLUGIN_DIR).filter((f) => f.endsWith('.mjs'))
const mods = []
for (const f of files) {
  // Windows 下 import() 的绝对路径必须转 file:// URL，否则报 ERR_UNSUPPORTED_ESM_URL_SCHEME
  mods.push(await import(pathToFileURL(path.join(PLUGIN_DIR, f)).href))
}

console.log(`加载 ${mods.length} 个插件…`)
const loaded = await host.load(mods)
console.log('已加载:', loaded.join(', ') || '（无）')
if (host.errors.length) console.log('失败:', host.errors)

console.log(`\n注册命令 ${host.commands.length} 个:`)
for (const c of host.commands) console.log(`  · ${c.id} —— ${c.title}`)

console.log('\n逐个执行：')
for (const c of host.commands) {
  const t0 = Date.now()
  try {
    const r = await c.run()
    console.log(`  · ${c.id}: ${r.ok ? 'OK' : 'FAIL'} (${Date.now() - t0}ms) —— ${r.summary}`)
  } catch (e) {
    console.log(`  · ${c.id}: 抛错 ${e.message}`)
  }
}
process.exit(0)
