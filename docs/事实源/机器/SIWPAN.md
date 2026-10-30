# 机器事实 · `SIWPAN`（第三台接入机器，曾改名）

> **时点** 2026-10-30（**本文件由 `本机事实.md` 按机器分区建立** —— 原 §0.1 的第三台机器表迁入。）
> **时点** 2026-10-29（**@`SIWPAN` 实测登记** —— 该机与 `DESKTOP-KQABATS` 名对不上，按
>   `机器分区索引.md` §3 纪律第 4 条**先求证后定性**：用户确认 = **第三台机器，且曾改名（现名 `SIWPAN`）**。）
> **观测工具** `Get-Volume` · `Get-CimInstance Win32_*` · `git rev-parse --show-toplevel`
> **失效条件** 换机、加减盘、重装系统、换运行时版本后**立即失效**；每次涉及机器事实的动作前
>   **现场复测**，不要照抄本文件。
> **上位判据** [`../../规范/SPEC-006-机器与路径约定.md`](../../规范/SPEC-006-机器与路径约定.md)。
> **本文件只记录 `SIWPAN` 这台**；其他机器见 [`../机器分区索引.md`](../机器分区索引.md) §1。

---

## 1. 本机标识（@`SIWPAN` 实测，2026-10-29）

| 项 | 实测值 | 观测方式 |
| --- | --- | --- |
| **主机名** | **`SIWPAN`** | `Win32_ComputerSystem.Name`（该机 `$env:COMPUTERNAME` = `SIWPAN`，非空） |
| 用户目录 | `C:\Users\13122` | `$env:USERNAME` = `13122` |
| 厂商 / 主板 | WMI 原始值 **`X`**（未填充，不推断） | `Win32_ComputerSystemProduct` / `Win32_BaseBoard` |
| CPU | Intel Core **i7-9750H** @ 2.60GHz | `Win32_Processor` |
| 内存 | **31.9 GB** | `Win32_ComputerSystem.TotalPhysicalMemory` |
| 系统 | **Windows 11 专业版**，10.0.**26100** | `Win32_OperatingSystem` |
| 盘位 | **仅 C / D / E**（无 F: G:） | `Get-Volume` |
| 本仓仓根 | **`D:\projects\allin`** | `git rev-parse --show-toplevel` |
| 发布区 | **`D:\projects\repos`** | 与仓根同级 |

## 2. 与 `DESKTOP-KQABATS` 的实测差异（仅列事实，不作定性）

CPU 代际（9th i7-9750H vs 13th i5-13420H）、内存（31.9 vs 15.7 GB）、系统版本（专业版 26100 vs
家庭版 26300）、仓根/发布区盘位（D: vs E:）。**关系定性（用户 2026-10-29 求证）：`SIWPAN` 是第三台机器，
曾改名（现名 `SIWPAN`）。**

---

*本文件是 `SIWPAN` 这台的**唯一**事实源。改前先复测，并把旧值以"（原 …）"形式留在同格内。*
