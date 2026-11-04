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
 *
 * 2026-11-04 工程审查修复（C3）：hits Map 此前只增不删，唯一 `ip:email` 键
 * 永久驻留，长驻进程内存无界增长（攻击者可枚举随机 email 放大条目数）。
 * 现补：① 窗口过期的惰性清理；② 容量上限（超限丢弃最旧键，进程内限流本就是尽力而为）。
 */
const RATE_LIMIT_MAX_TRACKED = 10000;

/**
 * 固定窗口限流（进程内）。双桶口径（2026-11-04 P2 修复 F-008）：
 *   - `email:` 桶：防单账号暴力（原实现键里混了 ip，换 email 即换桶）；
 *   - `ip:`   桶：防「换 email 即换桶」绕过 —— 同一 IP 无论换多少 email，
 *                 总尝试数仍受硬上限约束。
 * contact 的限流挂在 multer 之前，body 尚无 email ⇒ 自动退化为纯 IP 口径，
 * 行为与修复前一致（max=5）。ipMax 可单独调共享 IP（NAT/办公室）的余量。
 */
function rateLimiter({ windowMs = 10 * 60 * 1000, max = 8, ipMax = null, name = 'generic' } = {}) {
  const ipCeiling = Number.isFinite(ipMax) ? ipMax : max;
  const hits = new Map();
  return function limit(req, res, next) {
    const now = Date.now();
    // ① 窗口过期的惰性清理；② 容量上限（超限丢弃最旧键，进程内限流本就是尽力而为）
    if (hits.size > 256) {
      for (const [k, v] of hits) {
        if (now > v.resetAt) hits.delete(k);
      }
    }
    if (hits.size >= RATE_LIMIT_MAX_TRACKED) {
      const oldest = hits.keys().next().value;
      hits.delete(oldest);
    }

    const email = String(req.body?.email || '').trim().toLowerCase();
    const checks = [[`ip:${String(req.ip || '')}`, ipCeiling, 'ip']];
    if (email) checks.push([`email:${email}`, max, 'email']);

    let blocked = null;
    for (const [key, ceiling, dimension] of checks) {
      const entry = hits.get(key);
      if (!entry || now > entry.resetAt) {
        hits.set(key, { count: 1, resetAt: now + windowMs });
        continue;
      }
      entry.count += 1;
      if (entry.count > ceiling && !blocked) blocked = { entry, ceiling, dimension };
    }
    if (!blocked) return next();

    const { entry, ceiling, dimension } = blocked;
    logAudit({
      actor: email ? email.replace(/^(.{1,2})[^@]*@/, '$1***@') : null,
      action: `rate_limit.${name}`,
      // C4：审计流水不写完整明文邮箱；ip 与脱敏邮箱一并留痕便于溯源。
      target: `${String(req.ip || '')}:${email ? email.replace(/^(.{1,2})[^@]*@/, '$1***@') : ''}`,
      ok: false,
      detail: `${entry.count} 次/${windowMs}ms（${dimension} 维上限 ${ceiling}）`,
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
  };
}

/**
 * 匿名写端点的来源围栏（/contact 用，2026-11-04 P2 修复 F-009）。
 *
 * 现有 csrfProtect 依赖登录会话里的 csrfToken，匿名表单没有会话 ⇒ 不能直接用。
 * 浏览器发起跨站表单 POST 必带 `Origin`，且带 `Sec-Fetch-Site: cross-site`；
 * 据此拒绝即可挡住「任意站驱动受害者写留言 + 传附件」。
 * 无来源信号的裸请求（curl / CLI / 服务端 / 冒烟脚本）不是 CSRF 向量，放行 ——
 * 这与门户那条围栏不同：门户只服务本机，可用 X-Allin-Local 标记，公开站不能要求它。
 */
function sameOriginGuard(req, res, next) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return next();
  const site = String(req.headers['sec-fetch-site'] || '').toLowerCase();
  const origin = String(req.headers.origin || '');
  const deny = (reason) => {
    logAudit({ actor: null, action: 'csrf.blocked', target: req.originalUrl, ok: false, detail: reason });
    if (req.accepts('html') && !req.xhr) {
      return res.status(403).render('error', {
        title: '请求来源不被允许',
        status: 403,
        message: '该请求不是从本站发起的，已阻止提交。',
        hint: '请从本站页面重新提交；若持续出现请检查浏览器设置。',
        pageKey: '',
      });
    }
    return res.status(403).json({ ok: false, code: 'CSRF_BLOCKED', message: '请求来源不被允许' });
  };
  if (site && site !== 'same-origin' && site !== 'none') return deny(`sec-fetch-site=${site}`);
  if (origin) {
    // 反代后 x-forwarded-proto 才是真实协议；缺省回退 Express 的 req.protocol。
    const proto = String(req.headers['x-forwarded-proto'] || req.protocol || 'http').split(',')[0].trim();
    const expected = `${proto}://${String(req.headers.host || '')}`;
    if (origin !== expected) return deny(`origin=${origin} expected=${expected}`);
  }
  return next();
}

module.exports = { securityHeaders, rateLimiter, sameOriginGuard };
