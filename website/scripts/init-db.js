'use strict';

/**
 * 数据库初始化：建目录 → 建表 → 生成/校验主密钥 → 打印状态。
 * 幂等：重复执行不会重建表、不会换密钥、不会动已有数据。
 *
 * 用法：npm run init
 */

const path = require('node:path');
const config = require('../src/config');
const { getDb, SCHEMA_VERSION } = require('../src/db');
const keystore = require('../src/crypto/keystore');

function main() {
  const db = getDb();
  const keyring = keystore.ensureKeyring(db);

  const tables = db
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    .all()
    .map((r) => r.name);

  console.log('\n  allin 官网 · 数据库初始化完成');
  console.log('  ------------------------------------------');
  console.log(`  数据库文件  ${path.relative(config.root, config.dbPath)}`);
  console.log(`  schema 版本 v${SCHEMA_VERSION}`);
  console.log(`  数据表      ${tables.join(', ')}`);
  console.log(`  密钥目录    ${path.relative(config.root, config.keyDir)}`);
  console.log(`  生效密钥    ${keyring.keyId}（来源 ${keyring.source}${keyring.created ? '，本次新建' : '，已存在'}）`);
  console.log(`  密钥清单    ${keystore.listKeys(db).map((k) => k.key_id).join(', ')}`);
  console.log('\n  下一步：npm run seed（导入配图与站点文案，均为加密写入）\n');
}

main();
