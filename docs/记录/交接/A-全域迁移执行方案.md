# A 全域结构化迁移执行方案（含形态裁决）

> 范围：关闭交接卷 §146.3 #7 的「全域结构化未迁移」缺口——
> 145 registry / 140 分级 / 34 工具 / 46 许可 / 13 路由 尚未进 facts.json。
> 本方案是 P0-A 的裁决 + 分阶段落地计划。Phase 1 已落地（见 §3）。
> 关联：SPEC-005（文档枢纽契约）、SPEC-204（系统架构）、g26 漂移门禁、g25 溯源门禁。

---

## 1. 核心裁决：真身反转采用「派生索引投影」而非「整段复制」

### 1.1 两条路对比

| 形态 | 做法 | 后果 | 是否与北极星冲突 |
|---|---|---|---|
| ❌ 整段复制 | 把 145/140/34/46/13 全部字段搬进 facts.json | 制造**第二个权威源**：registry YAML 与 facts.json 各存一份 → 双源漂移（正是 A 要消灭的） | 冲突：派生库可删，但 facts.json 成了第二权威，删了就丢真身 |
| ✅ 派生索引投影 | facts.json 仅持「索引 + `source_file` 溯源指针」，权威内容留在 Git 原源 | 单一权威不变；facts.json 是**可重建索引**，删了重建即得 | 一致：投影可删可重建，不破任何门禁 |

**裁决：采用派生索引投影。** 理由：
1. `platform/registry/projects/*.yaml` 已是结构化权威源（145 个），不存在「需要被结构化」的问题，只缺「被统一索引」。整段复制它才是制造问题。
2. 离线北极星要求「派生库可删可重建不破门禁」。索引投影满足；整段复制不满足。
3. 大规模（365 条）复制 = 维护负担 + 漂移温床，与治理目标背道而驰。

### 1.2 统一契约

- **声明态（权威）**：Git 内的 YAML/Markdown（registry、docs/事实源 表）。
- **facts.json.projects / .tiering / .tools / .licenses / .routes**：**派生索引投影**，每条带 `source_file` 指针，回指权威源的具体文件/行。
- **同步门禁**：g26 扩展的 `check_projects` 模式——投影缺失 → SKIP（可删），在场但不同步 → BLOCK（真漂移）。每次改权威源后跑生成器重建投影。

---

## 2. 五类数据的迁移形态

| 类别 | 当前权威源 | 目标形态 | 进度 |
|---|---|---|---|
| 145 registry | `platform/registry/projects/*.yaml`（已结构化） | facts.json.projects 索引投影（project_id/name/category/path/publish_repo/source_file） | ✅ Phase 1 完成 |
| 13 路由 | `docs/事实源/端口分配表.md`（人类可读孪生）+ `docs/事实源/ports.yaml`（机器可读权威）+ `platform/registry/ports.yaml`（旧双源之一） | **实测裁定**：端口分配表与 ports.yaml 是同一份「端口/路由分配」事实的孪生（13 行一一对应），故**不另建 facts.json.routes**——路由即端口分配；以 `docs/事实源/ports.yaml` 为唯一权威，facts.json.ports 为其派生索引投影，`platform/registry/ports.yaml` 重建为可重建镜像（双源消灭） | ✅ Phase 2 完成 |
| 140 分级 | `docs/事实源/组合分级决策索引.md`（人类可读孪生）+ `docs/事实源/tiering.yaml`（机器可读权威） | Q1/Q3 落地：抽成 YAML 结构化源 → facts.json.tiering 索引投影（仅 id/tier/domain/指针，详情留 YAML） | ✅ Phase 3 完成 |
| 34 工具 | `docs/事实源/工具分类索引.md`（人类可读孪生）+ `docs/事实源/tools.yaml`（机器可读权威） | Q1/Q3 落地：抽成 YAML 结构化源 → facts.json.tools 索引投影（仅 id/category/registry_id/指针，详情留 YAML） | ✅ Phase 3 完成 |
| 43 许可（原口径 46） | `docs/事实源/来源与许可表.md`（人类可读孪生）+ `docs/事实源/licenses.yaml`（机器可读权威） | Q1/Q3 落地：抽成 YAML 结构化源 → facts.json.licenses 索引投影（仅 id/license/status/指针，详情留 YAML） | ✅ Phase 3 完成 |

> 注：140 分级 / 34 工具 / 43 许可（原口径称「46 许可」，实测表内 43 目录，以 `licenses.yaml` 权威源 43 条为准）三类原在 **Markdown 表**里，现已抽成 `docs/事实源/{tiering,tools,licenses}.yaml` 结构化权威源（Q1 落地），facts.json 再投影（Q3 颗粒度）。直接解析 MD 表做投影脆弱，故先抽 YAML——本步已完成。

