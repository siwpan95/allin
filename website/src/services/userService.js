'use strict';

/**
 * 用户与会话。
 *
 * 口径：
 *   - 口令用 scrypt（Node 内置，无需第三方依赖），盐随机 16B，参数随行存储便于未来调参；
 *   - 邮箱不落明文：存 HMAC(主密钥, 小写邮箱) 供登录检索 + GCM 密文供展示；
 *   - 会话只把 256bit 随机 id 放进 httpOnly Cookie，其余（用户、CSRF、IP、UA、过期）全在库里；
 *   - 登录失败、用户不存在也走一次等价耗时的 scrypt，避免"用户是否存在"的时序侧信道。
 */

const crypto = require('node:crypto');
const { getDb } = require('../db');
const gcm = require('../crypto/gcm');
const envelope = require('../crypto/envelope');
const keystore = require('../crypto/keystore');
const { logAudit } = require('./audit');

const SCRYPT = { N: 32768, r: 8, p: 1, keylen: 64, maxmem: 96 * 1024 * 1024 };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD = 8;

function hashPassword(password, salt = crypto.randomBytes(16), params = SCRYPT) {
  const hash = crypto.scryptSync(password, salt, params.keylen, {
    N: params.N,
    r: params.r,
    p: params.p,
    maxmem: params.maxmem,
  });
  return { hash, salt };
}

/**
 * 解析随行存储的口令参数串（"scrypt$N=…,r=…,p=…,keylen=…"）。
 * verifyPassword 用它按**该用户注册时的参数**重算，从而 scrypt 成本（N）升级后
 * 历史账号仍能用旧参数验证（向后兼容），新账号自动用全局更高的 N。
 */
function parseParams(str) {
  const m = /N=(\d+),r=(\d+),p=(\d+),keylen=(\d+)/.exec(String(str || ''));
  if (!m) return SCRYPT;
  return { N: Number(m[1]), r: Number(m[2]), p: Number(m[3]), keylen: Number(m[4]), maxmem: SCRYPT.maxmem };
}

function paramsString() {
  return `scrypt$N=${SCRYPT.N},r=${SCRYPT.r},p=${SCRYPT.p},keylen=${SCRYPT.keylen}`;
}

function validateEmail(email) {
  return EMAIL_RE.test(String(email || '').trim());
}

function validatePassword(password) {
  const value = String(password || '');
  if (value.length < MIN_PASSWORD) return `口令至少 ${MIN_PASSWORD} 位`;
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) return '口令需同时包含字母与数字';
  return null;
}

function listUsers() {
  return getDb()
    .prepare('SELECT id, display_name, role, status, created_at, last_login_at FROM users ORDER BY id')
    .all();
}

function createUser({ email, password, displayName, role = 'member' }) {
  const db = getDb();
  const cleanEmail = String(email || '').trim().toLowerCase();
  if (!validateEmail(cleanEmail)) throw new Error('邮箱格式不正确');
  const pwdError = validatePassword(password);
  if (pwdError) throw new Error(pwdError);

  const { keyId, material } = keystore.getActiveKey(db);
  const emailHmac = gcm.lookupHmac(material, cleanEmail);
  if (db.prepare('SELECT id FROM users WHERE email_hmac = ?').get(emailHmac)) {
    throw new Error('该邮箱已注册');
  }

  const { hash, salt } = hashPassword(password);
  const sealed = envelope.sealSingle({
    masterKey: material,
    keyId,
    plaintext: cleanEmail,
    aad: `user-email:${emailHmac}`,
  });

  const res = db
    .prepare(
      `INSERT INTO users (email_hmac, email_cipher, display_name, role, status, password_hash, password_salt, password_params)
       VALUES (?, ?, ?, ?, 'active', ?, ?, ?)`
    )
    .run(emailHmac, Buffer.from(envelope.serialize(sealed), 'utf8'), String(displayName || cleanEmail.split('@')[0]), role, hash, salt, paramsString());

  // 审计只记用户 ID，不记邮箱：日志本身也是需要保护的个人信息面
  logAudit({ actor: `user:${res.lastInsertRowid}`, action: 'user.register', target: `user:${res.lastInsertRowid}` });
  return { id: Number(res.lastInsertRowid), email: cleanEmail, role };
}

