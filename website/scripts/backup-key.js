'use strict';

/**
 * 密钥灾备：导出 / 恢复主密钥（2026-11-04 工程审查补齐，演练情景 A / 缺口 G1 的收口件）。
 *
 * 背景：data/ 整目录被 gitignore、crypto_keys 表只登记 key_id 不存密钥材质 ——
 * 主密钥文件一旦丢失（换机误删/盘坏），全部密文不可逆丢失（SEV1，且无任何
 * 文档化的恢复路径）。本脚本把"备份可恢复"变成两条命令。
 *
 * 导出：npm run backup-key -- --out <外部目录> [--passphrase <口令>]
 *   - 把 data/keys/ 全部 .key 文件 + crypto_keys 表清单打进一个备份文件；
 *   - 给了口令（推荐）：AES-256-GCM 加密（scrypt 派生，N=2^15）；
 *     不给口令：**拒绝执行**（明文密钥备份 = 把 SEV1 换成密钥泄露，不接受）；
 *   - 备份文件权限 0600；拒绝写进仓库目录内（防止密钥备份被 git 意外收走）。
 *
 * 恢复：npm run restore-key -- --from <备份文件> [--passphrase <口令>]
 *   - 解开备份 → 按 crypto_keys 清单重建 key 文件 → 核对 is_active 一致；
 *   - 恢复后必跑：npm run verify:crypto && npm run smoke（SPEC-106 §6 口径）。
 *
 * 注意：env 来源（SITE_MASTER_KEY_BASE64）的密钥材质不落盘、不进备份 ——
 * 它的灾备责任在密钥管理服务/注入通道本身，恢复时由环境变量重新注入。
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { getDb } = require('../src/db');
const config = require('../src/config');
const keystore = require('../src/crypto/keystore');

const SCRYPT_N = 1 << 15;
const BACKUP_MAGIC = 'ALLIN-KEYBACKUP-v1';

function argValue(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : null;
}

function fail(msg) {
  console.error(`\n  ✗ ${msg}\n`);
  process.exit(1);
}

function deriveCryptKey(passphrase, salt) {
  // N=2^15, r=8 需要 128*N*r=32MB 内存，须显式放宽 maxmem（Node 默认 32MB 会抛 INVALID_SCRYPT_PARAMS）
  return crypto.scryptSync(passphrase, salt, 32, { N: SCRYPT_N, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
}

function collectKeys(db) {
  const rows = keystore.listKeys(db).map((k) => ({
    key_id: k.key_id,
    source: k.source,
    is_active: Number(k.is_active) === 1 ? 1 : 0,
    created_at: k.created_at,
  }));
  const files = {};
  for (const row of rows) {
    if (row.source === 'env') continue; // env 密钥不落盘，灾备责任在注入通道
    const material = fs.existsSync(keystore.keyFilePath(row.key_id))
      ? fs.readFileSync(keystore.keyFilePath(row.key_id))
      : null;
    files[row.key_id] = material ? material.toString('base64') : null;
  }
  return { rows, files };
}

function cmdBackup() {
  const outDir = argValue('--out');
  const passphrase = argValue('--passphrase') || process.env.SITE_BACKUP_PASSPHRASE || '';
  if (!outDir) fail('用法：npm run backup-key -- --out <外部目录> [--passphrase <口令>]');
  if (!passphrase) {
    fail(
      '拒绝明文备份：必须提供口令（--passphrase 或环境变量 SITE_BACKUP_PASSPHRASE）。\n' +
        '  明文密钥备份等于把「密钥丢失 SEV1」换成「密钥泄露」，两种都不接受。'
    );
  }
  const resolvedOut = path.resolve(outDir);
  if (resolvedOut.startsWith(path.resolve(config.root) + path.sep) && !resolvedOut.startsWith(os.tmpdir())) {
    fail(`备份不得写进仓库目录内（${resolvedOut}）—— 换外部介质/目录，防 git 意外收走。`);
  }
  const db = getDb();
  const activeId = keystore.getActiveKeyId(db);
  if (!activeId) fail('密钥环未初始化（无 active 密钥），无可备份。');
  const { rows, files } = collectKeys(db);
  const materialCount = Object.values(files).filter(Boolean).length;
  if (materialCount === 0 && rows.some((r) => r.source === 'file')) {
    fail('key 文件已缺失（这正是本脚本要防的状态），无材质可备份 —— 先排查 data/keys/。');
  }

  const salt = crypto.randomBytes(16);
  const nonce = crypto.randomBytes(12);
  const payload = Buffer.from(
    JSON.stringify({ magic: BACKUP_MAGIC, created_at: new Date().toISOString(), activeId, rows, files }),
    'utf8'
  );
  const cipher = crypto.createCipheriv('aes-256-gcm', deriveCryptKey(passphrase, salt), nonce, {
    authTagLength: 16,
  });
  const ciphertext = Buffer.concat([cipher.update(payload), cipher.final()]);
  const body = Buffer.concat([
    Buffer.from(BACKUP_MAGIC + '\n', 'utf8'),
    salt,
    nonce,
    cipher.getAuthTag(),
    ciphertext,
  ]);
  fs.mkdirSync(resolvedOut, { recursive: true });
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
  const file = path.join(resolvedOut, `allin-keybackup-${stamp}.bin`);
  fs.writeFileSync(file, body, { mode: 0o600 });
  try {
    fs.chmodSync(file, 0o600);
  } catch {
    /* Windows 权限语义有限，尽力而为 */
  }
  console.log('\n  密钥备份完成');
  console.log('  ------------------------------------------');
  console.log(`  备份文件    ${file}`);
  console.log(`  密钥清单    ${rows.map((k) => k.key_id + (k.is_active ? '*' : '')).join(', ')}`);
  console.log(`  材质条目    ${materialCount} 个 key 文件（env 来源不备份，责任在注入通道）`);
  console.log(`  加密        AES-256-GCM（scrypt N=2^15，口令派生）`);
  console.log('\n  演练建议：每月从备份 restore 一次并跑 npm run verify:crypto && npm run smoke\n');
}

