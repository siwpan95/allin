# 机器事实 · `DESKTOP-KQABATS`

> **时点** 2026-10-30 17:00（**`tools/facts/measure.py` 自动采集 + 人工裁决** —— 机器 `DESKTOP-KQABATS`；
>   本段为**采集原始值**，凡与上一版不符者须逐项复测后再改，**不要直接覆盖**。
>   **可机检断言**（判据见 `g20-facts`）：仓根 `E:\projects\allin` **现存**；
>   发布区 `E:\projects\repos` **22** 个目录；主 Python `D:\Python314\python.exe` **现存**；
>   `D:\musickit` **现存**；`D:\private-radio-stations` **现存**；
>   `E:\projects\reference` **现存**；`E:\projects\_governance` **现存**。）
> **时点** 2026-10-30 上午（**本机独有事实全量补录** —— 章节语义与另两台分区文件对齐：
>   §1 标识 / §2 盘位 / §3 工作区 / §4 仓数 / §5 运行时（§5.1 解释器）/ §6 环境变量 / §7 推送 / §8 差异。
>   ⚠ **本块的两处结论已被上块修正**：① `$env:COMPUTERNAME` 在 **WorkBuddy 宿主内实测非空**
>   （= `DESKTOP-KQABATS`；Python `os.environ` 与 `platform.node()` 一致）—— 当日凌晨曾读到**空**，
>   ⇒ 该变量**随宿主而异**，仍**不可**用于区分机器（与 `DESKTOP-8RSV60V.md` 同一结论）；
>   ② git 在 **PATH 上有两份**（WorkBuddy vendor PortableGit 优先 / 系统安装版次之），
>   实测解析到哪一份**取决于调用进程**，不是单一现值。）
> **时点** 2026-10-29（**机器名登记**：机器名 `DESKTOP-KQABATS`；`pushurl` **0 条** ⇒ 只推 Gitee 单核。）
> **观测工具** `tools/facts/measure.py`（`Get-Volume` / `Get-Disk` / `Get-Command` / `git config`）、
>   `Get-CimInstance Win32_*`、`git rev-parse --show-toplevel`、Gitee API 匿名查询、
>   `python -c "import tkinter"` 实测
> **失效条件** 换机、加减盘、重装系统、换运行时版本后**立即失效**；每次涉及机器事实的动作前
>   **现场复测**，不要照抄本文件。
> **上位判据** [`../../规范/SPEC-006-机器与路径约定.md`](../../规范/SPEC-006-机器与路径约定.md)。
> **本文件只记录 `DESKTOP-KQABATS` 这台**；其他机器见 [`../机器分区索引.md`](../机器分区索引.md) §1。

---

## 1. 本机标识（2026-10-30 复测）

| 项 | 实测值 | 观测方式 |
| --- | --- | --- |
| **主机名** | **`DESKTOP-KQABATS`** | `Win32_ComputerSystem.Name` / `platform.node()` / `hostname` 三者一致 |
| `$env:COMPUTERNAME` | **非空** = `DESKTOP-KQABATS` | ⚠ **随宿主而异**：WorkBuddy 宿主内非空，当日凌晨在另一类会话内读到**空** ⇒ **不可**用于区分机器，取名仍用 `Win32_ComputerSystem.Name` |
| 用户目录 | `C:\Users\13122` | `$env:USERNAME` = `13122` |
| 厂商 / 主板 | Lecoo / `ADPT1L` | `Win32_BaseBoard` |
| CPU | 13th Gen Intel Core i5-13420H | `Win32_Processor` |
| 内存 | 15.7 GB | `Win32_ComputerSystem.TotalPhysicalMemory` |
| 系统 | Microsoft Windows 11 家庭版 中文版 10.0.26300（build 26300） | `Win32_OperatingSystem`（measure.py 一致） |
| 物理盘 | 1 块 NVMe `TWSC TSC3AN1T0-F6Q10S`（954 GB）+ 2 个 USB 读不到容量 | `Get-Disk`（measure.py） |
| 本仓仓根 | `E:\projects\allin` | `git rev-parse --show-toplevel` |
| 发布区 | `E:\projects\repos` | 与仓根同级 |

## 2. 盘位（2026-10-30 实测）

| 盘 | 卷标 | 文件系统 | 容量 GB | 可用 GB | 角色 |
| --- | --- | --- | --- | --- | --- |
| `C:` | （无） | NTFS | 200 | 101 | 系统盘；`C:\Users\13122` 家目录（含 `.workbuddy` 便携工具链） |
| `D:` | 本地磁盘 | NTFS | 377 | 247 | **工具与数据盘**：Python / node / musickit / 各工具现役落点 |
| `E:` | 本地磁盘 | NTFS | 377 | 312 | **工作区 / 项目盘** |

