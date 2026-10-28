# allin 系统架构与设计文档

> 本文档是 `allin` 治理仓的**架构与设计说明**，定位「系统怎么搭、数据怎么流」。
> 与 `docs/` 文档枢纽不同：本文档放在仓库根 `architecture/`（**刻意置于 `docs/` 之外**），
> 以免触发 `docs_index` 门禁的 D1/D8 登记约束（新增文档若进 `docs/` 必须在 `docs/INDEX.md` 登记，
> 而架构图是工程视图、不属于四分类文档体系）。
> 治理约束/流程的**唯一事实源**仍在 `docs/规范/`（SPEC-001/002/003/005/006/203）。

## 1. 总览

`allin` 是 124 个 Gitee 仓的 **「制度 + 文档枢纽 + 执行器」三位一体** 治理仓：

- **制度**在 `docs/规范/`（铁律、协作流程、治理准则、文档契约、本机边界、platform 契约）。
- **文档枢纽**在 `docs/`（`INDEX.md` 总目录 + 规范/事实源/记录/历史 四分类）。
- **执行器**有两条执行面（互不耦合）：Python/Cordis 内核 CLI（`kernel/` + `allin_cli.py`）与
  Node 集成平台（`platform/` 门户）；外加 `tools/gate/` 治理门禁作「监工」。
- **治理大脑（Agent）** 以**双形态**落地：WorkBuddy 侧 skill 与 DSH 侧 preset 治理段，同源同步。

```text
            ┌─────────────────────────────────────────────────────┐
  治理事实源 │  docs/ 规范(SPEC-*) · 事实源(本机事实) · 记录(审计/决策) │◄── 开卷必读
            │         INDEX.md 总目录                              │
            └─────────────────────────────────────────────────────┘
                              ▲ 双形态同步判据 (verify-mount.ps1 + check:governance)
            ┌─────────────────────────────────────────────────────┐
  治理大脑   │  .workbuddy/skills/allin-governance-agent  ⇄          │
   (Agent)  │  preset/allin/allin.patch.yml  GOVERNANCE:BEGIN/END   │
            │  + 15 个专项 skill 路由表                             │
            └─────────────────────────────────────────────────────┘
                 │ 调度/放行                       │ 治理段文本注入(非运行时耦合)
        ┌───────────────────┐         ┌──────────────────────────────────┐
  执行面A│  allin CLI        │         │  执行面B: platform 集成平台        │
        │  allin_cli.py     │         │  portal :9000 (node:http 零依赖)   │
        │  kernel/ Cordis   │         │  Host围栏+loopbackOnly 安全边界     │
        │  4 pillars:       │         │  @allin/core (registry/launch/     │
        │  docs/platform/   │         │  workshop/probe/gitee)             │
        │  preset/tools     │         │  data/ running.json tasks.log      │
        └───────────────────┘         └──────────────────────────────────┘
                 │ subprocess                      │ 读写共享状态
            ┌─────────────────────────────────────────────────────┐
  治理门禁   │  tools/gate: g00–g19(19道,缺g02) · docs_index(D1–D8) │
   (监工)    │  repocheck(30规则) · repo_hygiene(H1–H8)            │
            └─────────────────────────────────────────────────────┘
                 │ 校验对象 / 推送目标
            ┌─────────────────────────────────────────────────────┐
  外部       │  repos/<仓名> (124 成员仓, 独立进程) + Gitee API(135) │
            │  divergence-events.jsonl 分歧事件源                   │
            └─────────────────────────────────────────────────────┘
```

（组件级架构图见 [`system-architecture.svg`](system-architecture.svg)；数据流图见 [`data-flow.svg`](data-flow.svg)。）
（**现行架构决策**见 [`adr/README.md`](adr/README.md)：换栈 / 增删门禁 / 放宽约束 / 长期例外都在此留痕；
与 `docs/记录/决策/` 的分工是「现行 vs 冻结」。）

## 2. 核心模块（按层）

