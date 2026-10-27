# Changelog · platform（allin 集成平台）

本文件记录 platform/ 子件的 notable 变更。整仓发布与版本以仓库根为准。

## [Unreleased]

### 治理补强（2026-10-27）
- 补齐安全与协作契约：`SECURITY.md` / `CONTRIBUTING.md` / `CHANGELOG.md`。
- 新增 CI（`.gitee/workflows/ci.yml`）：Node 校验 + `npm run check` + `npm test`。
- 新增 `platform/test/` 冒烟测试，验证 package.json 契约与顶层文件齐备。
