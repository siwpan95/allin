# allin —— 个人全项目治理索引仓库

> **do it better than future**
>
> 本仓的标语，出自对扎克伯格那句 **「Done is better than perfect.」（完成比完美更重要）** 的延伸感悟 ——
> 它不只说「先做出来」，更往前一步：**做出来的东西，要好过它被设想时的样子**。
>
> 这句话也是本仓**治理取向**的浓缩：门禁不追求一次到位，基线棘轮只允许单向收紧（不放松），
> 每一处文档与代码都先落地、先可跑、先留账，再在真实事故里迭代改好。
> 它写在 2026-06-04 的初始提交里，**保留不动**。

> **仓根随机器而异**（本仓多机检出、多端共写）：三台接入机器的仓根 / 发布区落点、盘位、运行时各不相同，
> **唯一事实源 = [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md)**（每机一件分区文件，
> 由 `tools/facts/measure.py` 采集、g20-facts 门禁对账）。本 README 只写**跨机共识**，不写单一机器的路径与数值。

一个**单一索引仓库**承载工作区治理说明、文档枢纽入口与 DeepSeek Harness 治理模式的**可重装载体**：
游戏引擎、游戏、爬虫、音视频工具、电台/转播服务、AI 项目、音乐资产等全部个人项目的事实源与约定都从这里索引出去。

> **📜 盘位沿革（历史事实，保留备查）**：原整盘工作区（盘符已撤销）的代码曾统一归置到 `/projects/`（13 个成员项目）；
> 本仓曾挂在旧盘根 `/allin`，2026-09-27 由 `allin_push` 改名为 **`allin`**（目录名与远端仓名一致）。
> 上述斜杠路径是**当时那台机器**的写法，**不是现行通用口径**；现行各机落点见机器分区索引，仓内文档里
> 出现的历史路径以"当时的事实"保留。
> 接手完整背景请读本仓 [`docs/README.md`](docs/README.md) 与 [`docs/记录/快照/新机配置汇总_2026-09-24.md`](docs/记录/快照/新机配置汇总_2026-09-24.md)。

> **📖 文档枢纽在最前面**：[`docs/`](docs/README.md) —— 整个工作区的文档入口（**开发过程透明可读、可复跑、可接手续做**）。
> 接手请按顺序读：[`docs/MEMORY.md`](docs/MEMORY.md)（铁律与约定）→ [`docs/规范/SPEC-002-协作工作流程.md`](docs/规范/SPEC-002-协作工作流程.md)（流程与放行口径）→
> [`docs/记录/交接/2026-08.md`](docs/记录/交接/2026-08.md)（事实流水与坑）。
> 想复刻这套治理模式 → [`docs/规范/SPEC-105-治理模式建设指南.md`](docs/规范/SPEC-105-治理模式建设指南.md)。

## 命名约定（重要）

- **allin** = 本仓（索引 + 治理说明 + [文档枢纽 `docs/`](docs/README.md) + 审核证据 `audit-fragments/`）。检出目录名 = 远端仓名 `allin`（2026-09-27 前名为 `allin_push`，历史）；**检出路径随机器而异**，见 [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md)。
- **一仓一目录**：每个 gitee 仓库对应 `<项目盘>/<仓名>` 一个目录，仓名 = 目录名。
- **alloy** = 统一游戏引擎（原 allin_engine，2026-08-23 改名；仓库 siwpan/an-engine）。
- **复制优于共享**：项目内联引擎/字体/资源副本是**有意为之**，不算冗余；缓存（__pycache__/.venv/node_modules/build/dist）不算重复。

## 顶层结构（本仓实际内容）

