/**
 * allin-console · 入口（SPEC-205 §C3）
 *
 * 只负责应用生命周期；窗口与 IPC 逻辑在 app.js（供 smoke.mjs 复用）。
 *
 * ⚠ 顺序很关键（P4）：
 *   ① 先 applyEnv() 设好 PLATFORM_PORTS / PLATFORM_REPOS_ROOT / PLATFORM_ROOT
 *   ② 再 import app.js —— app.js 内部动态 import '@allin/core'，
 *      而 core 在模块顶层就把 PORTS_YAML 求值成 const。
 *   顺序颠倒 ⇒ core 锁死成打包目录里的假路径 ⇒ registry 加载到 0 条。
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { app } = require('electron')
import path from 'node:path'
import { writeFileSync } from 'node:fs'
import { applyEnv } from './config.js'

const home = applyEnv()
if (home.bundled) {
  console.log(
    '[allin-console] ⚠ 未定位到本机 allin 仓，当前为**清单快照模式**：\n'
    + `  · registry 来自包内随附快照：${home.portsYaml}\n`
    + '  · 可以浏览清单、查端口、跑只读命令；**启停与路径解析不可用**\n'
    + '  · 要启用完整功能，请设置环境变量 ALLIN_HOME=<allin 仓根>，\n'
    + '  · 或写 %APPDATA%\\allin-console\\config.json：'
      + '{"allinHome": "<ALLIN_ROOT>"}（示例见 README）',
  )
} else if (!home.root) {
  console.error(
    '[allin-console] 未定位到 allin 仓，且包内也没有 registry 快照。\n'
    + '  请设置环境变量 ALLIN_HOME=<allin 仓根>，\n'
    + '  或写 %APPDATA%\\allin-console\\config.json：'
      + '{"allinHome": "<ALLIN_ROOT>"}（示例见 README）',
  )
} else {
  console.log(`[allin-console] allin 仓：${home.root}（来源：${home.source}）`)
  console.log(`[allin-console] 发布区：${home.reposRoot}`)
}

// 动态 import —— 保证 env 已设好之后才加载 core
const { createConsoleWindow, registerIpc, listProjects } = await import('./app.js')

/**
 * 探针模式（P4 打包验证用）。
 *
 * 设了 ALLIN_CONSOLE_PROBE=1 时：不开窗口，只跑一次 registry 读取，
 * 把结果写进 ALLIN_CONSOLE_PROBE_OUT 指定的文件后退出 —— 让
 * `scripts/verify-packaged.mjs` 能**断言**打包产物的路径解析是对的，
 * 而不是靠人眼看 GUI。
 *
 * ⚠ 必须写文件而不是打 stdout：Windows GUI 子系统的进程不继承控制台句柄，
 *   stdout 会直接丢失（实测退出码 0 但一个字节都没打印）。
 */
if (process.env.ALLIN_CONSOLE_PROBE === '1') {
  const out = process.env.ALLIN_CONSOLE_PROBE_OUT || path.join(process.cwd(), 'probe-out.txt')
  try {
    const r = listProjects()
    // problems 详情一并写出：只给数量无法诊断（安装态与源码态数量不同，
    // 必须知道**哪一条**不一样）。实测这一步确实抓到了安装态独有的那条。
    const problems = (r.problems || []).map((p) => String(p))
    writeFileSync(out, [
      `registry=${r.total}`,
      `problems=${problems.length}`,
      ...problems.map((p) => `problem: ${p}`),
      '',
    ].join('\n'), 'utf8')
    process.exit(0)
  } catch (e) {
    try {
      writeFileSync(out, `ERROR ${e?.stack || e}\n`, 'utf8')
    } catch { /* 写不出去就算了 */ }
    process.exit(1)
  }
}

app.whenReady().then(() => {
  registerIpc()
  createConsoleWindow()
  app.on('activate', () => {
    createConsoleWindow()
  })
})

app.on('window-all-closed', () => {
  app.quit()
})