### 2.0 治理事实源 —— `docs/`
- `docs/规范/`（`SPEC-NNN` 编号 + 效力声明头）：铁律（SPEC-001）、协作流程（SPEC-002）、
  治理准则（SPEC-003）、文档索引契约（SPEC-005）、本机边界（SPEC-006）、
  platform 契约（SPEC-203）、治理模式建设指南（SPEC-105）。
- `docs/事实源/`：机器类现值（盘位 / 运行时 / 工具链），如 `本机事实.md`。
- `docs/记录/`：审计 / 决策 / 交接 / 专题（只增不改）。
- `docs/INDEX.md`：总目录，全部文档一张表；是文档索引契约门禁的登记面。

### 2.1 治理大脑（Agent）—— 双形态落地
- **WorkBuddy 侧**：`.workbuddy/skills/allin-governance-agent/SKILL.md`（本仓项目级 skill）。
- **DSH 侧**：`preset/allin/allin.patch.yml` 的 `GOVERNANCE:BEGIN/END` 段（`config.id: allin`，
  插入 `@deepseek-ai/dsh-agent-preset`）。
- **同一份治理事实的双形态**：任一侧修改须同步另一侧。漂移判据 =
  `preset/allin/verify-mount.ps1` 漂移层 + 本仓 `npm run check:governance`。
- **路由表**：本仓已有 15 个专项 skill（`dsh-deploy-repair` / `c-drive-scan-clean` /
  `cordis-v4-integration` / `electron-portable-gitee-release` / `gitee-blocked-file-fetch` /
  `gitee-push-from-extracted-dir` / `github-release-source-archive-download` /
  `lab-tournament-daily-automation` / `multilang-board-engine-lab` / `pluginplayer-win-build` /
  `pyglet-app-package-dist` / `pypi-publish-prep` / `repo-sync-remote-to-local` /
  `venv-ca-security-audit` / `windows-node-env-diagnose`），匹配到即转交，不重造。
- Agent 自身负责：治理放行判断、四事实源阅读、门禁总调度、文档新增流程、推送/发版纪律把守。

### 2.2 执行面 A —— allin Cordis CLI（`kernel/` + `allin_cli.py`）
- **前门**：`allin_cli.py`（`argparse` 子命令 `tools` / `docs` / `platform` / `preset`），
  先强制 UTF-8 输出（与门禁同口径），再 boot Cordis 内核后按域分发。
- **引导**：`kernel/tree.py` 用 Cordis 原生 `Loader` 按 `kernel/configs/cordis.allin.yml`
  挂载配置树；`mount_tree()` 一行式引导 + `await_ready()` 就绪等待。
- **封闭白名单**：`kernel/registry.py` 的 `SERVICES`（`docs`/`platform`/`preset`/`tools`
  → `kernel/services/*.py`）。Cordis 的 `Loader` 会把每条 entry 的 `name` 直接 `import`，
  故 `tree.py` 用 `ALLOWED_NAME_PREFIXES` / `ALLOWED_NAME_EXACT` 钉死命名空间
  （`配置即代码` 评审绕过风险）。
- **四大服务**（`kernel/services/`）用子进程封装底层工具：
  - `DocsService`：`build_portfolio.py` / `make_doc_aliases.ps1` / `docs_index.py`。
  - `PlatformService`：`npm run check:repos` 等 Node 工具。
  - `PresetService`：preset 组合包只读盘点（`list`/`show`/`apply` 默认 dry-run）。
  - `ToolService`：`gitee_release.py` / 凭据脚本 / `venv_ca_audit.py` / 已吸收技能清单；
    令牌取自 `GITEE_TOKEN` 或 `git credential fill`，**绝不硬编码**。

### 2.3 执行面 B —— platform 集成平台（`platform/`，Node + Cordis，聚合不融合）
- **门户**：`platform/apps/portal/src/index.js` —— 零依赖 `node:http`，绑 `127.0.0.1:9000`
  （`PORT` 环境变量；`PORT=0` 按需端口 + 自动开浏览器）。