| 目录/文件 | 内容 |
|---|---|
| `README.md` | 本文件（仓门面） |
| `LICENSE` / `.gitignore` | MIT 许可 + 忽略规则（密钥/构建物一律不入库） |
| `docs/` | **文档枢纽**：[总目录 `INDEX.md`](docs/INDEX.md) + 四分类（[`规范/`](docs/规范/) 约束 · [`事实源/`](docs/事实源/) 活台账 · [`记录/`](docs/记录/) 证据流水 · `md/` 历史树）。接手从 [`docs/README.md`](docs/README.md) 进 |
| `preset/` | **治理模式的载体**：`preset/allin/` = DSH agent preset「工作区治理」的 0.1.7+ 声明式可重装副本（见下节与 [`preset/allin/安装说明.md`](preset/allin/安装说明.md)） |
| `tools/` | 工作区门禁与工具（死根路径 + AST 未定义名 + **文档索引契约** + 别名重建，见其 README） |
| `platform/` | **全项目集成平台**（2026-10-26 由原 `siwpan/allin-platform` 整仓并入）：门户 + 内核 + 注册表 + harness 黄金值门禁。入口 [`platform/README.md`](platform/README.md)，契约 [`SPEC-203`](docs/规范/SPEC-203-allin-platform契约.md) |
| `kernel/` | **治理内核**（2026-10-27 立档）：Python/Cordis 服务图 + `allin` CLI 前门（`allin_cli.py`），四大支柱 `docs/platform/preset/tools` 经 `kernel/configs/cordis.allin.yml` 配置树挂载。说明见 [`kernel/README.md`](kernel/README.md) |
| `architecture/` | **系统架构与设计文档**（2026-10-27）：组件级架构图 [`system-architecture.svg`](architecture/system-architecture.svg) + 数据流图 [`data-flow.svg`](architecture/data-flow.svg) + 设计说明。刻意置于 `docs/` 之外以避开文档索引契约 |
| `audit-fragments/` | 深度审核的**过程证据**（报告本体已归 [`docs/记录/审计/`](docs/记录/审计/)） |
| `siwpan旧机配置汇总.html` | 旧机（已退役）机器事实源，作换机基线 |

> 历史 README 还列过 `repos/ platform/ local/ assets/ archive/ notpython/` 等目录 —— 那是旧整盘时期的形态（历史事实，保留备查）；
> 此后各项目已各自成为发布区 `<工作区根>/repos/<仓名>` 独立子仓，不再以"子目录"形式寄存在本仓内。

## 核心项目速览（成员项目示例）

- **alloy**（an-engine）：统一游戏引擎——ECS + EventBus + Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI。
- **private-radio-stations**：Node.js + Cordis 插件式转播站（radio/video/portal 三簇）。
- **musickit**（repos/musickit）：phonk 混音项目（真实采样 + 授权分级治理）。
- **deepseek-harness-master**：DeepSeek Harness（`@deepseek-ai/dsh-root` 0.1.7-rc.1）本地 fork；原独立 gitee 仓
  `siwpan/deepseek-harness` **已于 2026-10-26 整合后删除**——治理内核并入本仓（见「三仓整合」第 6 条）。
  工具本体是**仓外现役 checkout，落点随机器而异**（如 `@DESKTOP-8RSV60V` 在其数据盘 `deepseek-harness/`，
  同日旧检出 `G:\repos\deepseek-harness` 已移除）；各机有无检出及现值见 [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md)。
- 其余成员：`webcopier` `cordis-table-app` `foolproof-operation` `lab` `moba_battle_platform` `roleplayer` `music-master` `ncmturnmp3` `D20`。
- 以上 13 个为**成员示例子集**；各机检出规模不同（现值唯一事实源 = 机器分区索引），
  全量 Gitee 仓库见 [`PORTFOLIO.md`](PORTFOLIO.md) 与下节「Gitee 项目组合全量索引」。

## DeepSeek-Harness 治理落地（2026-09-26）

工作区治理模式（"开卷必读四事实源 + 三条铁律 + 本机边界"）已落进 DSH **0.1.7+ 声明式 preset**：

