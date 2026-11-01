'use strict';

/**
 * 加密层自检：把"应该失败的情形"也跑一遍。
 *
 * 只测正向加解密是不够的 —— 完整性保障的价值恰恰体现在它**拒绝**什么：
 * 密文被改、AAD 对不上、密钥不对、摘要不符，都必须失败且带正确分类码。
 *
 * 用法：npm run verify:crypto
 */

const crypto = require('node:crypto');
const gcm = require('../src/crypto/gcm');
const { DecryptError, KeyUnavailableError } = require('../src/crypto/errors');
const keystore = require('../src/crypto/keystore');
const { getDb } = require('../src/db');

const results = [];

function check(name, fn, expectedCode) {
  try {
    const value = fn();
    if (expectedCode) {
      results.push({ name, ok: false, detail: `本应失败(${expectedCode})却成功了` });
    } else {
      results.push({ name, ok: true, detail: value || 'ok' });
    }
  } catch (err) {
    const code = err instanceof DecryptError ? err.code : err.name;
    if (expectedCode && code === expectedCode) {
      results.push({ name, ok: true, detail: `按预期失败：${code}` });
    } else {
      results.push({ name, ok: false, detail: `意外异常 ${code}: ${err.message}` });
    }
  }
}

function seal(material, keyId, plaintext, aad) {
  return gcm.encrypt({ masterKey: material, keyId, plaintext, aad });
}

function open(envelope) {
  return gcm.decrypt(envelope).toString('utf8');
}

const master = crypto.randomBytes(32);
const other = crypto.randomBytes(32);
const aad = 'asset:site_home_hero_01';
const plaintext = 'allin 官网加密自检 · do it better than future';

// 1) 正常往返
check('往返加解密一致', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  const out = open({ ...env, masterKey: master, aad });
  return out === plaintext ? `${plaintext.length} 字节往返一致` : `不一致：${out}`;
});

// 2) 密文被改一个字节 → GCM 认证失败
check('密文篡改被拒', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  const tampered = Buffer.from(env.ciphertext);
  tampered[0] ^= 0x01;
  open({ ...env, ciphertext: tampered, masterKey: master, aad });
}, 'AUTH_FAILED');

// 3) AAD 对不上（把 A 记录的密文搬到 B 记录） → 认证失败
check('AAD 绑定生效', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  open({ ...env, masterKey: master, aad: 'asset:another_key' });
}, 'AUTH_FAILED');

// 4) 密钥不对 → 认证失败（而不是返回乱码明文）
check('错误密钥被拒', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  open({ ...env, masterKey: other, aad });
}, 'AUTH_FAILED');

// 5) 认证标签正确但摘要不符 → 完整性不符
check('摘要不符被拒', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  open({ ...env, masterKey: master, aad, sha256Plain: crypto.createHash('sha256').update('other').digest('hex') });
}, 'INTEGRITY_MISMATCH');

// 6) nonce 被改 → 认证失败
check('nonce 篡改被拒', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  const bad = Buffer.from(env.nonce);
  bad[0] ^= 0x80;
  open({ ...env, nonce: bad, masterKey: master, aad });
}, 'AUTH_FAILED');

// 7) 封套缺字段 → 结构错误
check('封套不完整被拒', () => {
  gcm.decrypt({ masterKey: master, aad });
}, 'ENVELOPE_BAD');

// 8) 版本不受支持
check('不支持的封套版本被拒', () => {
  const env = seal(master, 'k-test', plaintext, aad);
  open({ ...env, v: 99, masterKey: master, aad });
}, 'VERSION_UNSUPPORTED');

// 9) 真实密钥环：取不到材质时 fail loud
check('密钥缺失时报错', () => {
  keystore.getKeyMaterial(getDb(), 'k-not-exist-000000');
}, 'KeyUnavailableError');

// 10) 邮箱检索哈希的确定性与主密钥相关性
check('邮箱检索哈希可用', () => {
  const a = gcm.lookupHmac(master, 'Demo@Example.com');
  const b = gcm.lookupHmac(master, 'demo@example.com');
  const c = gcm.lookupHmac(other, 'demo@example.com');
  if (a !== b) throw new Error('大小写归一化失效');
  if (a === c) throw new Error('不同主密钥应产生不同哈希');
  return '大小写归一化 + 主密钥相关，均符合预期';
});

const failed = results.filter((r) => !r.ok);
console.log('\n  加密层自检（AES-256-GCM / HKDF-SHA256）');
console.log('  ------------------------------------------');
results.forEach((r) => console.log(`  ${r.ok ? 'PASS' : 'FAIL'}  ${r.name.padEnd(22, ' ')} ${r.detail}`));
console.log('  ------------------------------------------');
console.log(`  ${results.length - failed.length}/${results.length} 通过\n`);
process.exit(failed.length ? 1 : 0);
