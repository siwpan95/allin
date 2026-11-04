'use strict';

/**
 * P1-5 回归：seed 随机口令生成与 reused 分支。
 *
 * 背景（全检发现）：
 *   1) 旧 randomBytes(9).toString('base64url').slice(0, 14) 约 12.8% 概率不含数字，
 *      createUser 抛错 → seed 半途失败；
 *   2) 旧 reused 分支把 env 值或占位串 `(已存在，沿用原口令)` 直接写进
 *      seed-accounts.json，与库内 hash 不一致 → smoke 管理员登录 302 失败。
 *
 * 隔离：本文件在 require 任何 src/ 之前把 DB_PATH / KEY_DIR 指到系统临时目录。
 * node:test 每个测试文件独立进程，不会污染 crypto / auth-redirect 测试，
 * 也不会碰 website/data/ 下的真实运行时数据。
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { test, after } = require('node:test');
const assert = require('node:assert/strict');

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'allin-seed-test-'));
process.env.DB_PATH = path.join(TMP, 'data', 'site.db');
process.env.KEY_DIR = path.join(TMP, 'data', 'keys');

const userService = require('../src/services/userService');
const { closeDb } = require('../src/db');
const { randomPassword, previousPasswords, ensureUser } = require('../scripts/seed');

const EMAIL = 'seed-regression@allin.local';
const ENV_VAR = 'SEED_TEST_ENV_PASSWORD';
delete process.env[ENV_VAR];

after(() => {
  closeDb();
  fs.rmSync(TMP, { recursive: true, force: true });
});

test('randomPassword：500 次生成全部满足 validatePassword（原实现 12.8% 失败）', () => {
  for (let i = 0; i < 500; i += 1) {
    const pwd = randomPassword();
    assert.equal(userService.validatePassword(pwd), null, `第 ${i} 次生成不合法：${pwd}`);
    assert.match(pwd, /[A-Za-z]/, '必须含字母');
    assert.match(pwd, /\d/, '必须含数字');
    assert.ok(pwd.length >= userService.MIN_PASSWORD, '长度需 >= MIN_PASSWORD');
  }
});

test('previousPasswords：读回账本，忽略 null 口令与脏记录', () => {
  const accountsFile = path.join(path.dirname(process.env.DB_PATH), 'seed-accounts.json');
  fs.mkdirSync(path.dirname(accountsFile), { recursive: true });
  fs.writeFileSync(
    accountsFile,
    JSON.stringify({
      accounts: [
        { email: 'a@x.local', password: 'Abc12345' },
        { email: 'b@x.local', password: null },
        null,
      ],
    }),
    { mode: 0o600 }
  );
  const got = previousPasswords();
  assert.equal(got['a@x.local'], 'Abc12345');
  assert.equal(got['b@x.local'], undefined, 'null 口令不可被当作可复用');
  fs.rmSync(accountsFile);
});

test('previousPasswords：账本缺失 / 损坏时返回空对象而非抛错', () => {
  assert.deepEqual(previousPasswords(), {});
  const accountsFile = path.join(path.dirname(process.env.DB_PATH), 'seed-accounts.json');
  fs.writeFileSync(accountsFile, '{ not json', { mode: 0o600 });
  assert.deepEqual(previousPasswords(), {}, '损坏的账本应被安全忽略');
  fs.rmSync(accountsFile);
});

test('ensureUser 全分支（顺序执行，共享同一个隔离库）', async (t) => {
  let createdPassword = null;

  await t.test('新建账号 → reused:false，写出的口令确实能解开库内 hash', () => {
    const r = ensureUser(EMAIL, '回归用户', 'member', ENV_VAR, {});
    assert.equal(r.reused, false);
    assert.equal(r.email, EMAIL);
    assert.equal(userService.validatePassword(r.password), null);
    const user = userService.findUserByEmail(EMAIL);
    assert.ok(user, '账号应已入库');
    assert.equal(userService.verifyPassword(user, r.password), true, '口令必须可登录');
    createdPassword = r.password;
  });

  await t.test('reused + 账本口令可复用 → 写回同一可登录口令，不写占位串', () => {
    const r = ensureUser(EMAIL, '回归用户', 'member', ENV_VAR, { [EMAIL]: createdPassword });
    assert.equal(r.reused, true);
    assert.equal(r.password, createdPassword, '必须写回真实可登录口令');
    assert.equal(r.note, undefined, '无冲突时不应产生多余说明');
    const user = userService.findUserByEmail(EMAIL);
    assert.equal(userService.verifyPassword(user, r.password), true);
  });

  await t.test('reused + env 与库内不一致 + 账本正确 → 忽略 env，写回可登录口令并注明', () => {
    process.env[ENV_VAR] = 'WrongEnvPass123';
    try {
      const r = ensureUser(EMAIL, '回归用户', 'member', ENV_VAR, { [EMAIL]: createdPassword });
      assert.equal(r.reused, true);
      assert.equal(r.password, createdPassword, '绝不能把错误的 env 口令写进账本');
      assert.ok(r.note && r.note.includes('不一致'), '需说明 env 被忽略');
      const user = userService.findUserByEmail(EMAIL);
      assert.equal(userService.verifyPassword(user, r.password), true);
    } finally {
      delete process.env[ENV_VAR];
    }
  });

  await t.test('reused + 候选全部不可复用 → password:null + 说明，绝不写假口令', () => {
    const r = ensureUser(EMAIL, '回归用户', 'member', ENV_VAR, { [EMAIL]: 'definitely-wrong-9' });
    assert.equal(r.reused, true);
    assert.equal(r.password, null, '宁可写 null，也不能写登不进去的假口令');
    assert.ok(r.note && r.note.includes('不可复用'));
    const user = userService.findUserByEmail(EMAIL);
    assert.equal(userService.verifyPassword(user, String(r.password)), false, 'null 不能碰巧撞对');
  });

  await t.test('新建分支：env 口令不合法时直接抛错，不创建半残账号', () => {
    process.env[ENV_VAR] = 'short';
    try {
      assert.throws(
        () => ensureUser('seed-bad-env@allin.local', '坏口令', 'member', ENV_VAR, {}),
        /不合法/
      );
      assert.equal(userService.findUserByEmail('seed-bad-env@allin.local'), undefined);
    } finally {
      delete process.env[ENV_VAR];
    }
  });
});
