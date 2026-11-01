'use strict';

/**
 * 数据库入口：SQLite（Node 内置 node:sqlite，无原生编译依赖，装完即跑）。
 *
 * 只做三件事：建目录 → 应用 schema（v1 幂等）→ 保证密钥环就绪。
 * 迁移策略：schema 全用 CREATE TABLE IF NOT EXISTS，version 记在 schema_meta；
 * 未来版本升级时在 migrations 数组里按版本号追加，不做破坏性改写。
 */

const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const config = require('../config');
const keystore = require('../crypto/keystore');

const SCHEMA_VERSION = 1;

let instance = null;

function applySchema(db) {
  const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8');
  db.exec(schema);
  const row = db.prepare('SELECT version FROM schema_meta ORDER BY version DESC LIMIT 1').get();
  if (!row) {
    db.prepare('INSERT INTO schema_meta (version) VALUES (?)').run(SCHEMA_VERSION);
  } else if (Number(row.version) > SCHEMA_VERSION) {
    throw new Error(`数据库版本 ${row.version} 高于程序支持的 ${SCHEMA_VERSION}，请升级代码后再启动`);
  }
}

function openDatabase() {
  fs.mkdirSync(path.dirname(config.dbPath), { recursive: true });
  fs.mkdirSync(config.keyDir, { recursive: true });
  const db = new DatabaseSync(config.dbPath);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec('PRAGMA busy_timeout = 5000');
  applySchema(db);
  keystore.ensureKeyring(db);
  return db;
}

function getDb() {
  if (!instance) instance = openDatabase();
  return instance;
}

function closeDb() {
  if (instance) {
    instance.close();
    instance = null;
  }
}

module.exports = { getDb, closeDb, applySchema, SCHEMA_VERSION };