- 载体：`preset/allin/allin.patch.yml` —— 插入一行 `@deepseek-ai/dsh-agent-preset`（`config.id: allin`），`persona.prefix` 末尾追加治理段（`GOVERNANCE:BEGIN/END`）。
- **创造模式兼容**：0.1.7 声明式 preset 即"原有创造模式（creator/cordis 声明式编写）"的落地方式；在对话里也能等价编写。
- **无法挂载兜底**：`allin` 是独立 id（非 `cordis`），DSH 破坏性变更导致挂载失败时会话**自动降级到工厂 `standard`/`cordis`**（部署不崩、仅该会话无治理段）。
- **配套脚本**（`preset/allin/`）：
  - `verify-mount.ps1` —— 三层校验（安装层 / 结构层 / 漂移层）+ 兜底指引（UTF-8 BOM 运行）。
  - `make-bundle.ps1` —— 把 `allin.patch.yml` 封装成可 `dsh plugin add` 的 npm bundle（可选 `-Install`）；⚠️ bundle 是 `allin.patch.yml` 的派生副本，**改了源必须重跑本脚本刷新**，CI 用 `.\make-bundle.ps1 -Check` 拦落后。
  - `verify-upstream-merge.ps1` —— 上游 PR 合并门禁：合入前确认 allin overlay 与官方 harness 能力集无冲突。
- **独立 gitee 仓**：`siwpan/deepseek-harness`（remote `gitde`）—— 解耦 overlay 与上游镜像，上游破坏性变更只动我们的 pin、不动源；比对 shipped `cordis.patch.yml` 即可定位漂移点。
- **上游关系纪律（§八）**：官方 `github.com/deepseek-ai/deepseek-harness` 仅作 SHAPE 核对 / 漂移定位的**参考对象**，不直接 fetch 进部署；其更新经 PR 合入主干前须确认与 allin overlay **无冲突**（`verify-mount.ps1` 漂移层作判据之一）。完整纪律见 `docs/DSH升级与插件不兼容_2026-09-24.md` §八。

安装/校验/回滚全流程见 [`preset/allin/安装说明.md`](preset/allin/安装说明.md)。

## 治理 Agent 与内核（2026-10-27）

本仓治理以 **「Agent 双形态 + Cordis 内核 + 集成平台」** 三元落地，三者共享同一份治理事实（见 [`architecture/`](architecture/README.md) 设计文档与 [`architecture/system-architecture.svg`](architecture/system-architecture.svg)）：

- **治理大脑（Agent，双形态）**
  - **WorkBuddy 侧**：[`.workbuddy/skills/allin-governance-agent`](.workbuddy/skills/allin-governance-agent/SKILL.md) —— 本仓项目级治理 agent（总控大脑）：开卷读四事实源、按铁律/SPEC 放行判断、把具体活路由到 15 个专项 skill 或亲自跑门禁。
  - **DSH 侧**：[`preset/allin/allin.patch.yml`](preset/allin/allin.patch.yml) 的 `GOVERNANCE:BEGIN/END` 段（上节「DeepSeek-Harness 治理落地」），`config.id: allin`。
  - 二者是**同一份治理事实的两种落地形态**，文本注入式、非运行时耦合；任一侧改写须同步另一侧，漂移判据 = `preset/allin/verify-mount.ps1` 漂移层 + 本仓 `npm run check:governance`。
- **治理内核（Cordis 服务图）**：[`kernel/`](kernel/README.md) —— Python/Cordis 服务图，`allin_cli.py` 作统一前门（`tools` / `docs` / `platform` / `preset` 子命令）。`kernel/tree.py` 用 Cordis `Loader` 按 `kernel/configs/cordis.allin.yml` 挂载；`kernel/registry.py` 的 `SERVICES` 封闭白名单（`docs/platform/preset/tools` → `kernel/services/*.py`）把 entry name 钉死为代码边界（防「配置即代码」评审绕过）。
- **集成平台（Node）**：[`platform/`](platform/README.md) —— 零依赖 `node:http` 门户 `:9000`（Host 围栏 + loopbackOnly 防 DNS rebinding）+ `@allin/core` 注册表/启停/工坊内核；聚合不融合，项目是独立进程。API 契约见 [`platform/apps/portal/openapi.yaml`](platform/apps/portal/openapi.yaml)（OpenAPI 3.0.3，13 条路径，由真实源码生成）。

