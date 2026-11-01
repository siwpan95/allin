'use strict';

/**
 * 资源投递：把"数据库里的密文"变成 HTTP 响应。
 *
 * 职责边界（这一层专门处理失败）：
 *   - 不存在           → 404 + 占位图（不泄露库里有哪些 key）
 *   - 权限不匹配       → 匿名跳登录、已登录回 403，且都写审计
 *   - GCM 解密失败     → 410 + 占位图 + 审计留痕（视为安全事件，绝不是"返回空字节"）
 * 任何情况下都不把异常细节抛给用户，只回友好文案。
 */

const crypto = require('node:crypto');
const assetService = require('./assetService');
const { DecryptError } = require('../crypto/errors');
const { logAudit } = require('./audit');
const auth = require('../middleware/auth');

const PLACEHOLDER = (label) => Buffer.from(
  `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#0a0d16"/><stop offset="100%" stop-color="#1a0b26"/></linearGradient></defs>
  <rect width="640" height="360" fill="url(#g)"/>
  <g stroke="#00f0ff" stroke-opacity="0.25">
    ${Array.from({ length: 9 }, (_, i) => `<line x1="0" y1="${i * 40 + 20}" x2="640" y2="${i * 40 + 20}"/>`).join('')}
  </g>
  <text x="320" y="176" fill="#ff2bd6" font-family="monospace" font-size="22" text-anchor="middle">${label}</text>
  <text x="320" y="208" fill="#7b8798" font-family="monospace" font-size="13" text-anchor="middle">resource unavailable</text>
</svg>`,
  'utf8'
);

function parseMeta(row) {
  return assetService.readMeta(row);
}

function scopeOf(row) {
  const meta = parseMeta(row);
  return meta.scope || (Number(row.is_public) === 1 ? 'public' : 'private');
}

function sendPlaceholder(res, status, label) {
  res.status(status).type('image/svg+xml').set('Cache-Control', 'no-store').send(PLACEHOLDER(label));
}

/**
 * @param {object} args
 * @param {Array<string>} args.allow 允许的作用域：public / member / admin
 */
function sendAsset({ req, res, assetKey, allow = ['public'], denyNotice = 'login_needed_file' }) {
  const row = assetService.getAssetRow(assetKey);
  if (!row) {
    logAudit({ actor: req.user ? req.user.email : null, action: 'asset.missing', target: assetKey, ok: false });
    return sendPlaceholder(res, 404, '404 · 资源不存在');
  }

  const scope = scopeOf(row);
  if (!allow.includes(scope)) {
    logAudit({
      actor: req.user ? req.user.email : null,
      action: 'asset.forbidden',
      target: assetKey,
      ok: false,
      detail: `scope=${scope} allow=${allow.join('|')}`,
    });
    if (!req.user) {
      if (auth.wantsJson(req)) {
        return res.status(401).json({ ok: false, code: 'LOGIN_REQUIRED', message: '该资源需登录后访问' });
      }
      return res.redirect(`/login?next=${encodeURIComponent(req.originalUrl)}&notice=${denyNotice}`);
    }
    return res.status(403).render('error', {
      title: '无权访问该资源',
      status: 403,
      message: '这个文件属于其他权限组。',
      hint: '如需访问请联系管理员开通对应权限。',
      pageKey: '',
    });
  }

  let payload;
  try {
    payload = assetService.readAssetBytes(assetKey);
  } catch (err) {
    const code = err instanceof DecryptError ? err.code : 'DECRYPT_FAILED';
    console.error(`[asset] 解密失败 ${assetKey}: ${code}`);
    return sendPlaceholder(res, 410, `410 · ${code}`);
  }

  const etag = `"${crypto.createHash('sha256').update(payload.bytes).digest('hex').slice(0, 32)}"`;
  const cacheable = scope === 'public';
  res.set({
    'Content-Type': payload.mime,
    'Content-Length': payload.bytes.length,
    ETag: etag,
    'Cache-Control': cacheable ? 'public, max-age=86400' : 'private, no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  if (req.headers['if-none-match'] === etag) {
    res.status(304).end();
    return undefined;
  }
  if (req.method === 'HEAD') {
    res.end();
    return undefined;
  }
  res.send(payload.bytes);
  return undefined;
}

module.exports = { sendAsset, scopeOf, parseMeta, sendPlaceholder };
