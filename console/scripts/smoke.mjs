/**
 * allin-console · 冒烟验证（P0 验收判据的可执行形态）
 *
 * 判据（任一不满足即 exit 1）：
 *   1. UI 能加载且渲染出项目条目（> 0）
 *   2. 统计栏文本包含「/ 148」这类总数（证明读的是 registry 而非硬编码）
 *   3. 能截到一张非空图（证明真的画出来了，不是黑屏）
 *
 * 用法：
 *   npm run smoke                    # 无头截图到 data/smoke.png
 *   SMOKE_SHOT=xxx.png npm run smoke # 指定输出
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { app } = require('electron')
import path from 'node:path'
import { mkdirSync, writeFileSync, statSync } from 'node:fs'
import { createConsoleWindow, registerIpc } from '../apps/shell/app.js'

const HERE = path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1')
const OUT = process.env.SMOKE_SHOT || path.join(HERE, '..', 'data', 'smoke.png')

function log(msg) { console.log(`[smoke] ${msg}`) }

app.whenReady().then(async () => {
  try {
    registerIpc()
    const { uiView } = createConsoleWindow({ width: 1280, height: 840, show: true })
    const wc = uiView.webContents

    await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('did-finish-load 超时（15s）')), 15_000)
      wc.once('did-finish-load', () => { clearTimeout(t); resolve() })
    })
    log('UI 已加载')

    // 轮询 DOM：registry 读取 + 渲染是异步的
    let count = 0
    for (let i = 0; i < 40; i += 1) {
      count = await wc.executeJavaScript("document.querySelectorAll('.item').length", true)
      if (count > 0) break
      await new Promise((r) => setTimeout(r, 250))
    }
    const stats = await wc.executeJavaScript(
      "document.getElementById('stats')?.textContent || ''", true)
    const status = await wc.executeJavaScript(
      "document.getElementById('status')?.textContent || ''", true)

    log(`渲染条目: ${count}`)
    log(`统计栏  : ${stats}`)
    log(`状态栏  : ${status}`)

    // 等一帧，确保绘制完成
    await new Promise((r) => setTimeout(r, 600))

    // —— 端到端：选中带 CLI 的项目 → 点「跑 info --json」→ 校验渲染出**纯 JSON** ——
    // 注意判据是「以 { 开头」而不是「包含 {」：实测 audio-pipeline 的 cli.py 把
    // 信息打到 stderr、stdout 为空，用宽松判据会把它误判成合规。
    const candidates = await wc.executeJavaScript(`
      [...document.querySelectorAll('.item')]
        .filter((el) => el.querySelector('.badge.cli'))
        .map((el) => el.dataset.id)
    `, true)
    log(`带 CLI 的项目: ${candidates.length} 个`)

    let jsonOk = false
    let picked = null
    let jsonHead = ''
    const nonCompliant = []

    for (const id of candidates.slice(0, 8)) {
      await wc.executeJavaScript(`
        (() => {
          const el = [...document.querySelectorAll('.item')].find((n) => n.dataset.id === ${JSON.stringify(id)});
          if (el) el.click();
        })()
      `, true)
      await new Promise((r) => setTimeout(r, 250))
      await wc.executeJavaScript("document.getElementById('btn-info')?.click()", true)

      let text = ''
      for (let i = 0; i < 25; i += 1) {
        text = await wc.executeJavaScript("document.querySelector('pre.out')?.textContent || ''", true)
        if (text.trim()) break
        await new Promise((r) => setTimeout(r, 200))
      }
      const trimmed = text.trim()
      if (trimmed.startsWith('{')) {
        jsonOk = true
        picked = id
        jsonHead = trimmed.split('\n').slice(0, 2).join(' | ')
        break
      }
      nonCompliant.push(id)
    }

    log(`info 合规: ${jsonOk ? picked : '（前 8 个均不合规）'}`)
    if (jsonHead) log(`JSON 首行: ${jsonHead.slice(0, 110)}`)
    if (nonCompliant.length) {
      log(`不合规项目（stdout 非纯 JSON）: ${nonCompliant.join(', ')}`)
    }

    // —— 运行态接口：只读调用，不启动任何项目（避免冒烟产生副作用）——
    const runningOk = await wc.executeJavaScript(`
      (async () => {
        const r = await window.allin.runningIds();
        return Array.isArray(r && r.ids);
      })()
    `, true)
    log(`runningIds 接口: ${runningOk ? 'OK' : '不可用'}`)

    const img = await wc.capturePage()
    mkdirSync(path.dirname(OUT), { recursive: true })
    writeFileSync(OUT, img.toPNG())
    const size = statSync(OUT).size
    log(`截图    : ${OUT}（${size} 字节）`)

    // —— 插件命令面板：打开 → 执行首个命令 → 截图 ——
    const cmdCount = await wc.executeJavaScript(`
      (async () => {
        document.getElementById('btn-cmd')?.click();
        await new Promise((r) => setTimeout(r, 700));
        return document.querySelectorAll('.cmd-item').length;
      })()
    `, true)
    log(`命令面板条目: ${cmdCount}`)

    let cmdRan = false
    if (cmdCount > 0) {
      await wc.executeJavaScript(`
        (() => { document.querySelector('.cmd-item')?.click(); })()
      `, true)
      for (let i = 0; i < 40; i += 1) {
        const txt = await wc.executeJavaScript(
          "document.getElementById('cmd-out')?.textContent || ''", true)
        if (txt && !txt.includes('执行 ')) { cmdRan = true; log(`首个命令结果: ${txt.split('\\n')[0].slice(0, 90)}`); break }
        await new Promise((r) => setTimeout(r, 250))
      }
      const cmdShot = OUT.replace(/\.png$/, '-cmd.png')
      const img2 = await wc.capturePage()
      writeFileSync(cmdShot, img2.toPNG())
      log(`命令面板截图: ${cmdShot}（${statSync(cmdShot).size} 字节）`)
    }

    const problems = []
    if (count <= 0) problems.push('未渲染出任何项目条目')
    if (!/\/\s*\d+/.test(stats)) problems.push(`统计栏未体现总数：${stats}`)
    if (size < 5000) problems.push(`截图过小（${size} 字节），疑似空白`)
    if (!picked) problems.push('前 8 个带 CLI 的项目里没有一个 info 返回纯 JSON')
    if (!runningOk) problems.push('runningIds 接口不可用（启停链路未接通）')
    if (cmdCount === 0) problems.push('命令面板没有任何插件命令（cordis-js 宿主未生效）')
    if (cmdCount > 0 && !cmdRan) problems.push('插件命令执行后没有结果回传')

    if (problems.length) {
      for (const p of problems) console.error(`[smoke] ✗ ${p}`)
      app.exit(1)
      return
    }
    log('PASS')
    app.exit(0)
  } catch (e) {
    console.error('[smoke] ✗ 异常：' + (e && e.message))
    app.exit(1)
  }
})