---

## 3. Phase 1 已落地（145 registry）

新增/修改：
- `tools/facts/build_projects.py`：registry → facts.json.projects 生成器，含 `--write`/`--check`/`--selftest`，零依赖（仅可选 yaml）。
- `facts/facts.schema.json`：新增 `projects` 数组 + `$defs/project`（声明为派生物，可重建）。
- `facts/facts.json`：写入 145 条 project 索引（project_id=文件名 stem，source_file 回指 registry YAML）。
- `tools/gate/facts_drift.py`（g26）：新增 `check_projects`，与 registry 同步对账（无 yaml 依赖；缺失→SKIP，不同步→BLOCK）。
- `scripts/run_all_gates.sh`：接入 g26 `--selftest` 与 `--json`。

验证：`build_projects --selftest` PASS、`facts_drift --selftest` PASS、`facts_drift --json` clean（projects 145==145）、`cli validate` OK。

---

## 4. ports 双源红线（Phase 2 已消）

> 原红线 1/2 在 Phase 2 实测后裁定如下，均已关闭。

1. **ports 双源（已消）**：`docs/事实源/ports.yaml`（13 条，机器可读）与 `platform/registry/ports.yaml`（旧 4 端口 stub，仅「回退默认/重建自 projects」）并存，且旧 `facts.json.ports` 是第三份手改源。
   **实测裁定（Q2）**：`docs/事实源/ports.yaml` 是唯一权威（被 SPEC-106/204、README、新人指南、INDEX、ADR-0009 引用，且是唯一含 13 端口 + change_log + segments 的机器可读源）；`platform/registry/ports.yaml` 经实测仅为回退默认/重建 stub，非权威。
   **处理**：docs 那份 = 唯一被手改源；`platform/registry/ports.yaml` 重建为它的**可重建镜像**（删了重建即得）；`facts.json.ports` 改为 docs 的**派生索引投影**（带 `source_file`，删了重建即得）。三份中仅 docs 一份被手改 —— 双源漂移消灭。
2. **ports 形态差异（已澄清）**：原担心的 `owner` 括号描述实际只存在于人类可读孪生 `端口分配表.md`；机器可读 `docs/事实源/ports.yaml` 的 `owner` 本就是干净路径（如 `/website`），与 `facts.json.ports.owner`（同样从 docs 取）、`platform/registry/ports.yaml` 镜像的 `owner`（从 docs 重建的同值）一致。三源 owner 现已一致；g26 端口判据仍保留「不比 owner」的豁免（无害 legacy，日后可收紧为比对 owner）。

---

## 5. 分阶段推进建议（待用户拍板）

- **Phase 1（已完成）**：145 registry 索引投影 + 同步门禁。
- **Phase 2（已完成）**：消 ports 双源（§4）→ 以 `docs/事实源/ports.yaml` 为唯一权威，`facts.json.ports` 改为其派生索引投影（13 条，带 `source_file`），`platform/registry/ports.yaml` 重建为可重建镜像（4 核心端口，删了重建即得）；g26 增 `check_ports_mirror` 防镜像漂移；`build_ports.py` 生成器接入 `run_all_gates.sh`（--check）。「13 路由」缺口由 facts.json.ports 一并关闭（路由=端口分配，无需独立 routes 实体）。
- **Phase 3（已完成）**：140 分级 / 34 工具 / 43 许可 抽成 `docs/事实源/{tiering,tools,licenses}.yaml` 结构化权威源（Q1 落地：先抽 YAML 再投影；MD 降级为人类可读孪生，二者同源维护），再各自 `facts.json.{tiering,tools,licenses}` 索引投影（Q3 颗粒度：仅 id/分类/指针，详情留 YAML）；g26 增通用 `check_index_sync` 对三表做双向同步对账（权威有/facts 缺→滞后 BLOCK，facts 有/权威缺→真漂移 BLOCK）；三个生成器接入 `run_all_gates.sh`（--check）。每表已在 `facts.schema.json` 登记为派生物（升 schema_version 见 §8）。

## 6. 用户已裁决的点（✅ = 已拍板）

- Q1（✅ 同意）：140 分级 / 34 工具 / 46 许可 三类**先抽成 `docs/事实源/*.yaml` 再投影**（与 registry 同构）。Phase 3 执行。
- Q2（✅ 实测裁定）：ports 双源以 **`docs/事实源/ports.yaml`** 为唯一权威（非原推荐 platform/registry）。依据见 §4。
- Q3（✅ 同意）：索引投影颗粒度仅 `id/name/category/path/source_file`（不搬详情），详情只留权威源。145 registry 投影已落地此口径；Phase 3 同口径。

