'use strict';

/**
 * 密文封套的序列化：把 {salt, nonce, tag, ciphertext} 四个 Buffer 打成一段 JSON。
 * 用于"单列表格只存一列密文"的场景（如 users.email_cipher）。
 */

const gcm = require('./gcm');

function serialize(envelope) {
  return JSON.stringify({
    v: envelope.v,
    alg: envelope.alg,
    keyId: envelope.keyId,
    salt: Buffer.from(envelope.salt).toString('base64'),
    nonce: Buffer.from(envelope.nonce).toString('base64'),
    tag: Buffer.from(envelope.tag).toString('base64'),
    ciphertext: Buffer.from(envelope.ciphertext).toString('base64'),
    sha256Plain: envelope.sha256Plain,
  });
}

function parse(raw) {
  // SQLite 的 BLOB 可能以 Buffer 或 Uint8Array 形式返回，两者都要认
  const obj =
    raw instanceof Uint8Array
      ? JSON.parse(Buffer.from(raw).toString('utf8'))
      : typeof raw === 'string'
        ? JSON.parse(raw)
        : raw;
  return {
    v: obj.v,
    alg: obj.alg,
    keyId: obj.keyId,
    salt: Buffer.from(obj.salt, 'base64'),
    nonce: Buffer.from(obj.nonce, 'base64'),
    tag: Buffer.from(obj.tag, 'base64'),
    ciphertext: Buffer.from(obj.ciphertext, 'base64'),
    sha256Plain: obj.sha256Plain,
  };
}

/** 单列密文 → 明文 Buffer（失败抛 DecryptError，分类码见 crypto/errors.js） */
function openSingle(material, raw, aad) {
  const env = parse(raw);
  return gcm.decrypt({ ...env, masterKey: material, aad });
}

module.exports = { serialize, parse, openSingle, sealSingle: gcm.encrypt };
