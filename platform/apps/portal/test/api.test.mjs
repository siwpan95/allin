// portal API 测试：临时端口启动真实服务，验证三个页签的数据面。
import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import http from 'node:http'
import net from 'node:net'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'

// 隔离数据目录（launch 日志不落真实 data/）
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-api-'))
process.env.PLATFORM_ROOT = tmp
process.env.PORT = '0'
// 2026-11-08：状态变更要令牌。测试用固定值，避免依赖临时文件读取时序。
process.env.ALLIN_PORTAL_TOKEN = 'portal-test-token'
const PORTAL_TOKEN = process.env.ALLIN_PORTAL_TOKEN
// 异机结构校验：登记的 path 指向作者机器的项目目录（本机不存在），
// 测试只校验清单结构与端口查表（PLATFORM_PATH_CHECK=absolute），不绑定具体机器。
process.env.PLATFORM_PATH_CHECK = 'absolute'

const { server } = await import('../src/index.js')
await new Promise((resolve) => server.once('listening', resolve))
const base = 'http://127.0.0.1:' + server.address().port

test('GET /api/status', async () => {
  const res = await fetch(base + '/api/status')
  const body = await res.json()
  assert.equal(body.platform, 'allin-platform')
  // §六第二阶段契约：报「实际绑定端口」（PORT=0 下为临时端口），字段名 boundPort；
  // 旧字段 port 已退役，不得残留 —— 报配置端口 0 会让消费方误判为「端口未知」。
  assert.equal(body.boundPort, server.address().port, '/api/status.boundPort 必须等于实际绑定端口')
  assert.equal(Object.prototype.hasOwnProperty.call(body, 'port'), false, 'port 已更名 boundPort，不得残留旧字段')
})

test('GET /api/overview（bridge）：portal.boundPort 为实际绑定端口，无旧 port 字段', async () => {
  const res = await fetch(base + '/api/overview')
  assert.equal(res.status, 200)
  const body = await res.json()
  // deps 注入值来自 listen 回填；字段名已在 bridge.js 同步 port→boundPort。
  assert.equal(body.portal.boundPort, server.address().port, 'overview.portal.boundPort 必须等于实际绑定端口')
  assert.equal(Object.prototype.hasOwnProperty.call(body.portal, 'port'), false, 'overview 旧字段 port 不得残留')
})

// Phase 1（2026-09-24）：Host 头围栏——防 DNS rebinding 打穿 loopbackOnly。
// undici fetch 禁止设置 Host 头，故用原生 http.request 指定伪造 Host。
function rawGet(pathname, hostHeader) {
  return new Promise((resolve, reject) => {
    const req = http.request(base + pathname, { headers: { host: hostHeader }, method: 'GET' }, (res) => {
      res.resume()
      res.on('end', () => resolve(res.statusCode))
    })
    req.on('error', reject)
    req.end()
  })
}

test('Host 围栏：回环 Host（127.0.0.1 / localhost / [::1]）放行', async () => {
  assert.equal(await rawGet('/api/status', '127.0.0.1:' + server.address().port), 200)
  assert.equal(await rawGet('/api/status', 'localhost:9999'), 200)
  assert.equal(await rawGet('/api/status', '[::1]:8888'), 200)
})

test('Host 围栏：攻击域名 / 空 Host → 403（DNS rebinding 防护）', async () => {
  assert.equal(await rawGet('/api/status', 'evil.example.com'), 403)
  assert.equal(await rawGet('/api/status', 'attacker.rebind.local:80'), 403)
  assert.equal(await rawGet('/api/library', 'evil.example.com'), 403, 'GET 读取面同样受保护')
  // HTTP/1.0 无 Host 头（Node http.request 会自动补 Host，须 raw socket 实测）
  assert.equal(await rawRequest10('/api/status'), 403, '缺 Host 头一律拒绝')
})

function rawRequest10(pathname) {
  return new Promise((resolve, reject) => {
    const sock = net.connect(server.address().port, '127.0.0.1', () => {
      sock.write(`GET ${pathname} HTTP/1.0\r\n\r\n`)
    })
    let head = ''
    sock.on('data', (c) => { head += c; sock.end() })
    sock.on('end', () => resolve(Number((/^HTTP\/1\.[01] (\d{3})/.exec(head) || [])[1])))
    sock.on('error', reject)
  })
}

