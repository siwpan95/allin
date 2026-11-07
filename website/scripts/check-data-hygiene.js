'use strict';

/**
 * 运行时数据卫生体检（**只读**：绝不改写 / 删除 / 移动任何文件）。
 *
 * 背景（2026-11-07 安全评估 F-03）：
 *   本站把内容、图片、附件全部以 AES-256-GCM 密文存进 site.db，主密钥单独放
 *   data/keys/。「密钥与密文分离」是这套设计唯一的安全前提 —— 一旦图省事把
 *   data/ 整目录复制成备份，备份里同时出现 site.db 与 keys/*.key，密文就退化
 *   成可解密数据：谁拿到这份目录，谁就能解开全库。实测本机存在这样的快照。
 *
 * 本脚本把这条红线机械化：只读扫描 data/，发现任何子目录同时含「数据库副本」
 * 与「主密钥材质」即 exit 1 并给出处置建议。**删除/移动一律留给人工确认**，
 * 脚本不替人做破坏性动作。
 *
 * 用法：npm run check:data-hygiene
 */

const fs = require('node:fs');
const path = require('node:path');
const config = require('../src/config');

const ROOT = path.resolve(config.root);
const DATA = path.resolve(config.dataDir);
const KEY_DIR = path.resolve(config.keyDir);

const errors = [];
const warnings = [];

function rel(p) {
  return path.relative(ROOT, p).split(path.sep).join('/');
}

function isDbFile(name) {
  return name.startsWith('site.db') || /\.(db|sqlite|sqlite3)$/i.test(name);
}

/** 在 sub 下（限 3 层）分别收集 .key 与数据库文件；不做任何写入。 */
function collect(sub, depth = 0, acc = { keys: [], dbs: [] }) {
  if (depth > 3) return acc;
  let entries;
  try {
    entries = fs.readdirSync(sub, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const e of entries) {
    const p = path.join(sub, e.name);
    if (e.isDirectory()) {
      if (e.name !== 'node_modules' && !e.name.startsWith('.')) collect(p, depth + 1, acc);
    } else if (e.isFile()) {
      if (e.name.endsWith('.key')) acc.keys.push(p);
      else if (isDbFile(e.name)) acc.dbs.push(p);
    }
  }
  return acc;
}

function main() {
  if (!fs.existsSync(DATA)) {
    console.log(`\n  check:data-hygiene — ${rel(DATA)} 尚不存在（全新检出），无运行时数据可体检。\n`);
    return 0;
  }

  // ① 规范布局：data/ 根节点只应有 site.db 系列，密钥只能待在 data/keys/。
  const rootEntries = fs.readdirSync(DATA, { withFileTypes: true });
  const strayRootKeys = rootEntries.filter((e) => e.isFile() && e.name.endsWith('.key')).map((e) => e.name);
  if (strayRootKeys.length) {
    errors.push(`${rel(DATA)} 根下散落 ${strayRootKeys.length} 个 .key 文件（${strayRootKeys.join(', ')}）；密钥只允许放在 ${rel(KEY_DIR)}`);
  }

  // ② 每个子目录单独判定：同时含「库」与「密钥」= 一份可完整解密的快照。
  for (const e of rootEntries) {
    if (!e.isDirectory() || e.name.startsWith('.')) continue;
    const sub = path.join(DATA, e.name);
    if (path.resolve(sub) === KEY_DIR) continue; // 规范密钥目录，本身不含库
    const found = collect(sub);
    if (found.keys.length && found.dbs.length) {
      errors.push(
        `备份目录 ${rel(sub)} 同时含 ${found.dbs.length} 个数据库文件与 ${found.keys.length} 个主密钥文件 —— 该目录可解开全部密文`
      );
    }
  }

  // ③ 明文账号口令：属既有设计（0600 + gitignore），给提醒但不判失败。
  const accountsFile = path.join(DATA, 'seed-accounts.json');
  if (fs.existsSync(accountsFile)) {
    let plaintext = false;
    try {
      const obj = JSON.parse(fs.readFileSync(accountsFile, 'utf8'));
      plaintext = Array.isArray(obj.accounts) && obj.accounts.some((a) => a && typeof a.password === 'string' && a.password);
    } catch {
      /* 非明文（加密/损坏）按不报处理，具体由 verify:crypto 管 */
    }
    if (plaintext) {
      warnings.push(
        `${rel(accountsFile)} 含明文管理员/演示口令。该文件 0600 且已被 gitignore，但落盘即明文：` +
        `仅本机单用户使用时可接受；共享主机、上云备份或曾外发过该目录时，请重置两个账号口令。`
      );
    }
  }

  // ④ POSIX 下检查密钥文件权限（Windows 的 chmod 语义有限，尽力而为）。
  if (process.platform !== 'win32' && fs.existsSync(KEY_DIR)) {
    for (const name of fs.readdirSync(KEY_DIR).filter((n) => n.endsWith('.key'))) {
      const mode = fs.statSync(path.join(KEY_DIR, name)).mode & 0o777;
      if (mode & 0o077) warnings.push(`${rel(path.join(KEY_DIR, name))} 权限为 ${mode.toString(8)}，建议 chmod 600`);
    }
  }

  console.log('\n  allin 官网 · 运行时数据卫生体检');
  console.log('  ------------------------------------------');
  for (const msg of warnings) console.log(`  ! ${msg}`);
  if (errors.length) {
    for (const msg of errors) console.log(`  ✗ ${msg}`);
    console.log('\n  处置建议（需人工确认后再动手，本脚本不删任何文件）：');
    console.log('    1. 先做一份带口令的密钥备份：npm run backup-key -- --out <外部介质> --passphrase <口令>');
    console.log('    2. 把该快照里的 keys/ 与数据库分开保管，或确认无用后删除整份过期快照');
    console.log('    3. 今后数据库备份改用：npm run backup:data -- --out <外部目录>（只产出密文库，永不带密钥）');
    console.log('    4. 若这份快照曾外发 / 上云 / 进过公开仓库，按全库泄露处置：');
    console.log('       npm run rotate-key 轮换主密钥，并重置两个种子账号口令\n');
    return 1;
  }
  console.log('  ✓ 未发现「密钥与密文同处一份可复制快照」的高危布局');
  if (!warnings.length) console.log('  ✓ 无其它提醒');
  console.log('');
  return 0;
}

process.exit(main());
