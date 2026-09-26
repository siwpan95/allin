# gitee 项目记录

> 记录时间：2026-08-20
> 项目总览页：https://gitee.com/siwpan/projects
> 说明：gitee 上的仓库名与 G:\ 实际目录名**并不一一对应**，本页仅作索引记录；以总览页为准确来源。

## G:\ 与 gitee 的映射（已确认）

| gitee 仓库 | 说明 | G:\ 对应 |
|---|---|---|
| `siwpan/allin` | G:\ 的文档枢纽 + 全盘索引仓库（仓库根 = `G:\allin`，跟踪 `目录索引.txt` / `LICENSE` / `.gitignore` / `docs/` 等 262 个文件） | `G:\allin`（2026-09-24 用 `git rev-parse --show-toplevel` 核实；原记"整个 G:\ 是一个 git 工作树"已不成立，`G:\.git` 不存在） |
| `siwpan/music`（分支 musickit） | musickit 项目仓库（历史提及，见 musickit/README.md） | `/music/musickit`（本地同步区 `/music/_gitee_push`） |
| `siwpan/zhuangtaiji` | 多范式决策引擎 + 可视化工作台（Python 纯标准库内核 + React 编排编辑器，MIT）；登记端口 8011；已发布 v1.0.0 / v1.0.1（见下「已发布版本」） | `/repos/zhuangtaiji`（版本说明的权威副本见该仓 `CHANGELOG.md`） |

其余项目请以 https://gitee.com/siwpan/projects 页面为准。

## 已发布版本（Release 记录）

> 每个版本 = 一个**注解 tag** + 一个 Gitee Release，两者绑定同一提交；版本说明的仓库内权威副本见各仓 `CHANGELOG.md`。
> 判「发布成功」以 tag 与 Release 的绑定提交一致为准（`git ls-remote --tags` 的 `^{}` 行 + Release 的 `target_commitish`）。

| 仓库 | 版本 | tag 绑定提交 | 摘要 | Release | 日期 |
|---|---|---|---|---|---|
| `siwpan/zhuangtaiji` | `v1.0.0` | `10357b6` | Cordis 风格内核重构完成（P0–P4） | [releases/tag/v1.0.0](https://gitee.com/siwpan/zhuangtaiji/releases/tag/v1.0.0) · id 1163773 | 2026-09-24 |
| `siwpan/zhuangtaiji` | `v1.0.1` | `429710a` | Web 编排服务默认只绑回环地址（安全修复） | [releases/tag/v1.0.1](https://gitee.com/siwpan/zhuangtaiji/releases/tag/v1.0.1) · id 1163801 | 2026-09-24 |

## allin 仓库约定（2026-08-20 起；2026-09-24 按现盘核实校正）

- **仓库根 = `G:\allin`**（不是 `G:\` 根）：2026-09-24 实测 `git rev-parse --show-toplevel` → `G:/allin`，且 `G:\.git` 不存在
- 跟踪面共 262 个文件：`目录索引.txt`、`.gitignore`、`LICENSE`（MIT No Attribution, Copyright 2026 siwpan）**以及文档枢纽 `docs/`**——原记"仅推目录索引 + LICENSE，其余内容不入库"与现盘不符，此处按现盘更正
- 其余 G:\ 内容仍为无关内容，不在本仓版本库内
- 推送方式：本机系统 git（`git -C G:\allin push origin master`），或 WorkBuddy PortableGit（完整路径见 DSH 部署事件记录）
