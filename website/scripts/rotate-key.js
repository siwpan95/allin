'use strict';

/**
 * 密钥轮换：生成新主密钥 → 置为 active → 逐行"旧密钥解密 / 新密钥重加密"。
 *
 * 为什么必须重加密而不只是换 active：数据是 HKDF(主密钥) 派生 DEK 后加密的，
 * 换掉主密钥就等于旧数据全解不开。所以轮换 = 全量重新封装（re-wrap）。
 * 用户表额外要重算 email_hmac（它派生自主密钥），否则轮换后谁都登录不上。
 *
 * 用法：npm run rotate-key
 */

const { getDb } = require('../src/db');
const gcm = require('../src/crypto/gcm');
const keystore = require('../src/crypto/keystore');
const envelope = require('../src/crypto/envelope');
const config = require('../src/config');
const { logAudit } = require('../src/services/audit');

function rewrapAssets(db, newKeyId, newMaterial) {
  const rows = db.prepare('SELECT * FROM assets').all();
  let n = 0;
  for (const row of rows) {
    const oldMaterial = keystore.getKeyMaterial(db, row.key_id);
    const plaintext = gcm.decrypt({
      masterKey: oldMaterial,
      keyId: row.key_id,
      salt: row.salt,
      nonce: row.nonce,
      tag: row.tag,
      ciphertext: row.ciphertext,
      aad: row.aad,
      sha256Plain: row.sha256_plain,
    });
    const env = gcm.encrypt({ masterKey: newMaterial, keyId: newKeyId, plaintext, aad: row.aad });
    db.prepare(
      `UPDATE assets SET alg = ?, key_id = ?, salt = ?, nonce = ?, tag = ?, ciphertext = ?,
              sha256_plain = ?, updated_at = datetime('now') WHERE id = ?`
    ).run(env.alg, env.keyId, env.salt, env.nonce, env.tag, env.ciphertext, env.sha256Plain, row.id);
    n += 1;
  }
  return n;
}

function rewrapDocs(db, newKeyId, newMaterial) {
  const rows = db.prepare('SELECT * FROM secure_docs').all();
  let n = 0;
  for (const row of rows) {
    const oldMaterial = keystore.getKeyMaterial(db, row.key_id);
    const plaintext = gcm.decrypt({
      masterKey: oldMaterial,
      keyId: row.key_id,
      salt: row.salt,
      nonce: row.nonce,
      tag: row.tag,
      ciphertext: row.ciphertext,
      aad: row.aad,
      sha256Plain: row.sha256_plain,
    });
    const env = gcm.encrypt({ masterKey: newMaterial, keyId: newKeyId, plaintext, aad: row.aad });
    db.prepare(
      `UPDATE secure_docs SET alg = ?, key_id = ?, salt = ?, nonce = ?, tag = ?, ciphertext = ?,
              sha256_plain = ?, updated_at = datetime('now') WHERE id = ?`
    ).run(env.alg, env.keyId, env.salt, env.nonce, env.tag, env.ciphertext, env.sha256Plain, row.id);
    n += 1;
  }
  return n;
}

function rewrapUsers(db, newKeyId, newMaterial) {
  const rows = db.prepare('SELECT * FROM users').all();
  let n = 0;
  for (const row of rows) {
    const oldMaterial = keystore.getKeyMaterial(db, envelope.parse(row.email_cipher).keyId);
    const email = envelope
      .openSingle(oldMaterial, row.email_cipher, `user-email:${row.email_hmac}`)
      .toString('utf8');
    const sealed = gcm.encrypt({
      masterKey: newMaterial,
      keyId: newKeyId,
      plaintext: email,
      aad: `user-email:${gcm.lookupHmac(newMaterial, email)}`,
    });
    db.prepare('UPDATE users SET email_hmac = ?, email_cipher = ? WHERE id = ?').run(
      gcm.lookupHmac(newMaterial, email),
      Buffer.from(envelope.serialize(sealed), 'utf8'),
      row.id
    );
    n += 1;
  }
  return n;
}

function main() {
  const db = getDb();
  const before = keystore.getActiveKeyId(db);

  // 2026-11-04 工程审查修复（C7）：轮换此前无事务 —— rewrap 三表逐行执行，
  // 中途任一行解密失败会让 assets/secure_docs/users 处于新旧密钥混合态且 active key
  // 未切换（可手工恢复，但 keys 清单与数据状态漂移）。现全流程包进单事务：
  // 失败即整体回滚，密钥环与数据保持轮换前的原子状态。
  // 顺带修（C12）：source=env 时若 SITE_MASTER_KEY_BASE64 与旧钥同材质，
  // 就是"换 key_id 不换材质"的伪轮换 —— 全量重加密零安全增益，直接拒绝。
  db.exec('BEGIN');
  try {
    const created = keystore.createKey(db, { source: config.masterKeyBase64 ? 'env' : 'file', activate: false });
    if (before && created.source === 'env') {
      const oldMaterial = keystore.getKeyMaterial(db, before);
      if (created.material.equals(oldMaterial)) {
        throw new Error(
          `伪轮换拒绝：新 env 密钥与旧密钥 ${before} 材质完全相同（SITE_MASTER_KEY_BASE64 未更换）。` +
            '请先生成新的 32 字节随机串再注入，或改用 source=file。'
        );
      }
    }
    const newMaterial = created.material;

    const assets = rewrapAssets(db, created.keyId, newMaterial);
    const docs = rewrapDocs(db, created.keyId, newMaterial);
    const users = rewrapUsers(db, created.keyId, newMaterial);

    keystore.setActiveKey(db, created.keyId);
    db.exec('COMMIT');

    logAudit({ actor: 'rotate-key', action: 'crypto.rotate', target: `${before} -> ${created.keyId}`, detail: `assets=${assets} docs=${docs} users=${users}` });

    console.log('\n  密钥轮换完成（单事务，失败即整体回滚）');
    console.log('  ------------------------------------------');
    console.log(`  旧密钥      ${before}`);
    console.log(`  新密钥      ${created.keyId}（来源 ${created.source}）`);
    console.log(`  重新封装    资源 ${assets} 项 / 文档 ${docs} 条 / 用户 ${users} 个`);
    console.log(`  密钥清单    ${keystore.listKeys(db).map((k) => `${k.key_id}${Number(k.is_active) === 1 ? '*' : ''}`).join(', ')}`);
    console.log('\n  验证：npm run verify:crypto && npm run smoke\n');
  } catch (err) {
    db.exec('ROLLBACK');
    logAudit({
      actor: 'rotate-key',
      action: 'crypto.rotate_failed',
      target: before || null,
      ok: false,
      detail: String(err && err.message ? err.message : err).slice(0, 500),
    });
    console.error('\n  轮换失败，已整体回滚（密钥环与数据保持轮换前状态）：');
    console.error(`  ${err && err.message ? err.message : err}`);
    console.error('\n  排查：npm run verify:crypto 查看可解密性；勿手工改动 crypto_keys。\n');
    process.exitCode = 1;
  }
}

main();
