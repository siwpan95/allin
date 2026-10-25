# 可行性分析：拆 deepseek-harness 开源源码喂给 allin-platform

> 2026-09-24 规划 · 同日 Phase 1 已实施并推送（本文已随执行状态更新）·
> 参考对象：deepseek-ai/deepseek-harness master@2026-09-22（MIT）
> 分析对象：allin-platform（纯 JS ESM，唯一运行时依赖 js-yaml，零框架）
> 证据基线：DSH 仓库实测 307 个包的内部依赖密度 + npm 发布状态逐包探针
> 实施记录（ADR）：`decisions/2026-09-24-harness-reference-hardening.md`（P0–P2）、
> `decisions/2026-09-24-phase1-host-guard-durable-jsonl.md`（Phase 1）

---

## 零、借鉴记账（来源与边界声明）

> 本节按治理要求登记本文件对外部上游的借鉴关系（`repo_hygiene` H6「借鉴记账三要素」：
> **上游 URL + 许可证 + 不入仓声明**）。

| 项 | 内容 |
| --- | --- |
| **上游项目** | DeepSeek Harness（`deepseek-ai/deepseek-harness`） |
| **上游 URL** | <https://github.com/deepseek-ai/deepseek-harness> |
| **本机镜像/fork** | <https://gitee.com/siwpan/deepseek-harness>（本机 fork，用于同版本对照） |
| **版本基线** | master@2026-09-22（本文件的分析与实测均以该时点为准） |
| **许可证** | MIT |
| **借鉴方式** | **工程模式的纯 JS 复刻**（P0–P2 三批 + Phase 1），**不复制上游源码** |
| **不入仓声明** | **上游源码与产物均不入本仓、不随本仓分发**。本仓只保留本文这类**分析与记账文档**，以及自行实现的纯 JS 代码；任何对上游源码的引用都只以 URL + 版本号形式记录，**不进入任何公开仓**。 |

---

## 一、结论卡（TL;DR）

**可行，且有三条通路的分界线非常清晰**：

| 路线 | 形态 | 可行性 | 建议 |
|---|---|---|---|
| A 模式移植 | 复刻 DSH 工程模式为纯 JS（已在 P0–P2 走通） | ✅ 高（零依赖，已验证） | **进行中：P0–P2 + Phase 1 已完成推送** |
| B 组件拆取 | 引入 DSH 已发布的 npm 子包 / 手工移植源码 | ⚠️ 有条件（见下） | **中期评估，设触发条件** |
| C 宿主化 | allin-platform 反向接入为 DSH 插件 | ❌ 低（与"聚合不融合"冲突） | **不建议** |

**一句话**：DSH 的"车架"对 allin-platform 而言太重，但它的**零件**（子进程终止梯、原子写、溢出落盘、路由围栏）可以按需拆——其中大部分已用纯 JS 复刻完成并推送（P0–P2 三批 + Phase 1：Host 围栏 + durable JSONL，commit `124191a/0e20337/08be656/f1ad0ba/0fd742c`），剩余项均已设触发条件。

---

## 二、三条硬事实（实测证据）

### 事实 1：DSH 是 307 包的巨型 monorepo，但与 allin 相关的只有约 8 个

逐包扫描 `packages/*/src` 内部依赖密度（`@deepseek-ai/*` 依赖计数）：

| allin 相关候选包 | src 文件数 | 内部依赖 | 发布状态（npmmirror 探针） |
|---|---|---|---|
| dsh-atomic-write | 1 | 0 | ✅ 已发布 0.0.1-rc.1 |
| dsh-subprocess（契约层） | 3 | 0 | ✅ 已发布 |
| dsh-spill（有界输出+溢出落盘） | 2 | 0 | ✅ 已发布 |
| dsh-subprocess-local（实现层） | 16 | 2（lazy-require, win32-process） | ✅ 已发布，**deps 含 node-pty 原生模块** |
| dsh-win32-process | 7 | 1 | ✅ 已发布 |
| dsh-host-webserver（路由+Host 围栏） | ~11 | 2（schemastery） | ✅ 已发布 |
| dsh-storage-json（原子 JSON 存储） | ~5 | 5 | ✅ 已发布 |
| dsh-session-persistence-jsonl（日志世代发布） | 13 | 6 | 链路较深 |

其余 299 个包（client-ui-* 约 1000+ 文件、llm、session、sandbox 等）与 allin 的
"启停/装配/审计"域**正交，不在拆取范围**。

