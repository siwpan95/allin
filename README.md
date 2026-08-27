# allin —— 个人全项目大仓库（G:\ 盘整体）

一个**单一索引仓库**承载 G:\ 盘全部个人项目的目录索引与治理说明：游戏引擎、游戏、爬虫、音视频工具、电台/转播服务、AI 项目、音乐资产等。

## 命名约定（重要）

- **allin** = 本仓（索引四件套：README / .gitignore / LICENSE / 目录索引.txt），单独挂载于 `G:\allin`，不再摊在 G:\ 根。
- **一仓一目录**（2026-08-27 重建仓 + 目录重构）：每个 gitee 仓库对应 `G:\repos\<仓名>` 一个目录，仓名 = 目录名。
- **alloy** = 统一游戏引擎（原 allin_engine，2026-08-23 改名；仓库 siwpan/an-engine，目录 G:\repos\an-engine）。
- **复制优于共享**：项目内联引擎/字体/资源副本是**有意为之**，不算冗余；缓存（__pycache__/.venv/node_modules/build/dist）不算重复。

## 顶层结构

| 目录 | 内容 |
|---|---|
| allin/ | 本仓四件套（索引 + 治理说明） |
| repos/ | 与 gitee siwpan 一一对应的 86+ 项目（一仓一目录，master） |
| platform/ | allin-platform 集成平台（库/工坊/引擎视图 + registry） |
| docs/ | 治理文档（规划、报告、MEMORY/SKILL 约定、端口分配表） |
| local/ | 未发布/本地独有项目与历史归档（原 games/tools/ai/crawlers/media 中未上仓者） |
| assets/ | 音乐资产（stems/转码素材/采样库，不入版本库） |
| archive/ | 归档区（只进不出） |
| notpython/ | 外部参考源码（deepseek-harness 等） |
| ai/ | 暂留：video_generator（本地服务运行中，未迁移） |
| Temp/ tmp/ job/ logs/ _job/ | 临时与任务区 |

## 核心项目速览

- **alloy**（repos/an-engine）：统一游戏引擎——ECS + EventBus（emit/waterfall/serial）+ Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI。**J2 引擎整合完成（2026-08-25）**：media 子系统（media 域公式引擎 + 21 效果原语 + 4973 配方，自 pywallpaper 并入）、ca 规则引擎（141 规则 8 族，自 cellular_automaton 并入）；bloodmusic 维持外部仓。测试 374 项。
- **private-radio-stations**（repos/private-radio-stations）：Node.js + Cordis 插件式转播站（radio/video/portal 三簇；cordis.yml 插件注册表 + 启动装配审计 + invariants + schemastery）。
- **crawl_hub**（repos/crawl-hub）：爬虫聚合启动器（聚合不融合、子进程隔离、配置审计 + JSONL 任务日志）。
- **musickit**（repos/musickit）：phonk 混音项目（真实采样 + 授权分级治理 + 本地混音引擎 + 框架安装包）。
- **allin-platform**（platform/）：Steam 式全项目集成平台（库 + 创意工坊 + 引擎视图，聚合不融合；registry 项目清单 + ports 查表纪律）。

## 发布面（gitee）

- 全部仓库公开 + MIT（铁律 0）；一项目一仓，主分支 master，发行版 tag `<项目>-v<版本>`。
- 2026-08-27 重建仓：集合仓退役改名 `*-legacy`（media/tools/game/ai-collection、music），45 个分支项目拆为独立仓，版本分支转 tag。详见 docs/md/allin主工作区/重建仓执行报告_2026-08-27.md。

## 治理文档

规划与报告集中在 docs/md/allin主工作区/（引擎插件化规划、重建仓报告、资产治理报告、每日日志、MEMORY 约定）。