# 机器事实 · `DESKTOP-KQABATS`

> **时点** 2026-10-30（**本轮补录：本机独有事实全量实测** —— §0 多机定位与本机身份、§1 盘位、
>   §2 工作区落点、§3 仓数口径、§4 运行时与工具链（含 §4.1 解释器清单）、§5 跨仓环境变量；
>   **章节语义与 `DESKTOP-8RSV60V.md` 对齐**，便于两机对照。推送口径见 §6。）
> **时点** 2026-10-29（**机器名登记**：机器名 `DESKTOP-KQABATS`；`$env:COMPUTERNAME` **为空**，
>   取机器名须用 `Win32_ComputerSystem.Name`；`pushurl` **0 条** ⇒ 只推 Gitee 单核。）
> **观测工具** `Get-Volume` · `Get-CimInstance Win32_*` · `Get-Command -All` ·
>   `git rev-parse --show-toplevel` · `git config --get-all remote.origin.pushurl` ·
>   `Get-ChildItem -Recurse` 逐目录扫 · `python -c "import tkinter"` 实测
> **失效条件** 换机、加减盘、重装系统、换运行时版本后**立即失效**；每次涉及机器事实的动作前
>   **现场复测**，不要照抄本文件。
> **上位判据** [`../../规范/SPEC-006-机器与路径约定.md`](../../规范/SPEC-006-机器与路径约定.md)。
> **本文件只记录 `DESKTOP-KQABATS` 这台**；其他机器见 [`../机器分区索引.md`](../机器分区索引.md) §1。

---

## 0. 本机身份与多机序列中的位置

### 0.1 本机标识（2026-10-30 实测）

| 项 | 实测值 | 观测方式 |
| --- | --- | --- |
| **主机名** | **`DESKTOP-KQABATS`** | `Win32_ComputerSystem.Name`（⚠ **不要用 `$env:COMPUTERNAME`**，本机该变量**为空**） |
| 用户目录 | `C:\Users\13122` | `$env:USERNAME` = `13122` |
| 厂商 / 主板 | Lecoo / `ADPT1L` | `Win32_BaseBoard` |
| CPU | 13th Gen Intel Core i5-13420H | `Win32_Processor` |
| 内存 | 15.7 GB | `Win32_ComputerSystem.TotalPhysicalMemory` |
| 系统 | Windows 11 家庭版 中文版，10.0.26300 | `Win32_OperatingSystem` |
| 本仓仓根 | `E:\projects\allin` | `git rev-parse --show-toplevel` |
| 发布区 | `E:\projects\repos` | 与仓根同级 |

### 0.2 三台机器并存（**不是同一台的三种观测**）

| 机器 | 形态 | 与本机的关系 |
| --- | --- | --- |
| **`DESKTOP-KQABATS`（本机）** | Lecoo 主机，i5-13420H（13 代移动），Win11 家庭版，盘位 C/D/E | —— |
| `DESKTOP-8RSV60V` | 微星台式机，i5-12600KF，Win11 专业版，盘位 C/D/F/G | **另一台并存电脑**，非本机别名 |
| `SIWPAN` | i7-9750H（9 代移动），Win11 专业版，盘位 C/D/E | 第三台接入机器，曾改名 |

> 本机与 `DESKTOP-8RSV60V` 的**软件布局同构、盘符映射不同**（那台是工作区 G: + 数据 D: + 依赖 F:，
> 本机是工作区 E: + 工具数据 D:）⇒ **两机的事实不可互相照抄**，各以本文件为准。

## 1. 盘位（2026-10-30 实测）

| 盘 | 卷标 | 文件系统 | 容量 | 角色 |
| --- | --- | --- | --- | --- |
| `C:` | （系统） | NTFS | 200 GB | 系统盘；`C:\Users\13122` 家目录（含 `.workbuddy` 便携工具链） |
| `D:` | 本地磁盘 | NTFS | 376.8 GB | **工具与数据盘**：Python / node / musickit / 各工具的现役落点 |
| `E:` | 本地磁盘 | NTFS | 376.8 GB | **工作区 / 项目盘** |

