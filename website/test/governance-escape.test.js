// WJ-02 回归测试：治理看板前端对服务端可控字段（degraded.message / code / message）
// 必须做 HTML 转义，不能以 innerHTML 原样落地 XSS。
//
// 无 jsdom 依赖：用最小 DOM 桩加载 governance.js（IIFE），驱动两条真实渲染路径
// （降级三态渲染 + 写操作失败回显），断言恶意载荷被转义、不出现可执行标签。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const GOV = path.resolve('website/src/public/js/governance.js');

// ---- DOM 桩 ----
const elements = new Map();
function makeEl(id) {
  const el = {
    id,
    _html: '',
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    textContent: '',
    hidden: false,
    disabled: false,
    dataset: {},
    classList: { add() {}, remove() {} },
    setAttribute() {},
    getAttribute() { return ''; }, // gov-config 取不到属性 ⇒ CFG 走默认值（admin='0'，不挂 entries 轮询）
    addEventListener() {},
    closest() { return null; },
  };
  return el;
}
function getEl(id) {
  if (!elements.has(id)) elements.set(id, makeEl(id));
  return elements.get(id);
}

const listeners = {};
global.document = {
  hidden: false,
  getElementById: (id) => getEl(id),
  addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); },
};
global.location = { assign() {} };

// 让 loop() 的递归 setTimeout 只跑有限次，避免事件循环挂起；同时让 tick 真正执行一次。
let timerBudget = 40;
const realSetTimeout = setTimeout;
global.setTimeout = (fn, _ms) => {
  // 跳过 showInline 的 8000ms 自动清除回调（function(){ el.innerHTML=''; }），
  // 在桩环境下它会以 0ms 提前清空 gov-inline，导致写操作失败回显断言落空。
  if (String(fn).includes('innerHTML')) return 0;
  return (timerBudget-- > 0 ? realSetTimeout(fn, 0) : 0);
};
global.clearTimeout = () => {};

// fetch 桩：entries 写操作失败回显走 code/message；其余（概览/编排）返回降级载荷。
function makeFetch() {
  return async (url) => {
    if (String(url).includes('entries')) {
      return {
        status: 200, ok: false,
        json: async () => ({ ok: false, code: '<script>alert(1)</script>', message: 'boom' }),
      };
    }
    return {
      status: 200, ok: true,
      json: async () => ({ degraded: { code: 'PORTAL_UNREACHABLE', message: '<img src=x onerror=alert(1)>' }, data: null }),
    };
  };
}
global.fetch = makeFetch();

await import(pathToFileURL(GOV).href);

function flush() { return new Promise((r) => realSetTimeout(r, 20)); }

test('服务端 degraded.message 经 innerHTML 渲染被转义（不出现可执行标签）', async () => {
  await flush(); // 等概览轮询 tick → renderDegrade → setCard(banner)
  const banner = getEl('gov-banner-overview').innerHTML;
  assert.ok(banner.length > 0, 'banner 应已被渲染');
  assert.ok(banner.includes('&lt;img'), '恶意 <img> 应被转义为 &lt;img');
  assert.ok(!banner.includes('<img src=x'), '不得出现未转义的 <img 标签');
});

test('写操作失败回显的 payload.code 被转义（不出现可执行标签）', async () => {
  // 构造两段式确认已跳过（无 data-confirm）、closest('[data-gov-action]') 命中、closest('form') 命中
  const form = { action: '/member/api/governance/entries/x/start' };
  const btn = {
    dataset: {},
    disabled: false,
    textContent: '',
    classList: { add() {}, remove() {} },
    closest(sel) { return sel === 'form' ? form : btn; },
  };
  const handler = listeners['click'][0];
  assert.ok(handler, 'document click 监听器应已注册');
  handler({ target: btn, preventDefault() {} });
  await flush(); // 等 submitAction 的 fetch + 回显落地
  const inline = getEl('gov-inline').innerHTML;
  assert.ok(inline.includes('&lt;script&gt;'), '恶意 <script> 应被转义为 &lt;script&gt;');
  assert.ok(!inline.includes('<script>alert(1)'), '不得出现未转义的 <script> 标签');
});
