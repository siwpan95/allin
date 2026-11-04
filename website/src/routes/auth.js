'use strict';

/** 注册 / 登录 / 登出 / 会话保持。 */

const express = require('express');
const config = require('../config');
const userService = require('../services/userService');
const { logAudit } = require('../services/audit');
const { requireAuth, csrfProtect } = require('../middleware/auth');
const { rateLimiter } = require('../middleware/security');

const router = express.Router();

/** 审计流水里不写完整邮箱，够定位即可。 */
function maskEmail(email) {
  return String(email || '').replace(/^(.{1,2})[^@]*@/, '$1***@');
}

// 回跳白名单抽到纯函数模块，见 src/safeRedirect.js（P1 开放重定向修复）
// 注：不放 lib/ —— g05-hygiene 把 lib/ 视为被忽略的产物目录，跟踪它会判红。
const { safeNext, withNotice } = require('../safeRedirect');

function setSessionCookie(res, sessionId) {
  res.cookie(config.session.cookieName, sessionId, {
    httpOnly: true,
    sameSite: 'lax',
    secure: config.session.secure,
    maxAge: config.session.ttlHours * 3600 * 1000,
    path: '/',
  });
}

router.get('/login', (req, res) => {
  if (req.user) return res.redirect('/member');
  res.render('login', {
    title: '登录 · allin 官网',
    pageKey: 'login',
    next: safeNext(req.query.next),
    form: { email: '' },
    errors: [],
  });
});

router.post('/login', rateLimiter({ name: 'login', max: 8, windowMs: 10 * 60 * 1000 }), (req, res, next) => {
  try {
    const email = String(req.body.email || '').trim();
    const password = String(req.body.password || '');
    const errors = [];
    if (!userService.validateEmail(email)) errors.push('请填写有效的邮箱地址');
    if (!password) errors.push('请填写口令');

    const user = errors.length === 0 ? userService.findUserByEmail(email) : null;
    if (!errors.length && (!user || !userService.verifyPassword(user, password))) {
      if (!user) userService.dummyHash(password);
      errors.push('邮箱或口令不正确');
      logAudit({ actor: maskEmail(email), action: 'auth.login_failed', target: null, ok: false });
    }

    if (errors.length) {
      return res.status(400).render('login', {
        title: '登录 · allin 官网',
        pageKey: 'login',
        next: safeNext(req.body.next),
        form: { email },
        errors,
      });
    }

    if (user.status !== 'active') {
      return res.status(403).render('error', {
        title: '账号不可用',
        status: 403,
        message: '该账号已被停用。',
        hint: '请联系站点管理员恢复后重试。',
        pageKey: '',
      });
    }

    const session = userService.createSession(user.id, { ip: req.ip, userAgent: req.headers['user-agent'] });
    setSessionCookie(res, session.id);
    userService.touchLogin(user.id);
    logAudit({ actor: `user:${user.id}`, action: 'auth.login', target: `user:${user.id}` });
    return res.redirect(withNotice(safeNext(req.body.next), 'welcome_back'));
  } catch (err) {
    return next(err);
  }
});

router.get('/register', (req, res) => {
  if (req.user) return res.redirect('/member');
  res.render('register', {
    title: '注册 · allin 官网',
    pageKey: 'register',
    next: safeNext(req.query.next),
    form: { email: '', displayName: '' },
    errors: [],
  });
});

router.post('/register', rateLimiter({ name: 'register', max: 10, windowMs: 10 * 60 * 1000 }), (req, res, next) => {
  try {
    const form = {
      email: String(req.body.email || '').trim(),
      displayName: String(req.body.displayName || '').trim(),
    };
    const password = String(req.body.password || '');
    const errors = [];

    if (!userService.validateEmail(form.email)) errors.push('请填写有效的邮箱地址');
    if (form.displayName.length < 2) errors.push('昵称至少 2 个字符');
    const pwdError = userService.validatePassword(password);
    if (pwdError) errors.push(pwdError);
    if (String(req.body.passwordConfirm || '') !== password) errors.push('两次输入的口令不一致');

    if (errors.length) {
      return res.status(400).render('register', {
        title: '注册 · allin 官网',
        pageKey: 'register',
        next: safeNext(req.body.next),
        form,
        errors,
      });
    }

    const created = userService.createUser({ email: form.email, password, displayName: form.displayName });
    const session = userService.createSession(created.id, { ip: req.ip, userAgent: req.headers['user-agent'] });
    setSessionCookie(res, session.id);
    userService.touchLogin(created.id);
    return res.redirect('/member?notice=registered');
  } catch (err) {
    // 业务校验错误（邮箱已注册等）回表单，系统错误交给错误页
    if (err.message === '该邮箱已注册' || err.message === '邮箱格式不正确' || /^口令/.test(err.message)) {
      return res.status(400).render('register', {
        title: '注册 · allin 官网',
        pageKey: 'register',
        next: safeNext(req.body.next),
        form: { email: String(req.body.email || '').trim(), displayName: String(req.body.displayName || '').trim() },
        errors: [err.message],
      });
    }
    return next(err);
  }
});

router.post('/logout', requireAuth, csrfProtect, (req, res) => {
  userService.destroySession(req.user.sessionId);
  logAudit({ actor: `user:${req.user.id}`, action: 'auth.logout', target: `user:${req.user.id}` });
  res.clearCookie(config.session.cookieName, { path: '/' });
  res.redirect('/?notice=logged_out');
});

module.exports = router;
