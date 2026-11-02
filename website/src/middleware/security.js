'use strict';

/**
 * 安全基线：响应头 + 登录限流。
 * 不引入 helmet —— 需要的头就这几个，自己设更可控，也少一个依赖。
 */

const { logAudit } = require('../services/audit');

function securityHeaders(req, res, next) {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'geolocation=(), camera=(), microphone=()');
  res.setHeader(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "script-src 'self'",
      // 2026-11-02 实测（Chromium）：全站 10 个模板共 120 处内联 style="" 被本策略拦截，
      // 管理台布局被打断。样式注入的 XSS 风险远低于脚本（script-src 仍严格 'self'），
      // 故 style-src 放行内联；模板侧后续如收敛为 class，可撤掉 'unsafe-inline'。
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self' data:",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
    ].join('; ')
  );
  next();
}

/**
 * 固定窗口限流（进程内）。单机部署够用；多实例部署时换成共享存储，
 * 接口保持相同，无需改调用方。
 */
function rateLimiter({ windowMs = 10 * 60 * 1000, max = 8, name = 'generic' } = {}) {
  const hits = new Map();
  return function limit(req, res, next) {
    const key = `${req.ip}:${String(req.body?.email || '').trim().toLowerCase()}`;
    const now = Date.now();
    const entry = hits.get(key);
    if (!entry || now > entry.resetAt) {
      hits.set(key, { count: 1, resetAt: now + windowMs });
      return next();
    }
    entry.count += 1;
    if (entry.count > max) {
      logAudit({
        actor: String(req.body?.email || '').replace(/^(.{1,2})[^@]*@/, '$1***@') || null,
        action: `rate_limit.${name}`,
        target: key,
        ok: false,
        detail: `${entry.count} 次/${windowMs}ms`,
      });
      if (req.accepts('html') && !req.xhr) {
        return res.status(429).render('error', {
          title: '请求过于频繁',
          status: 429,
          message: '尝试次数过多，请等待片刻后重试。',
          hint: '这是防暴力的临时限制，不会封禁账号。',
          pageKey: '',
        });
      }
      return res.status(429).json({ ok: false, code: 'RATE_LIMITED', message: '尝试过于频繁' });
    }
    return next();
  };
}

module.exports = { securityHeaders, rateLimiter };