- **安全边界（防 DNS rebinding）**：
  - `hostAllowed()`：`LOOPBACK_HOST = /^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$/i`，
    非回环 Host 一律 403（GET 读取面同样受保护，不止写操作）。
  - `loopbackOnly()`：写操作额外校验远端地址是 `127.0.0.1` / `::1` / `::ffff:127.0.0.1`。
  - 静态文件用「路径分隔符边界」前缀校验（防 `public-evil` 同级前缀绕过）。
- **内核 `@allin/core`**（`platform/packages/core`）：
  - `registry.js`：`loadRegistry()` / `validateEntry()`（fail-loud，必填字段 + id 形状 +
    launch.command + 端口查表 + 归属核对）/ `resolvePath()`（**去盘符**，唯一路径解析入口）。
  - `launch.js`：`startEntry()`（detached 子进程）/ `stopEntry()`（优雅停止优先，回退树杀）/
    `isRunning()` / `runningInfo()` / `shutdownAll()` / `logTask()`（日志即事实源，超 5MB 轮转）。
  - `workshop.js`：`listWorkshop()` / `subscribe()` / `unsubscribe()`（先停再删，杜绝孤儿进程）/
    `update()` / `rollback()` / `auditWorkshop()` / `checkUpdate()`（60s 缓存，避免打满 Gitee API）。
  - `probe.js`：`probeEntry()` / `probePort()`（宽限期探测）。
  - `gitee.js`：`fetchBranchCommit()`。
- **CLI**：`platform/apps/cli/src/index.js`（`list` / `search` / `status` / `start` / `stop`）。
- **聚合不融合纪律**：平台零业务代码；项目是独立进程（子进程隔离），绝不 `import` 项目代码；
  新端口先查 `registry/ports.yaml`（外部端口分配表，唯一事实源）。
- **API 契约**：见同仓 `platform/apps/portal/openapi.yaml`（OpenAPI 3.0.3，13 条路径，
  含请求/响应 schema 与示例；由真实源码生成，非推测）。

### 2.4 治理门禁（监工）—— `tools/gate/`
- **19 道治理门禁** `g00-meta` … `g19-docs-refs`：`tools/gate/governance/run.ts` 聚合，
  `npm run check:governance` 驱动，全绿 `exit 0`；`check:governance:selfcheck` 自证。
- **文档索引契约** `docs_index.py`：D1–D8（INDEX 份数 / 登记 / 头部 / 别名…）。
- **仓库体检** `repocheck/main.py`：30 规则，0–10 健康分，text/json/csv/html 导出。
- **仓库卫生** `repo_hygiene.py`：H1–H8 基线棘轮（`--all` 跑全量）。

### 2.5 治理模式载体 —— `preset/allin/`
- `allin.patch.yml`：DSH 声明式可重装副本（`config.id: allin`），含 `GOVERNANCE` 治理段。
- `agent.cordis.yml`、`locate-root.ps1`（零配置跨机定位仓根）、`make-bundle.ps1`
  （封装 npm bundle，`-Check` 拦落后）、`verify-mount.ps1`（三层校验 + 漂移层）、
  `verify-upstream-merge.ps1`（上游 PR 合并门禁）、`bundle/`、`安装说明.md`。

## 3. 数据流

### 3.1 平台启停与分歧事件链路（`platform`）
```text
registry/projects/*.yaml
   │  loadRegistry()        → 读全部 *.yaml，逐条 validateEntry()（fail-loud，_valid 标记）
   ▼
probeEntry(entry)          → 端口/进程探测（宽限期 STARTING_GRACE_MS）
   │
   ▼  [启动]
startEntry(entry)          → detached 子进程；原子写 running.json + tasks.log（日志即事实源）
   │
   ▼  [运行态]
running.json (DATA_DIR)    → 各项目运行态；portal 与 CLI 经回环 HTTP + 共享 running.json 同步
   │
   ▼  [分歧事件]
各项目 data/divergence-events.jsonl   → readAlerts() 聚合（按 ts 倒序，封顶 100 条）
   │
   ▼
GET /api/alerts            → 前端工坊页订阅分歧事件（订阅方）
```
> 门户与 CLI **不依赖数据库**：状态靠 `running.json`（原子写：temp + fsync + rename + .bak 回退）
> 与 `tasks.log`（超 5MB 轮转）在文件系统上共享。引擎视图（`/api/engine`）经
> `PLATFORM_ALLIN_ENGINE_CWD` 指向外部 an-engine 项目，调用 `allin_engine dump-profile --json`，
> 缓存 30s（`execFile` 异步，不阻塞事件循环）。

