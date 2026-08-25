# allin —— 个人全项目大仓库（G:\）

一个**单一 git 仓库**承载全部个人项目：游戏引擎、游戏、爬虫、音视频工具、电台/转播服务、AI 项目、音乐资产等。

## 命名约定（重要）

- **allin** = 本仓库（G:\ 盘整体）
- **alloy** = 统一游戏引擎（原名 allin_engine，2026-08-23 改名；兼容 shim 见 G:\games\allin_engine）
- **复制优于共享**：项目内联引擎/字体/资源副本是**有意为之**，不算冗余；缓存（.pyc/__pycache__/.venv/node_modules）不算重复。

## 顶层结构

| 目录 | 内容 |
|---|---|
| games/ | 游戏项目 + 引擎本体 alloy/（6 个项目内联引擎副本） |
| tools/ | video（Cordis 视频转播站）、private-radio-stations（Cordis monorepo 电台+视频）、audio/crawler/desktop/visual/dev/ai 六组工具 |
| crawlers/ | crawl_hub 聚合启动器 + 爬虫项目 |
| music/ | 音乐项目与资产（musickit、station、stem 库） |
| media/ ai/ web/ | 媒体、AI、网页项目 |
| docs/md/allin主工作区/ | 治理文档（规划、报告、MEMORY/SKILL 约定） |
| notpython/ | 外部参考源码（deepseek-harness 等） |
| archive/ _migration/ _backup/ | 归档/迁移区（只进不出） |

## 核心项目速览

- **alloy**（games/alloy）：统一游戏引擎——ECS + EventBus（emit/waterfall/serial）+ Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI。**J2 引擎整合完成（2026-08-25）**：media 子系统（media 域公式引擎 + 21 效果原语 + 4973 配方，自 pywallpaper 并入）+ ca 规则引擎（141 规则 8 族，自 cellular_automaton 并入）；bloodmusic 维持外部库（提取独立化）。测试 374 项（唯一失败 = 无头 Tk 基线）。
- **private-radio-stations / video / audio/private-radio-stations-2.0**：Node.js + Cordis 插件式转播站（cordis.yml 插件注册表 + 启动装配审计 + invariants + schemastery）。
- **crawl_hub**（crawlers/crawl_hub）：爬虫聚合启动器（聚合不融合、子进程隔离、配置审计 + JSONL 任务日志）。
- **musickit**（music/musickit）：phonk 混音项目（真实采样 + 授权分级治理 + 本地混音引擎）。

## 引擎整合声明（J2 · 2026-08-25）

- 仓库内引擎类**只保留 alloy 一个综合引擎** + 外部库 bloodmusic。
- pywallpaper（壁纸应用）与 cellular_automaton（CA 壁纸应用）的能力层已并入 alloy（media/ 与 media/ca/），应用侧保留内联副本（各自 engine.patch.yaml 记录），内容层（effects JSON/规则 JSON）不吞并。
- 详见 docs/md/allin主工作区/引擎整合规划_2026-08-24.md 与《引擎能力清单_2026-08-25》。

## 治理文档

规划与报告集中在 docs/md/allin主工作区/（引擎插件化三件事规划、其余项目插件化路线图、资产治理执行报告、每日日志、MEMORY 约定）。

## 本远程仓库（gitee: siwpan/allin）

体量超 gitee 限制，本仓库**只存索引三件套**，不含文件内容：

- .gitignore —— 大仓库忽略规则（yasuobao 等大体积下载缓存本地保留、不进版本库）
- 目录索引.txt —— 全仓库文件索引（路径+字节数，生成时间见头部）
- README.md —— 本说明

## 常用命令

- 引擎测试：cd G:\games && python -m alloy.test.run_all
- 引擎装配自省：python -m alloy dump-profile [--json]
- 副本同步：python -m alloy sync <项目> --dry-run|--apply
- 爬虫启动器审计：cd G:\crawlers\crawl_hub && python launcher.py --check
- 电台/视频：cd G:\tools\private-radio-stations && npm run radio / npm run video
