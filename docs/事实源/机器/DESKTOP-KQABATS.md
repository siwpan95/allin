# 机器事实 · `DESKTOP-KQABATS`

> **时点** 2026-10-30（**本文件由 `本机事实.md` 按机器分区建立** —— 原 §0.1 的本机表与 §9 的本机侧口径迁入。）
> **时点** 2026-10-29（**实测登记**：机器名 `DESKTOP-KQABATS`；`$env:COMPUTERNAME` **为空**，
>   取机器名须用 `Win32_ComputerSystem.Name`；`pushurl` **0 条** ⇒ 只推 Gitee 单核。）
> **观测工具** `Get-Volume` · `Get-CimInstance Win32_*` · `git rev-parse --show-toplevel` ·
>   `git config --get-all remote.origin.pushurl`
> **失效条件** 换机、加减盘、重装系统、换运行时版本后**立即失效**；每次涉及机器事实的动作前
>   **现场复测**，不要照抄本文件。
> **上位判据** [`../../规范/SPEC-006-机器与路径约定.md`](../../规范/SPEC-006-机器与路径约定.md)。
> **本文件只记录 `DESKTOP-KQABATS` 这台**；其他机器见 [`../机器分区索引.md`](../机器分区索引.md) §1。

---

## 1. 本机标识（2026-10-29 实测）

| 项 | 实测值 | 观测方式 |
| --- | --- | --- |
| **主机名** | **`DESKTOP-KQABATS`** | `Win32_ComputerSystem.Name`（⚠ **不要用 `$env:COMPUTERNAME`**，本机该变量**为空**） |
| 用户目录 | `C:\Users\13122` | `$env:USERNAME` = `13122` |
| 厂商 / 主板 | Lecoo / `ADPT1L` | `Win32_BaseBoard` |
| CPU | 13th Gen Intel Core i5-13420H | `Win32_Processor` |
| 内存 | 15.7 GB | `Win32_ComputerSystem.TotalPhysicalMemory` |
| 系统 | Windows 11 家庭版 中文版，10.0.26300 | `Win32_OperatingSystem` |
| 盘位 | **仅 C / D / E**（**无 F: G:**） | `Get-Volume` |
| 本仓仓根 | `E:\projects\allin` | `git rev-parse --show-toplevel` |
| 发布区 | `E:\projects\repos` | 与仓根同级 |

> **本机尚未补录的独有事实**（见 [`../机器分区索引.md`](../机器分区索引.md) §1 与 8RSV60V 文件的对应章节）：
> 工作区落点细节、`/repos` 仓数、运行时与解释器清单、跨仓环境变量 —— **待复测补录**。

## 2. 推送与远端镜像（@`DESKTOP-KQABATS` 侧，2026-10-29 实测）

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