**系统架构图**：组件分层 [`architecture/system-architecture.svg`](architecture/system-architecture.svg) · 数据流 [`architecture/data-flow.svg`](architecture/data-flow.svg) · 设计说明 [`architecture/README.md`](architecture/README.md)。
> 该目录刻意置于 `docs/` 之外——新增文档若进 `docs/` 必须在 [`docs/INDEX.md`](docs/INDEX.md) 登记（文档索引契约 D1/D8），而架构图是工程视图、不属于四分类文档体系，故不入枢纽。

## 发布面（gitee）

- 全部仓库公开 + MIT（铁律 0）；一项目一仓，主分支 master，发行版 tag `<项目>-v<版本>`。
  **唯一例外**：`pluginplayer` 随包分发 GPL v3 的 FFmpeg `full_build-shared` 与 MinGW 运行时，许可必须随上游走 **GPL-3.0-or-later**（改 MIT 才是违规）。
- 2026-08-27 重建仓：集合仓退役改名 `*-legacy`，45 个分支项目拆为独立仓，版本分支转 tag。详见 `docs/md/allin主工作区/重建仓执行报告_2026-08-27.md`。

## 仓库体检工具：`tools/repocheck/`（2026-10-26 由原独立仓并入）

离线只读体检：**不联网、不执行被测代码、零第三方依赖**（纯标准库）。对一个根目录（典型为各机发布区
`<工作区根>/repos/`，路径随机器见机器分区索引）下的每个项目
按 **30 条规则**打分（0–10 健康分），支持 text / JSON / CSV / HTML 四种导出，可进 CI。

```bash
python tools/repocheck/main.py            # 无参数 = GUI
python tools/repocheck/main.py <发布区>    # 命令行体检整个发布区（如 <工作区根>/repos）
python tools/repocheck/main.py . --fail-on error   # 进 CI：有 error 级问题就失败
```

规则清单（error/warn/info 三级共 30 条）、五档退出码口径、健康分算法与 45 条命令行参数见
[`tools/repocheck/README.md`](tools/repocheck/README.md)；变更记录见其 `CHANGELOG.md`，Agent 维护说明见其 `SKILL.md`。

### 本仓自检口径（治理别人先治理自己）

本仓是 monorepo：`tools/` `docs/` `preset/` 等是**仓库自身的中间目录**，不是独立项目，
直接 `main.py .` 会把它们误当项目扫描。**自检只打真实子件**，两条命令：

```bash
# A) 平台子件（排除中间目录 tools/ vendor/ preset/）
python tools/repocheck/main.py .     --exclude tools,vendor,preset --skip-rules 1,7 --fail-on error
# B) 体检器自身（排除中间目录 gate/）
python tools/repocheck/main.py tools/ --exclude gate --skip-rules 1,2,4,5 --fail-on error
```

豁免与已知偏差（**每一条都经实测核对，不是随手跳过**）：

| 项 | 处理 | 依据 |
| --- | --- | --- |
| 规则 1「无版本控制」 | `--skip-rules 1` | monorepo 子件本就没有自己的 `.git`，属结构固有（因此健康分上限被压到 6.0） |
| 规则 7「旧路径残留」 | `--skip-rules 7` | 唯一命中是 `tools/gate/scan_hardcoded.ps1` —— 它**本身就是路径门禁脚本**，内含 `X:\foo`、`G:/fake/` 等测试夹具与注释举例（第 228 行仅出现在注释说明里） |
| 规则 2「无 README」 | B) `--skip-rules 2` | `tools/` 下只有两个子件：`tools/repocheck` **有** README；`tools/security` 是单文件标准库脚本（`venv_ca_audit.py`），其用法记在 `.workbuddy/skills/venv-ca-security-audit/` 与仓内文档 |
| 规则 4「无依赖声明」 | B) `--skip-rules 4` | 同上：单文件脚本、只用标准库，无第三方依赖可声明（`tools/repocheck` 有 `pyproject.toml`） |
| 规则 5「无 LICENSE」 | B) `--skip-rules 5` | 二者都是本仓的子目录（非独立仓），许可随**仓根 LICENSE** 覆盖（铁律 0/4 的「根 LICENSE 存在」已满足） |
| 规则 3「无测试」 | ✅ **已修（2026-10-30）** | 原「规则只查项目根下的 `tests/`/`test/`，对 monorepo workspace 误报」的盲区已扩口：嵌套 `test/`/`tests/` 目录（路径段精确匹配）与 `*.test.*`/`*.spec.*`（任意层级）均被认可，`platform` 的 7 个 `.test.mjs` 不再需要记偏差；回归用例 4 条，套件 60 项全绿（见 `tools/repocheck/CHANGELOG.md` Unreleased） |

