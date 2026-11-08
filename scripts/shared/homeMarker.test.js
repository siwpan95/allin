'use strict';

/**
 * B5 负向夹具（防 false-green）：正面证明 isHomeMarkerPresent 在「marker 缺失」时
 * 返回 false，而不是只能靠反复全绿来间接暗示 CP4 的判定正确。
 *
 * 此前 CP4 的「首页 marker 探测」判定内联在 smoke_e2e.mjs 里
 * （home.status===200 && (await home.text()).includes('ALLIN LAB')）。
 * 全绿跑再多也只能证明「绿的时候绿」，无法正面证明「该红的时候会红」。
 * 抽成纯函数后，这里直接用单测钉死判定边界。
 *
 * 跑法：node --test scripts/shared/homeMarker.test.js
 */

const test = require('node:test');
const assert = require('node:assert');

const isHomeMarkerPresent = require('./homeMarker.js');

test('marker 命中：HTTP 200 且正文含 "ALLIN LAB" → true', () => {
  assert.strictEqual(isHomeMarkerPresent(200, '欢迎来到 ALLIN LAB'), true);
});

test('marker 缺失：HTTP 200 但正文无 marker → false（防 false-green 核心）', () => {
  assert.strictEqual(isHomeMarkerPresent(200, '这是一个普通首页'), false);
});

test('状态码非 200：即便正文含 marker 也 → false', () => {
  assert.strictEqual(isHomeMarkerPresent(500, 'ALLIN LAB'), false);
  assert.strictEqual(isHomeMarkerPresent(302, 'ALLIN LAB'), false);
});

test('text 非字符串：防御性 → false', () => {
  assert.strictEqual(isHomeMarkerPresent(200, null), false);
  assert.strictEqual(isHomeMarkerPresent(200, undefined), false);
  assert.strictEqual(isHomeMarkerPresent(200, 12345), false);
});

test('判定口径与 CP4 原内联逻辑逐情形一致', () => {
  const inline = (status, text) =>
    status === 200 && typeof text === 'string' && text.includes('ALLIN LAB');
  const cases = [
    [200, 'ALLIN LAB'],
    [200, 'no marker here'],
    [404, 'ALLIN LAB'],
    [200, null],
    [301, 'ALLIN LAB'],
    [200, 0],
  ];
  for (const [s, t] of cases) {
    assert.strictEqual(
      isHomeMarkerPresent(s, t),
      inline(s, t),
      `口径不一致：status=${s}, text=${JSON.stringify(t)}`,
    );
  }
});
