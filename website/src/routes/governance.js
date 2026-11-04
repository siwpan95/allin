'use strict';

/**
 * 治理看板路由组：
 *   GET  /member/dashboard                       登录用户 · 只读看板（audit: governance.view）
 *   GET  /member/api/governance/overview         登录用户 · 总览代理（平台离线 → 200 + 降级标记）
 *   GET  /member/api/governance/orchestration    登录用户 · 编排代理（同上）
 *   GET  /member/api/governance/entries          登录用户 · 登记项目明细代理（管理台列表用）
 *   POST /member/api/governance/entries/:id/:action  仅 admin + CSRF · 启停转发（audit: governance.entry.*）
 *   GET  /admin/governance                       仅 admin · 治理管理页（audit: governance.view）
 *
 * 写操作成败均落 audit_log（governance.entry.start/stop）；页面加载记 governance.view 一次。
 * 页面路由不调 portal（不阻塞 TTFB），卡片数据由浏览器首帧 fetch 填充。
 */

const express = require('express');
const portalProxy = require('../services/portalProxy');
const { requireAuth, requireRole, csrfProtect } = require('../middleware/auth');
const { logAudit, recentAudit } = require('../services/audit');

const router = express.Router();

// ---- 只读页面 ----

router.get('/member/dashboard', requireAuth, (req, res) => {
  logAudit({ actor: req.user.email, action: 'governance.view', target: 'dashboard', ok: true });
  res.render('dashboard', {
    title: '治理看板 · allin 官网',
    pageKey: 'governance-dashboard',
    pageScript: 'governance',
    isAdmin: req.user.role === 'admin',
  });
});

router.get('/admin/governance', requireRole('admin'), (req, res) => {
  logAudit({ actor: req.user.email, action: 'governance.view', target: 'admin', ok: true });

  // 审计过滤视图（SSR，GET 查询参数驱动；数据源复用既有 recentAudit，不碰 audit.js）
  const qAction = String(req.query.action || '').trim().slice(0, 100);
  const qOk = ['ok', 'fail'].includes(req.query.ok) ? req.query.ok : '';
  const qLimit = [20, 50, 100].includes(Number.parseInt(req.query.limit, 10))
    ? Number.parseInt(req.query.limit, 10)
    : 20;

  let rows = recentAudit(200);
  if (qAction) rows = rows.filter((r) => (r.action || '').includes(qAction));
  if (qOk) rows = rows.filter((r) => (qOk === 'ok' ? Number(r.ok) === 1 : Number(r.ok) !== 1));
  rows = rows.slice(0, qLimit);

  res.render('admin-governance', {
    title: '治理管理 · allin 官网',
    pageKey: 'governance-admin',
    pageScript: 'governance',
    isAdmin: true,
    audit: rows,
    filters: { action: qAction, ok: qOk, limit: qLimit },
  });
});

// ---- 只读 JSON 代理（requireAuth；上游失败 → 200 + degraded 分类，页面始终可用） ----

function sendGovPayload(res, payload) {
  res.set('cache-control', 'no-store');
  return res.status(200).json(payload);
}

router.get('/member/api/governance/overview', requireAuth, async (req, res, next) => {
  try {
    sendGovPayload(res, await portalProxy.getOverview());
  } catch (err) {
    next(err);
  }
});

router.get('/member/api/governance/orchestration', requireAuth, async (req, res, next) => {
  try {
    sendGovPayload(res, await portalProxy.getOrchestration());
  } catch (err) {
    next(err);
  }
});

router.get('/member/api/governance/entries', requireAuth, async (req, res, next) => {
  try {
    sendGovPayload(res, await portalProxy.getEntries());
  } catch (err) {
    next(err);
  }
});

// ---- 写代理（三道闸：会话 + admin 角色 + CSRF；转发 portal 既有 POST 端点） ----

router.post(
  '/member/api/governance/entries/:id/:action',
  requireRole('admin'),
  csrfProtect,
  async (req, res, next) => {
    try {
      const { id, action } = req.params;
      const result = await portalProxy.proxyEntryAction(id, action);
      // 成败均记审计（写路径可追责，P1b R4 缓解）
      logAudit({
        actor: req.user.email,
        action: `governance.entry.${action}`,
        target: `entry:${id}`,
        ok: result.ok,
        detail: result.ok
          ? (result.result && result.result.pid ? `pid=${result.result.pid}` : 'ok')
          : `${result.code}: ${result.message}`,
      });
      res.set('cache-control', 'no-store');
      if (!result.ok) {
        const status = result.code === 'BAD_REQUEST' ? 400 : result.code === 'NOT_FOUND' ? 404 : 502;
        return res.status(status).json({ ok: false, id, code: result.code, message: result.message });
      }
      return res.status(200).json({ ok: true, id, pid: result.result.pid ?? null, result: result.result });
    } catch (err) {
      return next(err);
    }
  }
);

module.exports = router;
