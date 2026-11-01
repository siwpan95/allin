'use strict';

/** 登录用户专区：受保护内容 + 会员级文件下载（权限校验在中间件与投递层各做一次）。 */

const express = require('express');
const content = require('../services/contentService');
const assetService = require('../services/assetService');
const delivery = require('../services/assetDelivery');
const keystore = require('../crypto/keystore');
const { getDb } = require('../db');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

function ok(docs) {
  return docs.filter((d) => d.data).map((d) => ({ ...d.data, _meta: d._meta }));
}

function memberFiles() {
  return assetService
    .listAssets()
    .map((row) => ({ row, meta: assetService.readMeta(row), scope: delivery.scopeOf(row) }))
    .filter((item) => ['member', 'public'].includes(item.scope))
    .map((item) => ({
      assetKey: item.row.asset_key,
      title: item.meta.title || item.row.asset_key,
      note: item.meta.note || '',
      mime: item.row.mime,
      byteSize: item.row.byte_size,
      updatedAt: item.row.updated_at,
    }));
}

router.get('/member', requireAuth, (req, res) => {
  const db = getDb();
  res.render('member', {
    title: '客户控制台 · allin 官网',
    pageKey: 'member',
    tickets: ok(content.listDocs('ticket')),
    files: memberFiles(),
    activeKeyId: keystore.getActiveKeyId(db),
    storage: assetService.countAssets(),
  });
});

router.get('/member/files/:key', requireAuth, (req, res) => {
  delivery.sendAsset({
    req,
    res,
    assetKey: req.params.key,
    allow: ['member', 'public'],
    denyNotice: 'login_needed_file',
  });
});

module.exports = router;
