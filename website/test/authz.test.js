'use strict';

/**
 * website 授权/越权分支回归（S6 缺口：requireRole 此前无自动化测试）。
 *
 * 覆盖 src/middleware/auth.js 的 requireAuth / requireRole：
 *   - member / guest 越权访问 admin 路由（HTML 与 JSON 两种响应）
 *   - 多角色命中与未命中
 *   - admin 合法放行（不能把合法访问误记为越权）
 *   - 匿名访问（写 auth.denied 而非 authz.denied）
 *   - requireAuth 非 active 账号（写 auth.denied / status=disabled）
 *   - 可证伪自证：证明差分断言既非恒真也非恒等
 *
 * 口径：auth.js:15 是**解构导入** `const { logAudit } = require('../services/audit')`，
 * 运行时替换 require('../src/services/audit').logAudit 对 requireRole 无效（模块加载
 * 时已绑定函数引用），因此一律走**真实 DB 断言**：调用中间件后查 audit_log 表，
 * 不做任何 logAudit mock。
 *
 * 用 node:test（零新依赖），DB_PATH / KEY_DIR 重定向到临时目录，
 * 全程不触碰真实 data/。跑法：npm test（或 node --test test/authz.test.js）。
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

// —— 必须在 require 任何 src 模块之前重定向数据目录（config 在 require 时读 env）——
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'allin-authz-test-'));
process.env.DB_PATH = path.join(TMP, 'data', 'site.db');
process.env.KEY_DIR = path.join(TMP, 'data', 'keys');
delete process.env.SITE_MASTER_KEY_BASE64;

const { getDb, closeDb } = require('../src/db');
const { requireAuth, requireRole } = require('../src/middleware/auth');

test.after(() => {
  closeDb();
  fs.rmSync(TMP, { recursive: true, force: true });
});

// ------------------------------------------------------------------ mock 工具

function mockRes() {
  const headers = Object.create(null);
  return {
    headers,
    statusCode: 200,
    body: undefined,
    redirectTo: undefined,
    rendered: undefined,
    status(code) { this.statusCode = code; return this; },
    type(t) { headers['Content-Type'] = t; return this; },
    set(key, value) {
      if (key && typeof key === 'object') Object.assign(headers, key);
      else headers[key] = value;
      return this;
    },
    send(b) { this.body = b; return this; },
    end() { return this; },
    json(o) { this.body = o; return this; },
    redirect(u) { this.redirectTo = u; return this; },
    render(v, o) { this.rendered = { view: v, options: o }; return this; },
  };
}

function mockReq(headers = {}, extra = {}) {
  return {
    method: 'GET',
    originalUrl: '/admin/settings',
    headers,
    ip: '203.0.113.7',
    body: {},
    user: { email: 'admin@example.com', role: 'admin' },
    xhr: false,
    protocol: 'http',
    accepts: () => false,
    ...extra,
  };
}

function count(sql, ...args) {
  return getDb().prepare(sql).get(...args).n;
}

// 按 action 精确计数的差分基准：漏掉 `WHERE action = ?` 会把其它分支写入的
// audit（如匿名 auth.denied）也算进来，导致「合法访问 +0」断言误红。
function auditCount(action) {
  return count('SELECT COUNT(*) AS n FROM audit_log WHERE action = ?', action);
}

function lastAudit(action) {
  return getDb()
    .prepare('SELECT actor, action, target, ok, detail FROM audit_log WHERE action = ? ORDER BY id DESC LIMIT 1')
    .get(action);
}

// ------------------------------------------------------------------ S6 越权/授权分支

test('S6-a member 越权访问 admin 路由（HTML）→ 403/error 视图，写 1 条 authz.denied', () => {
  const before = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin')(
    mockReq({}, { user: { email: 'member@example.com', role: 'member' } }),
    res,
    () => { next += 1; }
  );
  assert.equal(res.statusCode, 403);
  assert.equal(next, 0);
  assert.equal(res.rendered.view, 'error');
  assert.equal(res.rendered.options.status, 403);
  assert.equal(auditCount('authz.denied'), before + 1, '拒绝必须恰好新增 1 条越权审计');
  const row = lastAudit('authz.denied');
  assert.equal(row.actor, 'member@example.com');
  assert.equal(row.ok, 0);
  assert.equal(row.target, '/admin/settings');
  assert.match(String(row.detail), /role=member need=admin/);
});

test('S6-b JSON 分支（xhr:true）→ 403 FORBIDDEN，写 1 条 authz.denied', () => {
  const before = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin')(
    mockReq({}, { user: { email: 'member@example.com', role: 'member' }, xhr: true }),
    res,
    () => { next += 1; }
  );
  assert.equal(res.statusCode, 403);
  assert.deepEqual(res.body, { ok: false, code: 'FORBIDDEN', message: '权限不足' });
  assert.equal(next, 0);
  assert.equal(auditCount('authz.denied'), before + 1);
});

test('S6-b JSON 分支（Accept: application/json）→ 403 FORBIDDEN，写 1 条 authz.denied', () => {
  const before = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin')(
    mockReq({ accept: 'application/json' }, { user: { email: 'member@example.com', role: 'member' } }),
    res,
    () => { next += 1; }
  );
  assert.equal(res.statusCode, 403);
  assert.deepEqual(res.body, { ok: false, code: 'FORBIDDEN', message: '权限不足' });
  assert.equal(next, 0);
  assert.equal(auditCount('authz.denied'), before + 1);
});

test('S6-c admin 合法放行 → next=1/200，authz.denied 计数不增（不误记合法访问）', () => {
  const before = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin')(
    mockReq({}, { user: { email: 'admin@example.com', role: 'admin' } }),
    res,
    () => { next += 1; }
  );
  assert.equal(next, 1);
  assert.equal(res.statusCode, 200);
  assert.equal(auditCount('authz.denied'), before, '合法访问不得记为越权');
});

test('S6-d 多角色命中：auditor 在 [admin,auditor] 中 → 放行，authz.denied 不增', () => {
  const before = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin', 'auditor')(
    mockReq({}, { user: { email: 'auditor@example.com', role: 'auditor' } }),
    res,
    () => { next += 1; }
  );
  assert.equal(next, 1);
  assert.equal(res.statusCode, 200);
  assert.equal(auditCount('authz.denied'), before);
});

test('S6-d 多角色未命中：guest → 403 + authz.denied +1（need=admin|auditor）', () => {
  const before = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin', 'auditor')(
    mockReq({}, { user: { email: 'guest@example.com', role: 'guest' }, xhr: true }),
    res,
    () => { next += 1; }
  );
  assert.equal(res.statusCode, 403);
  assert.equal(next, 0);
  assert.equal(auditCount('authz.denied'), before + 1);
  const row = lastAudit('authz.denied');
  assert.equal(row.actor, 'guest@example.com');
  assert.equal(row.ok, 0);
  assert.match(String(row.detail), /role=guest need=admin\|auditor/);
});

test('S6-e 匿名 xhr → 401 LOGIN_REQUIRED，写 auth.denied（不是 authz.denied）+1', () => {
  const beforeAuth = auditCount('auth.denied');
  const beforeAuthz = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin')(mockReq({}, { user: null, xhr: true }), res, () => { next += 1; });
  assert.equal(res.statusCode, 401);
  assert.equal(res.body.code, 'LOGIN_REQUIRED');
  assert.equal(next, 0);
  assert.equal(auditCount('auth.denied'), beforeAuth + 1, '匿名访问必须写 auth.denied');
  assert.equal(auditCount('authz.denied'), beforeAuthz, '匿名访问不得写 authz.denied');
  const row = lastAudit('auth.denied');
  assert.equal(row.actor, null);
  assert.equal(row.ok, 0);
  assert.equal(row.target, '/admin/settings');
});

test('S6-e 匿名 HTML → redirect /login?next=...&notice=login_required，写 auth.denied +1', () => {
  const beforeAuth = auditCount('auth.denied');
  const beforeAuthz = auditCount('authz.denied');
  const res = mockRes();
  let next = 0;
  requireRole('admin')(mockReq({}, { user: null }), res, () => { next += 1; });
  assert.equal(next, 0);
  assert.match(
    String(res.redirectTo),
    /^\/login\?next=%2Fadmin%2Fsettings&notice=login_required$/
  );
  assert.equal(auditCount('auth.denied'), beforeAuth + 1);
  assert.equal(auditCount('authz.denied'), beforeAuthz);
});

test('S6-f requireAuth 非 active 账号 → 403/error(status=403)，写 auth.denied(status=disabled)+1', () => {
  const before = auditCount('auth.denied');
  const res = mockRes();
  let next = 0;
  requireAuth(
    mockReq({}, { user: { email: 'x@example.com', status: 'disabled' } }),
    res,
    () => { next += 1; }
  );
  assert.equal(res.statusCode, 403);
  assert.equal(res.rendered.options.status, 403);
  assert.equal(next, 0);
  assert.equal(auditCount('auth.denied'), before + 1);
  const row = lastAudit('auth.denied');
  assert.equal(row.actor, 'x@example.com');
  assert.equal(row.ok, 0);
  assert.match(String(row.detail), /status=disabled/);
});

test('S6-g 可证伪自证：同一 actor 仅 role 不同 → member 恰好 +1 / admin +0', () => {
  const actor = 'falsify@example.com';
  const run = (role) => {
    const res = mockRes();
    let next = 0;
    requireRole('admin')(
      mockReq({}, { user: { email: actor, role }, xhr: true }),
      res,
      () => { next += 1; }
    );
    return { res, next };
  };
  const base = auditCount('authz.denied');

  const m = run('member');
  assert.equal(m.next, 0);
  assert.equal(m.res.statusCode, 403);
  assert.equal(auditCount('authz.denied'), base + 1, 'member 必须恰好 +1（写成 >= 或恒等都会放过假实现）');

  const a = run('admin');
  assert.equal(a.next, 1);
  assert.equal(a.res.statusCode, 200);
  assert.equal(auditCount('authz.denied'), base + 1, 'admin 必须 +0');

  // 若差分 SQL 漏 `WHERE action='authz.denied'`，e1/e2 写入的 auth.denied 会抬高
  // 全局计数，使本用例及 c/d1 的「+0」断言误红；若 a/b/d2 的 +1 断言被改成
  // 恒真（如只断言 after>=before），则真实实现里摘掉 logAudit 也会误绿。
  // 两段串联同时挡住这两种假绿。
});
