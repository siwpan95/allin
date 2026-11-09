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
| 140 分级 | `docs/事实源/组合分级决策索引.md` 表 | 抽成结构化源 → facts.json.tiering 索引 | ⬜ Phase 3 |
| 34 工具 | `docs/事实源/工具分类索引.md` 表 | 抽成结构化源 → facts.json.tools 索引 | ⬜ Phase 3 |
| 46 许可 | `docs/事实源/来源与许可表.md` 表 | 抽成结构化源 → facts.json.licenses 索引 | ⬜ Phase 3 |

> 注：140/34/46 三类目前在 **Markdown 表**里，不是结构化源。迁移必须先「抽成结构化源（YAML/JSON）」再投影；直接解析 MD 表做投影脆弱。Phase 3 的推荐做法是：把三张表转成 `docs/事实源/*.yaml`（与 registry 同构），facts.json 再投影。

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
- **Phase 3**：140 分级 / 34 工具 / 46 许可 抽结构化源 → 各自索引投影 + g26 扩展判据。每加一类升一次 `schema_version` 并立 ADR。

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