- 另有一个 **0.3 GB FAT32 无盘符分区**（系统/恢复类，未挂盘符）。
- **本机无 F: / G:** —— 任何引用 `G:\` 或 `F:\` 路径的脚本在本机**必然失败**。

## 2. 工作区落点（2026-10-30 实测）

### 2.1 `E:\projects\`（工作区根，NTFS）

| 路径 | 内容 |
| --- | --- |
| `E:\projects\allin` | **本仓**（治理 / 文档枢纽 / preset 载体），远端 `siwpan/allin` |
| `E:\projects\repos` | **发布区：22 个仓**（见 §3） |
| `E:\projects\reference` | 参考源码区：`blender/`、`blender-legacy-bloom/`、`blender-notes.md`（**非 git 仓**） |
| `E:\projects\_governance` | 2026-10-26 的体检输出存档（`repocheck_allin_selfA/B.txt`、`check_repos*.txt`、`repocheck_repos.json`） |
| `E:\projects\foolproof-operation-master` | `foolproof-operation` 的**源码副本（无 `.git`**，含 README/LICENSE/CHANGELOG） |
| `E:\projects\foolproof-operation-portable-v1.1.2` | 同上的便携版副本（无 `.git`） |
| `E:\projects\密码.txt` | ⚠ **敏感文件，仓外**（102 字节，2026-10-06）。**不进版本控制**；本条只登记存在性 |

### 2.2 `D:\`（工具与数据盘，NTFS）

| 路径 | 内容 |
| --- | --- |
| `D:\musickit` | **git 仓**（origin `https://gitee.com/siwpan/music.git`，HEAD `605efc4`，2026-08-21）—— 见 §5 的版本差异说明 |
| `D:\private-radio-stations` | **git 仓**（origin `https://gitee.com/siwpan/private-radio-stations.git`，HEAD `678ab24`） |
| `D:\private-radio-stations-2.0` | 同上的 2.0 分支副本 |
| `D:\Python314` | **本机唯一带 tkinter 的 Python**（见 §4.1） |
| `D:\node` | 独立 node 安装（`node.exe` + `corepack` + `node_modules`） |
| `D:\deep seek` / `D:\leidian` / `D:\sdm` / `D:\VLC` | 各类工具现役落点 |

### 2.3 便携工具链（`C:\Users\13122\.workbuddy\binaries\`）