- 另有一个 **0.3 GB FAT32 无盘符分区**（系统/恢复类，未挂盘符）。
- `measure.py` 的卷表另列 `F:` / `G:` 两项（**0 容量、无文件系统、无盘符**）⇒ 那是**读不到盘符**，
  **不是真盘**；本机**无 F: / G:** ⇒ 引用那两盘的脚本在本机必然失败。

## 3. 工作区落点（2026-10-30 实测）

| 落点 | 内容 |
| --- | --- |
| `E:\projects\allin` | **本仓**（治理 / 文档枢纽 / preset 载体），远端 `siwpan/allin` |
| `E:\projects\repos` | **发布区：22 个仓**（见 §4） |
| `E:\projects\reference` | 参考源码区：`blender/`、`blender-legacy-bloom/`、`blender-notes.md`（**非 git 仓**） |
| `E:\projects\_governance` | 2026-10-26 的体检输出存档（`repocheck_allin_selfA/B.txt`、`check_repos*.txt`、`repocheck_repos.json`） |
| `E:\projects\foolproof-operation-master` | `foolproof-operation` 的**源码副本（无 `.git`**，含 README/LICENSE/CHANGELOG） |
| `E:\projects\foolproof-operation-portable-v1.1.2` | 同上的便携版副本（无 `.git`） |
| `E:\projects\`（顶层一个敏感文件） | ⚠ **敏感文件，仓外**（102 字节，2026-10-06）。**不进版本控制**；本条只登记存在性 |

### 3.1 工具与数据盘 `D:\`

| 路径 | 内容 |
| --- | --- |
| `D:\musickit` | **git 仓**（origin `https://gitee.com/siwpan/music.git`，HEAD `605efc4`，2026-08-21）—— 见 §6 的版本差异说明 |
| `D:\private-radio-stations` | **git 仓**（origin `https://gitee.com/siwpan/private-radio-stations.git`，HEAD `678ab24`） |
| `D:\private-radio-stations-2.0` | 同上的 2.0 分支副本 |
| `D:\Python314` | **本机唯一带 tkinter 的 Python**（见 §5.1） |
| `D:\node` | 独立 node 安装（`node.exe` + `corepack` + `node_modules`） |
| `D:\deep seek` / `D:\leidian` / `D:\sdm` / `D:\VLC` | 各类工具现役落点 |

### 3.2 便携工具链（`C:\Users\13122\.workbuddy\binaries\`）

