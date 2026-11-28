// restore_observed_from_snapshot.mjs —— 从扫描快照恢复观测态（registry/observed/*.json）
//
// 边界（与 discover_repos.mjs 的 --apply 同构，绝不越界）：
//   - 只写 registry/observed/（机器观测态：id/path/launch/publish）——这里允许覆盖；
//   - **永不写 registry/projects/**（人工语义：name/category/note/verify…）。
//
// 用途：观测态目录丢失、或换机后需要「那台机当时看到的样子」。
// 快照里人属字段的值（human_values，2026-11-28 起备份）只用于**提示**人工恢复，
// 不作为自动写回的依据——自动写回人工目录会把「观测」伪装成「已确认」。
//
// 用法：
//   node restore_observed_from_snapshot.mjs --machine SIWPAN --dry-run
//   node restore_observed_from_snapshot.mjs --machine SIWPAN
//   （默认取本机 hostname；找不到快照就明确报错，不静默跳过）

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const FACTS = path.join(ROOT, 'facts', 'machine')
const OBSERVED = path.join(ROOT, 'platform', 'registry', 'observed')

function main() {
  const argv = process.argv.slice(2)
  const dry = argv.includes('--dry-run')
  const mi = argv.indexOf('--machine')
  const machine = mi >= 0 ? argv[mi + 1] : (os.hostname() || '').toLowerCase()
  const snapPath = path.join(FACTS, machine, 'scan-snapshot.json')
  if (!fs.existsSync(snapPath)) {
    console.error(`没有 ${machine} 的扫描快照：${snapPath}\n先跑 discover_repos.mjs --audit --snapshot`)
    process.exit(2)
  }
  const snap = JSON.parse(fs.readFileSync(snapPath, 'utf8'))
  let written = 0, noProbe = 0, humanHint = 0
  for (const row of snap.rows || []) {
    if (!row.launch_probe) { noProbe++; continue }
    const id = (row.machine?.id || [])[0] || row.name
    const obj = {
      id,
      path: (row.machine?.path || [])[0] || `repos/${id}`,
      checkout: 'local',
      launch: { command: row.launch_probe.command },
      publish: {
        repo: (row.machine?.['publish.repo'] || [])[0] || row.git_remote || '',
        branch: (row.machine?.['publish.branch'] || [])[0] || row.local_head || 'master',
      },
      _origin: 'snapshot-restore',
      _scanned_at: snap.generated_at || '',
      _note: `从 ${machine} 快照恢复的观测态（依据 ${row.launch_probe.basis}）；人工字段仍在 registry/projects/。`,
    }
    if (row.human_values && Object.keys(row.human_values).length) humanHint++
    const file = path.join(OBSERVED, `${id}.json`)
    if (dry) console.log(`[dry] ${path.relative(ROOT, file)}`)
    else {
      fs.mkdirSync(OBSERVED, { recursive: true })
      fs.writeFileSync(file, JSON.stringify(obj, null, 2) + '\n', 'utf8')
    }
    written++
  }
  console.log(`== ${dry ? '将' : '已'}恢复 ${written} 条观测态；${noProbe} 条探针不可用（交人工，不伪造）`)
  console.log(`== ${humanHint} 条快照含人属字段值——仅供人工恢复 projects/ 时参考，脚本不写人工目录`)
}

main()