### 3.2 治理放行链路（Agent）
```text
开卷读四事实源 (INDEX → SPEC-001 → SPEC-002 → 本机事实)
   │
   ▼  按铁律/SPEC 放行判断（先问→计划→review→执行→复盘；高风险动作逐项确认）
路由到专项 skill 或亲自执行门禁命令 (scripts/run_all_gates.sh / check:governance / docs_index)
   │
   ▼  改动后过两道门禁：check:governance + docs_index（全绿才算过）
推送 / 发版 → tools/gitee_release.py（幂等可重入；令牌绝不回显；一次性 URL 推送不加 -u）
```

### 3.3 双形态同步链路
```text
.workbuddy/skills/allin-governance-agent/SKILL.md   ⇄   preset/allin/allin.patch.yml  GOVERNANCE 段
        │                                                │
        └── 文本注入式（治理论述被注入 Agent 上下文），非运行时耦合 ──┘
            漂移判据：verify-mount.ps1 漂移层 + npm run check:governance
```

## 4. 安全边界汇总

| 边界 | 落点 | 防护 |
| --- | --- | --- |
| 机器路径 | `g01-paths` 门禁 / `SPEC-006` | 禁止写死盘符路径（铁律 5）；`resolvePath()` 去盘符 |
| 门户暴露面 | `portal/index.js` | Host 围栏 + loopbackOnly 防 DNS rebinding；静态文件边界校验 |
| 配置即代码 | `kernel/tree.py` `ALLOWED_NAME_*` | entry name 白名单，等同代码边界 |
| 端口纪律 | `registry/ports.yaml` | 未登记端口拒绝登记；归属核对 |
| 凭据红线 | 公开仓 + `.gitignore` | 令牌 env / `git credential fill`，绝不进仓、绝不回显 |
| 公开仓铁律 | `SPEC-001` 铁律 0 | 默认公开+MIT；真实凭据一律不得落入 |

## 5. 依赖与可移植性

- **kernel**：依赖 vendored Cordis（`vendor/cordis`，经 `.pth` 暴露；`CORDIS_SRC` 可覆盖）。
- **platform**：唯一三方依赖 `js-yaml`（`npm install --registry=npmmirror`）。
- **tools**：Python 标准库 / Node 自带（零三方，拷走即用）。
- **路径/端口全部 env 可覆盖**（跨机/CI 友好）：
  `ALLIN_CONFIGS` · `ALLIN_ROOT` · `PLATFORM_ROOT` · `PLATFORM_PORTS` ·
  `PLATFORM_REPOS_ROOT` · `PLATFORM_REGISTRY` · `PLATFORM_PATH_CHECK` ·
  `PLATFORM_ALLIN_ENGINE_CWD` · `PLATFORM_PYTHON` · `PLATFORM_PORTAL_AUTO_OPEN`。
- **CI/异机模式**：`PLATFORM_PATH_CHECK=absolute` 仅校验路径形状（登记 path 指向外部目录，
  天然不存在，跳过存在性检查），`check:governance` 同理只校验形状，不 fail-loud 误杀。

---

*本设计文档与 `system-architecture.svg` / `data-flow.svg` 同步编写（2026-10-27），
数据源为本仓真实代码（`allin_cli.py` / `kernel/*` / `platform/apps/portal/src/index.js` /
`platform/packages/core/src/*` / `preset/allin/allin.patch.yml` / `.workbuddy/skills/allin-governance-agent`）。*