| 组件 | 落点 |
| --- | --- |
| Node | `node\versions\22.22.2-6\node.exe` |
| Python | `python\versions\3.13.12\python.exe`（**目录名是 3.13.12，实际版本 3.13.14**） |
| PortableGit | `PortableGit\versions\{1.3.0, current}\`（**不在 PATH**） |

## 4. 仓数口径（2026-10-30 实测）

| 项 | 值 | 依据 |
| --- | --- | --- |
| **远端仓总数**（Gitee `siwpan`） | **137** | 跨机共识值，唯一登记处见 [`../机器分区索引.md`](../机器分区索引.md) §5 |
| **本机发布区目录数** | **22** | `Get-ChildItem E:\projects\repos -Directory` |
| 含 `.git` | **22 / 22** | 逐目录 `Test-Path .git` |
| 含 `origin` | **22 / 22** | 逐仓读 `.git/config` 判 `[remote "origin"]` |
| 本机 `.git` 总数 | **24** | 22（发布区）+ `D:\musickit` + `D:\private-radio-stations` |

本机 22 个仓名：`3dworld`、`3dworld-demos`、`3dworld-globe`、`an-engine`、`arcade`、`ashen-beacon`、
`bloodmusic`、`calculator`、`cordis-py`、`dict-scene-engine`、`dse-core`、`haha`、`Idle`、`lab`、
`lonely-desert-road`、`maga`、`niulai`、`peasy-ai`、`running-group-simulator`、`weiqi_lab`、
`worldbuilder`、`zhuangtaiji`。

- **口径**：提「远端仓数」一律查索引 §5；提「本机发布区仓数」一律**现场实测**。
  本机是**部分检出** —— 远端 137 与本地 22 的差额是**尚未在此机检出**的仓，不是缺失。
- ⚠ **与 `SIWPAN` 的差异**：那台是**全量检出**（137 = 远端 137），本机只有 22 ⇒
  「哪仓在哪台」以各机分区文件为准，**勿跨机假设**。
- ⚠ **与 `DESKTOP-8RSV60V` 的差异**：`calculator` 在本机发布区仍是独立目录，那台已把它收拢进
  `arcade` 并转 `archived` ⇒ **两机发布区不同步**，以各机实测为准。

## 5. 运行时与工具链（2026-10-30 实测；PATH 实际解析，非文档声称）

| 工具 | 现值 | 备注 |
| --- | --- | --- |
| Python | **`D:\Python314\python.exe` → 3.14.7**（**有 tkinter，Tk 9.0**） | 本机唯一带 tkinter 的解释器；清单见 §5.1 |
| Node | `C:\Users\13122\.workbuddy\binaries\node\versions\22.22.2-6\node.exe`（v22.22.2） | 便携工具链 |
| npm | 同目录（**10.9.7**） | 与 node 同版本目录 |
| git | **PATH 上有两份**：WorkBuddy vendor `…\resources\vendor\PortableGit\mingw64\bin\git.EXE`（2.55.0.windows.3，**Python 等子进程解析到此**）与系统安装版 `C:\Program Files\Git\cmd\git.exe`（**PowerShell 会话解析到此**） | ⚠ **解析到哪一份取决于调用进程**；`git --version` 两处分别报 2.55.0.windows.3 / 2.55.0.windows.5 |
| pwsh | **不在 PATH** | 本机无 PowerShell 7；`powershell` = 系统 Windows PowerShell 5.1 |

### 5.1 Python 解释器清单（2026-10-30 实测；选型前先测 `import tkinter`）

| 解释器 | 版本 | tkinter | 定位 |
| --- | --- | --- | --- |
| `D:\Python314\python.exe` | **3.14.7** | **有**（Tk 9.0） | ✅ **本机主 Python**（唯一带 tkinter 的） |
| `C:\Users\13122\.workbuddy\binaries\python\versions\3.13.12\python.exe` | 3.13.14 | **无** | WorkBuddy 便携工具链（**精简构建**）；路径里的 `3.13.12` 是**目录名**，判版本一律 `python -V` |
| `E:\projects\allin\.venv\Scripts\python.exe` | 3.13.14 | **无** | **本仓门禁套件实际使用的解释器**（`scripts/run_all_gates.sh` 钉死它） |
| `C:\Users\13122\AppData\Local\Microsoft\WindowsApps\python.exe` | —— | —— | ⚠ **Microsoft Store 占位符**，执行即报「Python was not found」—— **不是解释器**，脚本里别误选 |

- ⚠ **本机没有"随便哪个都行"的余地**：唯一带 tkinter 的是 `D:\Python314\python.exe`（3.14.7）；
  便携 3.13.14 与仓内 `.venv` **都无 tkinter**。
- ✅ **`repocheck` CLI 在本机可跑**：`tools/repocheck/main.py` 的 `import tkinter` 位于 **GUI 分支**
  （`main.py:26`），CLI 路径经 `cli.py` / `scanner.py` / `rulebase.py`（三者均**不 import tkinter**）
  ⇒ **无 tkinter 也能跑 CLI 体检**；本仓门禁在便携 3.13.14 上实测通过率 100%。
- ⚠ **选解释器先跑 `-c "import tkinter"`**，别只看版本号 —— 本机两个 3.13.14 都没有 tkinter。

## 6. 跨仓环境变量（2026-10-30 实测）

| 变量 | 本机状态 | 依据 |
| --- | --- | --- |
| `KONTAKT_TRANSCODE_ROOT` | **未设置**，且**本机 0 个消费者** | `D:\musickit\remix\tools\make_{brass,bst,bww1}_wanted.py` 三脚本**均不读** `os.environ`（逐文件 grep 实测） |
| `RIME_SRC` | **未设置**，本机**无落点** | 扫 `D:\`、`E:\` 与常见 RIME 路径（`AppData\Roaming\RIME` 等）均无 rime-ice |
| `GITEE_TOKEN` | **未设置** | `gitee_release.py` 走 `~/.git-credentials` 首段 hex 的 `--token-file` 口径 |

- ⚠ **与 `DESKTOP-8RSV60V` 侧的记载不同**：那台记「`KONTAKT_TRANSCODE_ROOT` 由 `G:\repos\musickit`
  的 3 个脚本各读一次」，而本机这份检出**没有该读取**。成因是**两机检出不同步** ——
  本机 `D:\musickit` HEAD = `605efc4`（**2026-08-21**），三个脚本最后改动 2026-08-20；那台更新。
  ⇒ **该变量属那台机器的现状，不适用本机**。
- **读法约定**：跨仓脚本引用数据根时**优先环境变量、未设则按 cwd 相对解析**（铁律 5 同口径）。

## 7. 推送与远端镜像（@`DESKTOP-KQABATS` 侧，2026-10-29 实测）

| 项 | 现值 |
| --- | --- |
| `remote.origin.url` | `https://gitee.com/siwpan/allin.git` |
| `remote.origin.pushurl` 条数 | **0**（`git config --get-all remote.origin.pushurl` 无输出） |
| 独立 remote | 无（`git remote -v` 只有 origin） |
| 推送口径 | **只推 Gitee 单核**，`git push` 走默认 url |
| 核对口径 | 只核 Gitee 一侧（`ls-remote origin` + `rev-list --left-right --count` 0/0 + 工作树干净） |