### 事实 2：已发布的子包是 ESM（`type: module`，`lib/index.js`），纯 JS 可直接 import

——但**全部挂着 `peerDependencies: @deepseek-ai/cordis ^4.0.1-rc.1`**。
即：官方发布的拆取通道 = **必须引入 DSH 自家的 Cordis fork 运行时**。

⚠️ 注意区分：DSH 用的是 `@deepseek-ai/cordis`（自家 fork，4.0.1-rc.1），
不是 dict-scene-engine 在用的 `cordis`（cordiverse 官方，4.0.0-rc.9）。
两者 API 同源，但是**不同的包、不同的版本线**，不能混装复用现有经验直接上。

### 事实 3：DSH 处于 developer preview，官方明示「THERE WILL BE COMPATIBILITY-BREAKING CHANGES」

所有已发布包都是 0.0.1-rc.1 / 0.1.7-alpha.2 线。现在深度引入 = 绑定一个
breaking-change 常态化的移动目标。

---

## 三、逐项可行性：allin-platform 到底能"吃"到什么

### 已吃到的（P0–P2 + Phase 1，模式移植路线 A 的实证）✅

| DSH 模式 | allin 落地 | 状态 |
|---|---|---|
| Windows durable publish | running.json/workshop.json 原子写（temp+rename+.bak） | ✅ 已推送（P0，后于 Phase 1 升级 fsync） |
| 终止梯（TERM→grace→KILL） | stopEntry 异步化（优雅 await→settle→taskkill） | ✅ 已推送（P1） |
| 数量 informational 门禁 | 测试数量断言跟随 estate | ✅ 已推送（P0） |
| 日志世代轮转 | tasks.log / divergence-events 5MB 归档 .1 | ✅ 已推送（P1，Phase 1 加归档前 fsync） |
| fail-loud / 不静默吞引用 | gitee checkError 显式上告警 | ✅ 已推送（P1） |
| 文档税表 + 冻结 ADR | AGENTS.md + docs/architecture.md + decisions/ | ✅ 已推送（P2） |
| **Host 头围栏（api-request-trust）** | **回环 Host 白名单，全路由前置，GET 读取面同保护** | ✅ 已推送（Phase 1，commit `f1ad0ba`） |
| **durable JSONL（fsync→rename）** | **writeDurable + 归档前 fsync（目录 fsync 尽力语义已记录）** | ✅ 已推送（Phase 1，commit `f1ad0ba`） |

### 还能吃的（按价值/成本排序；①② 已在 Phase 1 落地）

**① Host 头围栏（防 DNS rebinding）——Route A，✅ 已实施（Phase 1）**
- DSH 证据：`packages/client/connection/src/api-request-trust.ts:1-13` 威胁模型 + Host 校验，非法配置加载即抛。
- 落地形态：仅接受字面量回环 Host（`127.0.0.1 / localhost / [::1]` 任意端口），其余 403；刻意不做可配置白名单（单机形态少一个误配面，差异已记 ADR）。
- 测试：4 例（含 raw socket HTTP/1.0 缺 Host——Node http.request 自动补 Host，必须 raw socket 覆盖）。

**② JSONL 世代发布（crash-safe 轮转升级）——Route A，✅ 已实施（Phase 1）**
- DSH 证据：ADR `2026-07-05-windows-jsonl-durable-publish.md`（POSIX fsync+link；Windows MoveFileExW WRITE_THROUGH）+「模型可见 ⟺ 可从日志重建」不变量。
- 落地形态：状态文件 open→write→fsync→close→rename；归档 rename 前 fsync；Node 无 Windows 目录 fsync 等价，「尽力语义」差异已记录。

**③ 输出捕获 + spill（有界内存 + 溢出落盘）——Route A/B，按需，先备案**
- DSH 证据：`dsh-spill`（2 文件，零内部依赖）：内存留尾 + 全量写 spill 文件。
- allin 现状：launch 用 `stdio: 'ignore'`，**看不到项目 stdout**，排障只能靠各项目自己的日志。
- 若要"平台侧看项目输出"（库页加日志查看），这套契约直接照抄。触发条件：全哥需要日志面板时。

