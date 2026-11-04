'use strict';

/**
 * portal 代理（BFF）：治理数据经本服务端代理读写 platform portal，浏览器不直连。
 *
 * 错误三分类（P1b 决策三，绝不把 502 原样吐给用户页）：
 *   PORTAL_UNREACHABLE — portal.port 缺失 / 连接拒绝 → 「平台未启动」降级卡
 *   PORTAL_FORBIDDEN   — Host 围栏被改等 403 → fail-loud 报警（不静默）
 *   UPSTREAM_TIMEOUT   — 3s 超时 → 返回上次成功快照 + snapshotAt 时间戳标注
 *
 * website 不持久化任何治理状态：唯一"缓存"是进程内存里的最近一次成功快照。
 * bridge 端点（/api/overview、/api/orchestration）未上线时按 404 处理：
 *   overview 退化为用既有 /api/status + /api/library 聚合（缺失维度置 null）；
 *   orchestration 返回 readable:false + 空集（与 gate-history 的 readable 模式一致），不报错。
 */

const fs = require('node:fs');
const config = require('../config');

const CODE_MESSAGES = Object.freeze({
  PORTAL_UNREACHABLE: '平台未启动（治理面 portal 离线）',
  PORTAL_FORBIDDEN: '平台回环围栏校验失败（PORTAL_FORBIDDEN），请检查 platform 安全配置',
  UPSTREAM_TIMEOUT: '平台响应超时，已回退到最近一次快照',
});

// 进程内存快照缓存：仅存最近一次成功结果，供 UPSTREAM_TIMEOUT 降级回退
const cache = {
  overview: null, // { data, at: ISO }
  orchestration: null,
  entries: null,
};

function readPortalBase() {
  const explicit = config.portal.baseUrl;
  if (explicit) return explicit.replace(/\/+$/, '');
  try {
    const raw = fs.readFileSync(config.portal.portFile, 'utf8').trim();
    const port = Number.parseInt(raw, 10);
    if (!Number.isFinite(port) || port <= 0 || port > 65535) return null;
    return `http://127.0.0.1:${port}`;
  } catch {
    return null; // portal.port 不存在 = 平台未启动（PORT=0 机制下进程退出即删文件）
  }
}

/**
 * 统一上游 GET/POST：3s AbortController 超时，按三分类返回。
 * 返回 { kind:'OK', status, body } 或 { kind: CODE }。
 */
async function fetchJson(pathname, { method = 'GET' } = {}) {
  const base = readPortalBase();
  if (!base) return { kind: 'PORTAL_UNREACHABLE' };
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), config.portal.timeoutMs);
  try {
    const res = await fetch(base + pathname, {
      method,
      signal: ac.signal,
      headers: { accept: 'application/json' },
    });
    if (res.status === 403) return { kind: 'PORTAL_FORBIDDEN' };
    const text = await res.text();
    let body = null;
    try {
      body = JSON.parse(text);
    } catch {
      body = null; // 非 JSON 响应按 null 处理，由调用方按状态码分类
    }
    return { kind: 'OK', status: res.status, body };
  } catch (err) {
    if (err && (err.name === 'AbortError' || ac.signal.aborted)) return { kind: 'UPSTREAM_TIMEOUT' };
    return { kind: 'PORTAL_UNREACHABLE' };
  } finally {
    clearTimeout(timer);
  }
}

function okResult(key, data) {
  const at = new Date().toISOString();
  cache[key] = { data, at };
  return { ok: true, degraded: null, snapshotAt: at, data };
}

function degradedResult(key, code) {
  const snap = cache[key];
  return {
    ok: true,
    degraded: { code, message: CODE_MESSAGES[code] || code },
    // 超时降级时携带快照与时间戳；其余降级 data 为 null（snapshotAt 供参考）
    snapshotAt: snap ? snap.at : null,
    data: code === 'UPSTREAM_TIMEOUT' && snap ? snap.data : null,
  };
}

// ---- overview：bridge 优先，未上线时用既有端点聚合 ----

function libraryAggregate(items) {
  const list = Array.isArray(items) ? items : [];
  return {
    total: list.length,
    running: list.filter((e) => e && e.running).length,
    invalid: list.filter((e) => e && e.valid === false).length,
  };
}

function composeOverview(statusBody, libraryBody) {
  return {
    portal: statusBody && typeof statusBody === 'object'
      ? { version: statusBody.version ?? null, uptime: statusBody.uptime ?? null, port: statusBody.port ?? null }
      : null,
    library: libraryAggregate(libraryBody && libraryBody.items),
    alerts: null, // 既有端点不吐 alerts 聚合，bridge 上线后补齐
    gates: null, // 同上：gate 维度以 /api/overview（bridge）为准
  };
}

