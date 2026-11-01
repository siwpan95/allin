'use strict';

/** 管理台：留言（解密查看）、用户、密钥环、审计流水。全部接口要求 admin 角色。 */

const express = require('express');
const content = require('../services/contentService');
const contactService = require('../services/contactService');
const userService = require('../services/userService');
const assetService = require('../services/assetService');
const delivery = require('../services/assetDelivery');
const keystore = require('../crypto/keystore');
const { recentAudit } = require('../services/audit');
const { getDb } = require('../db');
const { requireRole, csrfProtect } = require('../middleware/auth');
const { logAudit } = require('../services/audit');

const router = express.Router();

router.get('/admin', requireRole('admin'), (req, res) => {
  const db = getDb();
  res.render('admin', {
    title: '管理台 · allin 官网',
    pageKey: 'admin',
    messages: contactService.listMessages({ limit: 100, order: 'desc' }),
    users: userService.listUsers(),
    keys: keystore.listKeys(db),
    docStats: content.countDocs(),
    storage: assetService.countAssets(),
    audit: recentAudit(20),
  });
});

router.post('/admin/messages/:id/status', requireRole('admin'), csrfProtect, (req, res) => {
  const id = Number.parseInt(req.params.id, 10);
  const status = ['new', 'reading', 'closed'].includes(req.body.status) ? req.body.status : 'new';
  contactService.setMessageStatus(id, status);
  logAudit({ actor: req.user.email, action: 'admin.message_status', target: `doc:${id}`, detail: status });
  res.redirect('/admin#messages');
});

router.get('/admin/messages/:id/attachment', requireRole('admin'), (req, res) => {
  const id = Number.parseInt(req.params.id, 10);
  const row = content.getDocRowById(id);
  if (!row) return res.status(404).render('error', { title: '留言不存在', status: 404, message: '找不到该条留言。', hint: '', pageKey: '' });
  let data;
  try {
    data = content.decryptRow(row);
  } catch {
    return res.status(410).render('error', { title: '留言解密失败', status: 410, message: '该留言内容无法解密，已记录安全日志。', hint: '', pageKey: '' });
  }
  if (!data.attachmentKey) {
    return res.status(404).render('error', { title: '无附件', status: 404, message: '这条留言没有附件。', hint: '', pageKey: '' });
  }
  delivery.sendAsset({ req, res, assetKey: data.attachmentKey, allow: ['admin'], denyNotice: 'admin_required' });
  return undefined;
});

module.exports = router;
