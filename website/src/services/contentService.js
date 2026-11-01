'use strict';

/**
 * 加密文档仓库：站点文案、服务包、时间线、FAQ、工单等结构化内容。
 *
 * 一个 doc = 一行 secure_docs，明文是 JSON，落库是 GCM 密文，AAD 绑定 `doc:<doc_key>`。
 * 页面渲染时解密，管理端可写回；数据库被拷走也拿不到任何文案原文明文。
 */

const { getDb } = require('../db');
const gcm = require('../crypto/gcm');
const keystore = require('../crypto/keystore');
const { DecryptError } = require('../crypto/errors');
const { logAudit } = require('./audit');

function putDoc({ docKey, kind, data, status = 'new' }) {
  const db = getDb();
  const { keyId, material } = keystore.getActiveKey(db);
  const aad = `doc:${docKey}`;
  const plaintext = Buffer.from(JSON.stringify(data), 'utf8');
  const envelope = gcm.encrypt({ masterKey: material, keyId, plaintext, aad });

  db.prepare(
    `INSERT INTO secure_docs
       (doc_key, kind, status, alg, key_id, salt, nonce, tag, ciphertext, aad, sha256_plain, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
     ON CONFLICT(doc_key) DO UPDATE SET
       kind = excluded.kind,
       status = excluded.status,
       alg = excluded.alg,
       key_id = excluded.key_id,
       salt = excluded.salt,
       nonce = excluded.nonce,
       tag = excluded.tag,
       ciphertext = excluded.ciphertext,
       aad = excluded.aad,
       sha256_plain = excluded.sha256_plain,
       updated_at = datetime('now')`
  ).run(
    docKey,
    kind,
    status,
    envelope.alg,
    envelope.keyId,
    envelope.salt,
    envelope.nonce,
    envelope.tag,
    envelope.ciphertext,
    aad,
    envelope.sha256Plain
  );
  return docKey;
}

function getDocRow(docKey) {
  return getDb().prepare('SELECT * FROM secure_docs WHERE doc_key = ?').get(docKey);
}

function getDocRowById(id) {
  return getDb().prepare('SELECT * FROM secure_docs WHERE id = ?').get(Number(id));
}

function decryptRow(row) {
  const material = keystore.getKeyMaterial(getDb(), row.key_id);
  const result = gcm.tryDecrypt({
    masterKey: material,
    keyId: row.key_id,
    salt: row.salt,
    nonce: row.nonce,
    tag: row.tag,
    ciphertext: row.ciphertext,
    aad: row.aad,
    sha256Plain: row.sha256_plain,
  });
  if (!result.ok) {
    logAudit({
      actor: null,
      action: 'doc.decrypt_failed',
      target: row.doc_key,
      ok: false,
      detail: `${result.error.code} ${result.error.detail || ''}`.trim(),
    });
    throw result.error instanceof DecryptError ? result.error : new DecryptError('ENVELOPE_BAD');
  }
  return JSON.parse(result.plaintext.toString('utf8'));
}

function getDoc(docKey) {
  const row = getDocRow(docKey);
  if (!row) return null;
  return { ...decryptRow(row), _meta: { docKey: row.doc_key, status: row.status, updatedAt: row.updated_at } };
}

function listDocs(kind, { status = null, limit = 100, order = 'asc' } = {}) {
  const db = getDb();
  const dir = String(order).toLowerCase() === 'desc' ? 'DESC' : 'ASC';
  const rows = status
    ? db
        .prepare(`SELECT * FROM secure_docs WHERE kind = ? AND status = ? ORDER BY id ${dir} LIMIT ?`)
        .all(kind, status, limit)
    : db.prepare(`SELECT * FROM secure_docs WHERE kind = ? ORDER BY id ${dir} LIMIT ?`).all(kind, limit);

  return rows.map((row) => {
    let data = null;
    let error = null;
    try {
      data = decryptRow(row);
    } catch (err) {
      // 单条损坏不影响整页：标记为不可用，交给上层渲染"该条内容不可用"的友好提示
      error = { code: err.code || 'DECRYPT_FAILED', message: err.message };
    }
    return { data, error, _meta: { id: row.id, docKey: row.doc_key, status: row.status, updatedAt: row.updated_at, createdAt: row.created_at } };
  });
}

function setDocStatus(id, status) {
  return getDb()
    .prepare("UPDATE secure_docs SET status = ?, updated_at = datetime('now') WHERE id = ?")
    .run(status, id).changes;
}

function countDocs() {
  return getDb().prepare('SELECT kind, COUNT(*) AS n FROM secure_docs GROUP BY kind ORDER BY kind').all();
}

module.exports = { putDoc, getDoc, getDocRow, getDocRowById, listDocs, setDocStatus, countDocs, decryptRow };
