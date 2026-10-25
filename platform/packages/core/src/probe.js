// @allin/core — 探活：TCP 端口探测 / HTTP 健康检查。
import net from 'node:net'
import http from 'node:http'

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

export async function probeEntry(entry, running) {
  if (running) return { running: true, via: 'process' }
  if (entry.health && entry.health.url) {
    const ok = await probeUrl(entry.health.url)
    return { running: ok, via: ok ? 'health-url' : 'health-url-fail' }
  }
  if (entry.port !== undefined && entry.port !== null) {
    const ok = await probePort(Number(entry.port))
    return { running: ok, via: ok ? 'port' : 'port-closed' }
  }
  return { running: false, via: 'no-probe' }
}