**现状**（2026-10-30 @`SIWPAN` 复测退出码）：`A)` **0**（通过）；`B)` **0**（豁免 1/2/4/5 四条结构固有项后通过）。
`platform` 的 warn 级（无 SECURITY / CONTRIBUTING / CHANGELOG / CI 配置）**已于 2026-10-27 清零**
（`419eb7e` / `de14746`，REC-AU-14 治理巡检，四件套 + dependabot 均已入库）；复跑 repocheck 0 问题、exit 0。

> ⚠ **上表的口径是「实测出来的」，不是抄来的**：2026-10-28 对账时发现原「`B)` 仅剩规则 1 固有项」与实际不符 ——
> B 实为 5 条 error（规则 1/2/4/5，命中 `tools/security` 单文件脚本），退出码 **1**。经逐条核对确认四条均属结构固有后，
> 才按上表豁免并复验到退出码 0。**规则口径变了就要改命令、改依据、改现状，三者一起改。**


## 三仓整合（2026-10-26）：repocheck + allin-platform + deepseek-harness → allin

> **本次变更**：用户拍板把治理相关的三个独立仓并入本仓，实现「管理与治理一体化」，完成后删除三仓远端。
> 过去的治理更多依靠长期实践积累的经验；**本仓自此成为「制度 + 载体 + 执行器」三位一体的单一入口**：
> 制度在 `docs/规范/`，载体是 [`platform/`](platform/README.md)，执行器是 [`tools/repocheck/`](tools/repocheck/README.md)，
> 粘合剂叙事取自 `deepseek-harness` 的治理内核（并入方式不同，见下方第 6 条）。
>
> **整合理念**（据用户说明，2026-10-26）：整合的目的，是**后续统一用 allin 管理与治理 repos**——
> 治理入口收敛到一处；因此 DSH 也需要纳入本仓体系。同时用户定性：**DSH 最重要的就是 API key（付费接口）**，
> 移入 allin 只是治理归位，**不影响原有功能继续发挥**。

| 原独立仓 | 本仓落点 | 历史处理 | 版本锚点 | 远端 |
| --- | --- | --- | --- | --- |
| `siwpan/repocheck`（14 commits / 29 文件） | `tools/repocheck/` | 压缩为 1 个 squash 提交 | `repocheck-v1.0.0` · `repocheck-v2.0.0` | 整合后删除 |
| `siwpan/allin-platform`（54 commits / 152 文件） | `platform/`（制度上提） | 压缩为 1 个 squash 提交 | `platform-v1.0.0` | 整合后删除 |
| `siwpan/deepseek-harness`（88 commits / 14339 文件） | `docs/记录/`、`docs/规范/`（**仅治理内核**） | **解构式并入**，见第 6 条 | 本地 `1.1.0` / 上游 `v0.1.7-rc.1` | 整合后删除 |

**关键取舍与记账**（六条，均可复跑核对）：

1. **历史压缩**：repocheck + allin-platform 两仓共 68 个 commit 压成 2 个 squash 提交（用户拍板），主仓历史保持线性干净。
   代价是不能用 `git log` 追溯中间过程；补偿措施是为三个历史发行版建了**内容精确的孤儿快照 tag**
   （tree 已加对应目录前缀），它们不在 master 主历史内，但 `git checkout <tag>` 能拿到当时的真实内容。
