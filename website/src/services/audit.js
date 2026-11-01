'use strict';

/** 审计流水：登录、越权尝试、解密失败都要留痕，否则"被篡改过"无从追责。 */
const { getDb } = require('../db');

function logAudit({ actor = null, action, target = null, ok = true, detail = null }) {
  try {
    getDb()
      .prepare('INSERT INTO audit_log (actor, action, target, ok, detail) VALUES (?, ?, ?, ?, ?)')
      .run(actor, action, target, ok ? 1 : 0, detail ? String(detail).slice(0, 500) : null);
  } catch {
    // 审计写失败不能反过来拖垮业务请求，但也不静默：打到 stderr 由运维接住
    console.error('[audit] 写入失败', { actor, action, target });
  }
}

function recentAudit(limit = 20) {
  return getDb()
    .prepare('SELECT at, actor, action, target, ok, detail FROM audit_log ORDER BY id DESC LIMIT ?')
    .all(limit);
}

module.exports = { logAudit, recentAudit };
