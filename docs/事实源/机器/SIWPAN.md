# 机器事实 · `SIWPAN`（第三台接入机器，曾改名）

> **时点** 2026-10-30（**@`SIWPAN` 全量复测补录** —— `tools/facts/measure.py` 采集 + 人工裁决；
>   本次补齐盘位卷标、工作区落点、仓数口径、运行时与解释器清单、推送口径，
>   并按 [`机器分区索引.md`](../机器分区索引.md) §0 归属规则只写本机事实。）
> **时点** 2026-10-30（**@`SIWPAN` 实测登记**（上午）：凭据审计遗留逐条核对本机归属 ——
>   `C:\Users\psw`、`D:\deepseek-harness`、`.dsvault` 均不存在；`remote.origin.pushurl` = **0** 条。）
> **时点** 2026-10-29（**@`SIWPAN` 实测登记** —— 该机与 `DESKTOP-KQABATS` 名对不上，按
>   `机器分区索引.md` §3 纪律第 4 条**先求证后定性**：用户确认 = **第三台机器，且曾改名（现名 `SIWPAN`）**。）
> **观测工具** `tools/facts/measure.py`（`Get-Volume` / `Get-Disk` / `Get-Command` / `git config`）、
>   `Get-CimInstance Win32_*`、`git rev-parse --show-toplevel`、Gitee API 匿名查询
> **失效条件** 换机、加减盘、重装系统、换运行时版本后**立即失效**；每次涉及机器事实的动作前
>   **现场复测**，不要照抄本文件。
> **上位判据** [`../../规范/SPEC-006-机器与路径约定.md`](../../规范/SPEC-006-机器与路径约定.md)。
> **本文件只记录 `SIWPAN` 这台**；其他机器见 [`../机器分区索引.md`](../机器分区索引.md) §1。

---

## 1. 本机标识（@`SIWPAN` 复测，2026-10-30）

| 项 | 实测值 | 观测方式 |
| --- | --- | --- |
| **主机名** | **`SIWPAN`** | `Win32_ComputerSystem.Name`（该机 `$env:COMPUTERNAME` = `SIWPAN`，非空） |
| hostname 大小写 | `hostname` 命令输出**小写** `siwpan` | 与 `Win32_ComputerSystem.Name` 的 `SIWPAN` 是**同一台**（Windows 主机名大小写不敏感），勿当两台 |
| 用户目录 | `C:\Users\13122` | `$env:USERNAME` = `13122` |
| CPU | Intel Core **i7-9750H** @ 2.60GHz | `Win32_Processor`（2026-10-29 实测，本轮未复测） |
| 内存 | **31.9 GB** | `Win32_ComputerSystem.TotalPhysicalMemory`（2026-10-29 实测） |
| 系统 | **Windows 11 专业版**，10.0.**26100**（build 26100） | `Win32_OperatingSystem`（measure.py 复测一致） |
| 物理盘 | **1 块**：`M.2 SSD 1TB`（SATA，932 GB）——三卷同盘分区 | `Get-Disk`（measure.py） |
| 本仓仓根 | **`D:\projects\allin`** | `git rev-parse --show-toplevel` |
| 发布区 | **`D:\projects\repos`** | 与仓根同级 |

## 2. 盘位（2026-10-30 实测）

| 盘 | 卷标 | 文件系统 | 容量 GB | 可用 GB | 角色 |
| --- | --- | --- | --- | --- | --- |
| `C:` | `system` | NTFS | 118 | 41 | 系统盘 |
| `D:` | `dalang` | NTFS | 405 | 326 | **工作区盘**（仓根 + 发布区） |
| `E:` | `erlang` | NTFS | 407 | 389 | 数据盘（主 Python `E:\Python314` 在此） |

- **仅 C / D / E 三卷，无 F: / G:**（2026-10-29 与 10-30 两轮实测一致）。
- `C:\Users\psw` **现已不存在**（8RSV60V 侧的用户目录，本机从未有）。
- `D:\deepseek-harness` **已不存在**（8RSV60V 侧的 DSH 现役 checkout；本机无 DSH 检出）。

## 3. 工作区落点（2026-10-30 实测）

| 落点 | 内容 |
| --- | --- |
| `D:\projects\allin` | **本仓**（治理仓，`origin` = `https://gitee.com/siwpan/allin.git`） |
| `D:\projects\repos` | **发布区**（Gitee 仓的本地检出，全量检出，见 §4 仓数） |

