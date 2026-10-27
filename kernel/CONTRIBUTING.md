# Contributing · kernel（allin 治理内核）

> 本目录只是 allin 单一索引大仓的一个子件。**所有改动必须随整仓一起提交、整仓推送**
> （见 `docs/规范/SPEC-101-推送流程.md` §5），禁止只推送 kernel 子目录。

## 开发环境

- Python ≥ 3.12；Cordis 运行时由仓库内 `vendor/cordis`（见 `kernel/_cordis_locate.py`）
  定位，**无需联网、无需额外 pip 安装**即可自举。
- 跑本子件相关治理门禁：`bash scripts/run_all_gates.sh`。

## 改动流程（铁律）

1. **先读 README**：动 kernel 前读 `kernel/README.md` 与仓库根 `README.md`。
2. **五阶段**：先问 → 计划 → review → 执行 → 复盘；一批 ≤ 4 个问题且必带推荐项。
3. **提交前过门禁**：本地 `bash scripts/run_all_gates.sh` 全绿；`docs_index.py` 无 blocking。
4. **推送在场**：本地提交即时做；推送只在维护者在场并放行时做，推后 `git ls-remote` 核对 IN_SYNC。

## 代码边界

- 新增被内核调度的支柱/工具：只改 `kernel/registry.py` 的 `SERVICES` + 对应 `kernel/services/*.py`。
- 新增模块若依赖 Cordis，统一 `from kernel.cordis import Service`（重导出层），不要直接 `from cordis import …`。
- 禁止引入机器相关绝对路径；路径一律相对仓根推导（`kernel/paths.py`）。