**④ 子进程契约强化（进程组等待 / 防孤儿 15ms 轮询）——Route A，可选**
- DSH 证据：`subprocess-local/src/spawn.ts:83-90`（存活轮询防父进程假静默成孤儿）、`SubprocessHandle.waitForExit` 等待整个进程组。
- allin 现状：P1 已有终止梯，但树杀后不确认进程组全灭（Windows taskkill /T 基本覆盖，POSIX 侧只有 SIGTERM 一发）。
- 价值：POSIX 部署时才有实际意义；纯 Windows 使用可缓。

**⑤ schemastery 式 Config schema——Route B1 专属，暂缓**
- 手写 validateEntry 已 fail-loud 且零依赖；引入 schemastery 换来的主要是类型生成与默认值声明。allin 的 yaml 清单是数据不是代码，收益低。

### 吃不到 / 不该吃的

- **Cordis Service/inject 四件套运行时**：需要 `@deepseek-ai/cordis` peer。allin 的 core 是函数式模块，组合点只有 harness registry.mjs 一处，运行时收益不抵依赖成本。
- **node-pty（dsh-subprocess-local 的 deps）**：原生模块，Windows 编译链是坑；allin 的 shell:true spawn 模式用不上 pty。
- **Route C 宿主化**：allin 做成 DSH 插件 = 平台自身绑死 preview 运行时 + 违背「平台零业务代码/独立更新」的立项纪律（helminth/media_engine 教训：融合即死）。

---

## 四、成本/风险评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| DSH preview 期 breaking changes | 高（若走 Route B） | Route A 零暴露；Route B 锁定精确版本 + vendor 化 |
| peer 依赖拖入 @deepseek-ai/cordis fork | 中 | Route A 不触碰；与现有 cordiverse cordis 4.0.0-rc.9 经验不通用，需单独评估 |
| node-pty Windows 原生编译 | 中 | 不引 subprocess-local，只抄模式 |
| 许可/合规 | 低 | MIT + **治理准则·借鉴必记账**（出处：`G:\allin\docs\MEMORY.md` §「治理准则：创新三原则」第 1 条；ADR 已记录来源与范围，持续维护） |
| 模式移植走样（形似神不似） | 中 | 每个 DSH 模式落地必须带 ADR 记录「原文位置→落地差异」，已建立该流程 |

**工作量估算（Route A 剩余三项）**：① Host 围栏 ~0.5 天；② 世代发布 ~0.5 天；③ spill 备案 ~0（只写 ADR 不实现）。合计约 1 天，全部带测试。

**Route B1（npm 引包）触发条件（建议写死，防止手痒提前上）**：
1. DSH 发布 1.0 稳定线（脱离 preview）；**且**
2. allin 出现真实需求：进程组级管理 / 平台侧输出捕获 / 多机 registry——手写成本明显超过引依赖成本；**且**
3. 全哥拍板接受 `@deepseek-ai/cordis` fork 进入依赖树（与 dict-scene-engine 的 cordiverse 线并存）。

---

## 五、推进状态（2026-09-24 当日走完全程）

- **P0–P2（已推送）**：`124191a`（95vs105 修复 + 路径解绑 + 原子写）、`0e20337`（stopEntry 异步化 + gitee 错误区分 + 日志轮转 + workshop 自愈）、`08be656`（.iss 对齐 + AGENTS.md 文档工程）。验证：npm test 36/36、check/harness exit 0。
- **命名订正（已随远端同步）**：`5f7cca3` alloy → allin-engine（PyPI 权威口径：分发名 allin-engine、导入名 allin_engine；`PLATFORM_ALLIN_ENGINE_CWD`）。
- **Phase 1（✅ 已实施并推送）**：Host 围栏 + durable JSONL（commit `f1ad0ba`），README 安全边界声明 + architecture 不变量同步（commit `0fd742c`）。验证：npm test 39/39、harness exit 0、冒烟 normal 200 / evil-host 403 / localhost 200。
- **Phase 2（备案，不实现）**：spill 输出捕获、进程组强化已写入 ADR `decisions/2026-09-24-phase1-host-guard-durable-jsonl.md`，触发条件：① spill——需要「库页日志面板」时；② 进程组——POSIX 部署或孤儿进程实证。
- **Phase 3（Route B1，冻结待触发）**：满足三条件（DSH 1.0 稳定 / 真实需求 / 接受 @deepseek-ai/cordis fork 入依赖树）后，先引 `dsh-atomic-write`（1 文件零风险）试点，再评估 `dsh-host-webserver`。
