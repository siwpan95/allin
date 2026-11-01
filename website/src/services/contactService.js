'use strict';

/** 联系留言：正文与联系方式加密入库，只有管理员可解密查看。 */

const crypto = require('node:crypto');
const content = require('./contentService');
const { logAudit } = require('./audit');

const MAX_BODY = 4000;

function createMessage({ name, email, topic, body, attachmentKey = null, attachmentName = null, ip = null, userAgent = null }) {
  const cleanName = String(name || '').trim().slice(0, 60);
  const cleanEmail = String(email || '').trim().slice(0, 120);
  const cleanTopic = String(topic || '').trim().slice(0, 60);
  const cleanBody = String(body || '').trim().slice(0, MAX_BODY);

  if (!cleanName) throw new Error('请填写称呼');
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) throw new Error('邮箱格式不正确');
  if (!cleanBody) throw new Error('请填写需求描述');

  const docKey = `contact-${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}-${crypto.randomBytes(3).toString('hex')}`;
  content.putDoc({
    docKey,
    kind: 'contact',
    status: 'new',
    data: {
      name: cleanName,
      email: cleanEmail,
      topic: cleanTopic || '未分类',
      body: cleanBody,
      attachmentKey,
      attachmentName,
      ip,
      userAgent: userAgent ? String(userAgent).slice(0, 200) : null,
      submittedAt: new Date().toISOString(),
    },
  });
  logAudit({ actor: null, action: 'contact.submit', target: docKey });
  return { docKey };
}

function listMessages({ status = null, limit = 200, order = 'desc' } = {}) {
  return content.listDocs('contact', { status, limit, order });
}

function setMessageStatus(id, status) {
  return content.setDocStatus(id, status);
}

module.exports = { createMessage, listMessages, setMessageStatus, MAX_BODY };
