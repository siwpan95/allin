// CLI 纯函数测试：过滤/表格对齐/端口文件解析（不触网、不需要门户运行）。
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// CLI 模块在 import 时固化 PLATFORM_ROOT，必须先设隔离 env 再动态 import。
process.env.PLATFORM_ROOT = fs.mkdtempSync(path.join(os.tmpdir(), 'platform-cli-'))

const { filterEntries, displayWidth, renderTable, readPortalPort } = await import('../src/index.js')

test('filterEntries 多关键词 AND 模糊匹配（id/名称/分类/标签）', () => {
  const entries = [
    { id: 'radio', name: '电台', category: 'media', gameplay: [] },
    { id: 'arcade', name: '街机', category: 'game', gameplay: ['arcade'], note: '怀旧' },
    { id: 'fish', name: '钓鱼', category: 'game', gameplay: ['fishing'] },
  ]
  assert.equal(filterEntries(entries, 'radio').length, 1)
  assert.equal(filterEntries(entries, '电台').length, 1)          // 中文名匹配
  assert.equal(filterEntries(entries, 'game arcade').length, 1)   // 分类 + 标签 AND
  assert.equal(filterEntries(entries, 'game fishing').length, 1)
  assert.equal(filterEntries(entries, 'game').length, 2)
  assert.equal(filterEntries(entries, '').length, 3)              // 空查询 = 全量
  assert.equal(filterEntries(entries, '不存在').length, 0)
})

test('displayWidth 中文按 2 列计', () => {
  assert.equal(displayWidth('abc'), 3)
  assert.equal(displayWidth('电台'), 4)
  assert.equal(displayWidth('a电b'), 4)
  assert.equal(displayWidth(''), 0)
})

test('renderTable 中英文混排各行显示宽度一致', () => {
  const out = renderTable(['ID', '名称'], [['radio', '电台'], ['arcade', '街机']])
  const lines = out.split('\n')
  assert.equal(lines.length, 4)
  assert.ok(lines[1].startsWith('-----'))
  assert.equal(displayWidth(lines[2]), displayWidth(lines[3]))
  assert.equal(displayWidth(lines[0]), displayWidth(lines[2]))
})

test('readPortalPort 端口文件解析 / 缺失与损坏返回 null', () => {
  assert.equal(readPortalPort(), null)  // 无 data/portal.port
  const dataDir = path.join(process.env.PLATFORM_ROOT, 'data')
  const portFile = path.join(dataDir, 'portal.port')
  fs.mkdirSync(dataDir, { recursive: true })
  fs.writeFileSync(portFile, '34567', 'utf8')
  assert.equal(readPortalPort(), 34567)
  fs.writeFileSync(portFile, 'not-a-port', 'utf8')
  assert.equal(readPortalPort(), null)
})
