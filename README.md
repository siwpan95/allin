# allin —— 个人全项目治理索引仓库（`/projects/allin`）

一个**单一索引仓库**承载工作区治理说明、文档枢纽入口与 DeepSeek Harness 治理模式的**可重装载体**：
游戏引擎、游戏、爬虫、音视频工具、电台/转播服务、AI 项目、音乐资产等全部个人项目的事实源与约定都从这里索引出去。

> **⚠️ 盘位已变更（2026-09-24）**：原整盘工作区（盘符已撤销）的代码统一归置到 **`/projects/`**（12 个成员项目）。
> 本仓原先挂在 `/allin`（旧盘根），2026-09-24 起落在 `/projects/`，2026-09-27 由 `allin_push` 改名为 **`allin`**（目录名与远端仓名一致）；其文档里仍会出现一些历史路径，以"当时的事实"保留，新项目一律走 `/projects/`。
> 接手完整背景请读本仓 [`docs/README.md`](docs/README.md) 与 [`docs/新机配置汇总_2026-09-24.md`](docs/记录/快照/新机配置汇总_2026-09-24.md)。

> **📖 文档枢纽在最前面**：[`docs/`](docs/README.md) —— 整个工作区的文档入口（**开发过程透明可读、可复跑、可接手续做**）。
> 接手请按顺序读：[`docs/MEMORY.md`](docs/MEMORY.md)（铁律与约定）→ [`docs/协作工作流程约定_2026-08-28.md`](docs/规范/SPEC-002-协作工作流程.md)（流程与放行口径）→
> [`docs/记录/交接/2026-08.md`](docs/记录/交接/2026-08.md)（事实流水与坑）。
> 想复刻这套治理模式 → [`docs/allin治理模式_建设指南.md`](docs/规范/SPEC-105-治理模式建设指南.md)。

## 命名约定（重要）

- **allin** = 本仓（索引 + 治理说明 + [文档枢纽 `docs/`](docs/README.md) + 审核证据 `audit-fragments/`），本机检出在 `/allin`（原 `/projects/allin`；2026-09-27 前名为 `allin_push`）。
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
| `audit-fragments/` | 深度审核的**过程证据**（报告本体已归 [`docs/记录/审计/`](docs/记录/审计/)） |
| `siwpan旧机配置汇总.html` | 旧机（已退役）机器事实源，作换机基线 |

> 历史 README 还列过 `repos/ platform/ local/ assets/ archive/ notpython/` 等目录 —— 那是 `/` 整盘时期的形态；
> 盘位归并到 `/projects/` 后，各项目已各自成为 `/projects/<仓名>` 独立子仓，不再以"子目录"形式寄存在本仓内。

## 核心项目速览（现盘 `/projects/` 成员）

- **alloy**（an-engine）：统一游戏引擎——ECS + EventBus + Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI。
- **private-radio-stations**：Node.js + Cordis 插件式转播站（radio/video/portal 三簇）。
- **musickit**（repos/musickit）：phonk 混音项目（真实采样 + 授权分级治理）。
- **deepseek-harness-master**：DeepSeek Harness（`@deepseek-ai/dsh-root` 0.1.7-rc.1）本机 fork，已推独立 gitee 仓 `siwpan/deepseek-harness`（见下）。
- 其余成员：`webcopier` `cordis-table-app` `foolproof-operation` `lab` `moba_battle_platform` `roleplayer` `music-master` `ncmturnmp3` `D20`。
- 以上 12 个为本机已克隆的**成员子集**；全量 121 个 Gitee 仓库见 [`PORTFOLIO.md`](PORTFOLIO.md)。

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

## 发布面（gitee）

- 全部仓库公开 + MIT（铁律 0）；一项目一仓，主分支 master，发行版 tag `<项目>-v<版本>`。
  **唯一例外**：`pluginplayer` 随包分发 GPL v3 的 FFmpeg `full_build-shared` 与 MinGW 运行时，许可必须随上游走 **GPL-3.0-or-later**（改 MIT 才是违规）。
- 2026-08-27 重建仓：集合仓退役改名 `*-legacy`，45 个分支项目拆为独立仓，版本分支转 tag。详见 `docs/md/allin主工作区/重建仓执行报告_2026-08-27.md`。

## Gitee 项目组合全量索引（121 仓）

全量 **121 个 Gitee 仓库**（公开 121 · 私有 0，2026-09-26 经 Gitee API 核实）的索引见 [`PORTFOLIO.md`](PORTFOLIO.md)：
按仓库名排序，含语言 / Star / 简介 / 可见性。该文件由脚本从 Gitee API 自动生成，是**索引而非源码镜像**。

**治理原则：源码按需懒拉取**——只有开始具体开发某个项目时，才 `git clone` 到本地 `/projects/<仓名>`；
不预先克隆全量 121 仓。本仓（allin）只承载治理说明、文档枢纽与 DSH preset 载体；
其余 120 个仓库各自独立，按需克隆、独立演进、整仓推送（铁律 0/3）。
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

*最后更新：2026-09-28（文档枢纽大修：四分类 + 总目录 `INDEX.md` + 规范编号化 + 索引契约门禁；仓根重复的审核报告已并入 `docs/记录/审计/`）*
