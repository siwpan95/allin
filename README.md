# allin —— 个人全项目治理索引仓库（`D:\projects\allin_push`）

一个**单一索引仓库**承载工作区治理说明、文档枢纽入口与 DeepSeek Harness 治理模式的**可重装载体**：
游戏引擎、游戏、爬虫、音视频工具、电台/转播服务、AI 项目、音乐资产等全部个人项目的事实源与约定都从这里索引出去。

> **⚠️ 盘位已变更（2026-09-24）**：原 `G:\` 整盘工作区已撤销，三盘散落代码统一归置到 **`D:\projects\`**（12 个成员项目）。
> 本仓原先挂在 `G:\allin`，现落在 `D:\projects\allin_push`；其文档里仍会出现一些历史路径（如 `G:\`），以"当时的事实"保留，新项目一律走 `D:\projects\`。
> 接手完整背景请读本仓 [`docs/README.md`](docs/README.md) 与 [`docs/新机配置汇总_2026-09-24.md`](docs/新机配置汇总_2026-09-24.md)。

> **📖 文档枢纽在最前面**：[`docs/`](docs/README.md) —— 整个工作区的文档入口（**开发过程透明可读、可复跑、可接手续做**）。
> 接手请按顺序读：[`docs/MEMORY.md`](docs/MEMORY.md)（铁律与约定）→ [`docs/协作工作流程约定_2026-08-28.md`](docs/协作工作流程约定_2026-08-28.md)（流程与放行口径）→
> [`docs/会话交接_2026-08-27.md`](docs/会话交接_2026-08-27.md)（事实流水与坑）。
> 想复刻这套治理模式 → [`docs/allin治理模式_建设指南.md`](docs/allin治理模式_建设指南.md)。

## 命名约定（重要）

- **allin** = 本仓（索引 + 治理说明 + 深度审核报告 `深度审核报告_20260827.md` + 审核证据 `audit-fragments/`），单独挂载于 `D:\projects\allin_push`（原 `G:\allin`）。
- **一仓一目录**：每个 gitee 仓库对应 `D:\projects\<仓名>` 一个目录，仓名 = 目录名。
- **alloy** = 统一游戏引擎（原 allin_engine，2026-08-23 改名；仓库 siwpan/an-engine）。
- **复制优于共享**：项目内联引擎/字体/资源副本是**有意为之**，不算冗余；缓存（__pycache__/.venv/node_modules/build/dist）不算重复。

## 顶层结构（本仓实际内容）

| 目录/文件 | 内容 |
|---|---|
| `README.md` | 本文件（仓门面） |
| `LICENSE` / `.gitignore` | MIT 许可 + 忽略规则（密钥/构建物一律不入库） |
| `docs/` | **文档枢纽**：活跃事实源（MEMORY / 会话交接 / 协作约定 / ports.yaml / 文档地图 README / 治理模式建设指南），历史文档树在 `docs/md/`；DeepSeek-Harness 升级与治理专档见 `docs/DSH升级与插件不兼容_2026-09-24.md` |
| `preset/` | **治理模式的载体**：`preset/allin/` = DSH agent preset「工作区治理」的 0.1.7+ 声明式可重装副本（见下节与 [`preset/allin/安装说明.md`](preset/allin/安装说明.md)） |
| `tools/` | 工作区门禁与工具（死根路径门禁 + AST 未定义名检查，见其 README） |
| `audit-fragments/` | 深度审核的过程证据（与 `深度审核报告_20260827.md` 配套） |
| `深度审核报告_20260827.md` | 治理准则首次成文（R0–R11 处置清单） |
| `siwpan旧机配置汇总.html` | 旧机（已退役）机器事实源，作换机基线 |

> 历史 README 还列过 `repos/ platform/ local/ assets/ archive/ notpython/` 等目录 —— 那是 `G:\` 整盘时期的形态；
> 盘位归并到 `D:\projects\` 后，各项目已各自成为 `D:\projects/<仓名>` 独立子仓，不再以"子目录"形式寄存在本仓内。

## 核心项目速览（现盘 `D:\projects/` 成员）

- **alloy**（an-engine）：统一游戏引擎——ECS + EventBus + Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI。
- **private-radio-stations**：Node.js + Cordis 插件式转播站（radio/video/portal 三簇）。
- **musickit**（repos/musickit）：phonk 混音项目（真实采样 + 授权分级治理）。
- **deepseek-harness-master**：DeepSeek Harness（`@deepseek-ai/dsh-root` 0.1.7-rc.1）本机 fork，已推独立 gitee 仓 `siwpan/deepseek-harness`（见下）。
- 其余成员：`webcopier` `cordis-table-app` `foolproof-operation` `lab` `moba_battle_platform` `RolePlayer` `music-master` `ncmturnmp3` `D20`。

## DeepSeek-Harness 治理落地（2026-09-26）

工作区治理模式（"开卷必读四事实源 + 三条铁律 + 本机边界"）已落进 DSH **0.1.7+ 声明式 preset**：

- 载体：`preset/allin/allin.patch.yml` —— 插入一行 `@deepseek-ai/dsh-agent-preset`（`config.id: allin`），`persona.prefix` 末尾追加治理段（`GOVERNANCE:BEGIN/END`）。
- **创造模式兼容**：0.1.7 声明式 preset 即"原有创造模式（creator/cordis 声明式编写）"的落地方式；在对话里也能等价编写。
- **无法挂载兜底**：`allin` 是独立 id（非 `cordis`），DSH 破坏性变更导致挂载失败时会话**自动降级到工厂 `standard`/`cordis`**（部署不崩、仅该会话无治理段）。
- **配套脚本**（`preset/allin/`）：
  - `verify-mount.ps1` —— 三层校验（安装层 / 结构层 / 漂移层）+ 兜底指引（UTF-8 BOM 运行）。
  - `make-bundle.ps1` —— 把 `allin.patch.yml` 封装成可 `dsh plugin add` 的 npm bundle（可选 `-Install`）。
  - `verify-upstream-merge.ps1` —— 上游 PR 合并门禁：合入前确认 allin overlay 与官方 harness 能力集无冲突。
- **独立 gitee 仓**：`siwpan/deepseek-harness`（remote `gitde`）—— 解耦 overlay 与上游镜像，上游破坏性变更只动我们的 pin、不动源；比对 shipped `cordis.patch.yml` 即可定位漂移点。
- **上游关系纪律（§八）**：官方 `github.com/deepseek-ai/deepseek-harness` 仅作 SHAPE 核对 / 漂移定位的**参考对象**，不直接 fetch 进部署；其更新经 PR 合入主干前须确认与 allin overlay **无冲突**（`verify-mount.ps1` 漂移层作判据之一）。完整纪律见 `docs/DSH升级与插件不兼容_2026-09-24.md` §八。

安装/校验/回滚全流程见 [`preset/allin/安装说明.md`](preset/allin/安装说明.md)。

## 发布面（gitee）

- 全部仓库公开 + MIT（铁律 0）；一项目一仓，主分支 master，发行版 tag `<项目>-v<版本>`。
  **唯一例外**：`pluginplayer` 随包分发 GPL v3 的 FFmpeg `full_build-shared` 与 MinGW 运行时，许可必须随上游走 **GPL-3.0-or-later**（改 MIT 才是违规）。
- 2026-08-27 重建仓：集合仓退役改名 `*-legacy`，45 个分支项目拆为独立仓，版本分支转 tag。详见 `docs/md/allin主工作区/重建仓执行报告_2026-08-27.md`。

## 治理准则（2026-08-27 深度审核固化）

> **创新 = 借鉴 + 调整 + 同步 + 记账；「推倒重来」只允许发生在结构层，资产与历史永远保全。**

1. **借鉴必记账**：复制/借鉴任何外部代码、配置、概念前，记录「来源 + 许可证 + 借用范围」（上游 dsh/Cordis 或自己的样板都算）。
2. **调整必同步**：任何灵活更新之后三步回写——推远端（ls-remote 验证）→ 更新引用（registry/ports/目录索引）→ 跑黄金值（check / harness exit 0）。
3. **结构可重建、资产与历史永不推倒**：合并优于双仓并存；补优于删；还原优于分支（上游修复后弃用自维护补丁）。

- **敏感信息红线**：API Key / 令牌 / cookie 真实值绝不进代码、配置与仓库（一律 example 化 + .gitignore）。
- 全量审核（对照 deepseek-harness 与 gitee 全量仓）与逐项处置清单 R0–R11：见本仓 `深度审核报告_20260827.md`；本地推进详情：`docs/MEMORY.md`。

## 治理文档

**文档枢纽 = `docs/`**（入口 [`docs/README.md`](docs/README.md)），含活跃事实源（MEMORY / 会话交接 / 协作约定 / ports.yaml）、
审计与核对报告、历史文档树 `docs/md/`，以及《allin 治理模式 · 建设指南》。
深度审核报告随本仓发布：`深度审核报告_20260827.md`。

---

*最后更新：2026-09-26（订正盘位为 `D:\projects\`、12 项目成员；`preset/` 改写为 0.1.7 声明式治理 + 三配套脚本 + 上游 §八 纪律）*