/** 治理总览：portal/version/uptime + 登记/运行/异常 + 门禁摘要。 */
async function getOverview() {
  const r = await fetchJson('/api/overview');
  if (r.kind === 'OK' && r.status === 200 && r.body && typeof r.body === 'object' && !Array.isArray(r.body)) {
    return okResult('overview', r.body);
  }
  if (r.kind === 'OK' && r.status === 404) {
    // bridge 未上线：用既有 /api/status + /api/library 聚合（比裸降级多给真实数据）
    const [status, library] = await Promise.all([fetchJson('/api/status'), fetchJson('/api/library')]);
    if (
      status.kind === 'OK' && status.status === 200 && library.kind === 'OK' && library.status === 200
    ) {
      return okResult('overview', composeOverview(status.body, library.body));
    }
    const worse = [status, library].find((x) => x.kind === 'PORTAL_FORBIDDEN') || [status, library].find((x) => x.kind === 'UPSTREAM_TIMEOUT');
    return degradedResult('overview', worse ? worse.kind : 'PORTAL_UNREACHABLE');
  }
  return degradedResult('overview', r.kind);
}

// ---- orchestration：g21 判据 + routes.yaml 路由表（数据源对前端透明） ----

function emptyOrchestration() {
  return {
    routes: [],
    drift: [],
    lastCheckAt: null,
    lastCheckError: null,
    healthy: false,
    readable: false,
  };
}

/** 编排状态：路由条目 + 漂移（severity: error|warn）+ 门禁自身健康。 */
async function getOrchestration() {
  const r = await fetchJson('/api/orchestration');
  if (r.kind === 'OK' && r.status === 200 && r.body && typeof r.body === 'object' && Array.isArray(r.body.routes)) {
    const data = {
      routes: r.body.routes,
      drift: Array.isArray(r.body.drift) ? r.body.drift : [],
      lastCheckAt: r.body.lastCheckAt ?? null,
      lastCheckError: r.body.lastCheckError ?? null,
      healthy: Boolean(r.body.healthy),
      readable: r.body.readable !== false,
    };
    return okResult('orchestration', data);
  }
  if (r.kind === 'OK' && r.status === 404) {
    // bridge 未上线：按「路由表不可读」呈现（readable:false），不算平台故障
    return okResult('orchestration', emptyOrchestration());
  }
  return degradedResult('orchestration', r.kind);
}

// ---- entries：登记项目明细（管理台启停列表用，走既有 /api/library） ----

async function getEntries() {
  const r = await fetchJson('/api/library');
  if (r.kind === 'OK' && r.status === 200 && r.body && Array.isArray(r.body.items)) {
    return okResult('entries', { items: r.body.items, problems: r.body.problems ?? null });
  }
  return degradedResult('entries', r.kind);
}

// ---- 写代理：POST /api/library/{id}/start|stop（唯一写路径，转发 portal 既有端点） ----

/**
 * @param {string} id 项目登记 id（[a-z0-9-]+，与 portal 路由正则一致）
 * @param {'start'|'stop'} action
 * @returns {{ ok:true, id, result } | { ok:false, code, message }}
 */
async function proxyEntryAction(id, action) {
  if (!/^[a-z0-9-]+$/.test(id) || !['start', 'stop'].includes(action)) {
    return { ok: false, code: 'BAD_REQUEST', message: '非法的项目 id 或操作类型。' };
  }
  const r = await fetchJson(`/api/library/${id}/${action}`, { method: 'POST' });
  if (r.kind !== 'OK') return { ok: false, code: r.kind, message: CODE_MESSAGES[r.kind] || r.kind };
  if (r.status === 200) return { ok: true, id, result: r.body || {} };
  if (r.status === 404) return { ok: false, code: 'NOT_FOUND', message: '注册表中没有这个项目。' };
  if (r.status === 400) {
    return { ok: false, code: 'UPSTREAM_REJECTED', message: (r.body && r.body.error) || '平台拒绝了这次操作。' };
  }
  return { ok: false, code: 'UPSTREAM_ERROR', message: `平台返回异常状态 ${r.status}。` };
}

/** 供测试注入：清空内存快照（smoke 用隔离实例，不影响常驻进程）。 */
function _resetCacheForTest() {
  cache.overview = null;
  cache.orchestration = null;
  cache.entries = null;
}

module.exports = { getOverview, getOrchestration, getEntries, proxyEntryAction, _resetCacheForTest };
