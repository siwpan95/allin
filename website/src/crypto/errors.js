'use strict';

/**
 * 解密失败的分类错误码。
 *
 * 为什么必须分类：GCM 解密失败只有两种可能——密钥不对/密文被篡改，二者对运营的含义
 * 完全不同（前者是配置事故，后者是安全事件）。统一抛 "解密失败" 会让值班的人无从下手。
 */
const CODES = Object.freeze({
  ENVELOPE_BAD: 'ENVELOPE_BAD',
  VERSION_UNSUPPORTED: 'VERSION_UNSUPPORTED',
  KEY_UNAVAILABLE: 'KEY_UNAVAILABLE',
  AUTH_FAILED: 'AUTH_FAILED',
  INTEGRITY_MISMATCH: 'INTEGRITY_MISMATCH',
});

const MESSAGES = Object.freeze({
  ENVELOPE_BAD: '密文封套结构不完整',
  VERSION_UNSUPPORTED: '密文封套版本不受支持',
  KEY_UNAVAILABLE: '密钥不可用（未配置或已被轮换移除）',
  AUTH_FAILED: 'GCM 认证失败：密文或关联数据已被篡改',
  INTEGRITY_MISMATCH: '摘要校验失败：明文与写入时不一致',
});

class DecryptError extends Error {
  constructor(code, detail) {
    super(`${code}: ${MESSAGES[code] || '解密失败'}${detail ? ` (${detail})` : ''}`);
    this.name = 'DecryptError';
    this.code = CODES[code] ? code : 'ENVELOPE_BAD';
    this.detail = detail || null;
  }
}

class KeyUnavailableError extends Error {
  constructor(keyId) {
    super(`密钥不可用：${keyId}`);
    this.name = 'KeyUnavailableError';
    this.keyId = keyId;
  }
}

module.exports = { CODES, MESSAGES, DecryptError, KeyUnavailableError };
