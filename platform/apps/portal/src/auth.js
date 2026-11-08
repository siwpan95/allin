// @allin/portal —— 本地调用令牌（2026-11-08 深度审核 P1）
//
// 此前 `X-Allin-Local: 1` 是无凭证的全局通行证：回环上任何进程都能调用
// start/stop/rollback/shutdown，等于是「同机即管理员」。现在所有状态变更必须
// 同时持有门户令牌：服务启动时随机生成并写入 <DATA_DIR>/portal.token（0600），
// 或由 ALLIN_PORTAL_TOKEN 显式注入。门户前端通过 index.html 注入取得令牌，
// CLI / website 代理读同一文件。收紧为「能读到令牌或拿到注入令牌才能写」。
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

export function createTokenGate(dataDir) {
  const file = path.join(dataDir, 'portal.token')
  let token = (process.env.ALLIN_PORTAL_TOKEN || '').trim()
  if (!token) {
    try {
      token = fs.readFileSync(file, 'utf8').trim()
    } catch {
      token = crypto.randomBytes(32).toString('hex')
    }
  }
  if (!token) throw new Error('门户令牌为空，拒绝以无鉴权状态启动')
  // 无论令牌来自环境变量还是自动生成，都落盘一次，供 CLI / website 代理读取。
  try {
    fs.mkdirSync(dataDir, { recursive: true })
    fs.writeFileSync(file, token + '\n', { mode: 0o600 })
    try { fs.chmodSync(file, 0o600) } catch { /* Windows 权限语义有限，尽力而为 */ }
  } catch (e) {
    console.error('[portal] 令牌文件写入失败（其它进程需改用 ALLIN_PORTAL_TOKEN 注入）：' + e.message)
  }
  const expected = Buffer.from(token, 'utf8')
  return {
    token,
    valid(req) {
      const got = String(req.headers['x-allin-token'] || '')
      if (!got || Buffer.byteLength(got, 'utf8') !== expected.length) return false
      return crypto.timingSafeEqual(Buffer.from(got, 'utf8'), expected)
    },
  }
}
