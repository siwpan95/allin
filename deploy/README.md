# `deploy/` —— B 期三栈骨架（配置就绪，非运行态）

> **定位**：NetBox / Dolt / GraphRAG 三栈的**落仓配置与单向导入器**。
> 本目录全是纯文本、零第三方依赖、可离线审阅；**不含任何二进制、密钥、运行态数据**。
> Git 内 `facts/facts.json` 是唯一写入权威，本目录所有脚本一律 `dry-run` 默认，
> `--apply` 才写下游（ADR-0003 写入需显式确认）。

## 1. 目录职责

| 目录 | 内容 | 写谁 | 当前状态 |
|---|---|---|---|
| `dolt/` | `schema.sql`（9 表 + 2 视图 + `fact_version` 溯源表）、`import_from_git.py`（单向幂等导入 + 显式 `DOLT_COMMIT`）、`README.md` | Dolt 本地库（可重建派生物） | ✅ Dolt 2.7.2 已装、schema 真机执行、导入 + AS OF 验证通过 |
| `netbox/` | `docker-compose.override.yml`（回环绑定 + 显式密钥 + v2 token）、`sync_from_git.py`（幂等导入 + `changelog_message` 带 `source_git_sha`）、`README.md` | NetBox REST | 配置就绪；需 Docker Desktop + WSL2 才起服务 |
| `graphrag/` | `settings.yaml`（v3.x 键名）、`qa.yaml`（full/offline/readonly 三档）、`build_input.py`（叙述层语料唯一入口）、`README.md` | GraphRAG 叙述层索引 | `qa.yaml` 固定 `readonly`，未建索引 |

## 2. 三条不可让步的纪律

1. **SQL `COMMIT` ≠ dolt commit**。`import_from_git.py` 生成的 SQL 末尾必须带
   `CALL DOLT_COMMIT('-Am', 'facts: import git@<sha>', ...)`；漏了这条，`AS OF` /
   `dolt_diff_*` 的 transaction time 直接断掉。`--selftest` 专门断言它存在。
2. **`source_git_sha` 是跨四系统的统一溯源键**：Git HEAD → Dolt commit message +
   `fact_version` → NetBox `changelog_message` → GraphRAG citation。
   `tools/gate/facts_provenance.py`（g25）校验每条 fact 的 `source_file:line` 与下游 state 里的 sha。
3. **服务全挂 ≠ 门禁可以红**。三栈都不进 `run_all_gates.sh` 的阻断链前置；
   `tools/facts/cli.py --source auto` 在派生库缺失时回落纯 JSON 真身，
   `offline-check` 把「拔网 / 停三栈 / 删派生库」做成 6 项可复跑断言。

## 3. 命令速查（全部默认 dry-run）

```bash
# Dolt：生成导入 SQL（不写库）→ 真机导入 → 时间旅行验证
python deploy/dolt/import_from_git.py
python deploy/dolt/import_from_git.py --apply
python deploy/dolt/import_from_git.py --verify

# NetBox：生成幂等计划（不写服务）→ 显式写
python deploy/netbox/sync_from_git.py
NETBOX_URL=http://127.0.0.1:8000 NETBOX_TOKEN=nbt_... python deploy/netbox/sync_from_git.py --apply

# GraphRAG：只生成叙述层语料，不建索引
python deploy/graphrag/build_input.py
```

所有 state / 输入 / 派生目录都被 `.gitignore` 忽略，随 clone 不携带运行态数据。

## 4. B 期验收口径（来自终局架构蓝图 §9）

| 项 | 命令 | 期望 |
|---|---|---|
| 导入器判据自证 | `import_from_git.py --selftest` | `PASS`（幂等 + 显式 DOLT_COMMIT + sha 入 SQL） |
| g25 溯源判据自证 | `facts_provenance.py --selftest` | `PASS`（坏行号 / 缺文件 / 坏 sha 都被拦） |
| 真机时间旅行 | `import_from_git.py --verify` | `AS OF 'HEAD'` / `AS OF 'HEAD~1'` 均可查（已验 4 行）；**历史值差异**尚需制造一次真实事实变更后再验 |
| 服务缺席降级 | `bash scripts/run_all_gates.sh` | `ALLIN_GATE_SUMMARY status=clean`，三栈全停仍全绿 |
| 离线北极星 | `python tools/facts/cli.py offline-check` | `6/6 PASS` |

未完成的部署项（Docker / WSL2 / Dolt 二进制安装、NetBox 起栈、GraphRAG 索引）
逐项登记在 `docs/记录/交接/2026-11.md` 的 B 期记账节，**不得从表里删行消红**。

## 5. 许可与来源

核心三栈均为 Apache-2.0 / MIT；**NetBox 的 `branching` / `Custom Objects` 插件是
NetBox Limited Use License 1.0（非 Apache），按 O5=B 明确不引入**，
分支能力全部由 Dolt 承担。各组件官方来源与版本见三个子目录的 README。
