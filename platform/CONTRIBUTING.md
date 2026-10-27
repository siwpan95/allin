# Contributing · platform（allin 集成平台）

> 本目录只是 allin 单一索引大仓的一个子件。**所有改动必须随整仓一起提交、整仓推送**
> （见 `docs/规范/SPEC-101-推送流程.md` §5），禁止只推送 platform 子目录。

## 开发环境

- Node ≥ 22；`npm install`（workspace 安装：packages/*、apps/*）。
- 校验：`npm run check`；测试：`npm test`（node --test）。
- 架构地图与契约见 `docs/规范/SPEC-203-allin-platform契约.md` 与 `platform/README.md`。

## 改动流程（铁律）

1. **先读 README**：动 platform 前读 `platform/README.md`、仓库根 `README.md`。
2. **五阶段**：先问 → 计划 → review → 执行 → 复盘；一批 ≤ 4 个问题且必带推荐项。
3. **提交前过门禁**：本地 `bash scripts/run_all_gates.sh` 全绿；`docs_index.py` 无 blocking。
4. **推送在场**：本地提交即时做；推送只在维护者在场并放行时做，推后 `git ls-remote` 核对 IN_SYNC。

## 代码边界

- 新增平台能力：走 workspace（packages/*、apps/*）+ `platform/registry`。
- 路径一律相对仓根 / 配置推导，禁止硬编码绝对路径（受 `g01_paths` 门禁约束）。