2. **tag 去冲突**：两仓都有 `v1.0.0`，直接合并会丢一个。按本仓既有约定「tag = `<项目>-v<版本>`」重命名。
3. **文档肢解上提**：`platform/docs/` 的 4 份文档按 SPEC-005 四分类判据打散进枢纽 ——
   架构地图 → [`SPEC-203`](docs/规范/SPEC-203-allin-platform契约.md)（规范层，并入清单规范）；
   2 份 ADR → [`docs/记录/决策/`](docs/记录/决策/)（记录层，新增子类，已同步 SPEC-005 §3.1）；
   可行性分析 → `docs/记录/专题/`。目录搬了家，**「一个事实一个家」没有被搬家破坏**。
4. **License 不混同**：本仓根 LICENSE 是 **MIT-0**，两个子件各自是 **MIT** —— 各自的 LICENSE 文件随目录保留，不通吃、不替换。
5. **交叉引用已同步**：`platform/README.md`、`platform/AGENTS.md` 的文档链接改指向枢纽新位置；
   `docs/INDEX.md` 自述份数、SPEC-005 目录树均已同步（跑 `tools/gate/docs_index.py` 验证 `blocking=0`）。
6. **DSH 例外：解构式并入，不做 subtree squash**（`deepseek-harness`，88 commits / 14339 文件 / MIT，
   Copyright 2026 DeepSeek）。它的 14339 个文件若整体 squash 进来，会把主仓体积与治理焦点一起冲垮；
   而本次要的是它的**治理智慧**而非代码体积，故分三个提交提取并入：
   `479793f`（cordis 粘合剂 · 治理内核）→ `2448135`（治理哲学）→ `d11c47f`（通用架构原则，填补 allin 粘合剂叙事缺口），
   落点全在 `docs/记录/` 与 `docs/规范/`。**代码本体不并入**，理由有三：
   - 它是**现役运行工具**（仓外 checkout，落点随机器——`@DESKTOP-8RSV60V` 侧在其数据盘 `deepseek-harness/`，
     版本 `1.1.0`，末次提交 2026-10-09；各机有无检出见机器分区索引），
     `start-dsh-web.py` 与 `.dsh-home/` 会话数据都在，删了工具即断供；
   - 用户定性：**dsh 最重要的就是 API key，也就是付费接口** —— 移入 allin 只是治理归位，
     不影响原有功能继续发挥，功能性资产无需搬迁；
   - 治理资产的接任者已在（本条三个提交），符合「无接任者不可删」。
   ⚠️ **凭证边界**：`.dsh-home/`（含真实 API key）由该仓 `.gitignore` 第 74 行 `.dsh-home*/` 排除，
   **从未入库**；本仓 `.gitignore` 亦有 `私人令牌.txt` / `*.token` / `*.key` / `*.pem` / `.env` 兜底。
   本仓为**公开仓**（铁律 0），任何真实凭据一律不得落入，此条无例外。

### 发布区约定（已完成 · 2026-10-26）

> **已落地**：`platform/registry/projects/` 全部 **107 份** yaml 的 `path`，由写死的失效盘符 `G:\repos\...`
> 统一改为 **`repos/<仓名>`**（去盘符、保留 repos 语义）。这是 repocheck 规则 7 的治理对象。
>
> 目录约定（<工作区根> = 本仓的上一级，本仓检出在 `<工作区根>/allin/`）：
>
> ```
> <工作区根>/
> ├── allin/      ← 本仓：制度 + 文档枢纽 + 治理载体/执行器（唯一仓库本体）
> └── repos/      ← 发布区：各发布项目各自独立克隆，与本仓并立
>     ├── lab/
>     ├── webcopier/
>     └── ...     （源码按需懒拉取，不预先克隆全量）
> ```
>
> 路径解析基准（`platform/packages/core/src/registry.js` → `resolvePath()`）：
> `repos/...` → `<工作区根>` 之下；其它相对值 → 治理仓根 `allin/` 之下（如平台自身的 `platform`）。
> 可用 `PLATFORM_REPOS_ROOT` 覆盖发布区根。

