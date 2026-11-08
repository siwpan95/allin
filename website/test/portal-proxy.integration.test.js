'use strict';

/**
 * B2 · website↔portal BFF 在线集成测试（柯砚 P1 / 白樾问题）。
 *
 * 用 node:http 在临时端口起**可控假 portal**，通过 PORTAL_BASE_URL 注入，
 * 逐条覆盖 U-Q09 三分类降级四态 + U-Q07 数字对账。零第三方依赖，零盘符。
 *
 * 关键约束：
 *   - config 在 require 时读 env，故 PORTAL_BASE_URL 必须在 require 之前占位；
 *     运行中通过直接改写 config.portal.baseUrl / timeoutMs 切换场景（避免反复
 *     清 require 缓存）。
 *   - 用 test.before 起服务（CommonJS 不允许顶层 await），afterEach 调
 *     _resetCacheForTest() 清空进程内存快照，保证用例间隔离。
 *   - 超时降到 600ms，使 UPSTREAM_TIMEOUT 用例快且确定（原 3000ms）。
 *
 * 此前 _resetCacheForTest() 在代码库里**零调用**、bridge 未上线的 404 聚合
 * 路径**零覆盖** —— 本套件一并补齐（U-Q07③ + getEntries）。
 *
 * 跑法：node --test test/portal-proxy.integration.test.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

// —— env 必须在 require config 之前设定（config 在 require 时读 env）——
process.env.PORTAL_BASE_URL = 'http://127.0.0.1:1'; // 占位，test.before 起服务后覆盖
delete process.env.PORTAL_PORT_FILE; // 确保走 baseUrl 分支

const config = require('../src/config');
const portalProxy = require('../src/services/portalProxy');

// 超时降到亚秒级：UPSTREAM_TIMEOUT 用例快且确定（原 3000ms 会让用例等 3s）
config.portal.timeoutMs = 600;

// 无监听端口 → ECONNREFUSED → PORTAL_UNREACHABLE（不依赖特定特权端口假设）
const CLOSED_BASE = 'http://127.0.0.1:1';

// ---- 可控假 portal：行为由 mode 切换，响应体由各用例按需覆写 ----
let mode = 'ok-overview';
let overviewBody = {
  portal: { version: '1.2.3', uptime: 123, port: 9100 },
  library: { total: 10, running: 7, invalid: 1 },
  gates: { passed: 5, failed: 0 },
  alerts: [{ level: 'info', text: 'ok' }],
};
let orchestrationBody = {
  routes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
  drift: [{ severity: 'warn', path: 'x' }],
  healthy: true,
  readable: true,
  lastCheckAt: '2026-11-08T00:00:00Z',
  lastCheckError: null,
};
let statusBody = { platform: 'allin-platform', version: '1.2.3', uptime: 99, port: 9100 };
let libraryBody = { items: [] };

let BASE = CLOSED_BASE;

const server = http.createServer((req, res) => {
  const url = (req.url || '').split('?')[0];
  if (url === '/api/overview') {
    if (mode === 'forbidden') { res.writeHead(403); return res.end(); }
    if (mode === 'hang') { return; } // 故意不响应 → 触发超时降级
    if (mode === 'fallback-404') { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': 'application/json' });
    return res.end(JSON.stringify(overviewBody));
  }
  if (url === '/api/orchestration') {
    res.writeHead(200, { 'content-type': 'application/json' });
    return res.end(JSON.stringify(orchestrationBody));
  }
  if (url === '/api/status') {
    res.writeHead(200, { 'content-type': 'application/json' });
    return res.end(JSON.stringify(statusBody));
  }
  if (url === '/api/library') {
    res.writeHead(200, { 'content-type': 'application/json' });
    return res.end(JSON.stringify(libraryBody));
  }
  res.writeHead(404);
  res.end();
});

test.before(async () => {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  BASE = `http://127.0.0.1:${server.address().port}`;
  config.portal.baseUrl = BASE;
});

test.after(() => {
  // 关闭所有连接（含 hang 用例遗留的未结束请求），避免端口/句柄泄漏
  if (typeof server.closeAllConnections === 'function') server.closeAllConnections();
  server.close();
});

test.afterEach(() => {
  portalProxy._resetCacheForTest();
  config.portal.baseUrl = BASE; // 复位到在线假 portal
  mode = 'ok-overview';
});

// ============================================================ U-Q09 四态

test('U-Q09① PORTAL_UNREACHABLE：baseUrl 指向无监听端口 → 200 + degraded.code=PORTAL_UNREACHABLE', async () => {
  config.portal.baseUrl = CLOSED_BASE;
  const r = await portalProxy.getOverview();
  assert.equal(r.ok, true, '代理层不抛错，永远 200 包裹降级');
  assert.equal(r.degraded.code, 'PORTAL_UNREACHABLE');
  assert.equal(r.data, null);
  assert.equal(r.snapshotAt, null);
});

test('U-Q09② PORTAL_FORBIDDEN：上游 403 → 200 + degraded.code=PORTAL_FORBIDDEN（fail-loud 不静默）', async () => {
  mode = 'forbidden';
  const r = await portalProxy.getOverview();
  assert.equal(r.degraded.code, 'PORTAL_FORBIDDEN');
  assert.equal(r.data, null, 'FORBIDDEN 不携带任何快照数据');
});

test('U-Q09③ UPSTREAM_TIMEOUT（有快照）：超时 → 200 + degraded.code=UPSTREAM_TIMEOUT + 回退最近成功快照', async () => {
  // 先建立一次成功快照
  mode = 'ok-overview';
  const first = await portalProxy.getOverview();
  assert.equal(first.ok, true);
  assert.equal(first.degraded, null);
  const snapData = first.data;
  // 再让上游挂起 → 超时降级
  mode = 'hang';
  const r = await portalProxy.getOverview();
  assert.equal(r.degraded.code, 'UPSTREAM_TIMEOUT');
  assert.deepEqual(r.data, snapData, '超时降级必须回退到最近一次成功快照');
  assert.ok(r.snapshotAt, '必须携带快照时间戳 snapshotAt（前端据此标注"数据可能过期"）');
});

test('U-Q09④ UPSTREAM_TIMEOUT（无快照）：缓存为空时超时 → data=null（等价于 504 无缓存可回退）', async () => {
  mode = 'hang';
  const r = await portalProxy.getOverview();
  assert.equal(r.degraded.code, 'UPSTREAM_TIMEOUT');
  assert.equal(r.data, null, '无成功快照时超时降级 data 必须为 null（不放空对象误导前端）');
  assert.equal(r.snapshotAt, null);
});

// ============================================================ U-Q07 数字对账

test('U-Q07① overview 数字一致：portal /api/overview 的 running/total 维度原样透传', async () => {
  overviewBody = {
    portal: { version: '1.2.3', uptime: 123, port: 9100 },
    library: { total: 10, running: 7, invalid: 1 },
    gates: { passed: 5, failed: 0 },
    alerts: [{ level: 'info', text: 'ok' }],
  };
  mode = 'ok-overview';
  const r = await portalProxy.getOverview();
  assert.equal(r.ok, true);
  assert.equal(r.degraded, null);
  assert.deepEqual(r.data, overviewBody, 'overview 维度必须 1:1 透传 portal 响应，不得改键/丢字段');
  assert.equal(r.data.library.running, 7);
  assert.equal(r.data.library.total, 10);
});

test('U-Q07② orchestration 数字一致：routes/drift 数量与 portal 响应一致', async () => {
  orchestrationBody = {
    routes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
    drift: [{ severity: 'warn', path: 'x' }, { severity: 'error', path: 'y' }],
    healthy: true,
    readable: true,
    lastCheckAt: '2026-11-08T00:00:00Z',
    lastCheckError: null,
  };
  const r = await portalProxy.getOrchestration();
  assert.equal(r.ok, true);
  assert.equal(r.degraded, null);
  assert.equal(r.data.routes.length, 3, 'routes 数量必须与 portal 一致');
  assert.equal(r.data.drift.length, 2, 'drift 数量必须与 portal 一致');
  assert.deepEqual(r.data.routes, orchestrationBody.routes);
});

test('U-Q07③ bridge 未上线（/api/overview 404）→ 退化为 /api/status + /api/library 聚合，数字一致', async () => {
  mode = 'fallback-404';
  statusBody = { platform: 'allin-platform', version: '1.2.3', uptime: 99, port: 9100 };
  libraryBody = {
    items: [
      { id: 'a', running: true, valid: true },
      { id: 'b', running: false, valid: true },
      { id: 'c', running: true, valid: false },
    ],
  };
  const r = await portalProxy.getOverview();
  assert.equal(r.ok, true, '404 fallback 路径必须 ok:true（不算平台故障）');
  assert.equal(r.degraded, null);
  assert.equal(r.data.portal.version, '1.2.3', 'portal 维度来自 /api/status');
  assert.equal(r.data.library.total, 3, 'total 来自 /api/library items 长度');
  assert.equal(r.data.library.running, 2, 'running 来自 items 中 running:true 计数');
  assert.equal(r.data.library.invalid, 1, 'invalid 来自 items 中 valid===false 计数');
  assert.equal(r.data.alerts, null, 'bridge 未上线时 alerts 维度置 null');
  assert.equal(r.data.gates, null, 'bridge 未上线时 gates 维度置 null');
});

test('getEntries 透传 /api/library items（管理台启停列表数据源）', async () => {
  libraryBody = { items: [{ id: 'a' }, { id: 'b' }], problems: null };
  const r = await portalProxy.getEntries();
  assert.equal(r.ok, true);
  assert.equal(r.degraded, null);
  assert.equal(r.data.items.length, 2, 'items 必须原样透传');
});
