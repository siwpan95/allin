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
| 13 路由 | `docs/事实源/端口分配表.md` + 与 `platform/registry/ports.yaml` **重复** | 先消双源（见 §4 红线），再 facts.json.routes 索引 | ⬜ Phase 2 |
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

## 4. 必须先消的两条红线（阻碍 Phase 2/3 真落地）

1. **ports 双源**：`docs/事实源/ports.yaml`（13 条）与 `platform/registry/ports.yaml` 并存，且 `facts.json.ports` 又是第三份。这是**真实的双源漂移**，必须在路由迁移前先统一为单一权威（推荐：`platform/registry/ports.yaml` 为权威，docs 那份转为生成视图或删除，facts.json.ports 改为索引投影）。
2. **ports 形态差异**：`docs/事实源/ports.yaml` 的 `owner` 带括号描述（`/website（src/server.js…）`），`facts.json.ports.owner` 是干净路径（`/website`）。g26 的端口判据因此**只比 `port/service/status`，不比 `owner`**（已在 g26 注明）。统一后此豁免可移除。

---

## 5. 分阶段推进建议（待用户拍板）

- **Phase 1（已完成）**：145 registry 索引投影 + 同步门禁。
- **Phase 2（建议下一步）**：消 ports 双源（§4 红线 1/2）→ facts.json.routes/ports 索引投影 + 端口判据放开 owner 比对。
- **Phase 3**：140 分级 / 34 工具 / 46 许可 抽结构化源 → 各自索引投影 + g26 扩展判据。每加一类升一次 `schema_version` 并立 ADR。

## 6. 待用户裁决的点

- Q1：140/34/46 三类是否同意「先抽成 `docs/事实源/*.yaml` 再投影」（推荐），还是保留 MD 表 + 解析器？
- Q2：ports 双源统一以哪份为权威？（推荐 `platform/registry/ports.yaml`）
- Q3：索引投影的颗粒度是否同意仅 `id/name/category/path/source_file`（不搬详情），详情仍只在权威源？

> 以上裁决不影响 Phase 1 已落地内容；Phase 1 采用的「派生索引投影」形态即本方案 §1 的裁决结论，可直接作为后续 Phase 的模板。
