// platform 冒烟测试：验证关键清单/契约与顶层文件齐备（node --test 默认发现 *.test.mjs）。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');

test('package.json 存在且含 workspaces', () => {
  const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
  assert.ok(Array.isArray(pkg.workspaces) && pkg.workspaces.length > 0, 'workspaces 缺失');
  assert.equal(pkg.name, 'allin-platform');
});

test('顶层契约文件齐备（LICENSE / README / AGENTS）', () => {
  for (const f of ['LICENSE', 'README.md', 'AGENTS.md']) {
    assert.ok(existsSync(join(root, f)), `缺少 ${f}`);
  }
});