test('GET /api/library 与 registry 全集双向一致（problems 为空）', async () => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()
  // ── 判据形态更换（2026-11-01）───────────────────────────────────────────────
  // 旧写法在这份测试里写死一串 id 清单，被同一类漂移打中**三次**：
  //   ① d20（2026-10-20 清理死项，漏同步本断言）
  //   ② repocheck（2026-10-26 subtree 并入 allin/tools/，不再是独立仓）
  //   ③ station（registry 里从未有过 station.yaml，断言凭空要求）
  // 三次手法完全一样：registry 侧删/并条目，忘了同步这份断言。
  // ⇒ 「手写 id 清单」是**必漂移机制**；再写第四次注释是为必然发生的漂移买单，故换判据形态：
  //    期望集改从 registry 目录**现场推导**，两侧双向比对，不多不少。
  //    保护力不降反升：旧写法只护当时写死的 35 个 id，现写法护全部条目且永不需手工同步。
  const regDir = path.join(__dirnameOf(), '..', '..', '..', 'registry', 'projects')
  const regFiles = fs.readdirSync(regDir).filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))
  assert.equal(body.items.length, regFiles.length, 'library 条目数应等于 registry 清单文件数')
  const regIds = regFiles.map(f => yaml.load(fs.readFileSync(path.join(regDir, f), 'utf8')).id)
  const ids = body.items.map(i => i.id)
  assert.deepEqual(new Set(ids), new Set(regIds), 'library 的 id 集合应与 registry 完全一致（不多不少）')
  assert.equal(new Set(ids).size, ids.length, 'id 不得重复（重复会被 loadRegistry 计为 problem）')
  assert.deepEqual(body.problems, [])
})

function __dirnameOf() {
  return path.dirname(fileURLToPath(import.meta.url))
}

// 2026-11-24：原用例钉死 `id=arcade` / `gameplay=idle` 这两条注册条目，用来验
// 「gameplay 标签与 order/note 回填」。而 2026-11-23「66 个冻结仓移入备份区」后
// 这两条已不在 registry 里 ⇒ 用例恒红（实测 73/75，`idle 族应至少 5 个` /
// `arcade.gameplay` undefined），成了「主分支长期红」的一部分。
//
// 不删用例，也不改成 skip —— 那会把「回填契约」这条真实保护一起丢掉。改判据：
// 期望集**从 registry 现场推导**（与本文件上面那条 id 集合用例同一纪律），
// 校验「凡是声明了 gameplay 的条目，API 必须原样回填、且标签在受控枚举内」。
// 保护力反而更强：原先只护两个写死的 id，现在护全部声明条目，且不再需要手工同步。
test('GET /api/library 原样回填 registry 的 gameplay 标签（受控枚举）', async () => {
  const { KNOWN_GAMEPLAY } = await import('@allin/core')
  const res = await fetch(base + '/api/library')
  const body = await res.json()

  const declared = new Map()
  for (const file of registryFiles()) {
    const entry = yaml.load(fs.readFileSync(path.join(registryDir(), file), 'utf8'))
    if (entry?.id && entry.gameplay !== undefined) declared.set(entry.id, entry.gameplay)
  }
  assert.ok(declared.size > 0, 'registry 里应至少有一个声明 gameplay 的条目（否则本判据形同虚设）')

  const byId = new Map(body.items.map(i => [i.id, i]))
  for (const [id, tags] of declared) {
    const item = byId.get(id)
    assert.ok(item, `/api/library 缺条目 ${id}（registry 有、API 没有）`)
    assert.deepEqual(item.gameplay, tags, `${id} 的 gameplay 未原样回填 registry`)
    for (const tag of item.gameplay) {
      assert.ok(KNOWN_GAMEPLAY.includes(tag), `${id} 的 gameplay 标签 ${tag} 不在受控枚举内`)
    }
  }
})

