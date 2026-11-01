'use strict';

/**
 * 资源服务：图片 / 附件统一走"加密 → 入库 → 按需解密输出"。
 *
 * 关键口径：**public/ 目录里没有任何业务图片或用户文件**。
 * 配图源文件放在仓库的 assets-src/（非公开目录），由 scripts/seed.js 加密写入数据库；
 * 页面只能经 /media/:key 拿到字节，数据库里躺着的永远是密文 ——
 * 连描述信息（标题、alt、作用域）也是密文，避免"文件名即内容"的侧信道。
 */

const { getDb } = require('../db');
const gcm = require('../crypto/gcm');
const envelope = require('../crypto/envelope');
const keystore = require('../crypto/keystore');
const { DecryptError } = require('../crypto/errors');
const { logAudit } = require('./audit');

const MAGIC = [
  { mime: 'image/jpeg', test: (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff },
  { mime: 'image/png', test: (b) => b.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) },
  { mime: 'image/gif', test: (b) => b.subarray(0, 6).toString('ascii').startsWith('GIF8') },
  { mime: 'image/webp', test: (b) => b.subarray(0, 4).toString('ascii') === 'RIFF' && b.subarray(8, 12).toString('ascii') === 'WEBP' },
  { mime: 'application/pdf', test: (b) => b.subarray(0, 4).toString('ascii') === '%PDF' },
  { mime: 'image/svg+xml', test: (b) => b.subarray(0, 200).toString('ascii').includes('<svg') },
];

const EXT_MIME = {
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.zip': 'application/zip',
};

const ASSET_COLUMNS =
  'asset_key, mime, byte_size, sha256_plain, alg, key_id, salt, nonce, tag, ciphertext, aad, is_public, meta_cipher, created_at, updated_at';

function detectMime(buffer, filename = '') {
  for (const m of MAGIC) {
    if (m.test(buffer)) return m.mime;
  }
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  return EXT_MIME[ext] || 'application/octet-stream';
}

function putAsset({ assetKey, buffer, mime, isPublic = false, meta = null }) {
  const db = getDb();
  const { keyId, material } = keystore.getActiveKey(db);
  const aad = `asset:${assetKey}`;
  const envelopeData = gcm.encrypt({ masterKey: material, keyId, plaintext: buffer, aad });
  const metaCipher = meta
    ? Buffer.from(
        envelope.serialize(
          gcm.encrypt({
            masterKey: material,
            keyId,
            plaintext: Buffer.from(JSON.stringify(meta), 'utf8'),
            aad: `asset-meta:${assetKey}`,
          })
        ),
        'utf8'
      )
    : null;

  db.prepare(
    `INSERT INTO assets (${ASSET_COLUMNS})
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
     ON CONFLICT(asset_key) DO UPDATE SET
       mime = excluded.mime,
       byte_size = excluded.byte_size,
       sha256_plain = excluded.sha256_plain,
       alg = excluded.alg,
       key_id = excluded.key_id,
       salt = excluded.salt,
       nonce = excluded.nonce,
       tag = excluded.tag,
       ciphertext = excluded.ciphertext,
       aad = excluded.aad,
       is_public = excluded.is_public,
       meta_cipher = excluded.meta_cipher,
       updated_at = datetime('now')`
  ).run(
    assetKey,
    mime || detectMime(buffer),
    envelopeData.byteSize,
    envelopeData.sha256Plain,
    envelopeData.alg,
    envelopeData.keyId,
    envelopeData.salt,
    envelopeData.nonce,
    envelopeData.tag,
    envelopeData.ciphertext,
    aad,
    isPublic ? 1 : 0,
    metaCipher
  );
  return { assetKey, byteSize: envelopeData.byteSize, keyId: envelopeData.keyId };
}

function getAssetRow(assetKey) {
  return getDb().prepare(`SELECT ${ASSET_COLUMNS} FROM assets WHERE asset_key = ?`).get(assetKey);
}

/** 描述信息解密失败只降级为空对象，不影响资源本身投递。 */
function readMeta(row) {
  if (!row || !row.meta_cipher) return {};
  try {
    const parsed = envelope.parse(row.meta_cipher);
    const material = keystore.getKeyMaterial(getDb(), parsed.keyId);
    const plain = gcm.decrypt({ ...parsed, masterKey: material, aad: `asset-meta:${row.asset_key}` });
    return JSON.parse(plain.toString('utf8'));
  } catch (err) {
    console.error(`[asset] meta 解密失败 ${row.asset_key}: ${err.code || err.message}`);
    return {};
  }
}

/**
 * 解密取字节。失败一律抛 DecryptError（带分类码），
 * 由路由层决定是回占位图还是 404 —— 绝不对用户吐栈，也绝不返回"可疑明文"。
 */
function readAssetBytes(assetKey) {
  const row = getAssetRow(assetKey);
  if (!row) return null;
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
      action: 'asset.decrypt_failed',
      target: assetKey,
      ok: false,
      detail: `${result.error.code} ${result.error.detail || ''}`.trim(),
    });
    throw result.error instanceof DecryptError ? result.error : new DecryptError('ENVELOPE_BAD');
  }
  return { bytes: result.plaintext, mime: row.mime, row };
}

function listAssets({ onlyPublic = false } = {}) {
  const db = getDb();
  const sql = onlyPublic
    ? `SELECT ${ASSET_COLUMNS} FROM assets WHERE is_public = 1 ORDER BY asset_key`
    : `SELECT ${ASSET_COLUMNS} FROM assets ORDER BY asset_key`;
  return db.prepare(sql).all();
}

function countAssets() {
  return getDb().prepare('SELECT COUNT(*) AS n, COALESCE(SUM(byte_size), 0) AS bytes FROM assets').get();
}

function deleteAsset(assetKey) {
  return getDb().prepare('DELETE FROM assets WHERE asset_key = ?').run(assetKey).changes;
}

module.exports = { detectMime, putAsset, getAssetRow, readMeta, readAssetBytes, listAssets, countAssets, deleteAsset };
