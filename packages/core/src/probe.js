// @allin/core — 探活：TCP 端口探测 / HTTP 健康检查。
// 慢启动纪律（2026-08-28）：radio ~20s、video 1–2min、mixer >30s 才绑定端口——
// 启动宽限期（STARTING_GRACE_MS）内进程存活但端口/健康未就绪时，报 via='starting'
// （前端显示「启动中」），不再把"启动中"误判为失败；pid 不在时对端口/健康
// 做短时多轮探测（服务可能在平台外启动、端口尚未绑定）。
import net from 'node:net'
import http from 'node:http'

/** 慢启动服务（radio/video/mixer 等）的端口就绪确认窗口：3 分钟。 */
export const STARTING_GRACE_MS = 180000

export function probePort(port, timeout = 800) {
  return new Promise((resolve) => {
    const sock = net.connect({ port, host: '127.0.0.1', timeout })
    sock.on('connect', () => { sock.destroy(); resolve(true) })
    sock.on('timeout', () => { sock.destroy(); resolve(false) })
    sock.on('error', () => resolve(false))
  })
}

function probeUrl(url, timeout = 2000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout }, (res) => {
      res.resume()
      resolve(res.statusCode >= 200 && res.statusCode < 500)
    })
    req.on('timeout', () => { req.destroy(); resolve(false) })
    req.on('error', () => resolve(false))
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** 单轮"服务是否就绪"探测；条目未声明端口/健康时返回 null（不可探测）。 */
async function probeOnce(entry, portTimeout = 500, urlTimeout = 1200) {
  if (entry.health && entry.health.url) return probeUrl(entry.health.url, urlTimeout)
  if (entry.port !== undefined && entry.port !== null) return probePort(Number(entry.port), portTimeout)
  return null
}

/** 声明了端口/健康才算"有服务面"的慢启动服务。 */
function hasService(entry) {
  return (entry.port !== undefined && entry.port !== null) || Boolean(entry.health && entry.health.url)
}

/**
 * 条目探活。startedAt 为运行登记的开始时间（null = 未登记/未知）：
 *  - 进程存活 + 宽限期内服务未就绪 → { running: true, via: 'starting' }
 *  - 进程存活 + 服务就绪/宽限期外/无服务面 → { running: true, via: 'health-url'|'port'|'process' }
 *  - 进程不在 → 端口/健康短时多轮探测（3 轮，间隔 600ms）
 */
export async function probeEntry(entry, running, startedAt = null) {
  if (running) {
    if (hasService(entry) && startedAt !== null && Date.now() - startedAt < STARTING_GRACE_MS) {
      const ok = await probeOnce(entry)
      if (ok === null) return { running: true, via: 'process' } // 探测不可用（如 health url 无效）
      if (!ok) return { running: true, via: 'starting' }
      return { running: true, via: entry.health && entry.health.url ? 'health-url' : 'port' }
    }
    return { running: true, via: 'process' }
  }
  if (entry.health && entry.health.url) {
    for (let i = 0; i < 3; i++) {
      if (await probeUrl(entry.health.url)) return { running: true, via: 'health-url' }
      if (i < 2) await sleep(600)
    }
    return { running: false, via: 'health-url-fail' }
  }
  if (entry.port !== undefined && entry.port !== null) {
    for (let i = 0; i < 3; i++) {
      if (await probePort(Number(entry.port))) return { running: true, via: 'port' }
      if (i < 2) await sleep(600)
    }
    return { running: false, via: 'port-closed' }
  }
  return { running: false, via: 'no-probe' }
}
