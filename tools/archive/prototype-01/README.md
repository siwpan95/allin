# PROTOTYPE-01 归档工具（2026-11-26 并入）

> 原落点 `G:\tools`（原型机时期工作区脚本区）。全哥 2026-11-26 定调「整理有用的并入 allin，
> 无用的删除」，把两件**仍有历史价值**的工具并入本归档区。
> 归档性质：**只读历史物证**，不作为现行工具调用；现行门禁见 `tools/gate/` 与
> `allin-governance` 包。

| 文件 | 原用途 | 为什么归档 |
| --- | --- | --- |
| `build_dir_index.py.bak` | 从各项目 README 生成 `目录索引.txt`（初代整盘索引，123 项目） | 索引实物已归档至 `docs/事实源/机器/PROTOTYPE-01/目录索引.txt`；生成器是初代唯一工具，保留可追溯。⚠ 原型机整盘形态（`G:\` = 仓根）已不在，**不可重生成当年那份索引** |
| `filter-drop-dir-index.sh.bak` | `git filter-branch --index-filter` 从 git 历史剔除臃肿的 `目录索引.txt`（17 版本累计 568 MB，`.git` 10.7 GB → 14 MB） | 脚本头部注释记录了完整执行链、两个坑、以及「filter-branch 会连远端跟踪 ref 一起重写」的反直觉认知 —— 破坏性操作的经验只在脚本头部留存，删掉即失传 |

**不在此处的**：G:\tools 的 6 个门禁脚本（仓内 `tools/gate/` 已有接任，逐一同名）与
4 个已完成使命的一次性脚本（ACL 修复 ×2 / migrate-g-to-d / 索引剔除的重复副本），
按冗余三查删除；无接任的 6 件（`fetch_gh_via_jsdelivr.py` / 两份 tree 缓存 /
`admin-ops.ps1` / `dsh-elevated.ps1` / `restart-for-disk-check.ps1`）依全哥裁决处理。