## Gitee 项目组合全量索引（137 仓）

全量 **137 个 Gitee 仓库**（公开 137 · 私有 0，2026-10-30 API 匿名分页实测；
2026-10-26 口径为 135：整合删去 `repocheck`、`allin-platform`、`deepseek-harness` 三仓并补齐新项目，
此后净增 2 仓）的索引见 [`PORTFOLIO.md`](PORTFOLIO.md)：
按仓库名排序，含语言 / Star / 简介 / 可见性。该文件由脚本从 Gitee API 自动生成，是**索引而非源码镜像**。

**治理原则：源码按需懒拉取**——只有开始具体开发某个项目时，才 `git clone` 到本机发布区
（`<工作区根>/repos/<仓名>`；落点随机器，现值见 [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md)）；
不强制预先克隆全量 137 仓（各机按需，全量检出与部分检出并存）。本仓（allin）只承载治理说明、文档枢纽、DSH preset 载体，
以及**治理动脉**：两件已并入库的子件（`platform/` 集成平台、`tools/repocheck/` 体检器）
加上 `deepseek-harness` 的治理内核（仅文档层，见第 6 条）；
其余 **136 个仓库各自独立**（137 减本仓自身），按需克隆、独立演进、整仓推送（铁律 0/3）。
`PORTFOLIO.md` 随远端变化而过期，需刷新时重跑生成脚本。

## 治理准则（2026-08-27 深度审核固化）

> **创新 = 借鉴 + 调整 + 同步 + 记账；「推倒重来」只允许发生在结构层，资产与历史永远保全。**

1. **借鉴必记账**：复制/借鉴任何外部代码、配置、概念前，记录「来源 + 许可证 + 借用范围」（上游 dsh/Cordis 或自己的样板都算）。
2. **调整必同步**：任何灵活更新之后三步回写——推远端（ls-remote 验证）→ 更新引用（registry/ports/目录索引）→ 跑黄金值（check / harness exit 0）。
3. **结构可重建、资产与历史永不推倒**：合并优于双仓并存；补优于删；还原优于分支（上游修复后弃用自维护补丁）。

- **敏感信息红线**：API Key / 令牌 / cookie 真实值绝不进代码、配置与仓库（一律 example 化 + .gitignore）。
- 全量审核（对照 deepseek-harness 与 gitee 全量仓）与逐项处置清单 R0–R11：见 [`docs/记录/审计/深度审核报告_2026-08-27.md`](docs/记录/审计/深度审核报告_2026-08-27.md)（＋同目录 [`审核遗留处置_R0-R11_2026-08-27.md`](docs/记录/审计/审核遗留处置_R0-R11_2026-08-27.md)）；本地推进详情见 [`docs/记录/交接/`](docs/记录/交接/)。

## 治理文档

**文档枢纽 = [`docs/`](docs/README.md)**：入口是**总目录** [`docs/INDEX.md`](docs/INDEX.md)，下分四类 ——
[`规范/`](docs/规范/)（约束，带 `SPEC-NNN` 与效力声明头）、[`事实源/`](docs/事实源/)（活台账，带时点）、
[`记录/`](docs/记录/)（证据流水，只增不改）、`docs/md/`（历史树，冻结）。
深度审核报告随本仓发布：见 [`docs/记录/审计/深度审核报告_2026-08-27.md`](docs/记录/审计/深度审核报告_2026-08-27.md)。

---

*最后更新：2026-10-30（README 去单机化——标题与正文不再写死 `/projects/allin` 等单一机器路径，仓根/发布区/检出规模统一指向 [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md)；Gitee 组合口径 135 → **137**（2026-10-30 API 实测）并重跑 `build_portfolio.py --apply` 刷新 PORTFOLIO.md；DSH 仓外 checkout 落点标注随机器。@`SIWPAN` 实测。前史：2026-10-28 治理对账 `ef2a545`（订正门禁 15→19 陈旧口径、修 g15 自检假阳性、落地 REC-AU-17/18））*
