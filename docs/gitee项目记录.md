# gitee 项目记录

> 记录时间：2026-08-20
> 项目总览页：https://gitee.com/siwpan/projects
> 说明：gitee 上的仓库名与 G:\ 实际目录名**并不一一对应**，本页仅作索引记录；以总览页为准确来源。

## G:\ 与 gitee 的映射（已确认）

| gitee 仓库 | 说明 | G:\ 对应 |
|---|---|---|
| `siwpan/allin` | G:\ 的文档枢纽 + 全盘索引仓库（仓库根 = `G:\allin`，跟踪 `目录索引.txt` / `LICENSE` / `.gitignore` / `docs/` 等 262 个文件） | `G:\allin`（2026-09-24 用 `git rev-parse --show-toplevel` 核实；原记"整个 G:\ 是一个 git 工作树"已不成立，`G:\.git` 不存在） |
| `siwpan/music`（分支 musickit） | musickit 项目仓库（历史提及，见 musickit/README.md） | `G:\music\musickit`（本地同步区 `G:\music\_gitee_push`） |
| `siwpan/zhuangtaiji` | 多范式决策引擎 + 可视化工作台（Python 纯标准库内核 + React 编排编辑器，MIT）；登记端口 8011 | `G:\repos\zhuangtaiji` |

其余项目请以 https://gitee.com/siwpan/projects 页面为准。

## allin 仓库约定（2026-08-20 起；2026-09-24 按现盘核实校正）

- **仓库根 = `G:\allin`**（不是 `G:\` 根）：2026-09-24 实测 `git rev-parse --show-toplevel` → `G:/allin`，且 `G:\.git` 不存在
- 跟踪面共 262 个文件：`目录索引.txt`、`.gitignore`、`LICENSE`（MIT No Attribution, Copyright 2026 siwpan）**以及文档枢纽 `docs/`**——原记"仅推目录索引 + LICENSE，其余内容不入库"与现盘不符，此处按现盘更正
- 其余 G:\ 内容仍为无关内容，不在本仓版本库内
- 推送方式：本机系统 git（`git -C G:\allin push origin master`），或 WorkBuddy PortableGit（完整路径见 DSH 部署事件记录）
