'use strict';

/**
 * P1 开放重定向回归测试（2026-11-04 工程审查）。
 *
 * 直测 src/safeRedirect.js 的纯函数，逐条覆盖：反斜杠归一化、
 * 协议相对 URL、userinfo 混淆、字面控制字符、非 http(s) scheme，以及
 * withNotice 在带 query / 带 hash 时不能拼出双 ? 或把 notice 塞进 fragment。
 *
 * 单测与真实 router 解耦：不 require auth.js，因此不需要数据库 / 密钥环 /
 * 限流定时器，跑法 npm test（node --test "test/*.test.js" 每文件独立进程）。
 */

const test = require('node:test');
const assert = require('node:assert');

// 必须在 require 任何 src 模块之前固定 baseUrl（config 在 require 时读 env）
process.env.SITE_BASE_URL = 'http://localhost:9042';

const { safeNext, withNotice, BASE_ORIGIN } = require('../src/safeRedirect');
const BASE = 'http://localhost:9042';

test('BASE_ORIGIN 由 config.baseUrl 派生', () => {
  assert.strictEqual(BASE_ORIGIN, 'http://localhost:9042');
});

test('空值 / 非字符串 → 收敛到 /member', () => {
  assert.strictEqual(safeNext(''), '/member');
  assert.strictEqual(safeNext(null), '/member');
  assert.strictEqual(safeNext(undefined), '/member');
});

test('站内相对路径原样保留（含 query / hash）', () => {
  assert.strictEqual(safeNext('/services'), '/services');
  assert.strictEqual(safeNext('/member?tab=assets#list'), '/member?tab=assets#list');
  assert.strictEqual(safeNext('/'), '/');
});

test('同 origin 绝对 URL → 剥离 scheme/host，只回传站内路径', () => {
  assert.strictEqual(safeNext(`${BASE}/member?tab=a`), '/member?tab=a');
  assert.strictEqual(safeNext(BASE), '/');
});

test('站外 / 协议相对 / 反斜杠归一化一律拒绝（原实现漏报的核心向量）', () => {
  const evil = [
    'https://evil.example.com/',
    '//evil.example.com',
    '/\\evil.example.com',
    '\\/evil.example.com',
    'http:\\/\\/evil.example.com',
    'https:/\\evil.example.com',
  ];
  for (const v of evil) {
    assert.strictEqual(safeNext(v), '/member', `必须拒绝：${JSON.stringify(v)}`);
  }
});

test('userinfo 混淆 / 域名与端口伪装一律拒绝', () => {
  assert.strictEqual(safeNext('http://localhost:9042@evil.example.com/'), '/member');
  assert.strictEqual(safeNext('http://localhost:9042.evil.example.com/'), '/member');
  assert.strictEqual(safeNext('http://127.0.0.1:9042/'), '/member');
});

test('非 http(s) scheme 一律拒绝', () => {
  for (const v of ['javascript:alert(1)', 'data:text/html,x', 'vbscript:msgbox']) {
    assert.strictEqual(safeNext(v), '/member');
  }
});

test('字面控制字符 / CRLF 头注入一律拒绝', () => {
  assert.strictEqual(safeNext('/member\r\nSet-Cookie: a=b'), '/member');
  assert.strictEqual(safeNext('/member\u0000evil'), '/member');
  assert.strictEqual(safeNext('/member\u007f'), '/member');
});

test('百分号编码的反斜杠不会变成字面反斜杠（Location 不二次解码）', () => {
  const out = safeNext('/%5Cevil.example.com');
  assert.strictEqual(out.includes('\\'), false);
  assert.strictEqual(out.startsWith('/%5C'), true);
});

test('withNotice：无 query 时补 ?notice', () => {
  assert.strictEqual(withNotice('/member', 'welcome_back'), '/member?notice=welcome_back');
});

test('withNotice：已有 query 时用 &，绝不拼出双 ?', () => {
  const out = withNotice('/member?tab=assets', 'welcome_back');
  assert.strictEqual(out, '/member?tab=assets&notice=welcome_back');
  assert.strictEqual(out.split('?').length - 1, 1);
});

test('withNotice：带 hash 时 notice 插在 # 之前，不落进 fragment', () => {
  assert.strictEqual(
    withNotice('/member?tab=a#section', 'welcome_back'),
    '/member?tab=a&notice=welcome_back#section'
  );
  assert.strictEqual(
    withNotice('/member#top', 'welcome_back'),
    '/member?notice=welcome_back#top'
  );
});

test('withNotice 对 notice 做 URL 编码', () => {
  assert.strictEqual(withNotice('/member', 'a b&c'), '/member?notice=a%20b%26c');
});

test('登录成功回跳组合：safeNext + withNotice 不产生双 ? 且仍为站内', () => {
  const out = withNotice(safeNext('/member?tab=assets#list'), 'welcome_back');
  assert.strictEqual(out, '/member?tab=assets&notice=welcome_back#list');
  assert.strictEqual(out.split('?').length - 1, 1);
  assert.strictEqual(new URL(out, BASE).origin, BASE_ORIGIN);
});