- 便携工具链：`C:\Users\13122\.workbuddy\binaries\`（Node / Python / 等，随 WorkBuddy）；
  git 走 WorkBuddy vendor 的 PortableGit（见 §5）。
- WorkBuddy 会话工作区按日期目录管理（`C:\Users\13122\WorkBuddy\<日期时间>\`）。

## 4. 仓数口径（2026-10-30 实测）

| 项 | 值 | 依据 |
| --- | --- | --- |
| **远端仓总数**（Gitee `siwpan`） | **137** | API 匿名分页实测（2026-10-30 上午）；跨机共识值唯一登记处见 [`../机器分区索引.md`](../机器分区索引.md) §5 |
| **本机发布区目录数** | **137** | `D:\projects\repos` **137** 个仓 |
| 含 `.git` | **137 / 137** | 逐目录 `Test-Path .git` |
| 含 `origin` | **137 / 137** | 逐仓读 `.git/config` 判 `[remote "origin"]` |
| 本机 `.git` 总数 | **138** | 137（发布区）+ 本仓 `D:\projects\allin` |

- **口径**：本机是**全量检出**（137 = 远端 137）；提「远端仓数」一律查索引 §5；
  提「本机发布区仓数」一律**现场实测**。
- ⚠ **与 `DESKTOP-KQABATS` 的差异**：那机是**部分检出**（22 仓），本机是全量检出 ——
  「哪仓在哪台」以各机分区文件为准，勿跨机假设。

## 5. 运行时与工具链（2026-10-30 实测；PATH 实际解析，非文档声称）

| 工具 | 现值 | 备注 |
| --- | --- | --- |
| Python | **`E:\Python314\python.exe` → 3.13.14（有 tkinter，Tk 8.6）** | **本机主 Python**，唯一带 tkinter 的；本机无 `.venv`，门禁套件实际用 PATH 上的便携解释器 |
| Node | `C:\Users\13122\.workbuddy\binaries\node\versions\22.22.2-6\node.exe`（v22.22.2） | WorkBuddy 便携工具链 |
| npm | 同目录（10.9.7） | 与 node 同版本目录 |
| git | `C:\Users\13122\AppData\Local\Programs\WorkBuddy\resources\vendor\PortableGit\mingw64\bin\git.EXE`（**2.55.0.windows.3**） | WorkBuddy vendor 版**在 PATH**（与 KQABATS 的「系统安装版在 PATH」不同） |
| pwsh | **`C:\Program Files\PowerShell\7\pwsh.exe`（7.6.6）** | 在 PATH；`powershell` = 系统 Windows PowerShell 5.1 |
| `.venv` | 本仓 `D:\projects\allin` **无 `.venv`** | `run_all_gates.sh` 的仓内 `.venv` 优先策略在本机落到 PATH 解释器（便携 3.13.14，无 tkinter） |

### 5.1 Python 解释器清单（2026-10-30 实测；选型前先测 `import tkinter`）

| 解释器 | 版本 | tkinter | 定位 |
| --- | --- | --- | --- |
| `E:\Python314\python.exe` | **3.13.14** | **有**（Tk 8.6） | ✅ **本机主 Python**（唯一带 tkinter 的；`E:\Python314` 现存） |
| `C:\Users\13122\.workbuddy\binaries\python\versions\3.13.12\python.exe` | 3.13.14 | **无** | WorkBuddy 便携工具链（**精简构建**）；路径里的 `3.13.12` 是**目录名**，判版本一律 `python -V` |
| `C:\Users\13122\AppData\Local\Microsoft\WindowsApps\python.exe` | —— | —— | ⚠ **Microsoft Store 占位符**（存在），执行即报「Python was not found」—— **不是解释器**，脚本里别误选 |

- ⚠ **依赖 tkinter 的项目（GUI / repocheck GUI 模式）只能用 `E:\Python314\python.exe`**。
- ✅ **`repocheck` CLI 与本仓门禁在便携解释器上可跑**（tkinter 仅 GUI 分支需要）；本轮 19+1 道门禁实测全绿。

## 6. 跨仓环境变量（2026-10-30 实测）

| 变量 | 本机状态 |
| --- | --- |
| `KONTAKT_TRANSCODE_ROOT` | 未设置 |
| `RIME_SRC` | 未设置 |
| `GITEE_TOKEN` | 未设置（`gitee_release.py` 走 `~/.git-credentials` 首段 hex 的 `--token-file` 口径） |

- **读法约定**：跨仓脚本引用数据根时**优先环境变量、未设则按 cwd 相对解析**（铁律 5 同口径）。

## 7. 推送与远端镜像（@`SIWPAN` 侧，2026-10-30 实测）

| 项 | 现值 |
| --- | --- |
| `remote.origin.url` | `https://gitee.com/siwpan/allin.git` |
| `remote.origin.pushurl` 条数 | **0**（`git config --get-all remote.origin.pushurl` 无输出） |
| 独立 remote | 无（`git remote -v` 只有 origin） |
| 推送口径 | **只推 Gitee 单核**，`git push` 走默认 url |
| 核对口径 | 只核 Gitee 一侧（`ls-remote origin` + `rev-list --left-right --count` 0/0 + 工作树干净） |

- **作业口径**与 [`./DESKTOP-KQABATS.md`](./DESKTOP-KQABATS.md) §6 相同（该机亦 0 条 pushurl）；
  GitHub 镜像由 [`./DESKTOP-8RSV60V.md`](./DESKTOP-8RSV60V.md) §9 那台推送（pushurl 2 条），本机**不要求 GitHub 侧可见**，也**不补配** pushurl。
- ⚠ **跨机漂移现行（2026-10-30 实证）**：本机作业期间远端两次被其它机推进
  （`5a1d767→c9586d3` DIVERGED、`8b46e67→7f3fecc` PURE_BEHIND）——
  **动手前 fetch 对齐是硬纪律**，DIVERGED 时 g04 会拦。

## 8. 与 `DESKTOP-KQABATS` 的实测差异（仅列事实，不作定性）

CPU 代际（9th i7-9750H vs 13th i5-13420H）、内存（31.9 vs 15.7 GB）、系统版本（专业版 26100 vs
家庭版 26300）、仓根/发布区盘位（D: vs E:）、发布区规模（**全量 137 vs 部分 22**）、
git 来源（PATH 上是 WorkBuddy vendor PortableGit vs 系统安装版）、pwsh（7.6.6 在 PATH vs 不在 PATH）。
**关系定性（用户 2026-10-29 求证）：`SIWPAN` 是第三台机器，曾改名（现名 `SIWPAN`）。**

---

*本文件是 `SIWPAN` 这台的**唯一**事实源。改前先复测，并把旧值以"（原 …）"形式留在同格内。*
