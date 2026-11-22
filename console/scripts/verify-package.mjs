/**
 * 打包产物体检：检查 app.asar 内的依赖是否齐全。
 *
 * 为什么需要：electron-builder 对 `file:` 协议依赖的**传递依赖**收集有盲区
 * （实测：`@allin/core` 是符号链接到仓外，它声明的 `js-yaml` 不会被收进
 * asar，运行时 `import yaml from 'js-yaml'` 直接崩 —— 而且打包阶段只报一行
 * `cannot find path for dependency`，不阻断）。
 *
 * ⇒ 打包后必须独立验证，不能信「打包成功」的日志。
 *
 * 用法：node scripts/verify-package.mjs [产物目录]
 */
import path from 'node:path'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const HERE = path.dirname(fileURLToPath(import.meta.url))
const UNPACKED = process.argv[2] || path.join(HERE, '..', 'dist', 'win-unpacked')
const ASAR = path.join(UNPACKED, 'resources', 'app.asar')

const problems = []
const notes = []

function log(m) { console.log(`[pkg] ${m}`) }

// —— 1. 产物存在性 ——
if (!existsSync(UNPACKED)) {
  console.error(`[pkg] ✗ 产物目录不存在：${UNPACKED}`)
  process.exit(1)
}
const exe = path.join(UNPACKED, 'allin console.exe')
if (!existsSync(exe)) problems.push(`主程序不存在：${exe}`)
else notes.push(`主程序 ${(statSync(exe).size / 1024 / 1024).toFixed(1)} MB`)

// —— 2. asar 内的依赖完整性 ——
// 直接从 asar 读 package.json 的 dependencies，逐个确认在 asar 内有对应目录。
let asarPkg = null
try {
  const asar = require('@electron/asar')
  const list = asar.listPackage(ASAR)
  const topDirs = new Set()
  for (const p of list) {
    // asar 列表用反斜杠分隔：\node_modules\@allin\core\...
    // 归一化成 / 再匹配，避免 Windows 上的分隔符差异。
    const norm = p.replace(/\\/g, '/')
    const m = norm.match(/^\/node_modules\/([^/]+)(\/[^/]+)?/)
    if (m) topDirs.add(m[1] + (m[2] || ''))
  }
  const rootPkg = JSON.parse(asar.extractFile(ASAR, 'package.json').toString('utf8'))
  asarPkg = { deps: rootPkg.dependencies || {}, topDirs }
  notes.push(`asar 内顶层依赖 ${topDirs.size} 个：${[...topDirs].sort().join(', ')}`)
  for (const dep of Object.keys(rootPkg.dependencies || {})) {
    if (!topDirs.has(dep)) problems.push(`asar 内缺少依赖：${dep}`)
  }
} catch (e) {
  problems.push(`读取 asar 失败：${e.message}`)
}

// —— 3. core 的传递依赖（js-yaml）必须在 asar 里 ——
// 这是实测踩到的坑：core 是 file: 协议依赖，其传递依赖不被收集。
if (asarPkg) {
  const hasYaml = asarPkg.topDirs.has('js-yaml')
  if (!hasYaml) {
    problems.push('asar 内缺少 js-yaml —— @allin/core 解析 registry 靠它，运行时会崩')
  } else {
    notes.push('js-yaml 已在 asar 内')
  }
  const hasCordis = asarPkg.topDirs.has('@cordisjs')
  if (!hasCordis) problems.push('asar 内缺少 @cordisjs/core')
}

// —— 4. registry 资源 ——
const regDir = path.join(UNPACKED, 'resources', 'registry', 'projects')
if (!existsSync(regDir)) {
  problems.push(`registry 资源缺失：${regDir}`)
} else {
  const n = readdirSync(regDir).filter((f) => f.endsWith('.yaml')).length
  notes.push(`registry 资源 ${n} 条`)
  if (n < 100) problems.push(`registry 资源只有 ${n} 条（预期 148）`)
}

// —— 5. 门禁留痕位置说明（不随包分发，但要确认配置能指向它）——
// 安装后默认读「allin 仓」的留痕；包内不带留痕（它是运行产物，不是源码）。

log('== 打包产物体检 ==')
for (const n of notes) log('  · ' + n)
if (problems.length) {
  console.error('\n阻断项：')
  for (const p of problems) console.error('  ✗ ' + p)
  process.exit(1)
}
log('\n打包产物体检通过')
process.exit(0)
