'use strict';

/**
 * website 安全与一致性回归（2026-11-04 P2 修复：F-008 / F-009 / F-013 / F-014）。
 *
 * 覆盖：
 *   F-008  rateLimiter 双桶（换 email 不能绕过 IP 硬上限）
 *   F-009  sameOriginGuard（跨站 / 异 Origin 拒绝，同源与裸请求放行）
 *   F-013  contentService.withTransaction 回滚 + contactService 留言/审计原子
 *          + assetService.deleteAsset 补偿基础
 *   F-014  assetDelivery 对非位图强制 Content-Disposition: attachment
 *
 * 用 node:test（零新依赖），DB_PATH / KEY_DIR 重定向到临时目录，
 * 全程不触碰真实 data/。跑法：npm test（或 node --test test/）。
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

// —— 必须在 require 任何 src 模块之前重定向数据目录（config 在 require 时读 env）——
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'allin-security-test-'));
process.env.DB_PATH = path.join(TMP, 'data', 'site.db');
process.env.KEY_DIR = path.join(TMP, 'data', 'keys');
delete process.env.SITE_MASTER_KEY_BASE64;

const { getDb, closeDb } = require('../src/db');
const { rateLimiter, sameOriginGuard } = require('../src/middleware/security');
const content = require('../src/services/contentService');
const contactService = require('../src/services/contactService');
const assetService = require('../src/services/assetService');
const { sendAsset } = require('../src/services/assetDelivery');

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
    method: 'POST',
    originalUrl: '/contact',
    headers,
    ip: '203.0.113.7',
    body: {},
    user: { email: 'admin@example.com' },
    xhr: false,
    protocol: 'http',
    accepts: () => false,
    ...extra,
  };
}

function count(sql, ...args) {
  return getDb().prepare(sql).get(...args).n;
}

// ------------------------------------------------------------------ F-009 来源围栏

test('sameOriginGuard: Sec-Fetch-Site: cross-site → 403 且不放行到业务', () => {
  const res = mockRes();
  let next = 0;
  sameOriginGuard(mockReq({ 'sec-fetch-site': 'cross-site' }), res, () => { next += 1; });
  assert.equal(res.statusCode, 403);
  assert.equal(next, 0);
  assert.deepEqual(res.body, { ok: false, code: 'CSRF_BLOCKED', message: '请求来源不被允许' });
});

test('sameOriginGuard: 异 Origin → 403（反代按 x-forwarded-proto 判定期望源）', () => {
  for (const headers of [
    { origin: 'https://evil.example.com', host: 'site.example.com' },
    { 'x-forwarded-proto': 'https', origin: 'http://site.example.com', host: 'site.example.com' },
  ]) {
    const res = mockRes();
    let next = 0;
    sameOriginGuard(mockReq(headers), res, () => { next += 1; });
    assert.equal(res.statusCode, 403, `必须拒绝：${JSON.stringify(headers)}`);
    assert.equal(next, 0);
  }
});

test('sameOriginGuard: 同源 Origin / same-origin / 裸请求均放行', () => {
  for (const headers of [
    { origin: 'http://site.example.com', host: 'site.example.com' },
    { 'sec-fetch-site': 'same-origin', host: 'site.example.com' },
    { 'sec-fetch-site': 'none', host: 'site.example.com' },
    { 'x-forwarded-proto': 'https', origin: 'https://site.example.com', host: 'site.example.com' },
    {}, // curl / CLI / 冒烟脚本：无来源信号，不是 CSRF 向量
  ]) {
    const res = mockRes();
    let next = 0;
    sameOriginGuard(mockReq(headers), res, () => { next += 1; });
    assert.equal(next, 1, `应放行：${JSON.stringify(headers)}`);
    assert.equal(res.statusCode, 200);
  }
});

test('sameOriginGuard: GET / HEAD / OPTIONS 不受写围栏影响', () => {
  for (const method of ['GET', 'HEAD', 'OPTIONS']) {
    const res = mockRes();
    let next = 0;
    sameOriginGuard(mockReq({ 'sec-fetch-site': 'cross-site' }, { method }), res, () => { next += 1; });
    assert.equal(next, 1, `${method} 应直接放行`);
  }
});

// ------------------------------------------------------------------ F-008 双桶限流

test('rateLimiter: 换 email 不能绕过 IP 桶（原实现键里混 ip，换邮箱即换桶）', () => {
  const limit = rateLimiter({ name: 'probe-ip', windowMs: 60_000, max: 2, ipMax: 3 });
  const outcomes = [];
  for (const email of ['a@example.com', 'b@example.com', 'c@example.com', 'd@example.com']) {
    const res = mockRes();
    let next = 0;
    limit(mockReq({}, { body: { email } }), res, () => { next += 1; });
    outcomes.push(next === 1 ? 'pass' : `blocked:${res.statusCode}`);
  }
  assert.deepEqual(outcomes, ['pass', 'pass', 'pass', 'blocked:429']);
});

test('rateLimiter: 同一 email 仍受 email 维 max 约束，与 ip 上限互不干扰', () => {
  const limit = rateLimiter({ name: 'probe-email', windowMs: 60_000, max: 2, ipMax: 100 });
  const outcomes = [];
  for (let i = 0; i < 4; i += 1) {
    const res = mockRes();
    let next = 0;
    limit(mockReq({}, { body: { email: 'same@example.com' } }), res, () => { next += 1; });
    outcomes.push(next === 1 ? 'pass' : `blocked:${res.statusCode}`);
  }
  assert.deepEqual(outcomes, ['pass', 'pass', 'blocked:429', 'blocked:429']);
});

// ------------------------------------------------------------------ F-013 事务与补偿

test('contentService.withTransaction: 抛错时整体回滚，不留半写入', () => {
  const before = count("SELECT COUNT(*) AS n FROM secure_docs WHERE doc_key = 'txn-rollback-probe'");
  assert.equal(before, 0);
  assert.throws(() => {
    content.withTransaction(() => {
      content.putDoc({ docKey: 'txn-rollback-probe', kind: 'probe', status: 'new', data: { v: 1 } });
      throw new Error('forced failure');
    });
  }, /forced failure/);
  assert.equal(
    count("SELECT COUNT(*) AS n FROM secure_docs WHERE doc_key = 'txn-rollback-probe'"),
    0,
    '事务内写入必须随异常回滚'
  );
  // 回滚后连接必须可继续正常写入（没有卡在半开事务里）
  content.putDoc({ docKey: 'txn-after-rollback', kind: 'probe', status: 'new', data: { v: 2 } });
  assert.equal(count("SELECT COUNT(*) AS n FROM secure_docs WHERE doc_key = 'txn-after-rollback'"), 1);
});

test('contentService.withTransaction: 内层复用外层事务，不重复 BEGIN', () => {
  const result = content.withTransaction(() =>
    content.withTransaction(() => {
      content.putDoc({ docKey: 'txn-nested', kind: 'probe', status: 'new', data: { v: 3 } });
      return 42;
    })
  );
  assert.equal(result, 42);
  assert.equal(count("SELECT COUNT(*) AS n FROM secure_docs WHERE doc_key = 'txn-nested'"), 1);
});

test('contactService.createMessage: 校验失败既不写留言也不写审计', () => {
  const docsBefore = count("SELECT COUNT(*) AS n FROM secure_docs WHERE kind = 'contact'");
  const auditBefore = count("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'contact.submit'");
  assert.throws(
    () => contactService.createMessage({ name: 'A', email: 'not-an-email', body: 'hi' }),
    /邮箱格式不正确/
  );
  assert.equal(count("SELECT COUNT(*) AS n FROM secure_docs WHERE kind = 'contact'"), docsBefore);
  assert.equal(count("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'contact.submit'"), auditBefore);
});

test('contactService.createMessage: 正常提交同时产出留言与审计（同一事务）', () => {
  const r = contactService.createMessage({ name: '张三', email: 'z@example.com', body: '需求描述' });
  assert.equal(count('SELECT COUNT(*) AS n FROM secure_docs WHERE doc_key = ?', r.docKey), 1);
  assert.equal(
    count("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'contact.submit' AND target = ?", r.docKey),
    1
  );
});

test('assetService.deleteAsset: 删除生效（contact 孤儿附件补偿的基础）', () => {
  assetService.putAsset({
    assetKey: 'orphan-probe.txt',
    buffer: Buffer.from('x'),
    mime: 'text/plain',
    isPublic: false,
    meta: { scope: 'admin' },
  });
  assert.ok(assetService.getAssetRow('orphan-probe.txt'));
  assert.equal(assetService.deleteAsset('orphan-probe.txt'), 1);
  assert.ok(!assetService.getAssetRow('orphan-probe.txt'));
  assert.equal(assetService.deleteAsset('orphan-probe.txt'), 0);
});

// ------------------------------------------------------------------ F-014 附件强制下载

function deliver(assetKey, mime, isPublic, buffer) {
  assetService.putAsset({
    assetKey,
    buffer,
    mime,
    isPublic,
    meta: { scope: isPublic ? 'public' : 'admin' },
  });
  const res = mockRes();
  sendAsset({ req: mockReq(), res, assetKey, allow: [isPublic ? 'public' : 'admin'] });
  return res;
}

test('assetDelivery: SVG / 文本 / PDF 一律强制 attachment（防同源内联存储型 XSS）', () => {
  for (const [key, mime, buf] of [
    ['probe.svg', 'image/svg+xml', Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"></svg>')],
    ['probe.txt', 'text/plain; charset=utf-8', Buffer.from('hello')],
    ['probe.pdf', 'application/pdf', Buffer.from('%PDF-1.4')],
  ]) {
    const res = deliver(key, mime, true, buf);
    assert.equal(res.statusCode, 200, `${key} 应正常投递`);
    assert.match(String(res.headers['Content-Disposition'] || ''), /^attachment; /, `${key} 必须强制下载`);
  }
});

test('assetDelivery: 非 public 资源即使是位图也强制下载', () => {
  const res = deliver('private.png', 'image/png', false, Buffer.from('89504e470d0a1a0a', 'hex'));
  assert.equal(res.statusCode, 200);
  assert.match(String(res.headers['Content-Disposition'] || ''), /^attachment; /);
});

test('assetDelivery: public 位图保持内联（不误伤正常配图）', () => {
  const res = deliver('probe.png', 'image/png', true, Buffer.from('89504e470d0a1a0a', 'hex'));
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers['Content-Type'], 'image/png');
  assert.equal(res.headers['Content-Disposition'], undefined, '位图不应被强制下载');
});

test('assetDelivery: filename 白名单化，杜绝响应头注入', () => {
  const res = deliver('probe\r\nX-Injected: 1.svg', 'image/svg+xml', true, Buffer.from('<svg/>'));
  const cd = String(res.headers['Content-Disposition'] || '');
  assert.ok(!cd.includes('\r') && !cd.includes('\n'), '响应头不得含换行');
  assert.match(cd, /^attachment; filename="[A-Za-z0-9._-]+"$/);
});