- **作业口径**：**不要求 GitHub 侧在该机可见**；该机**不补配** GitHub pushurl（用户 2026-10-29 明确交代）。
  GitHub 镜像由**两台**推：[`./DESKTOP-8RSV60V.md`](./DESKTOP-8RSV60V.md) §9 与 [`./SIWPAN.md`](./SIWPAN.md) §7
  （均 pushurl 2 条；`@SIWPAN` 于 2026-10-31 经用户指令补配，提交 `2a6da31`）⇒ **本机单核 ≠ 镜像无人推**。
- ⚠ **跨机漂移现行（2026-10-30 实证）**：本机作业期间远端多次被其它机推进
  （`8b46e67→7f3fecc` PURE_BEHIND、`705f888→e245410` PURE_BEHIND）⇒ **动手前 fetch 对齐是硬纪律**，
  DIVERGED 时 `g04` 会拦。

## 8. 与另两台的实测差异（仅列事实，不作定性）

| 维度 | `DESKTOP-KQABATS`（本机） | `DESKTOP-8RSV60V` | `SIWPAN` |
| --- | --- | --- | --- |
| CPU / 内存 | i5-13420H / 15.7 GB | i5-12600KF / 16 GB | i7-9750H / 31.9 GB |
| 系统 | 家庭版 26300 | 专业版 26300 | 专业版 26100 |
| 工作区盘 | `E:` | `G:` | `D:` |
| 发布区规模 | **22（部分检出）** | 136 | **137（全量检出）** |
| git 在 PATH | WorkBuddy vendor PortableGit **与**系统安装版**两份并存** | `G:\Git\cmd\git.exe` | WorkBuddy vendor PortableGit |
| pwsh | **不在 PATH** | `G:\powershell\7` 在 PATH | `C:\Program Files\PowerShell\7` 在 PATH |

> **关系定性（用户 2026-10-29 求证）**：三台**并存**；`SIWPAN` 曾改名（现名 `SIWPAN`）。
> **本机与 `DESKTOP-8RSV60V` 的软件布局同构、盘符映射不同**（那台工作区 G: + 数据 D: + 依赖 F:，
> 本机工作区 E: + 工具数据 D:）⇒ **两机的事实不可互相照抄**。

## 9. 本机重要产出（归属留痕，非机器事实）

- **组合做大做强战略研究（REC-AU-20，2026-10-31，本机完成）**：本机对 `siwpan/allin` 组合做了一次战略研究
  （Gitee API **137** 仓实查 + 发布区 **22** 仓实测 + PyPI/pypistats 实查），结论"瓶颈在转化不在产能"，
  给出五断层诊断、三条战略路线（推荐 B 影响力先行 + A 单旗舰并行、C 后置）、90 天 11 项作战计划，并提"冻结新增仓"停手令。
  完整报告见 [`../../记录/审计/组合做大做强战略研究_2026-10-31.md`](../../记录/审计/组合做大做强战略研究_2026-10-31.md)。
  ⚠ **这是本机（`DESKTOP-KQABATS`）的工作成果，不是上游/他机带来的** —— 登记（`docs/INDEX.md` 的 `REC-AU-20`）
  与提交（`8d140ab`）均在本机完成；其归属归本机，不在机器分区索引的跨机共识里。

---

*本文件是 `DESKTOP-KQABATS` 这台的**唯一**事实源。改前先复测，并把旧值以"（原 …）"形式留在同格内。*
