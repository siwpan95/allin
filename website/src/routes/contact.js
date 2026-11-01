'use strict';

/** 联系我们：留言正文加密入库；附件同样加密入库，public/ 目录不留任何用户文件。 */

const express = require('express');
const multer = require('multer');
const crypto = require('node:crypto');
const config = require('../config');
const content = require('../services/contentService');
const contactService = require('../services/contactService');
const assetService = require('../services/assetService');
const { detectMime } = require('../services/assetService');

const router = express.Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: config.upload.maxBytes, files: 1 },
});

function renderContact(res, req, { form = {}, errors = [] }) {
  const profile = content.getDoc('site-profile');
  const faqs = content.listDocs('faq').filter((d) => d.data).slice(0, 4);
  res.render('contact', {
    title: '联系我们 · allin 项目开发与维护服务',
    pageKey: 'contact',
    profile: profile || {},
    faqs: faqs.map((d) => ({ ...d.data, _meta: d._meta })),
    form,
    errors,
  });
}

router.post('/contact', upload.single('attachment'), (req, res, next) => {
  const form = {
    name: String(req.body.name || '').trim(),
    email: String(req.body.email || '').trim(),
    topic: String(req.body.topic || '').trim(),
    body: String(req.body.body || '').trim(),
  };

  try {
    let attachmentKey = null;
    let attachmentName = null;
    if (req.file && req.file.size > 0) {
      attachmentName = req.file.originalname;
      const ext = (attachmentName.slice(attachmentName.lastIndexOf('.')) || '').toLowerCase();
      attachmentKey = `attachment-${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}-${crypto.randomBytes(3).toString('hex')}${ext}`;
      assetService.putAsset({
        assetKey: attachmentKey,
        buffer: req.file.buffer,
        mime: detectMime(req.file.buffer, attachmentName),
        isPublic: false,
        meta: { scope: 'admin', title: `联系表单附件（${form.topic || '未分类'}）`, via: 'contact' },
      });
    }

    contactService.createMessage({
      name: form.name,
      email: form.email,
      topic: form.topic,
      body: form.body,
      attachmentKey,
      attachmentName,
      ip: req.ip,
      userAgent: req.headers['user-agent'],
    });
    res.redirect('/contact?notice=contact_sent');
  } catch (err) {
    if (err && err.code === 'LIMIT_FILE_SIZE') {
      return res
        .status(400)
        .render('contact', {
          title: '联系我们 · allin 项目开发与维护服务',
          pageKey: 'contact',
          profile: content.getDoc('site-profile') || {},
          faqs: [],
          form,
          errors: [`附件超过 ${Math.floor(config.upload.maxBytes / 1024 / 1024)} MB 上限，请压缩后再传`],
        });
    }
    if (['请填写称呼', '邮箱格式不正确', '请填写需求描述'].includes(err.message)) {
      return res.status(400).render('contact', {
        title: '联系我们 · allin 项目开发与维护服务',
        pageKey: 'contact',
        profile: content.getDoc('site-profile') || {},
        faqs: [],
        form,
        errors: [err.message],
      });
    }
    return next(err);
  }
  return undefined;
});

module.exports = router;