// 同一条纪律：order/note 的判据也改为不依赖具体条目，只约束**契约**：
//   · 出现则类型必须对（order 正整数 / note 非空串）；
//   · 同一 gameplay 族里，只要有条目带 order，全族都得带，且必须是 1..n 连续 ——
//     缺一个就会让前端把 undefined 排到最前，这正是原用例想拦的那个坑。
test('GET /api/library 的 order/note 回填契约（同族 order 必须 1..n 连续）', async (t) => {
  const res = await fetch(base + '/api/library')
  const body = await res.json()

  const badOrder = body.items
    .filter(i => i.order !== undefined && i.order !== null && !(Number.isInteger(i.order) && i.order > 0))
    .map(i => `${i.id}=${JSON.stringify(i.order)}`)
  assert.deepEqual(badOrder, [], 'order 出现时必须是正整数: ' + badOrder.join(', '))

  const badNote = body.items
    .filter(i => i.note !== undefined && i.note !== null && (typeof i.note !== 'string' || !i.note))
    .map(i => i.id)
  assert.deepEqual(badNote, [], 'note 出现时必须是非空字符串: ' + badNote.join(', '))

  const tagged = body.items.filter(i => Array.isArray(i.gameplay) && i.gameplay.length > 0)
  const families = [...new Set(tagged.flatMap(i => i.gameplay))]
  let checked = 0
  for (const tag of families) {
    const family = tagged.filter(i => i.gameplay.includes(tag))
    if (!family.some(i => Number.isInteger(i.order))) continue
    checked += 1
    const missing = family.filter(i => !Number.isInteger(i.order)).map(i => i.id)
    assert.deepEqual(missing, [], `${tag} 族里有条目缺 order（前端会把它们排到最前）: ${missing.join(', ')}`)
    const sorted = [...family].sort((a, b) => a.order - b.order)
    assert.deepEqual(
      sorted.map(i => i.order),
      Array.from({ length: family.length }, (_, k) => k + 1),
      `${tag} 族的 order 必须从 1 连续递增`,
    )
  }
  // 让「本次到底判了几族」可见 —— 全为 0 时读者应知道这是数据现状，不是全绿。
  t.diagnostic(`带 gameplay 的条目 ${tagged.length} 个；其中带 order 的族 ${checked} 个`)
})

function registryDir() {
  return path.join(__dirnameOf(), '..', '..', '..', 'registry', 'projects')
}

function registryFiles() {
  return fs.readdirSync(registryDir()).filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))
}

test('GET /api/workshop 目录 = 有 publish 的项目（无订阅 → 不触发 gitee 网络）', async () => {
  const res = await fetch(base + '/api/workshop')
  const body = await res.json()
  assert.ok(body.catalog.length >= 20)
  assert.ok(body.catalog.every(i => !i.subscribed || i.subscribedAt))
})

test('GET /workshop/catalog 静态目录页（HTML）', async () => {
  const res = await fetch(base + '/workshop/catalog')
  const text = await res.text()
  assert.ok(res.headers.get('content-type').includes('text/html'))
  assert.ok(text.includes('工坊目录'))
  assert.ok(text.includes('gitee.com/siwpan/'))
})

test('GET /api/workshop/audit 审计流水', async () => {
  const res = await fetch(base + '/api/workshop/audit')
  const body = await res.json()
  assert.ok(Array.isArray(body.audit))
})

test('GET /api/alerts E5 订阅视图（聚合分歧事件，无事件时为空数组）', async () => {
  const res = await fetch(base + '/api/alerts')
  const body = await res.json()
  assert.ok(Array.isArray(body.alerts))
})

test('POST 启动未知项目 → 404（本地调用方带标记头）', async () => {
  const res = await fetch(base + '/api/library/nope/start', {
    method: 'POST',
    headers: { 'X-Allin-Local': '1', 'X-Allin-Token': PORTAL_TOKEN },
  })
  assert.equal(res.status, 404)
})

// 2026-11-04 工程审查 P0：状态变更来源围栏（CSRF）。
// 用原生 http.request 以便自由设置 Origin / Sec-Fetch-Site（undici fetch 对部分头有限制）。
function rawPost(pathname, headers = {}, withToken = true) {
  const allHeaders = withToken ? { 'X-Allin-Token': PORTAL_TOKEN, ...headers } : headers
  return new Promise((resolve, reject) => {
    const req = http.request(base + pathname, { method: 'POST', headers: allHeaders }, (res) => {
      res.resume()
      res.on('end', () => resolve(res.statusCode))
    })
    req.on('error', reject)
    req.end('x=1')
  })
}

