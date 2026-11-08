'use strict';

/**
 * B5 负向夹具支撑：把 smoke_e2e CP4 的「首页 marker 探测」判定抽成纯函数，
 * 使其可被单测直接证明——当首页不含 'ALLIN LAB' 时判定为 false（防 false-green）。
 *
 * 判定口径与 CP4 原内联逻辑完全一致：仅 HTTP 200 且正文含 'ALLIN LAB' 才算命中。
 * 抽出来后，单测能正面证明「marker 缺失 → false」，而不是只能靠全绿反复跑来间接暗示。
 */

function isHomeMarkerPresent(status, text) {
  return status === 200 && typeof text === 'string' && text.includes('ALLIN LAB');
}

module.exports = isHomeMarkerPresent;
