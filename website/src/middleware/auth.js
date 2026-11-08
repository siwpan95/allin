'use strict';

/**
 * 认证与权限中间件。
 *
 * 三条口径：
 *   1) **匿名访问受保护内容不报错，而是友好引导**：跳转 /login?next=<原路径>&notice=login_required；
 *      AJAX/JSON 请求则回 401 + 结构化 JSON，前端按 code 提示；
 *   2) **越权必留痕**：任何一次被拒的访问都写 audit_log，安全事件可追责；
 *   3) **CSRF 同源校验**：会话里存令牌，所有写操作的表单必须带回同一个令牌。
 */

const crypto = require('node:crypto');
const userService = require('../services/userService');
const { logAudit } = require('../services/audit');

function parseCookies(header) {
  const jar = {};
  if (!header) return jar;
  for (const part of header.split(';')) {
    const idx = part.indexOf('=');
    if (idx < 0) continue;
    // 2026-11-08 深度审核：畸形 Cookie（如 %E0%A4%A）让 decodeURIComponent
    // 抛 URIError，挂在全局 attachUser 上 ⇒ 任意请求 500（请求级 DoS）。
    // 单个坏 cookie 不应影响整次请求，按原值保留并继续。
    let value = part.slice(idx + 1).trim();
    try { value = decodeURIComponent(value); } catch { /* 保留原始值 */ }
    jar[part.slice(0, idx).trim()] = value;
  }
  return jar;
}

function attachUser(req, res, next) {
  const jar = parseCookies(req.headers.cookie);
  const sid = jar[require('../config').session.cookieName];
  req.user = sid ? userService.getSessionUser(sid) : null;
  res.locals.user = req.user;
  res.locals.csrfToken = req.user ? req.user.csrfToken : '';
  next();
}

function wantsJson(req) {
  return req.xhr || (req.headers.accept || '').includes('application/json');
}

function denyLogin(req, res, noticeCode = 'login_required') {
  logAudit({
    actor: req.user ? req.user.email : null,
    action: 'auth.denied',
    target: req.originalUrl,
    ok: false,
    detail: 'anonymous or expired session',
  });
  if (wantsJson(req)) {
    return res.status(401).json({
      ok: false,
      code: 'LOGIN_REQUIRED',
      message: '请先登录后再访问该内容',
      loginUrl: `/login?next=${encodeURIComponent(req.originalUrl)}`,
    });
  }
  return res.redirect(`/login?next=${encodeURIComponent(req.originalUrl)}&notice=${noticeCode}`);
}

function requireAuth(req, res, next) {
  if (!req.user) return denyLogin(req, res, 'login_required');
  if (req.user.status !== 'active') {
    logAudit({ actor: req.user.email, action: 'auth.denied', target: req.originalUrl, ok: false, detail: `status=${req.user.status}` });
    return res.status(403).render('error', {
      title: '账号不可用',
      status: 403,
      message: '账号已被停用，请联系管理员恢复。',
      hint: '',
      pageKey: '',
    });
  }
  return next();
}

function requireRole(...roles) {
  return function checkRole(req, res, next) {
    if (!req.user) return denyLogin(req, res, 'login_required');
    if (!roles.includes(req.user.role)) {
      logAudit({
        actor: req.user.email,
        action: 'authz.denied',
        target: req.originalUrl,
        ok: false,
        detail: `role=${req.user.role} need=${roles.join('|')}`,
      });
      if (wantsJson(req)) {
        return res.status(403).json({ ok: false, code: 'FORBIDDEN', message: '权限不足' });
      }
      return res.status(403).render('error', {
        title: '权限不足',
        status: 403,
        message: '这个区域仅管理员可访问。',
        hint: '已记录一次越权尝试；如需权限请联系站点管理员。',
        pageKey: '',
      });
    }
    return next();
  };
}

function csrfProtect(req, res, next) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return next();
  if (!req.user) return denyLogin(req, res, 'login_required');
  const sent = String(req.body?._csrf || req.headers['x-csrf-token'] || '');
  const expected = String(req.user.csrfToken || '');
  const ok =
    sent.length === expected.length &&
    expected.length > 0 &&
    crypto.timingSafeEqual(Buffer.from(sent), Buffer.from(expected));
  if (!ok) {
    logAudit({ actor: req.user.email, action: 'csrf.failed', target: req.originalUrl, ok: false });
    return res.status(403).render('error', {
      title: '表单校验失败',
      status: 403,
      message: '表单令牌无效或已过期。',
      hint: '请返回上一页刷新后重试（通常发生在页面停留过久）。',
      pageKey: '',
    });
  }
  return next();
}

module.exports = { attachUser, requireAuth, requireRole, csrfProtect, parseCookies, wantsJson };
