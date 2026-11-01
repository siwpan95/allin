'use strict';

/**
 * AES-256-GCM 封套加密（envelope encryption）。
 *
 * 结构（每份数据独立随机盐 + 独立随机 nonce）：
 *   KEK(主密钥) --HKDF-SHA256(salt, info)--> DEK(32B) --> AES-256-GCM(nonce, AAD) --> 密文 + Tag
 *
 * 三道完整性保障：
 *   1) GCM 认证标签 —— 密文或 AAD 任一字节被改，`final()` 直接抛错（AUTH_FAILED）；
 *   2) AAD 绑定业务主键 —— `asset:<key>` / `doc:<key>`，密文被整行搬到别的记录后同样解不开；
 *   3) 明文 SHA-256 落库 —— 解密后再比对一次，用于识别"密钥正确但明文被换"的极端情形。
 *
 * 不做的事：不自己拼 IV、不复用 nonce、不用 ECB/CBC。nonce 每次随机 96 bit，
 * 单密钥下密文量远低于 2^32 条的安全边界。
 */

const crypto = require('node:crypto');
const { DecryptError } = require('./errors');

const ALGORITHM = 'aes-256-gcm';
const ENVELOPE_VERSION = 1;
const SALT_BYTES = 16;
const NONCE_BYTES = 12;
const TAG_BYTES = 16;
const KEY_BYTES = 32;

function toBuffer(value, encoding = 'utf8') {
  if (Buffer.isBuffer(value)) return value;
  if (value instanceof Uint8Array) return Buffer.from(value);
  if (typeof value === 'string') return Buffer.from(value, encoding);
  throw new TypeError('无法转换为 Buffer');
}

function deriveDek(masterKey, salt, info) {
  const okm = crypto.hkdfSync('sha256', toBuffer(masterKey), toBuffer(salt), Buffer.from(info, 'utf8'), KEY_BYTES);
  return Buffer.from(okm);
}

/**
 * @param {{masterKey: Buffer|Uint8Array, keyId: string, plaintext: Buffer|string, aad: string}} args
 */
function encrypt({ masterKey, keyId, plaintext, aad }) {
  if (!masterKey) throw new Error('encrypt: 缺少主密钥');
  if (!keyId) throw new Error('encrypt: 缺少 keyId');
  const data = toBuffer(plaintext);
  const salt = crypto.randomBytes(SALT_BYTES);
  const nonce = crypto.randomBytes(NONCE_BYTES);
  const dek = deriveDek(masterKey, salt, `allin-site:v1:${keyId}`);
  const cipher = crypto.createCipheriv(ALGORITHM, dek, nonce, { authTagLength: TAG_BYTES });
  cipher.setAAD(Buffer.from(String(aad ?? ''), 'utf8'));
  const ciphertext = Buffer.concat([cipher.update(data), cipher.final()]);
  return {
    v: ENVELOPE_VERSION,
    alg: ALGORITHM,
    keyId: String(keyId),
    salt,
    nonce,
    tag: cipher.getAuthTag(),
    ciphertext,
    sha256Plain: crypto.createHash('sha256').update(data).digest('hex'),
    byteSize: data.length,
  };
}

/**
 * @param {{masterKey: Buffer|Uint8Array, salt, nonce, tag, ciphertext, aad: string, sha256Plain?: string}} envelope
 * @returns {Buffer} 明文
 * @throws {DecryptError} 分类错误，绝不返回"部分明文"
 */
function decrypt(envelope) {
  if (!envelope || !envelope.ciphertext || !envelope.nonce || !envelope.tag || !envelope.salt) {
    throw new DecryptError('ENVELOPE_BAD');
  }
  if (typeof envelope.masterKey === 'undefined' || envelope.masterKey === null) {
    throw new DecryptError('KEY_UNAVAILABLE', 'masterKey 为空');
  }
  if (envelope.v !== undefined && Number(envelope.v) !== ENVELOPE_VERSION) {
    throw new DecryptError('VERSION_UNSUPPORTED', `v=${envelope.v}`);
  }
  const dek = deriveDek(envelope.masterKey, envelope.salt, `allin-site:v1:${envelope.keyId}`);
  const decipher = crypto.createDecipheriv(ALGORITHM, dek, toBuffer(envelope.nonce), {
    authTagLength: TAG_BYTES,
  });
  decipher.setAAD(Buffer.from(String(envelope.aad ?? ''), 'utf8'));
  decipher.setAuthTag(toBuffer(envelope.tag));

  let plaintext;
  try {
    plaintext = Buffer.concat([decipher.update(toBuffer(envelope.ciphertext)), decipher.final()]);
  } catch (err) {
    // GCM 认证标签不匹配：密钥不对、密文被改、AAD 对不上，都落在这里
    throw new DecryptError('AUTH_FAILED', err.code || err.message);
  }

  if (envelope.sha256Plain) {
    const actual = crypto.createHash('sha256').update(plaintext).digest('hex');
    if (actual !== envelope.sha256Plain) {
      throw new DecryptError('INTEGRITY_MISMATCH');
    }
  }
  return plaintext;
}

/** 宽容版：返回 {ok, plaintext|error}，供"解密失败也要给用户友好反馈"的读取路径使用。 */
function tryDecrypt(envelope) {
  try {
    return { ok: true, plaintext: decrypt(envelope) };
  } catch (err) {
    return { ok: false, error: err };
  }
}

/** 邮箱可检索哈希：HMAC(派生密钥, 小写邮箱)，主密钥轮换时必须重算。 */
function lookupHmac(masterKey, value) {
  const key = deriveDek(masterKey, Buffer.from('allin-site:email-lookup-salt'), 'allin-site:email-lookup');
  return crypto.createHmac('sha256', key).update(String(value).trim().toLowerCase()).digest('hex');
}

module.exports = {
  ALGORITHM,
  ENVELOPE_VERSION,
  SALT_BYTES,
  NONCE_BYTES,
  TAG_BYTES,
  KEY_BYTES,
  deriveDek,
  encrypt,
  decrypt,
  tryDecrypt,
  lookupHmac,
};
