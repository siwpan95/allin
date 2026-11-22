#!/usr/bin/env node
/**
 * 打包前清理：干掉占用 dist 产物的进程，并删除 dist 目录。
 *
 * 为什么需要（实测踩到两次）：
 *   Electron 是**多进程**架构 —— 主进程退出后，渲染/GPU 子进程可能还持有
 *   `allin console.exe` 的句柄。Windows 的文件锁有延迟（杀毒/索引服务也会
 *   短暂持有），于是下一次打包报：
 *     `UNKNOWN: unknown error, open 'dist\win-unpacked\allin console.exe' failed`
 *   这个错**不是**打包配置问题，是文件锁。
 *
 * 处置：按进程名 kill（不按路径，避免误杀别的 Electron 应用）→ 等待 →
 *   重试删除，最多几轮。
 *
 * 用法：node scripts/clean-dist.mjs
 */
import path from 'node:path'
import { existsSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const DIST = path.join(HERE, '..', 'dist')

/** 只杀本项目产物对应的进程名，不按路径（防误杀别的 Electron 应用）。 */
const PROCESS_NAMES = ['allin console.exe', 'electron.exe']

function log(m) { console.log(`[clean] ${m}`) }

if (process.platform === 'win32') {
  for (const name of PROCESS_NAMES) {
    const r = spawnSync('taskkill', ['/F', '/IM', name, '/T'], { stdio: 'ignore' })
    if (r.status === 0) log(`已结束进程：${name}`)
  }
}

// 删目录：Windows 文件锁有延迟，重试几轮
let ok = false
for (let i = 1; i <= 6; i += 1) {
  if (!existsSync(DIST)) { ok = true; break }
  try {
    rmSync(DIST, { recursive: true, force: true, maxRetries: 3, retryDelay: 700 })
    ok = !existsSync(DIST)
  } catch {
    ok = false
  }
  if (ok) break
  log(`删除 dist 失败（第 ${i} 次），重试…`)
}

if (ok) {
  log('dist 已清理')
  process.exit(0)
}
log('⚠ dist 仍被占用（可能有 Electron 子进程残留），请手动关闭后重试')
process.exit(1)
