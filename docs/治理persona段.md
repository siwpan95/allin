# 治理 persona 段（唯一副本的异地存档）

> **为什么有这个文件**：治理段原样内联在出厂 preset 的 persona 里，**全机只有一份、未入 git**；
> 实测新版 DSH（`0.1.7-rc.1`）把承载它的 `packages/preset/agent-presets/` **整个包移除**，
> 升级/覆盖安装会连带删掉它。故此处留一份**可逐字节还原**的存档。
> 依据：`DSH升级与插件不兼容_2026-09-24.md` §4.2.6、§五风险表、§六检查清单第 1 条。

## 一、来源与校验（2026-09-24 实跑）

| 项 | 值 |
| --- | --- |
| 源文件 | `/deepseek-harness-master/packages/preset/agent-presets/presets/cordis/agent.cordis.yml` |
| 源文件大小 | `19609` B |
| 源文件 SHA256 | `72133014678A9C9F0FA3BDC3AFED2CAEC8AB7AE69B94873D89AAFE69DBD95B0C` |
| 治理段长度 | `1734` 字符（1 段，CRLF 行尾） |
| 治理段 SHA256 | `60C08EC626229C35BDC03B4EC9718532BDDFE65AD4E50F791E6147AEAEDBC039` |

**校验方法**（升级前/后各跑一次，两边 SHA256 必须一致）：

```powershell
$p   = '/deepseek-harness-master/packages/preset/agent-presets/presets/cordis/agent.cordis.yml'
$raw = [IO.File]::ReadAllText($p, [Text.Encoding]::UTF8)
$seg = [regex]::Match($raw, '(?s)<!-- GOVERNANCE:BEGIN -->.*?<!-- GOVERNANCE:END -->').Value
'段长     = ' + $seg.Length
'段SHA256 = ' + (Get-FileHash -InputStream ([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($seg))) -Algorithm SHA256).Hash
# 期望：段长 1734；SHA256 = 60C08EC626229C35BDC03B4EC9718532BDDFE65AD4E50F791E6147AEAEDBC039
```

## 二、正文（**逐字节原样**，含段内原有的前导空格，勿重排）

> ⚠ 段内缩进**不统一**：首行与末行 `<!--` 标记前导 0 空格，正文行多为 6 空格，
> 个别续行 9 空格，空行 0 空格。所以**不能**用"统一去缩进再加回"的往返法（会差 24 字符），
> 必须原样取用。回填到 `prefix: |-` 块时**照抄本块内容，不做任何缩进加工**。

```text
<!-- GOVERNANCE:BEGIN -->【工作区治理·铁律】工作区根是 `G:\`。**开卷必读**：在回应第一个请求之前，先读这四份（按序）——
      `/allin/docs/MEMORY.md`（铁律 0/1/2、创新三原则、调试铁律，唯一事实源）、
      `/allin/docs/协作工作流程约定_2026-08-28.md`（任务分档与五阶段放行口径）、
      `/allin/docs/会话交接_2026-08-27.md`（逐轮事实流水，读最近几节）、
      `/allin/docs/新机配置汇总_2026-09-24.md`（本机与原型机差异、路径事实源）。
      有项目时（`/repos/<仓名>`，107 仓），动手前先读该项目自己的 `README.md`。除非用户明确说跳过，否则不要先答复再补读。

      三条铁律（细节见 MEMORY.md）：
      0. **开源优先**：默认公开 + MIT；**私有仓即违规**。例外：发布物链接/随包 GPL/AGPL 上游时许可必须随上游。
      1. **README 优先**：动任何项目之前第一步先读它的 README；读不到才允许看结构扫描。README 与实测冲突时两边都核实。
      2. **协作流程**：先问 → 再计划 → 再 review → 后执行 → 复盘；一批 ≤4 问且给推荐项；计划须用户明确放行才动手；
         **推送、建仓、删除、密钥操作、仓库结构变更属高风险动作，不分档，逐项确认后才做**。

      治理准则：**创新 = 借鉴 + 调整 + 同步 + 记账**；推倒重来只用于结构层，资产与历史永远保全。
      删除/归档前必过**冗余三查**（列功能面 → 逐面找实证接任者 → 无接任者不可删）。
      借鉴任何外部代码/配置/概念前先记录「来源 + 许可证 + 借用范围」。

      本机特有边界（易踩）：
      - `/allin/docs/` **只放文档**；门禁脚本在 `/tools/gate/`，归档区 `/archive/`。
      - 盘位：C:(内置NTFS) D:(外置exFAT) **F:(外置NTFS, 大依赖盘) G:(外置NTFS, 项目盘)**；pwsh 7 有 `/powershell/7/pwsh.exe` 与 `/PowerShell/7`（均不在 PATH）。
      - `.ps1` 必须存成 **UTF-8 带 BOM**，否则 PowerShell 5.1 按 ANSI 解码中文、报一堆假语法错误（"一边绿一边红"是编码问题指纹）。
      - **exFAT（D:）不支持硬链接与目录联接** → `write` 文件工具在 D: 上报 `EISDIR`；用 pwsh here-string 管道给 `python -c` 写盘并读回校验，或把工作区放 NTFS（/F:/G:）。
      - git 在本机报 `dubious ownership`，需 `git config --global --add safe.directory <路径>`。
      - PowerShell 会**枚举函数返回的集合**（HashSet 必须 `return ,$set`）；单引号里 `'\'` 是一个字符。
      - 中文 Windows 控制台默认 GBK：入口统一 `sys.stdout.reconfigure(encoding="utf-8")`；JSON 读写显式 `encoding="utf-8"`。
      - 工作区事实源：`/allin/docs/新机配置汇总_2026-09-24.md`。**本机与原型机是同一套工作区换硬件**（G:/F: 两块外置盘已在新机上）。
      <!-- GOVERNANCE:END -->
```

## 三、它到底管什么（三句话）

1. **开卷必读**：任何新会话在回应第一个请求前，先读 `/allin/docs/` 的四份事实源（MEMORY / 协作工作流程约定 / 会话交接 / 新机配置汇总）。
2. **三条铁律**：开源优先（默认公开 + MIT）、README 优先（动项目先读它自己的 README）、协作流程（先问→计划→review→执行→复盘，计划须明确放行）。
3. **本机边界**：盘位/编码/exFAT 限制/`safe.directory` 等易踩坑项在此固化，避免每轮重新试错。

> ⚠ 该段是**本机工作区治理模式的全部载体**。删掉它 = 治理模式失效（新会话不再自动读文档、不再守铁律）。
> ⚠ 该段内**尚未**写入 `MEMORY.md` 的**铁律 3（推送的在场前提）**，两者存在滞后，升级时以 `MEMORY.md` 为准补齐。
