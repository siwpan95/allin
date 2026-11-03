'use strict';

/**
 * website 加密层单元测试（2026-11-04 工程审查补测，T4）。
 *
 * 此前 AES-256-GCM 加密核心只有 smoke-test 的「落盘无明文」一条间接断言；
 * 本套件直测 crypto 模块本身：gcm 往返 / 篡改必败 / AAD 绑定 / 轮换语义 /
 * keystore 文件源行为。用 node:test（零新依赖），KEY_DIR 重定向到临时目录，
 * 全程不触碰真实 data/。
 *
 * 跑法：npm test（或 node --test test/）
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');

// —— 必须在 require 任何 src 模块之前重定向数据目录（config 在 require 时读 env）——
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'allin-crypto-test-'));
process.env.KEY_DIR = path.join(TMP, 'keys');
process.env.DB_PATH = path.join(TMP, 'test.db');
delete process.env.SITE_MASTER_KEY_BASE64; // 测文件源路径，不测 env 注入

const gcm = require('../src/crypto/gcm');
const { DecryptError } = require('../src/crypto/errors');
const keystore = require('../src/crypto/keystore');

const KEY_A = crypto.randomBytes(32);
const KEY_B = crypto.randomBytes(32);

test.after(() => {
  fs.rmSync(TMP, { recursive: true, force: true });
});

// ---------------------------------------------------------------- gcm 往返

test('gcm: encrypt → decrypt 往返还原明文，且 sha256Plain 一致', () => {
  const plaintext = Buffer.from('你好，allin 加密层单测 🔐');
  const env = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-test-a', plaintext, aad: 'asset:test-1' });
  assert.strictEqual(env.v, gcm.ENVELOPE_VERSION);
  assert.strictEqual(env.keyId, 'k-test-a');
  const out = gcm.decrypt({ ...env, masterKey: KEY_A, aad: 'asset:test-1' });
  assert.deepStrictEqual(out, plaintext);
  // 每次加密盐/nonce 均随机 → 两份密文不同但都能解
  const env2 = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-test-a', plaintext, aad: 'asset:test-1' });
  assert.notDeepStrictEqual(env2.ciphertext, env.ciphertext);
  assert.notDeepStrictEqual(env2.nonce, env.nonce);
  assert.strictEqual(
    gcm.decrypt({ ...env2, masterKey: KEY_A, aad: 'asset:test-1' }).toString(),
    plaintext.toString()
  );
});

test('gcm: lookupHmac 对同一邮箱稳定、对主密钥敏感（轮换须重算）', () => {
  const h1 = gcm.lookupHmac(KEY_A, 'User@Example.com ');
  const h2 = gcm.lookupHmac(KEY_A, 'user@example.com');
  assert.strictEqual(h1, h2, '大小写与首尾空白应归一');
  assert.notStrictEqual(gcm.lookupHmac(KEY_B, 'user@example.com'), h1, '换主密钥必须换 HMAC');
});

// ---------------------------------------------------------------- 篡改必败

test('gcm: 密文被篡改一位 → AUTH_FAILED，绝不返回部分明文', () => {
  const env = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-test-a', plaintext: 'tamper-me', aad: 'doc:x' });
  env.ciphertext = Buffer.from(env.ciphertext);
  env.ciphertext[0] ^= 0x01;
  assert.throws(() => gcm.decrypt({ ...env, masterKey: KEY_A, aad: 'doc:x' }), (err) =>
    err instanceof DecryptError && err.code === 'AUTH_FAILED'
  );
});

test('gcm: AAD 绑定业务主键 —— 密文整行搬到别的记录解不开', () => {
  const env = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-test-a', plaintext: 'row-data', aad: 'asset:real-key' });
  assert.throws(() => gcm.decrypt({ ...env, masterKey: KEY_A, aad: 'asset:other-key' }), (err) =>
    err instanceof DecryptError && err.code === 'AUTH_FAILED'
  );
});

test('gcm: 错误主密钥 → AUTH_FAILED；缺密钥 → KEY_UNAVAILABLE；坏信封 → ENVELOPE_BAD', () => {
  const env = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-test-a', plaintext: 'secret', aad: 'doc:y' });
  assert.throws(() => gcm.decrypt({ ...env, masterKey: KEY_B, aad: 'doc:y' }), (err) =>
    err instanceof DecryptError && err.code === 'AUTH_FAILED'
  );
  assert.throws(() => gcm.decrypt({ ...env, masterKey: null }), (err) =>
    err instanceof DecryptError && err.code === 'KEY_UNAVAILABLE'
  );
  assert.throws(() => gcm.decrypt(null), (err) =>
    err instanceof DecryptError && err.code === 'ENVELOPE_BAD'
  );
});

test('gcm: tryDecrypt 宽容版返回 {ok:false,error} 而非抛出', () => {
  const env = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-test-a', plaintext: 's', aad: 'doc:z' });
  env.tag = Buffer.from(env.tag);
  env.tag[0] ^= 0xff;
  const r = gcm.tryDecrypt({ ...env, masterKey: KEY_A, aad: 'doc:z' });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.error.code, 'AUTH_FAILED');
});

// ---------------------------------------------------------------- 轮换语义（rotate 的密码学核心）

test('rotate: 旧密钥重加密到新密钥后，新钥可读、旧钥不可读（email HMAC 需同步重算）', () => {
  // 模拟 rotate-key.js 的 rewrap 语义：decrypt(旧) → encrypt(新)
  const plaintext = Buffer.from('rotate target row');
  const oldEnv = gcm.encrypt({ masterKey: KEY_A, keyId: 'k-old', plaintext, aad: 'doc:row-1' });
  const plain2 = gcm.decrypt({ ...oldEnv, masterKey: KEY_A, aad: 'doc:row-1' });
  const newEnv = gcm.encrypt({ masterKey: KEY_B, keyId: 'k-new', plaintext: plain2, aad: 'doc:row-1' });
  assert.deepStrictEqual(gcm.decrypt({ ...newEnv, masterKey: KEY_B, aad: 'doc:row-1' }), plaintext, '新钥可读');
  assert.throws(() => gcm.decrypt({ ...newEnv, masterKey: KEY_A, aad: 'doc:row-1' }), (err) =>
    err instanceof DecryptError && err.code === 'AUTH_FAILED'
  );
  assert.notStrictEqual(
    gcm.lookupHmac(KEY_B, 'a@b.c'),
    gcm.lookupHmac(KEY_A, 'a@b.c'),
    'users.email 的 HMAC 由主密钥派生，轮换后必须重算（README §6.4 口径）'
  );
});

// ---------------------------------------------------------------- keystore（文件源）

test('keystore: createKey 写 0600 key 文件并登记，getKeyMaterial 按材质取回', () => {
  const { getDb, closeDb } = require('../src/db');
  const db = getDb(); // DB_PATH/KEY_DIR 已重定向到临时目录（含 ensureKeyring）
  try {
    const created = keystore.createKey(db, { source: 'file', activate: true });
    assert.match(created.keyId, /^k-/);
    const file = keystore.keyFilePath(created.keyId);
    assert.ok(fs.existsSync(file), 'key 文件必须落盘（data/keys/）');
    const stat = fs.statSync(file);
    if (process.platform !== 'win32') {
      assert.strictEqual(stat.mode & 0o777, 0o600, 'key 文件权限必须 0600');
    }
    assert.deepStrictEqual(keystore.getKeyMaterial(db, created.keyId), created.material);
    // ensureKeyring 幂等：已有 active 时不建第二把
    const again = keystore.ensureKeyring(db);
    assert.strictEqual(again.created, false);
    assert.strictEqual(again.keyId, created.keyId);
  } finally {
    db.close();
  }
});
