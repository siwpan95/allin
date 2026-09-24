# allin —— 个人全项目大仓库（G:\ 盘整体）

一个**单一索引仓库**承载 G:\ 盘全部个人项目的目录索引与治理说明：游戏引擎、游戏、爬虫、音视频工具、电台/转播服务、AI 项目、音乐资产等。

> **📖 文档枢纽在最前面**：[`docs/`](docs/README.md) —— 整个 `G:\` 工作区的文档入口（**开发过程透明可读、可复跑、可接手续做**）。
> 接手请按顺序读：[`docs/MEMORY.md`](docs/MEMORY.md)（铁律与约定）→ [`docs/协作工作流程约定_2026-08-28.md`](docs/协作工作流程约定_2026-08-28.md)（流程与放行口径）→
> [`docs/会话交接_2026-08-27.md`](docs/会话交接_2026-08-27.md)（事实流水与坑）。
> 想复刻这套治理模式 → [`docs/allin治理模式_建设指南.md`](docs/allin治理模式_建设指南.md)。

## 命名约定（重要）

- **allin** = 本仓（索引四件套：README / .gitignore / LICENSE / 目录索引.txt + 治理报告 `深度审核报告_20260827.md` + 审核证据 `audit-fragments/`），单独挂载于 `G:\allin`，不再摊在 G:\ 根。
- **一仓一目录**（2026-08-27 重建仓 + 目录重构）：每个 gitee 仓库对应 `G:\repos\<仓名>` 一个目录，仓名 = 目录名。
- **alloy** = 统一游戏引擎（原 allin_engine，2026-08-23 改名；仓库 siwpan/an-engine，目录 G:\repos\an-engine）。
- **复制优于共享**：项目内联引擎/字体/资源副本是**有意为之**，不算冗余；缓存（__pycache__/.venv/node_modules/build/dist）不算重复。

## 顶层结构

| 目录 | 内容 |
|---|---|
| allin/ | 本仓四件套（索引 + 治理说明 + 深度审核报告） |
| repos/ | 与 gitee siwpan 一一对应的项目仓（一仓一目录，2026-09-24 现为 **107 个**；2026-08-27 深度审核后已全部挂接 git 远端） |
| platform/ | allin-platform 集成平台（库/工坊/引擎视图 + registry） |
| docs/ | **文档枢纽**（2026-09-24 自 `G:\docs` 汇总迁入）：活文档在根（MEMORY / 会话交接 / 协作约定 / ports.yaml / 文档地图 README / 治理模式建设指南），历史文档树在 `docs/md/` |
| local/ | 未发布/本地独有项目与历史归档（原 games/tools/ai/crawlers/media 中未上仓者） |
| assets/ | 音乐资产与字体工具（stems/转码素材/采样库/字体下载工具，不入版本库） |
| archive/ | 归档区（只进不出；`docs-nondoc-20260924/` 为文档枢纽纯文档化时迁出的非文档内容，含 MANIFEST，永不入库） |
| notpython/ | 外部参考源码（deepseek-harness 等；来源与许可表已汇总到 `docs/来源与许可表.md`） |
| tools/ | 工作区门禁与工具（`G:\tools\gate\`：死根路径门禁 + AST 未定义名检查，见其 README） |
| Temp/ tmp/ job/ logs/ _job/ | 临时与任务区 |

## 核心项目速览

- **alloy**（repos/an-engine）：统一游戏引擎——ECS + EventBus（emit/waterfall/serial）+ Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI。**J2 引擎整合完成（2026-08-25）**：media 子系统（media 域公式引擎 + 21 效果原语 + 4973 配方，自 pywallpaper 并入）、ca 规则引擎（141 规则 8 族，自 cellular_automaton 并入）；bloodmusic 维持外部仓。测试 374 项。
- **private-radio-stations**（repos/private-radio-stations）：Node.js + Cordis 插件式转播站（radio/video/portal 三簇；cordis.yml 插件注册表 + 启动装配审计 + invariants + schemastery）。
- **crawl_hub**（repos/crawl-hub）：爬虫聚合启动器（聚合不融合、子进程隔离、配置审计 + JSONL 任务日志）。
- **musickit**（repos/musickit）：phonk 混音项目（真实采样 + 授权分级治理 + 本地混音引擎 + 框架安装包）。
- **allin-platform**（platform/）：Steam 式全项目集成平台（库 + 创意工坊 + 引擎视图，聚合不融合；registry 项目清单 + ports 查表纪律）。

## 发布面（gitee）

- 全部仓库公开 + MIT（铁律 0）；一项目一仓，主分支 master，发行版 tag `<项目>-v<版本>`。
  **唯一例外**：`pluginplayer` 随包分发 GPL v3 的 FFmpeg `full_build-shared` 与 MinGW 运行时，许可必须随上游走 **GPL-3.0-or-later**（改 MIT 才是违规；证据见该仓 README 与 `THIRD_PARTY_NOTICES.md`）。
- 2026-08-27 重建仓：集合仓退役改名 `*-legacy`（media/tools/game/ai-collection、music），45 个分支项目拆为独立仓，版本分支转 tag。详见 docs/md/allin主工作区/重建仓执行报告_2026-08-27.md。

## 治理准则（2026-08-27 深度审核固化）

> **创新 = 借鉴 + 调整 + 同步 + 记账；「推倒重来」只允许发生在结构层，资产与历史永远保全。**

1. **借鉴必记账**：复制/借鉴任何外部代码、配置、概念前，记录「来源 + 许可证 + 借用范围」（上游 dsh/Cordis 或自己的样板都算）。
2. **调整必同步**：任何灵活更新之后三步回写——推远端（ls-remote 验证）→ 更新引用（registry/ports/目录索引）→ 跑黄金值（check / harness exit 0）。
3. **结构可重建、资产与历史永不推倒**：合并优于双仓并存；补优于删；还原优于分支（上游修复后弃用自维护补丁）。

- **敏感信息红线**：API Key / 令牌 / cookie 真实值绝不进代码、配置与仓库（一律 example 化 + .gitignore）。
- 全量审核（对照 deepseek-harness-master 与 gitee 全量仓）与逐项处置清单 R0–R11：见本仓 `深度审核报告_20260827.md`；本地推进详情：`docs/MEMORY.md`。

## 治理文档

**文档枢纽 = `docs/`**（2026-09-24 建设完成并公开）：入口 [`docs/README.md`](docs/README.md)，含活跃事实源（MEMORY / 会话交接 / 协作约定 / ports.yaml）、
审计与核对报告、历史文档树 `docs/md/`，以及《allin 治理模式 · 建设指南》。
深度审核报告随本仓发布：`深度审核报告_20260827.md`（2026-08-27，对照 dsh 上游与 gitee 全量，含治理准则与 R0–R11 处置顺序）。