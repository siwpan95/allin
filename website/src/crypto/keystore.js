'use strict';

/**
 * 密钥管理（KEK）。
 *
 * 三条口径：
 *   1) **密钥不进仓库**：key 文件落在 data/keys/（.gitignore 已覆盖 `data/` 与 `*.key`），
 *      环境变量注入优先于文件（生产推荐 `SITE_MASTER_KEY_BASE64`）；
 *   2) **一把 KEK 打天下，每条数据一把 DEK**：KEK 只用于 HKDF 派生，永不直接碰明文，
 *      单条数据的 DEK 随随机盐变化，把"一把钥匙泄露 = 全库裸奔"的爆炸半径压到最小；
 *   3) **轮换有状态**：crypto_keys 表记录 key_id / is_active，轮换 = 生成新 key → 置为 active
 *      → 用旧 key 解密、新 key 重加密全部行（见 scripts/rotate-key.js）。
 */

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const config = require('../config');
const { KeyUnavailableError } = require('./errors');
const { KEY_BYTES } = require('./gcm');

const KEY_FILE_SUFFIX = '.key';

function ensureKeyDir() {
  fs.mkdirSync(config.keyDir, { recursive: true });
  return config.keyDir;
}

function keyFilePath(keyId) {
  return path.join(ensureKeyDir(), `${keyId}${KEY_FILE_SUFFIX}`);
}

function generateKeyMaterial() {
  return crypto.randomBytes(KEY_BYTES);
}

function writeKeyFile(keyId, material) {
  const file = keyFilePath(keyId);
  fs.writeFileSync(file, material, { mode: 0o600 });
  try {
    fs.chmodSync(file, 0o600);
  } catch {
    /* Windows 上 chmod 语义有限，属尽力而为 */
  }
  return file;
}

function readKeyFile(keyId) {
  try {
    return fs.readFileSync(keyFilePath(keyId));
  } catch {
    return null;
  }
}

function envKeyMaterial() {
  const raw = config.masterKeyBase64;
  if (!raw) return null;
  const buf = Buffer.from(raw, 'base64');
  if (buf.length !== KEY_BYTES) {
    throw new Error(
      `SITE_MASTER_KEY_BASE64 解出 ${buf.length} 字节，应为 ${KEY_BYTES} 字节（base64 编码的 32 字节随机串）`
    );
  }
  return buf;
}

function registerKey(db, keyId, source) {
  db.prepare(
    `INSERT INTO crypto_keys (key_id, source, is_active) VALUES (?, ?, 0)
     ON CONFLICT(key_id) DO NOTHING`
  ).run(keyId, source);
}

function createKey(db, { source = 'file', activate = false } = {}) {
  ensureKeyDir();
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
  const keyId = `k-${stamp}-${crypto.randomBytes(3).toString('hex')}`;

  if (source === 'env') {
    const material = envKeyMaterial();
    if (!material) throw new Error('createKey(source=env): 未配置 SITE_MASTER_KEY_BASE64');
    registerKey(db, keyId, 'env');
    // 环境变量注入的密钥不落盘，只登记 id；运行时从环境直接取材质
    if (activate) setActiveKey(db, keyId);
    return { keyId, source: 'env', material };
  }

  const material = generateKeyMaterial();
  writeKeyFile(keyId, material);
  registerKey(db, keyId, 'file');
  if (activate) setActiveKey(db, keyId);
  return { keyId, source: 'file', material };
}

function setActiveKey(db, keyId) {
  db.prepare('UPDATE crypto_keys SET is_active = 0 WHERE is_active = 1').run();
  const res = db.prepare('UPDATE crypto_keys SET is_active = 1 WHERE key_id = ?').run(keyId);
  if (res.changes === 0) throw new KeyUnavailableError(keyId);
}

function listKeys(db) {
  return db.prepare('SELECT key_id, source, is_active, created_at FROM crypto_keys ORDER BY created_at').all();
}

function getActiveKeyId(db) {
  const row = db.prepare('SELECT key_id FROM crypto_keys WHERE is_active = 1 LIMIT 1').get();
  return row ? row.key_id : null;
}

/** 取主密钥材质：env 注入优先，其次 key 文件。缺失即抛错（fail loud，不静默降级）。 */
function getKeyMaterial(db, keyId) {
  const row = db.prepare('SELECT key_id, source FROM crypto_keys WHERE key_id = ?').get(keyId);
  if (!row) throw new KeyUnavailableError(keyId);
  if (row.source === 'env') {
    const material = envKeyMaterial();
    if (!material) throw new KeyUnavailableError(`${keyId} (环境变量未注入)`);
    return material;
  }
  const material = readKeyFile(keyId);
  if (!material || material.length !== KEY_BYTES) throw new KeyUnavailableError(keyId);
  return material;
}

/**
 * 初始化密钥环：保证"恰好一把 active 密钥"。
 * 幂等 —— 反复调用不会产生第二把密钥，也不会让已加密数据失效。
 */
function ensureKeyring(db) {
  ensureKeyDir();
  const keys = listKeys(db);
  const active = keys.find((k) => Number(k.is_active) === 1);
  if (active) {
    // 校验材质真的取得到，避免"表里有、盘上没了"的假可用
    getKeyMaterial(db, active.key_id);
    return { keyId: active.key_id, created: false, source: active.source };
  }
  const source = config.masterKeyBase64 ? 'env' : 'file';
  const created = createKey(db, { source, activate: true });
  return { keyId: created.keyId, created: true, source };
}

function getActiveKey(db) {
  const keyId = getActiveKeyId(db);
  if (!keyId) throw new KeyUnavailableError('(未初始化密钥环)');
  return { keyId, material: getKeyMaterial(db, keyId) };
}

module.exports = {
  ensureKeyDir,
  keyFilePath,
  generateKeyMaterial,
  writeKeyFile,
  readKeyFile,
  envKeyMaterial,
  createKey,
  setActiveKey,
  listKeys,
  getActiveKeyId,
  getKeyMaterial,
  ensureKeyring,
  getActiveKey,
};
