# foolproof-operation：Cordis 式内核 + 自研 NTFS USN 索引（规划 v1）

> 日期：2026-09-23　　仓：`siwpan/foolproof-operation`（本地 `G:\repos\foolproof-operation`，master，HEAD `d60555a` = 远端）
> 任务分档：**大任务**（结构性 / 架构改造）→ 走五阶段全流程，计划书面摆出，等放行。
> 用户已拍板的两个方向（先问阶段）：**① Everything 侧 = 自研 NTFS USN/MFT 索引器**（不选 ES 增强、不选仅归档）；**② Cordis 侧 = 用 Cordis 模型重构本仓 Python 内部架构**（不选接入 DSH、不选只做检索）。

---

## 0. 前置实测事实（本轮已跑，全部只读）

| 探测项 | 实测结果 | 影响 |
|---|---|---|
| Everything 本体源码 | **不开源**。官方只开源 ES 命令行 + Everything SDK（均 MIT © voidtools） | 原设想「利用 Everything 源码」不可成立 |
| `Everything-master.zip`（yuzhengyang/Everything） | 331 条目：C# 学习程序（`Y.FileQueryEngine`，2017）+ `EverythingSZ 源码`（codeplex TFS）+ 1.3.3.658b 二进制 + 百度文库 PDF。**零行 voidtools 源码，且许可不明** | 只作原理参考，**零代码复制**（否则污染 MIT 仓） |
| CSDN 那篇文章 | AI 生成的下载导流页，无技术内容，指向 gitcode `Universal-Tool/c5a7f` | 不构成资料来源 |
| 非提权 `CreateFile(\\.\G:)` + `FSCTL_QUERY_USN_JOURNAL` | **成功**（handle 1444；JournalID `0x1dd157da37b8f67`，FirstUsn 2566914048，NextUsn 2608812960） | 数据盘可不提权读 USN |
| 非提权 `CreateFile(\\.\C:)` | **INVALID_HANDLE_VALUE**（拒绝） | 系统盘 C: 需提权 → 必须设计降级 |
| `LowUsn=FirstUsn` 枚举（博客/复刻代码的写法） | 12,071 条后 `err=38`(ERROR_HANDLE_EOF) 结束 —— **只拿到 journal 窗口内的记录** | 这是那套 C# 复刻的隐性缺陷；全盘索引必须 `LowUsn=0` |
| `LowUsn=0` + `HighUsn=MAXLONGLONG` | **480,523 条 / 60s ≈ 8,000 条/秒**（速率随预热爬升），60s 未到 EOF；已命中 `python.exe`/`pythonw.exe`/`pyvenv.cfg`/`site-packages` 各 ≥10 | 全盘枚举可行，但**首次建库是分钟级**，必须后台化 |
| 卷与文件系统 | C/D/E/F/G **全部 NTFS**；G: 4.0 TB（已用约 1.45 TB） | USN 原生可用 |
| Everything 未运行时 `es.exe` | `Error 8: Everything IPC not found`，查询条数 0 | 现有 `cli es` 的硬依赖（重启后即失效） |
| 现有环境发现实现 | `requirements.py:439-516` 多层 `iterdir` 启发式（C:/ 顶层 + C:/Users/* + 各盘两层） | 深层 venv 会漏；每次重扫 |
| 运行环境 | Python 3.13.14；非提权（`SIWPAN\13122`） | — |

**本机既有同类内核（必须记账的复用对象）**：`G:\repos\an-engine\allin_engine` 已是**Python 版 Cordis 微内核**——
`allin_engine/core/context.py` 提供 `provide / effect / get / has / install / unload / dispose / child / fork / fork_install / scopes`
与 `DuplicateServiceError / MissingDependencyError / DuplicateScopeError`，`dispose` 逆序回滚且容错；`GameEngine.mount/unmount`；
更已有把外部项目整体接进内核的**适配层先例** `allin_engine/trpg/context.py`（`TrpgContext`：容器复用宿主 Context、事件骑宿主 EventBus、注册即回滚、dispose 逆序退订，14 个 Service 并入）。
MEMORY 明载：**新项目优先复用 alloy 模块，不从别处复制代码**。

---

## 1. 目标

- **G1**：把「环境 / 包发现」从启发式目录遍历升级为 **NTFS 元数据索引检索**——全盘任意深度、秒级查询、**不依赖 Everything 进程运行**。
- **G2**：用 **Cordis 模型**（可逆副作用 effect 栈 / 服务注册表 / `inject` 依赖 / `fork` 作用域 / 事务化装配）重构本仓内部结构，使**检索后端与功能模块成为可插拔插件行**。
- **G3**：**投入产出必须为正**——功能面零减少、README 既有承诺不破、零新增运行时依赖。

## 1.5 参照物（v2 修正，2026-09-23 用户质疑驱动）

**本仓定位**：Python 依赖库/环境管理工具（dev 组工具，源自 `G:\tools\dev\requirements`）——**不是**「单机 GUI 小游戏」。
既有分档（《其余项目插件化路线图》）：**B 类 = alloy 三件事模板（项目内部插件化）**；D 类「不动」只针对「games 单文件玩具」。

| 参照物 | 借什么 |
|---|---|
| `allin_engine/core/context.py` | 内核语义：`provide/effect/fork/fork_install` + 逆序容错回滚 |
| **B 类范例 `audio_pipeline`** | 项目内部插件化：能力/阶段 = 插件行 |
| `crawl_hub` | **配置即清单**（`crawlers.json` ↔ 本仓 `requirements_categories.json`）+ **启动审计 fail-loud** + **任务日志 JSONL** + 审计 CLI |
| dev 组 `repocheck` / `py_test_runner` | 同类工具型宿主；「规则即数据」 |

**判据对照（用户 2026-08-27 拍板：宿主是否天然「多能力组合 + 频繁增删 + 生命周期可逆」）**：

| 判据 | 本仓实证 | 结论 |
|---|---|---|
| 多能力组合 | 七个面：分类 / pip 执行与修复 / 环境发现 / requirements.txt 解析 / 检索（ES·索引·遍历）/ GUI / CLI | ✅ |
| 频繁增删 | 24 分类 760 库由 `requirements_categories.json` **数据驱动**，「🔍 自动发现」持续增补；检索后端可增删 | ✅ |
| 生命周期可逆 | pip 子进程 / 后台线程 / 卷句柄 / SQLite 索引 / tkinter 回调订阅，全是需回收的资源 | ✅ |

→ **三项全中：应当插件化**（且比 D20 更符合判据）。

**由此新增的设计落点**：
1. **每个 Python 环境 = `ctx.fork(env_id)` 作用域**（多环境矩阵 = `fork_install` 的多实例场景；环境卸载只回滚该 fork，不扰动其它环境）；
2. `requirements_categories.json` 升级为**配置即清单**（schema 校验 + 启动审计 fail-loud）；
3. **任务日志 JSONL + 审计 CLI**（B 类模板标配，v1 漏项）；
4. GUI = 插件行（视图订阅者），**不做微前端式过度设计**。

## 2. 边界（明确不做）

- **N1** 不引入许可不明的第三方代码（C# 复刻只作原理参考）。
- **N2** **不新增常驻服务 / 端口**（无服务面 → `ports.yaml` 不动；铁律「新服务端口先查 ports.yaml」在此不触发）。
- **N3（v2 已撤销原措辞）** ~~不做整体 GUI 插件化~~ → **整体插件化，GUI 也是插件行**：
  本仓是 **Python 依赖库/环境管理工具**（dev 组工具），**不是**「单机 GUI 小游戏」。原 v1 把它误套 D20「单机 GUI 小游戏整体插件化不划算」的拍板，属**参照物错**（详见 §10 修订记录）。
  正确分档 = 《其余项目插件化路线图》**B 类：alloy 三件事模板（项目内部插件化）**（D 类「不动」明确只针对「games 单文件玩具」）。
  GUI 作为插件行（**视图订阅者**）只订阅服务，内核回滚即视图回滚；仅保留「不做微前端式过度设计」（沿用 radio 门户方案 D 被否决的先例）。
- **N4** **不删任何现有功能面**：`es` 子命令、目录遍历扫描、requirements.txt 支持、pip 修复链全部保留（新增后端是**加法**，故不产生「功能面 × 接任者」对照表的需求；若执行中确需替换，先过冗余判定三查）。
- **N5** 不改变发布形态（除 `requirements.spec` 打包清单的必要增补）。

## 3. 三个关键决策（请你在 review 时确认，我给了推荐）

| # | 决策 | 推荐 | 理由 / 备选 |
|---|---|---|---|
| **D1** | 内核来源 | **内联最小内核（约 250 行）**，语义对齐 `allin_engine.core.context`，**记账「借鉴其语义、零代码复制」** | **仓库法级依据**（《其余项目插件化路线图》§1.3）：六组工具 README 统一口径「各工具保持独立运行（**复制优于共享原则**），**互不 import**」；叠加 README 明载「纯标准库 + tkinter，**无需额外依赖**」；`allin_engine` 是游戏引擎，拉为依赖违两条约定且拖大便携 zip。**备选**：`pip install allin-engine`（PyPI 1.0.0），若你更看重内核统一性则走这条 |
| **D2** | 索引写入面 | **默认全只读**：只读卷句柄 + ENUM/READ；**不创建 USN journal** | `FSCTL_CREATE_USN_JOURNAL` 是改卷状态的写操作 → 列为高风险，需你逐项放行；无 journal 的卷只做全量枚举，增量降级为「重扫该卷」 |
| **D3** | C: 盘无权限时 | **显式降级 + 明示**：C: 继续走现有目录遍历功能面，UI/日志明说「C: 索引需管理员权限」 | 绝不静默丢环境（误判「没有 Python」比慢更糟） |

## 4. 交付物清单

**新增（仓内，纯加法）**

| 文件 | 职责 |
|---|---|
| `core/context.py` | 最小 Cordis 式内核：Context（`provide/effect/get/has/install/unload/dispose/child/fork/fork_install/scopes`）+ Service 基类 + 三个错误类 |
| `core/events.py` | 轻量事件总线（`on/emit/waterfall`，语义对齐 allin_engine event_bus） |
| `core/loader.py` | 配置装配：`foolproof.yml` 声明插件行（id / plugin / config / 可选 isolate 作用域）+ 内置默认清单；**事务化装配**（任一行失败整体回滚） |
| `index/usn.py` | USN/MFT 只读客户端（ctypes：`CreateFileW` / `QUERY_USN_JOURNAL` / `ENUM_USN_DATA` / `READ_USN_JOURNAL` + `USN_RECORD_V2/V3` 解析） |
| `index/paths.py` | FRN→路径还原（父链缓存 + rename/delete 的 Reason 位处理） |
| `index/store.py` | SQLite 索引（按卷分库、WAL、`JournalID`/`FirstUsn` 校验与重建判定） |
| `index/service.py` | 索引服务：首次全量后台建库 + 增量同步 + 查询 API |
| `plugins/*.py` | 插件行：`categories` / `pip` / `installer` / `scanner` / `reqtxt` / `fileindex` / `search` / `gui` / `cli` |
| `tests/**` | **stdlib `unittest`**（守住零依赖）：内核语义 / USN 解析 / 路径还原 / 索引查询 / 装配回滚 |
| `core/tasklog.py` | **任务日志 JSONL**（安装/卸载/扫描/索引事件，与 WorldLog/`dump-log` 同构）+ `cli tasks` 审计子命令——**B 类模板标配**（crawl_hub `tasks.log` / audio_pipeline `pipelog.py` 先例） |
| `core/audit.py` | **启动审计 fail-loud**：分类清单/插件行/路径校验，缺入口或失效即显式报错（对齐 crawl_hub `--check`） |
| `docs/usn-indexer.md` | 原理 + 本机实测基准（含 §0 数据）+ 权限矩阵 |

**改动**：`requirements.py`（GUI 改订阅服务，入口不变）、`cli.py`（子命令走同一内核）、`README.md` / `README.en.md` / `CHANGELOG.md`、`requirements.spec`（打包清单核对）。

## 5. 阶段拆分（每阶段独立可验收、可回滚；每阶段一个提交，**默认不推送**，推送逐次放行）

| 阶段 | 内容 | 黄金值（验收判据） |
|---|---|---|
| **0** | 把 §0 实测数据固化进 `docs/usn-indexer.md`；确认 D1/D2/D3。**无代码变更** | 文档落盘；`git status` 仅新增文档 |
| **1** | 最小内核 `core/{context,events,loader}.py` + `tests/` | `python -m unittest discover tests` 全绿；新增文件 `py_compile` exit 0；测试须锁住「逆序回滚 / 重复注册抛错 / fork 隔离与不累积 / 装配失败整体回滚」 |
| **2** | USN 只读客户端 `index/{usn,paths}.py`（G/E/D/F 实测枚举与路径还原；C: 降级） | 单元测试绿 + 实盘探针输出「卷 × 记录数 × python.exe 命中 × 耗时」对照表，且与 §0 基准同量级 |
| **3** | 索引存储与服务 `index/{store,service}.py`（全量建库 / 增量 / 查询） | 查询 < 100ms；「JournalID 变化 → 重建」有测试；中断后可续 |
| **4** | 接入内核：`fileindex`/`search`/`scanner` 三个插件行，**现有遍历保留为 fallback 后端**；GUI/CLI 改走服务 | CLI 全子命令 exit 0；GUI 冒烟**捕获 stderr 无 Traceback**；scan 结果与旧版对照**环境数不减少** |
| **5** | 其余插件迁移（`categories`/`pip`/`installer`/`reqtxt`），**行为零变化** | 全测试套件绿（**245 例**）+ CLI/GUI 回归对照旧版输出一致 ✅ **已完成 2026-09-23**（基线来自 `git archive HEAD` 快照，迁移前后 **52 项断言逐字一致**；清单 8 行；GUI 仅叶子逻辑委托，流程编排留原处） |
| **6** | 文档与同步：README/README.en/CHANGELOG/docs + 「目录索引.txt」+ spec 打包核对 + 复盘 | `python smoke_test.py` exit 0；受影响时实跑便携 zip 冒烟 |

## 6. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | **首次建库慢**（实测 ≈8,000 条/秒；G: 4TB 若数百万条 → 单卷分钟级，5 卷可能 20~40 分钟） | 后台线程 + 进度可见 + 增量同步 + 启动不阻塞（无索引时仍可用旧遍历 / ES） |
| R2 | C: 非提权不可读 | D3 降级 + 明示，功能面不减少 |
| R3 | USN 记录版本/偏移差异（V2/V3/V4、长名、扩展记录） | 按 `MajorVersion` 分支解析 + 用实盘数据锁测试 |
| R4 | 卷句柄被安全软件/权限干扰 | 失败即降级并写日志，不向 UI 抛栈 |
| R5 | 重构期间 GUI 功能中断 | 新内核**并行开发**，最后一步才切入口；切换前旧路径始终可用 |
| R6 | 索引陈旧（Everything 未运行时文件已变） | 启动增量同步 + 查询结果可开「实测复核」 |
| R7 | pyinstaller 打包遗漏新模块 | 阶段 6 显式核对 `datas`/`hiddenimports` 并实跑 |

## 7. 高风险动作清单（执行到该步前逐项确认）

1. 任何 `git push`（默认全程不推；逐次确认 + `git ls-remote` 核对 IN_SYNC）；
2. 任何删除/移动现有文件（本方案设计上**零删除**；如出现，先过「功能面 × 接任者」三查并列对照表）；
3. 创建 USN journal（本方案**默认不做**）；
4. 仓库结构变更（新增 `core/`、`index/`、`plugins/`、`tests/`、`docs/` 均为**纯新增目录**，仍按结构层逐项确认）。

## 8. 记账与同步（铁律）

- **来源与许可记账**（记入 `docs/usn-indexer.md` 与 CHANGELOG）：ES 1.1.0.37（MIT © 2025 voidtools，已在仓内）/ Everything SDK（原理与接口参考）/ `yuzhengyang/Everything`（GitHub，**许可不明**）与 EverythingSZ（codeplex）**仅原理参考、零代码复制** / `allin_engine`（MIT，siwpan，借其 Context **语义**，代码不复制）/ 本轮实测数据（本机 2026-09-23）。
- **同步三步**：推远端（逐次放行）/ 更新引用（README + `目录索引.txt` + 平台清单如涉及）/ 黄金值实跑。
- **端口**：本方案不新增服务 → `ports.yaml` 不动。

## 9. 自查（对照用户原始描述逐条，review 步骤产物）

| 你的原话要素 | 本计划如何覆盖 |
|---|---|
| 「利用 everything 源码」 | **已纠正**：官方无源码；改为「利用 Everything 的**原理**（USN journal + MFT 枚举）+ 官方 ES 既有通道」。第三方 C# 复刻许可不明 → 零代码复制 ✅ |
| 「cordis 架构体系」 | 按你选的**乙**：重构本仓 Python 内部架构；语义基准 = 本机既有 `allin_engine` 内核；分档 = **B 类（项目内部插件化）**，按用户 2026-08-27 判据三项全中 → 应当插件化（GUI 亦为插件行）✅ |
| 「增强 foolproof-operation」 | 功能面零减少、README 承诺不破、**零新增运行时依赖**、不新增端口 ✅ |
| 流程要求（铁律 2） | 五阶段：先问（已问 3 问）→ 计划（本文）→ review（§9 + 你的意见）→ 执行（等放行）→ 复盘（阶段 6）✅ |

**自查无遗漏的声明**：以上覆盖用户描述全部要素；执行中若遇计划外重大事实（如非提权枚举在实际卷上失败、`allin_engine` 语义与本项目需求冲突）→ **停下回头补问**，不擅自改向。

---

## 11. 推送方案（待逐项放行，2026-09-23）

本地 = `origin/master` = `dea9d33`（无分叉）；**44 个文件待入**，全部改动目前只在本地。
建议切成 **3 个提交**（按阶段分组，便于日后二分与 review）：

| # | 提交信息 | 主要内容 |
|---|---|---|
| 1 | `feat(cordis): 可逆插件内核 + 自研 USN/MFT 索引 + 环境发现（阶段 0~4）` | `core/{context,events,loader,runtime}.py`、`index/*`、`plugins/{search,scanner}.py`、`foolproof.composition.json`、`tests/`（内核/索引/发现/探针）、`docs/usn-indexer.md` + 基准 JSON |
| 2 | `refactor(plugins): 分类/pip/requirements.txt/安装器四行迁移（行为零变化）` | `plugins/{categories,pip,reqtxt,installer}.py`、`cli.py`/`requirements.py` 委托改造、`tests/test_installer_plugins.py` |
| 3 | `feat(ops): 任务日志 + 启动审计（cli tasks/doctor）+ 打包 spec 修复 + GBK emoji 崩溃修复 + 文档同步` | `core/{tasklog,audit}.py`、`cli.py`（tasks/doctor）、`requirements.spec`、`README(.en)`/`CHANGELOG`、`tests/test_ops_plugins.py` |

**已执行（2026-09-23，逐项放行）**：

1. ✅ `git ls-remote --symref origin HEAD` 复核默认分支 = **master**；
2. ✅ 三个提交：`e8f1086`（内核+索引）/ `e0dd51b`（插件接线）/ `41b320a`（运维+打包+文档）；
   推前核对：6 项新增 + 6 项修改、**0 删除**、无产物误入；
3. ✅ `git push origin master` → `dea9d33..41b320a`，**ls-remote 核对 IN_SYNC**；
4. ✅ tag `v1.1.0`（附注 tag，含发布说明）已推送（远端 `6d08618`）；
5. ✅ gitee release id `1162143`（`https://gitee.com/siwpan/foolproof-operation/releases/tag/v1.1.0`），
   附件 `3255007` = `foolproof-operation-portable-v1.1.0.zip`（14 MB，含 `requirements.exe` +
   README/README.en/LICENSE/CHANGELOG）；**zip 不入库**（`dist/` 已在 .gitignore 内）。

中间修订自洽性核对（用 `git archive` 快照实跑，不改工作区）：
`e8f1086` → 171 例通过；`e0dd51b` → 245 例通过；`41b320a`（终态）→ 271 例通过。

---

## 10. 修订记录

### v2.2 阶段 3 实测补充（2026-09-23）

- **落库不是瓶颈**：全盘 479 万行落库 + 建二级索引 **≈50 秒**（8.4~10.2 万行/秒），索引总体积 ≈428 MB（≈95 B/行）。v2.1 担心的「SQLite 成为新瓶颈」**实测不成立**（批量事务 + 二级索引后建 + 纯 INSERT 快路径）。
- **查询达标**：0.02~1.46 ms（最大 3.13 ms），远优于 <100 ms 目标；路径懒回溯 0.03~0.06 ms/条。
- **新坑（性能护栏）**：`WHERE name IN (?) COLLATE NOCASE` 会**全表扫描**（G: 251 万行 355ms），逐项 `name = ? COLLATE NOCASE` 的 OR 形式命中索引后 **2.0ms**（差 177 倍）。已固化为 `index.store.name_lookup_sql()` + `QueryPlanTest`（EXPLAIN QUERY PLAN 断言无 `SCAN nodes`）。
- **新坑（资源泄漏）**：`IndexStore.open()` 自建连接却按「外部传入」判所有权 → `close()` 从不真正关闭连接；靠 `PYTHONWARNINGS=error::ResourceWarning` 当黄金值跑一次才揪出来。**建议该口径进 MEMORY 调试铁律。**
- 证据：`G:\repos\foolproof-operation\docs\usn-store-bench-2026-09-23.json`。

### v2.1 实测订正（2026-09-23，阶段 2 执行期）

- **C: 权限结论作废**：v2 写「C: 系统盘非提权被拒 → 需提权」。阶段 2 全量探针实测 **C:/D:/E:/F:/G: 五卷非提权全部可读**（journal 有效）；首测（BSOD 前）确曾返回 `INVALID_HANDLE_VALUE` —— 即**卷可读性受系统状态/争用影响，不是固定权限位**。
  → 订正：**降级路径仍然必需（工程防御），但「系统盘必然不可读」是错的**，不得据此把 C: 排除在索引之外。证据：`G:\repos\foolproof-operation\docs\usn-indexer.md` §3。
- **风险 R1 估偏悲观一个数量级**：v2 估「首次全量建库 20~40 分钟」。阶段 2 实测**全盘 5 卷 479 万条记录仅 58.1s**（46k~161k 条/秒）。
  → 订正：首次建库 ≈ 1 分钟量级；**新瓶颈是 SQLite 落库**（479 万行需批量事务），该验收项移到阶段 3。早期 8,000 条/秒的测量条件（BSOD 前机器异常 + Everything 冷启动并发）已注明。
- **增强效果已量化**（阶段 4 的验收基线）：现有 `cli scan` 找到 **4 个** Python 环境；USN 索引全盘枚举得到 **208 个 `python.exe` / 187 个 `pyvenv.cfg` / 211 个 `site-packages`**。根因=旧遍历只查各盘顶层+一层子目录，深层 venv 一律漏（例：`G:\notpython\kard_CN\venv`）。

### v1 → v2（2026-09-23，用户质疑「这个是小游戏吗？」驱动）

- **错误事实**：v1 把本仓归为「单机 GUI 小游戏」，据 D20 拍板在 N3 写「不做整体 GUI 插件化」。
- **错误机制**：**凭外形特征（单机 GUI）代替类别判定**——与铁律 1（README 优先）同型的错误：没先读该仓 README 与既有分档就套用别仓结论。
- **纠正**：本仓 = Python 依赖库/环境管理工具（dev 组工具）→ 《其余项目插件化路线图》**B 类（项目内部插件化）**；D 类「不动」仅指「games 单文件玩具」。
- **修订项**：① N3 撤销并反转为「整体插件化，GUI 亦为插件行」（§2）；② 新增 §1.5 参照物与判据对照；③ 交付物补 `core/tasklog.py`（任务日志 JSONL + `cli tasks`）与 `core/audit.py`（启动审计 fail-loud）——**B 类模板标配，v1 漏项**；④ 新增「每个 Python 环境 = `ctx.fork(env_id)`」设计落点；⑤ D1 依据升级为仓库法（「复制优于共享、互不 import」+ README 零依赖承诺）。
- **沉淀**：一条判据纪律——**判定某仓是否插件化，先读该仓 README 与《其余项目插件化路线图》分档，禁止用「也是单机 GUI」这类外形特征套用别仓拍板**。

---

**无异议请回复「开始执行」；要调整哪里（尤其 D1/D2/D3）直接说。**
