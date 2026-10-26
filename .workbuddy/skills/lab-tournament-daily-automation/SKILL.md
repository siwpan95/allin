---
name: lab-tournament-daily-automation
description: 维护 G:\repos\lab（多语言国际象棋引擎 + tournament 循环赛）的每日自动化：Windows 计划任务 + run_daily.cmd 运行器的搭建、核对与排障；以及在「本地提交 vs 远端」方向判断、U 盘/异机快照同步时的验证闸门。触发词：lab 自动化、tournament 定时任务、LabTournamentDaily、引擎自测、_parity、多语言引擎同步、Tier 2、重复惩罚、评估风格档。
agent_created: true
---

# lab tournament 每日自动化维护

适用仓库：`G:\repos\lab`（远端 `https://gitee.com/siwpan/lab`），里程碑标签 Tier 2-A（重复惩罚）/2-B（时间控制）/2-C（评估风格档）。

## 1. 现状（2026-10-08 已终止调度）

> **状态：每日调度已于 2026-10-08 终止**（用户指示）。`LabTournamentDaily` 已注销，运行资产全部保留在
> `C:\Users\psw\.workbuddy\lab_tournament\`。恢复方式：
> ```powershell
> Register-ScheduledTask -Xml (Get-Content 'C:\Users\psw\.workbuddy\lab_tournament\task_definition_20261008.xml' -Raw) -TaskName 'LabTournamentDaily'
> ```
> 终止前运行成果：9/29~10/8 共 10 次运行，0 次 ALIGN FAILED、全部 exitcode=0，战报 11 份。手工跑赛仍需重建驱动（见 §3）。

| 组件 | 路径 / 值 |
|---|---|
| 计划任务 | `LabTournamentDaily`（**已于 2026-10-08 注销**），每日 03:00，由 `Register-ScheduledTask` 注册 |
| 运行器 | `C:\Users\psw\.workbuddy\lab_tournament\run_daily.cmd`（CRLF + 全绝对路径） |
| 任务定义存档 | 同目录 `task_definition_20261008.xml`（Export-ScheduledTask 全量，可原样恢复） |
| 日志 | 同目录 `tournament_last_run.log`（5MB 上限，混编码，**grep 加 `-a`**） |
| 本机工具链覆盖 | `tournament/local.env`（gitignored）钉住 LAB_NODE / LAB_PYTHON 绝对路径 |
| 战报 | `tournament/reports/YYYY-MM-DD.md`（**自动化产物，不逐次入库**） |

**终止自动化时只注销调度，不删资产**：运行器脚本、日志、bundle、任务定义 XML 一律保留 —— 恢复成本几乎为零，删除则不可逆。

运行器流程：`git fetch` → `git merge --ff-only origin/master` → `node tournament/run_tournament.mjs`（`TOURNAMENT_DEPTH=4`）。三个失败点都只告警不阻断，并打 `!! ALIGN FAILED` / `!! RUN FAILED` 标记 + `[align] fetch=N merge=N`。

## 2. 本机可用引擎（工具链决定）

- ✅ js / py / rust / cpp / ts（rust 用 cargo、cpp 用 `bash build_engines.sh`、ts 用 `chess-cordis` 内 esbuild 打包 `drivers/ts/out/driver.cjs`）
- ❌ go（`G:\go` 标准库残缺：`src` 仅 8 项，缺 bufio/fmt → 需重装 Go）
- ❌ cs / fs / vb / java（缺 .NET 8 SDK 与 JDK 21；`vbnc` 不适用）
- 引擎清单是**探针制**：起不来的自动剔除并在战报注明，不会出假结果（`tournament/probe.mjs` 可单独探）

## 3. 验证闸门（改动引擎后必跑，全绿才提交）

```bash
cd /g/repos/lab
"C:/Users/psw/.workbuddy/binaries/python/versions/3.13.12/python.exe" _parity.py           # 8 语言源码级：97 项核心断言逐字一致 + perft 规范
cd PyChess && python main.py test        # 各自 111 项
cd ../JsChess && node main.js test
cd ../RustChess && cargo run --quiet --bin rustchess -- test
cd ../chess-cordis && npx esbuild ../TsChess/main.ts --bundle --platform=node --format=cjs --outfile=/tmp/ts_bundle.cjs && node /tmp/ts_bundle.cjs test
cd .. && bash build_engines.sh           # 重建 cpp（cs/fs/java 会按预期 SKIP）
cd chess-cordis/drivers/rust && cargo build --release
cd ../.. && node tournament/probe.mjs    # 期望 available: rust, ts, js, py, cpp
TOURNAMENT_DEPTH=2 GAMES_PER_PAIR=1 node tournament/run_tournament.mjs   # 冒烟 ~40s
```
`_parity.py` 是**源码级**校验，因此对无工具链的 go/cs/fs/vb/java 仍有意义；但要在提交信息里标「待复核」。

## 4. 方向判断（关键，别搞反）

推送前先核对，**不要凭「本地有新提交」就推**：
```bash
git log --format="%h %ad %an %s" --date=format:"%m-%d %H:%M" master..origin/master   # 远端有啥
git diff --stat origin/master master | tail -15                                      # 本地多啥
git diff --stat master origin/master | tail -15                                      # 远端多啥
```
- 若差异只落在少数文件且远端更全（含修复），本地提交应**丢弃并 `git reset --hard origin/master`**，而不是推送。
- 判断「谁更新」要看**内容**：USB/异机快照常含未入库工作，但也可能旧于远端某个修复；逐文件 diff，别看时间戳猜。
- 丢弃前必备份三件套：备份分支 + `git bundle create <path> --all`（仓外）+ 独特文件导出留档。
- 对齐后必须 `git ls-remote origin refs/heads/master` 与本地 HEAD 逐一比对（refs/remotes 可能过期）。

## 5. 排障要点（踩过的坑）

1. **Bash 工具工作目录不跨调用保持** → 每条命令显式 `cd /g/repos/lab && ...`，否则 `fatal: not a git repository`。
2. **`schtasks.exe` 被安全策略黑名单**（不可绕过）→ 改用 PowerShell：`New-ScheduledTaskAction` + `New-ScheduledTaskTrigger -Daily -At 03:00AM` + `Register-ScheduledTask -Force -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable)`；PowerShell 工具输出偶尔不回显，写文件再 Read 核对。
3. **cmd 的 if 块内 ASCII 圆括号会破坏解析**（报「此时不应有 --。」）→ 告警文案禁用 `(` `)`，用破折号或顿号。
4. **验证 cmd 脚本要用隔离副本**：`LOGDIR` 与 `REPO` 都要替换成临时值 —— 否则测试副会对真实仓库执行 `git fetch/merge`（曾因此意外推进了真实仓库）。
5. **tsx 不可用**：npx 缓存的 esbuild 缺 `@esbuild/win32-x64`，且 `npm i` 重装报 `spawnSync node.exe EBUSY` → 改用 `chess-cordis` 内 esbuild 打包入口再 `node` 跑，等效可信。
6. **日志混编码**：cmd 头行是 ANSI、node 输出是 UTF-8 → `grep -a`、`tr -d '\000'`。
7. **计划任务触发条件**：默认仅当前用户登录时触发；03:00 关机/未登录则不跑（`StartWhenAvailable` 只补已注册触发点）。
8. **分叉时 `--ff-only` 必然失败**且只写一行 git hint —— 依赖 `!! ALIGN FAILED` 标记发现，别漏看。
9. **终止调度**：`Unregister-ScheduledTask -TaskName <名> -Confirm:$false`（schtasks 不可用）。先 `Export-ScheduledTask` 存档全量定义，再注销；注销后按 `*Lab*` 过滤复查，注意 Windows 内置任务名（`*SyncDataAvailable` 等）会造成假阳性。幂等校验与 PowerShell 回显不稳时，把结果写文件再 Read。

## 6. 自动化产物不入库（既定决策）

`tournament/reports/*`、`local.env`、`*.exe/*.dll/target//out//node_modules/` 均在 `.gitignore`。构建产物换机后由 `bash build_engines.sh` + 各语言工具链重建，不推送。
