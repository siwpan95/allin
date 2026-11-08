'use strict';

/**
 * 数据库备份（只读源库，产物**永不包含**密钥材质与账号文件）。
 *
 * 2026-11-07 安全评估 F-03 的收口件：此前没有「正确的数据库备份命令」，
 * 于是有人直接复制整个 data/ —— 把 site.db 与 data/keys/*.key 一起打包，
 * 密文库瞬间变成一份可完整解密的快照。本脚本只产出一个 .db 文件，
 * 密钥与 seed-accounts.json 一个字节都不带。
 *
 * 用 SQLite `VACUUM INTO` 生成**一致性快照**：服务运行中也能备份，
 * 不需要停站，也不会把 WAL/SHM 的半写状态复制出去；源库全程只读。
 *
 * 用法：npm run backup:data -- --out <外部目录>
 * 配套：npm run backup-key -- --out <另一外部介质> --passphrase <口令>
 *       —— 密钥与密文必须分开存放、分开保管，不要放进同一个可复制的树。
 */

const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const config = require('../src/config');

function argValue(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : null;
}

function fail(msg) {
  console.error(`\n  ✗ ${msg}\n`);
  process.exit(1);
}

function main() {
  const outDir = argValue('--out');
  if (!outDir) fail('用法：npm run backup:data -- --out <外部目录>');

  const resolved = path.resolve(outDir);
  // 2026-11-08 深度审核 P1：围栏原先只挡 website/ 子树，父仓（版本库根）
  // 仍可写，产物会被 git 收走。上移到仓库根。
  const root = path.resolve(config.root, '..');
  if (resolved === root || resolved.startsWith(root + path.sep)) {
    fail('数据库备份不得写进仓库目录内（含父仓根）—— 避免与 data/keys/ 落进同一棵会被整体复制的树。请换外部目录/介质。');
  }
  if (!fs.existsSync(config.dbPath)) {
    fail(`源库不存在：${config.dbPath}（先跑 npm run bootstrap）`);
  }

  fs.mkdirSync(resolved, { recursive: true });
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
  const outFile = path.join(resolved, `allin-site-db-${stamp}.db`);
  if (fs.existsSync(outFile)) fail(`目标文件已存在，拒绝覆盖：${outFile}`);

  let db;
  try {
    db = new DatabaseSync(config.dbPath);
    // VACUUM INTO 不接受绑定参数，路径里的单引号按 SQL 字符串规则转义。
    const quoted = `'${outFile.replace(/'/g, "''")}'`;
    db.exec(`VACUUM INTO ${quoted}`);
  } catch (err) {
    // 失败时清掉可能产生的半截文件，避免留下看似可用的假备份。
    try { fs.unlinkSync(outFile); } catch { /* 本来就没生成 */ }
    fail(`VACUUM INTO 失败：${(err && err.message) || err}`);
  } finally {
    if (db) db.close();
  }

  // 2026-11-08 深度审核 P1：VACUUM INTO 复制整库，sessions 表里的 sid、
  // csrf_token、ip 会明文进快照 —— 拿到备份无需主密钥即可冒充在线用户。
  // 灾备快照只需要密文库，会话凭据不属于其中；生成后清空并物理压缩。
  let backup;
  try {
    backup = new DatabaseSync(outFile);
    backup.exec('DELETE FROM sessions');
    backup.exec('VACUUM');
  } catch (err) {
    try { fs.unlinkSync(outFile); } catch { /* 尽力而为 */ }
    fail(`备份快照清理会话表失败，已删除产物：${(err && err.message) || err}`);
  } finally {
    if (backup) backup.close();
  }

  const size = fs.statSync(outFile).size;
  if (size === 0) {
    try { fs.unlinkSync(outFile); } catch { /* 尽力而为 */ }
    fail('备份产物为空，已删除；请检查源库完整性');
  }
  try { fs.chmodSync(outFile, 0o600); } catch { /* Windows 权限语义有限 */ }

  console.log('\n  数据库备份完成（仅密文库）');
  console.log('  ------------------------------------------');
  console.log(`  产物        ${outFile}`);
  console.log(`  大小        ${(size / 1024 / 1024).toFixed(2)} MB`);
  console.log('  未包含      data/keys/ 主密钥、seed-accounts.json 账号口令、WAL/SHM');
  console.log('\n  密钥须单独备份并分开保管：');
  console.log('  npm run backup-key -- --out <另一外部介质> --passphrase <口令>');
  console.log('  恢复后必跑：npm run verify:crypto && npm run smoke\n');
  return 0;
}

process.exit(main());