> 以上裁决不影响 Phase 1 已落地内容；Phase 1 采用的「派生索引投影」形态即本方案 §1 的裁决结论，可直接作为后续 Phase 的模板。

---

## 7. Phase 2 落地清单（2026-11-09）

新增 / 修改：
- `tools/facts/build_ports.py`（新增）：docs/事实源/ports.yaml → facts.json.ports 投影 + platform/registry/ports.yaml 镜像生成器（`--write/--check/--selftest`，零依赖仅可选 yaml）。
- `tools/gate/facts_drift.py`（g26，修改）：增 `check_ports_mirror`（镜像⇄权威子集 + service 匹配，防双源复活）；`check_ports` 方向性判据保留（facts 子集，多出即真漂移）。
- `facts/facts.json`（修改）：`ports` 重写为 13 条派生索引投影（source_file→docs/事实源/ports.yaml，owner 取 docs 全值）。
- `facts/facts.schema.json`（修改）：`$defs/port` 增 `source_file`（派生可重建）。
- `platform/registry/ports.yaml`（重建）：改为 docs 的可重建镜像（4 核心端口 + 头部声明「删了重建即得，勿手改」）。
- `scripts/run_all_gates.sh`（修改）：接入 `build_projects.py --check` 与 `build_ports.py --check`（belt-and-suspenders，覆盖 Phase 1/2 派生投影同步）。

验证（全绿）：
- `build_ports --selftest` PASS（collect=2，sync_clean，drift_caught）
- `build_ports --check` clean（facts=0 mirror=0）
- `facts_drift --selftest` PASS（注入 phantom 99999 能拦，clean 能过）
- `facts_drift --json` clean（ports 13==13，mirror 13==13，projects 145==145，仅 Dolt state 滞后 WARN=派生物可重建）
- `cli validate` OK
- `bash -n run_all_gates.sh` 语法 OK

---

## 8. Phase 3 落地清单（2026-11-09）

新增 / 修改：
- `tools/facts/bootstrap_legacy_yaml.py`（新增）：**一次性**桥接——把三张遗留 MD 表解析成 `docs/事实源/{tiering,tools,licenses}.yaml` 结构化权威源（零依赖仅可选 yaml；`--check` 仅核对计数）。转完后日常编辑只改 YAML，MD 降级为人类可读孪生（头部已标注）。
- `docs/事实源/tiering.yaml` / `tools.yaml` / `licenses.yaml`（新增）：三表的结构化权威源（140 / 34 / 43 条，全字段保留在 YAML；MD 仅孪生）。
- `tools/facts/build_tiering.py` / `build_tools.py` / `build_licenses.py`（新增）：各自权威源 → facts.json 索引投影生成器（`--write/--check/--selftest`，零依赖仅可选 yaml）。
- `tools/gate/facts_drift.py`（g26，修改）：增通用 `check_index_sync`（YAML 权威 ⇄ facts.json 索引双向对账），对三表各跑一次。
- `facts/facts.json`（修改）：增 `tiering`(140) / `tools`(34) / `licenses`(43) 三条派生索引投影。
- `facts/facts.schema.json`（修改）：增 `tiering`/`tools`/`licenses` 数组 + `$defs/{tiering_index,tool_index,license_index}`（声明派生物，可重建）。
- 三张 MD 表头：各增「机器可读权威版：`*.yaml`」孪生声明，避免双源歧义。
- `scripts/run_all_gates.sh`（修改）：接入 `build_tiering.py --check` + `build_tools.py --check` + `build_licenses.py --check`（belt-and-suspenders，覆盖 Phase 3 派生投影同步）。

验证（全绿）：
- `bootstrap_legacy_yaml.py --check`：tiering=140 tools=34 licenses=43（类别 ai/audio/crawler/desktop/dev/game/visual 全解析）
- `build_{tiering,tools,licenses} --selftest` 均 PASS（collect / sync_clean / drift_caught）
- `build_{tiering,tools,licenses} --check` 均 clean
- `facts_drift --selftest` PASS、`--json` clean（tiering 140==140 / tools 34==34 / licenses 43==43，仅 Dolt state 滞后 WARN）
- `cli validate` OK
- `bash -n run_all_gates.sh` 语法 OK

> **A 全域迁移整体收口**：P0-A 三 Phase 全部完成——Phase 1（145 registry）、Phase 2（13 端口/路由，双源消灭）、Phase 3（140 分级 / 34 工具 / 43 许可）。交接卷 §146.3 #7「全域结构化未迁移」缺口关闭。