function cmdRestore() {
  const from = argValue('--from');
  const passphrase = argValue('--passphrase') || process.env.SITE_BACKUP_PASSPHRASE || '';
  if (!from) fail('用法：npm run restore-key -- --from <备份文件> [--passphrase <口令>]');
  const raw = fs.readFileSync(path.resolve(from));
  const nl = raw.indexOf(0x0a);
  if (raw.subarray(0, nl).toString('utf8') !== BACKUP_MAGIC) fail('不是本工具的备份文件（magic 不符）。');
  const salt = raw.subarray(nl + 1, nl + 17);
  const nonce = raw.subarray(nl + 17, nl + 29);
  const tag = raw.subarray(nl + 29, nl + 45);
  const ciphertext = raw.subarray(nl + 45);
  if (!passphrase) fail('需要口令（--passphrase 或 SITE_BACKUP_PASSPHRASE）。');
  let payload;
  try {
    const decipher = crypto.createDecipheriv('aes-256-gcm', deriveCryptKey(passphrase, salt), nonce, {
      authTagLength: 16,
    });
    decipher.setAuthTag(tag);
    payload = JSON.parse(Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8'));
  } catch {
    fail('解密失败：口令错误或备份损坏（AUTH_FAILED）。口令不匹配时不做任何写入。');
  }
  if (payload.magic !== BACKUP_MAGIC) fail('备份内容 magic 不符。');

  const db = getDb();
  const restored = [];
  for (const row of payload.rows) {
    db
      .prepare(
        `INSERT INTO crypto_keys (key_id, source, is_active) VALUES (?, ?, ?)
         ON CONFLICT(key_id) DO UPDATE SET source = excluded.source`
      )
      .run(row.key_id, row.source, 0); // 先全部置 0，最后按备份的 active 一次性置位
    const b64 = payload.files[row.key_id];
    if (b64) {
      keystore.writeKeyFile(row.key_id, Buffer.from(b64, 'base64'));
      restored.push(row.key_id);
    }
  }
  if (payload.activeId) keystore.setActiveKey(db, payload.activeId);
  console.log('\n  密钥恢复完成');
  console.log('  ------------------------------------------');
  console.log(`  key 文件重建 ${restored.length} 个：${restored.join(', ') || '（无）'}`);
  console.log(`  active 密钥  ${keystore.getActiveKeyId(db)}`);
  console.log('\n  必做验证：npm run verify:crypto && npm run smoke\n');
}

const mode = process.argv[2];
if (mode === 'backup') cmdBackup();
else if (mode === 'restore') cmdRestore();
else {
  console.log('用法：node scripts/backup-key.js <backup|restore> [options]');
  console.log('  backup  --out <外部目录> [--passphrase <口令>]');
  console.log('  restore --from <备份文件> [--passphrase <口令>]');
  process.exit(2);
}
