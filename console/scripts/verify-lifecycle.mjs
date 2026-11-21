/**
 * 临时验证：用 @allin/core 真跑一次 start → 等退出 → 读 tasks.log
 * 目的：确认 console 依赖的启停与日志链路在真实项目上成立（用完即删）。
 */
import path from 'node:path'
import { existsSync, readFileSync } from 'node:fs'
import { loadRegistry, PORTS_YAML, startEntry, runningIds, DATA_DIR } from '@allin/core'

const registryDir = path.join(path.dirname(PORTS_YAML), 'projects')
const { entries } = loadRegistry(registryDir)
const target = process.argv[2] || 'adventurelog'
const entry = entries.find((e) => e.id === target)
if (!entry) { console.error('未知项目', target); process.exit(1) }

console.log('目标:', entry.id, '| launch:', entry.launch.command)

const r = startEntry(entry, { owner: 'console-verify' })
console.log('startEntry →', JSON.stringify(r))
console.log('runningIds:', JSON.stringify(runningIds()))

await new Promise((res) => setTimeout(res, 4000))

const logFile = path.join(DATA_DIR, 'tasks.log')
console.log('tasks.log 存在:', existsSync(logFile))
if (existsSync(logFile)) {
  const rows = readFileSync(logFile, 'utf8').trim().split('\n').filter(Boolean)
    .map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean)
    .filter((x) => x.project === entry.id)
  console.log(`该项目的日志 ${rows.length} 条:`)
  for (const row of rows.slice(-4)) {
    console.log('  ', row.ts, row.action,
      row.exit_code !== undefined ? `exit=${row.exit_code}` : '',
      row.duration_ms !== undefined ? `${row.duration_ms}ms` : '')
  }
}
console.log('退出前 runningIds:', JSON.stringify(runningIds()))