function findUserByEmail(email) {
  const db = getDb();
  const { material } = keystore.getActiveKey(db);
  const emailHmac = gcm.lookupHmac(material, email);
  return db.prepare('SELECT * FROM users WHERE email_hmac = ?').get(emailHmac);
}

/** 解密展示用邮箱（失败返回脱敏串，不抛错——登录流程不该被展示层拖垮）。 */
function readableEmail(user) {
  try {
    const material = keystore.getKeyMaterial(getDb(), envelope.parse(user.email_cipher).keyId);
    return envelope.openSingle(material, user.email_cipher, `user-email:${user.email_hmac}`).toString('utf8');
  } catch (err) {
    console.error(`[user] 邮箱解密失败 user:${user.id}: ${err.code || err.message}`);
    return '(邮箱解密失败)';
  }
}

function verifyPassword(user, password) {
  const { hash } = hashPassword(password, user.password_salt, parseParams(user.password_params));
  const expected = Buffer.from(user.password_hash);
  if (expected.length !== hash.length) return false;
  return crypto.timingSafeEqual(expected, hash);
}

/** 用户不存在时也跑一次 scrypt，抹平时序差异。 */
function dummyHash(password) {
  hashPassword(password, crypto.randomBytes(16));
  return false;
}

function createSession(userId, { ip = null, userAgent = null } = {}) {
  const db = getDb();
  const id = crypto.randomBytes(32).toString('base64url');
  const csrfToken = crypto.randomBytes(24).toString('base64url');
  const expiresAt = new Date(Date.now() + require('../config').session.ttlHours * 3600 * 1000).toISOString();
  db.prepare(
    'INSERT INTO sessions (id, user_id, csrf_token, expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)'
  ).run(id, userId, csrfToken, expiresAt, ip, userAgent ? String(userAgent).slice(0, 200) : null);
  return { id, csrfToken, expiresAt };
}

function destroySession(sessionId) {
  if (!sessionId) return 0;
  return getDb().prepare('DELETE FROM sessions WHERE id = ?').run(sessionId).changes;
}

function purgeExpiredSessions() {
  return getDb().prepare("DELETE FROM sessions WHERE expires_at <= datetime('now')").run().changes;
}

function getSessionUser(sessionId) {
  if (!sessionId) return null;
  const db = getDb();
  const row = db
    .prepare(
      `SELECT s.id AS sid, s.csrf_token, s.expires_at, s.ip, s.user_agent, s.created_at AS session_created_at,
              u.id, u.display_name, u.role, u.status, u.email_hmac, u.email_cipher, u.last_login_at
       FROM sessions s JOIN users u ON u.id = s.user_id
       WHERE s.id = ?`
    )
    .get(sessionId);
  if (!row) return null;
  if (new Date(row.expires_at).getTime() <= Date.now()) {
    destroySession(sessionId);
    return null;
  }
  return {
    sessionId: row.sid,
    csrfToken: row.csrf_token,
    expiresAt: row.expires_at,
    ip: row.ip,
    userAgent: row.user_agent,
    sessionCreatedAt: row.session_created_at,
    id: row.id,
    displayName: row.display_name,
    role: row.role,
    status: row.status,
    email: readableEmail(row),
    lastLoginAt: row.last_login_at,
  };
}

function touchLogin(userId) {
  getDb().prepare("UPDATE users SET last_login_at = datetime('now') WHERE id = ?").run(userId);
}

function setUserStatus(userId, status) {
  return getDb().prepare('UPDATE users SET status = ? WHERE id = ?').run(status, userId).changes;
}

module.exports = {
  SCRYPT,
  MIN_PASSWORD,
  validateEmail,
  validatePassword,
  hashPassword,
  listUsers,
  createUser,
  findUserByEmail,
  readableEmail,
  verifyPassword,
  dummyHash,
  createSession,
  destroySession,
  purgeExpiredSessions,
  getSessionUser,
  touchLogin,
  setUserStatus,
};
