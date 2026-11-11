// V-3（2026-11-10 深度审计收尾）回归：门户首页把令牌拼进 <meta content="...">
// 时必须做 HTML 属性转义，防止一个含引号/尖括号的令牌打破标签属性结构（CWE-116）。
//
// 背景：令牌来源是管理员注入的 ALLIN_PORTAL_TOKEN 或 0600 文件（非远程可控），
// 故这不是远程可利用注入；但纵深防御要求"配置值进 HTML 属性也按不可信处理"。
// 原缺陷：index.js 用 gate.token 原值直接 String.replace 进 content="__TOKEN__"。
//
// 触发链：独立进程设置带特殊字符的令牌 → 模块加载时 createTokenGate 读它 →
// GET / 走 index.html 注入分支 → 断言：① 响应 200；② 注入位是转义后的实体、
// 不再含原始引号/尖括号；③ meta 标签仍是单个合法属性（没有多出 onload 之类）。
//
// 为何独立文件：令牌在 createTokenGate 时从 env 一次性读定，api.test.mjs 等用的是
// 'portal-test-token'（无特殊字符），同一进程内改不了；用单独进程 + 独立临时根隔离。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-token-injection-'))
process.env.PLATFORM_ROOT = tmp
process.env.PORT = '0'
process.env.PLATFORM_PATH_CHECK = 'absolute'
// 含 HTML 属性逃逸载荷的令牌：若原样注入会闭合并额外造出一个 onload 属性。
const EVIL_TOKEN = 'x" onload="window.__pwned=1><'
process.env.ALLIN_PORTAL_TOKEN = EVIL_TOKEN

const { server } = await import('../src/index.js')
await new Promise((resolve) => server.once('listening', resolve))
const base = 'http://127.0.0.1:' + server.address().port

test('V-3 回归：首页令牌注入做 HTML 属性转义，不打破 meta 标签', async () => {
  const res = await fetch(base + '/')
  assert.equal(res.status, 200)
  const html = await res.text()
  // 定位注入后的 meta 标签（而不是对整个文档做裸 < 断言 —— HTML 文档本就满是 <）。
  const metaTags = html.match(/<meta[^>]*name="allin-token"[^>]*>/g) || []
  assert.equal(metaTags.length, 1, '应恰好有一个 allin-token meta 标签')
  const tag = metaTags[0]
  // ① 精确断言 content 属性值。值里的引号若未转义，`/content="([^"]*)"/` 会在第一个
  // 裸引号处提前截断、捕获不到完整载荷；能捕获到完整转义串本身就证明属性转义生效。
  const m = tag.match(/content="([^"]*)"/)
  assert.ok(m, '应能完整提取 content 属性值（含裸引号会被提前截断）')
  assert.equal(m[1], 'x&quot; onload=&quot;window.__pwned=1&gt;&lt;',
    'content 值必须是转义后的实体：引号→&quot;、尖括号→&lt;/&gt;')
  // ② 未转义的逃逸载荷形态不得出现；标签以正常的 "> 收尾、没有多出属性或标签。
  assert.ok(!tag.includes('content="x" onload='), '令牌不得原样闭合 content 属性')
  assert.ok(tag.endsWith('&lt;">'), 'meta 标签应正常收尾，不得被注入额外属性')
  assert.ok(!/\sonload="window/.test(tag), 'meta 标签不得被注入 onload 属性')
  // ③ 转义是纯输出编码：脚本读取的令牌原值不变（落盘 token 文件仍是原文）。
  const onDisk = fs.readFileSync(path.join(tmp, 'data', 'portal.token'), 'utf8').trim()
  assert.equal(onDisk, EVIL_TOKEN, '转义只作用于 HTML 输出，不污染令牌真值/鉴权')
})

after(async () => {
  await new Promise((resolve) => server.close(resolve))
  try { fs.rmSync(tmp, { recursive: true, force: true }) } catch { /* Windows 占用容错 */ }
})