test('CSRF 围栏：跨站 Origin / cross-site / 裸请求 → 403，且 shutdown 不执行', async () => {
  const originHost = base.replace('http://', 'https://evil.example.com')
  assert.equal(await rawPost('/api/shutdown', { Origin: originHost }), 403, '跨站 Origin 必须拒绝')
  assert.equal(await rawPost('/api/shutdown', { 'Sec-Fetch-Site': 'cross-site' }), 403, 'Fetch Metadata cross-site 必须拒绝')
  assert.equal(await rawPost('/api/shutdown', {}), 403, '无来源信号的裸 POST 必须拒绝')
  assert.equal(await rawPost('/api/library/nope/start', { Origin: originHost }), 403, 'start 端点同样受保护')
  // 若上面任何一条放行，进程会退出，后续测试不会执行 —— 进程仍活着即证明副作用未发生
  assert.equal((await fetch(base + '/api/status')).status, 200, '门户进程仍在，shutdown 未被执行')
})

test('CSRF 围栏：本地标记头 / 同源浏览器信号 → 放行到业务逻辑', async () => {
  assert.equal(await rawPost('/api/library/nope/start', { 'X-Allin-Local': '1' }), 404)
  const sameOrigin = { Origin: base, 'Sec-Fetch-Site': 'same-origin' }
  assert.equal(await rawPost('/api/library/nope/start', sameOrigin), 404)
})

// 2026-11-08 深度审核 P1：`X-Allin-Local: 1` 不再是免凭证通行证。
test('令牌闸：无令牌 / 错令牌的写请求一律 403，shutdown 不执行', async () => {
  assert.equal(await rawPost('/api/shutdown', { 'X-Allin-Local': '1' }, false), 403, '只带本地标记必须拒绝')
  assert.equal(await rawPost('/api/library/nope/start', {
    'X-Allin-Local': '1', 'X-Allin-Token': 'wrong-token',
  }, false), 403, '错误令牌必须拒绝')
  assert.equal((await fetch(base + '/api/status')).status, 200, '门户进程仍在，shutdown 未被执行')
})

test('GET /api/gate-history：SKIP 单列，不污染 failed/escapeRate/lastOkAt', async () => {
  const trailFile = path.join(tmp, 'gate-history-runs.jsonl')
  const lines = [
    JSON.stringify({ ts: '2026-11-04T10:00:00Z', commit: 'c1', label: 'real-ok', exit: 0, ms: 10 }),
    JSON.stringify({ ts: '2026-11-04T11:00:00Z', commit: 'c1', label: 'real-red', exit: 1, ms: 10 }),
    JSON.stringify({ ts: '2026-11-04T12:00:00Z', commit: 'c1', label: 'skip', exit: 0, ms: 0, skipped: true }),
  ]
  fs.writeFileSync(trailFile, lines.join('\n') + '\n', 'utf8')
  // handler 运行时读 process.env.ALLIN_GATE_RUNS；try/finally 恢复，避免污染其他用例。
  const prev = process.env.ALLIN_GATE_RUNS
  process.env.ALLIN_GATE_RUNS = trailFile
  try {
    const res = await fetch(base + '/api/gate-history')
    const body = await res.json()
    assert.equal(body.readable, true)
    assert.equal(body.summary.skipped, 1)
    assert.equal(body.summary.failed, 1)
    assert.equal(body.summary.escapeRate, 0.5)                     // 分母 2（真跑），非 1/3
    assert.equal(body.summary.lastOkAt, '2026-11-04T10:00:00Z')   // 不被较新 SKIP 行污染
    assert.equal(body.summary.inTail, 3)
    assert.equal(body.summary.lastRunAt, '2026-11-04T12:00:00Z')  // 全量 tail 末行时间
    assert.equal(body.runs.length, 3)                              // 仍返回全部行
    assert.equal(body.runs.some(r => r.skipped === true), true)    // 且含 SKIP 行
  } finally {
    if (prev === undefined) delete process.env.ALLIN_GATE_RUNS
    else process.env.ALLIN_GATE_RUNS = prev
  }
})

after(() => server.close())