| 组件 | 落点 |
| --- | --- |
| Node | `node\versions\22.22.2-6\node.exe` |
| Python | `python\versions\3.13.12\python.exe`（**目录名是 3.13.12，实际版本 3.13.14**） |
| PortableGit | `PortableGit\versions\{1.3.0, current}\`（**不在 PATH**，PATH 上的 git 是系统安装版） |

## 3. 仓数口径（2026-10-30 实测）

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

- **口径**：提「远端仓数」一律查索引 §5；提「本机发布区仓数」一律**现场实测**（本机是**部分检出**，
  远端 137 与本地 22 的差额是**尚未在此机检出**的仓，不是缺失）。
- ⚠ **与另一台的差异**：`calculator` 在本机发布区仍是独立目录，而 `DESKTOP-8RSV60V` 侧已把它
  收拢进 `arcade` 并转 `archived` ⇒ **两机发布区不同步**，以各机实测为准。

## 4. 运行时与工具链（2026-10-30 实测）

| 工具 | 现值 | 备注 |
| --- | --- | --- |
| Python | **`D:\Python314\python.exe` → 3.14.7**（**有 tkinter，Tk 9.0**） | 本机唯一带 tkinter 的解释器；选型清单见 §4.1 |
| Node | `C:\Users\13122\.workbuddy\binaries\node\versions\22.22.2-6\node.exe`（v22.22.2） | 便携工具链 |
| npm | 同目录 `npm.ps1` | 与 node 同版本目录 |
| git | **`C:\Program Files\Git\cmd\git.exe`**（系统安装版） | ⚠ 便携 `PortableGit` 也在机器上但**不在 PATH**，PATH 解析到系统版 |
| pwsh | **不在 PATH** | 本机无 PowerShell 7；`powershell` = 系统 Windows PowerShell 5.1 |

### 4.1 Python 解释器清单（2026-10-30 实测；选型前先测 `import tkinter`）

| 解释器 | 版本 | tkinter | 定位 |
| --- | --- | --- | --- |
| `D:\Python314\python.exe` | **3.14.7** | **有**（Tk 9.0） | ✅ **本机主 Python**（唯一带 tkinter 的） |
| `C:\Users\13122\.workbuddy\binaries\python\versions\3.13.12\python.exe` | 3.13.14 | **无** | WorkBuddy 便携工具链（**精简构建**）；路径里的 `3.13.12` 是**目录名**，判版本一律 `python -V` |
| `E:\projects\allin\.venv\Scripts\python.exe` | 3.13.14 | **无** | **本仓门禁套件实际使用的解释器**（`scripts/run_all_gates.sh` 钉死它） |
| `C:\Users\13122\AppData\Local\Microsoft\WindowsApps\python.exe` | —— | —— | ⚠ **Microsoft Store 占位符**，执行即报「Python was not found」—— **不是解释器**，脚本里别误选 |

- ⚠ **本机没有"随便哪个都行"的余地**：唯一带 tkinter 的是 `D:\Python314\python.exe`（3.14.7）；
  便携 3.13.14 与仓内 `.venv` **都无 tkinter**。
- ✅ **`repocheck` 在本机可跑**：`tools/repocheck/main.py` 的 `import tkinter` 位于 GUI 分支
  （`main.py:26`），CLI 路径经 `cli.py` / `scanner.py` / `rulebase.py`（三者均**不 import tkinter**）
  ⇒ **无 tkinter 也能跑 CLI 体检**；本仓门禁实测通过率 100%。
- ⚠ **选解释器先跑 `-c "import tkinter"`**，别只看版本号 —— 本机两个 3.13.14 都没有 tkinter。

## 5. 跨仓环境变量（2026-10-30 实测）

| 变量 | 本机状态 | 依据 |
| --- | --- | --- |
| `KONTAKT_TRANSCODE_ROOT` | **本机 0 个消费者** | `D:\musickit\remix\tools\make_{brass,bst,bww1}_wanted.py` 三脚本**均不读** `os.environ`（逐文件 grep 实测） |
| `RIME_SRC` | **本机无落点、无消费者** | 扫 `D:\`、`E:\` 与常见 RIME 路径（`AppData\Roaming\RIME` 等）均无 rime-ice |

- ⚠ **与 `DESKTOP-8RSV60V` 侧的记载不同**：那台记「`KONTAKT_TRANSCODE_ROOT` 由 `G:\repos\musickit`
  的 3 个脚本各读一次」，而本机这份检出**没有该读取**。原因是**两机检出不同步** ——
  本机 `D:\musickit` HEAD = `605efc4`（**2026-08-21**），三个脚本最后改动 2026-08-20；
  那台 `G:\repos\musickit` 的版本更新。⇒ **该变量属那台机器的现状，不适用本机**。
- **读法约定**：跨仓脚本引用数据根时**优先环境变量、未设则按 cwd 相对解析**（与 `调试铁律 5`「去符盘」同一口径）。

## 6. 推送与远端镜像（@`DESKTOP-KQABATS` 侧，2026-10-29 实测）

| 项 | 现值 |
| --- | --- |
| `remote.origin.url` | `https://gitee.com/siwpan/allin.git` |
| `remote.origin.pushurl` 条数 | **0**（`git config --get-all remote.origin.pushurl` 无输出） |
| 独立 remote | 无 |
| 推送口径 | **只推 Gitee 单核**，`git push` 走默认 url |
| 核对口径 | 只核 Gitee 一侧 |

- **作业口径**：核对 `git rev-parse HEAD` 与 Gitee 一侧 `git ls-remote origin refs/heads/master`
  逐字符相等、`rev-list --left-right --count` 为 0/0、工作树干净即可；**不要求 GitHub 侧在该机可见**。
  该机**不补配** GitHub pushurl（用户 2026-10-29 明确交代）。
- **另一台的对照**（口径相反，勿套用）：[`./DESKTOP-8RSV60V.md`](./DESKTOP-8RSV60V.md) §9。

---

*本文件是 `DESKTOP-KQABATS` 这台的**唯一**事实源。改前先复测，并把旧值以"（原 …）"形式留在同格内。*
