# Changelog · kernel（allin 治理内核）

本文件记录本子件（kernel/）的 notable 变更。**整仓的发布与版本以仓库根为准**，这里只沉淀 kernel 自身的演进。

## [Unreleased]

### 治理补强（2026-10-27）
- 补齐安全与协作契约：`SECURITY.md` / `CONTRIBUTING.md` / `CHANGELOG.md`。
- 新增 CI（`.gitee/workflows/ci.yml`）：`py_compile` 语法检查 + `kernel/tests` 冒烟测试。
- 新增 `kernel/tests/` 冒烟测试，验证四大服务支柱可导入、Cordis 重导出可用。
- 新增 `kernel/cordis/` 重导出层，将 `from cordis import Service` 收敛为
  `from kernel.cordis import Service`，消除 repocheck rule 6 的 import 断裂误报
  （Cordis 本就是仓库内 vendored 依赖，运行时由 `_cordis_locate.ensure()` 定位）。
