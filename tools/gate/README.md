# `/tools/gate` — 可执行门禁（Executable Gates）

> 把「不许写死路径」「不许有未定义名」这类**口头规矩**变成**退出码**，并让它们能被复跑、被自检、被基线棘轮管理。
> 迁移记录：两个脚本原在 `/tools/gate/`（文档枢纽里混了脚本）；2026-09-24 文档枢纽纯文档化时迁到此处，内部默认路径同步更新。

## 1. `scan_hardcoded.ps1` — 死根路径门禁

**判定口径**：由浅到深检查「路径的父目录是否存在」——不存在即**死**（只看盘符/用户名会把 `Desktop\xxx` 已删的路径误判为活）。
**豁免**：系统路径白名单、URL、测试夹具、注释与用法示例、**行内审计注记**（写明「已失效/已不存在/占位/源自上游」等）。
**基线棘轮**：存量命中一次性写入基线，日常只拦新增 —— 让门禁可以**立刻上线**，不必先完成大清理。

```powershell
# 日常：只拦新增（CI/收尾用，退出码 0=干净 1=有新增阻断）
pwsh -File /tools/gate/scan_hardcoded.ps1

# 存量上线：把当前全部阻断项写进基线（随后退出码恒为 0）
pwsh -File /tools/gate/scan_hardcoded.ps1 -WriteBaseline

# 普查：忽略基线看全部存量（配合 -ListAll 打印明细）
pwsh -File /tools/gate/scan_hardcoded.ps1 -NoBaseline -ListAll

# 把文档/配置类命中也算阻断（默认只报告不阻断）+ 自测门禁本身
pwsh -File /tools/gate/scan_hardcoded.ps1 -IncludeDocs
pwsh -File /tools/gate/scan_hardcoded.ps1 -SelfTest
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `-Repos` | 全部 | 只扫指定仓（逗号分隔；内部会 `-split ','`，兼容 `pwsh -File` 的字符串绑定） |
| `-ReposRoot` | `G:\repos` | 仓根 |
| `-Path` | — | 额外扫描的非 git 目录 |
| `-Baseline` | `/tools/gate/audit/hardcoded_gate_baseline.csv` | 基线文件（不存在=空基线） |
| `-OutCsv` | `/tools/gate/audit/hardcoded_gate_<时间戳>.csv` | 明细落盘（静默模式与 0 命中时不落盘） |
| `-IncludeDocs` / `-Strict` / `-Deep` / `-ExcludeGenerated` / `-ListAll` / `-Quiet` | 关 | 见脚本头注释 |

**退出码**：`0` 干净 · `1` 有新阻断 · `2` 用法错误 · `3` 环境错误。

## 2. `check_undefined_names.py` — AST 未定义名检查

`py_compile` 只查语法，查不出「用了没导入」「`str` 与 `Path` 做 `/`」这类运行期才炸的缺陷。本脚本用 AST 收集 `Load` 名 vs `import`/赋值/`def`，报告**全文件从未定义过**的名字。

```powershell
python /tools/gate/check_undefined_names.py --repo /repos/musickit      # 只查该仓「paths)」提交改过的 .py
python /tools/gate/check_undefined_names.py --repo /repos/pluginplayer
```

## 3. 基线目录 `audit\`

| 文件 | 说明 |
| --- | --- |
| `hardcoded_gate_baseline.csv` | 死根路径门禁的当前基线（**0 字节 = 存量已清零**，2026-09-23 达成） |
| `hardcoded_gate_<时间戳>.csv` | 历次非静默运行的明细 |
| `hygiene_baseline.csv` | **仓库卫生门禁**基线（2026-09-25 首次建立：674 条存量） |
| `hygiene_fullscan_<日期>.json` | 卫生门禁全量普查的机读结果（按检查项分类，便于定位） |
| `watchdog_<日期>.json` | 看门狗巡检快照（盘健康 + 仓完整性 + 同步漂移） |

**纪律**：基线只在「存量确实清完」时刷新为 0；刷新前用 `-NoBaseline -ListAll`（PS）或
`--no-baseline --list-all`（py）看过全部存量，否则棘轮会把新增悄悄吞掉。
历史审计产物（含早期大 CSV）不放在这里 —— 见 `/archive/docs-nondoc-20260924/audit-fragments/`。

---

## 4. `repo_hygiene.py` — 仓库卫生门禁（2026-09-25 新增）

把 `docs/gitee推送流程_2026-09-25.md` §1 的「仓库卫生六项」从**文字**变成**退出码**。
此前该要求 6 项 → **0 项有门禁**（2026-09-25 实测确认）。

| 项 | 判据 |
| --- | --- |
| H1 LICENSE 唯一 | 判**路径**：仓根须有；`_ref/ThirdParty/LICENSE` 之类同样可见（只判 basename 会漏） |
| H2 无第三方源码目录 | `_ref/ vendor/ node_modules/ third_party/`（跟踪面内） |
| H3 无产物目录 | `output/ state/ cache/ dist/ build/ release/`（跟踪面内） |
| H4 无归档/大文件 | `*.zip *.tar.gz *.7z`；单文件 > 5 MiB（**blob 口径**，避开 `.gitattributes` 的 CRLF 坑） |
| H5 无凭据 | 令牌**本体子串**（从凭据文件读，不回显）+ 通用**形态** + URL 内嵌凭据 |
| H6 文档一致性 | `docs/` 下的借鉴记账须含「上游URL + 许可证 + 不入仓声明」 |
| H7 仓名=目录名 | 本地目录名须等于 origin 仓名 |
| H8 行尾一致性 | 「内容与库内逐字节相同却被标 modified」的假改动检测 |

```powershell
python /tools/gate/repo_hygiene.py --repo /repos/cordis-table-app   # 单仓
python /tools/gate/repo_hygiene.py --all                              # 全部（日常，用基线棘轮）
python /tools/gate/repo_hygiene.py --all --no-baseline --list-all     # 普查全部存量
python /tools/gate/repo_hygiene.py --all --write-baseline             # 存量上线
python /tools/gate/repo_hygiene.py --selfcheck                        # 注入破坏用例自证
```

**退出码**：`0` 通过 · `1` 基线外新增阻断 · `2` 用法错误 · `3` 环境错误。

**性能纪律（实测沉淀）**：
- H4 取体量曾**逐文件 spawn `git cat-file`**，几万文件 = 几万次进程创建，109 仓跑不完；
  改 `git ls-tree -r -l` 一次取全。
- H5 曾**无条件读入每个跟踪文件全文**，采样 15 仓时独占 11.1s/13.8s；改为跳过二进制后缀
  （凭据不会藏在 PNG/EXE 里，这是**判据上正确**的省略）+ 只读前 2 MiB。
- 优化后 109 仓全量 **106.6s**（此前 >600s 未完成）。

**误报治理（门禁的可信度纪律）**：误报多了门禁就没人看，等于失效。首次普查后按实证收紧两处——
- H6 曾匹配 README 里的「## 源码来源」标题（说明依赖来自哪个包管理器，不是借鉴记账）
  → 收窄为**只判 `docs/` 下的专档**，英文关键词加词边界（曾匹到 "Reference"）。
- H5 曾把 `password = 'Please enter your password'`（D&D 规则书 HTML 说明文字）判成凭据；
  又曾把 `...&token=<uuid>`（URL 查询参数）判成凭据 → 加「值须自身像密钥」判定 + 「键名
  不得紧跟 `&`/`?`/`/`」负向断言。**两处都补了反例用例**，防止日后回退。

---

## 5. `check_ps1_bom.py` — PowerShell 编码门禁（2026-09-25 新增）

`/tools/README.md` 纪律 1「`.ps1` 必须存成 UTF-8 带 BOM」此前**只是文字**。
2026-09-25 实测当场踩中：编辑工具改脚本后 **BOM 被剥掉**，导致 `scan_hardcoded.ps1`
在 PowerShell 5.1 下报假语法错误（`Unexpected token '}'`）——**该门禁在 PS 5.1 下完全不可用**。

```powershell
python /tools/gate/check_ps1_bom.py                       # 扫默认根
python /tools/gate/check_ps1_bom.py --fix                 # 就地补 BOM（默认干跑）
python /tools/gate/check_ps1_bom.py --selfcheck           # 自证
```

判据：含非 ASCII 却无 BOM → 阻断；纯 ASCII 无 BOM → 合法（不做无谓要求）；
有 BOM 但内容非合法 UTF-8 → 阻断（BOM 会掩盖真实编码损坏）。

---

## 6. `watchdog.py` — 工作区看门狗（2026-09-25 新增）

**起因是真实事故**：2026-09-25，G: 盘（外置 WD，Disk 3）全天持续 `disk 事件 153`（IO 重试），
19:07 触发 `Ntfs 事件 132`「短时间内发生太多修复事件」+ 9 次「卷 G: 上的文件系统结构现在已经
修复」——**NTFS 在线自愈在写入过程中改坏了 git 对象**，造成 4 个仓损坏（`allin`、`novel`、
`novel-down`、`ncmturnmp3`）。**全部是事后人工挖出来的，没有任何机制第一时间叫。**

| 职责 | 判据 |
| --- | --- |
| W1 盘健康 | 卷 dirty 位 / HealthStatus；**事件日志里的 IO 重试与 NTFS 自愈计数** |
| W2 仓完整性 | `.git/objects` 可读性（**事故指纹**）、`HEAD^{commit}` 可解、fsck 非 dangling 问题 |
| W3 同步漂移 | 本地 HEAD vs 远端 ref（**只信 `git ls-remote`**，不信陈旧的 remote-tracking ref） |

```powershell
python /tools/gate/watchdog.py                # 全量巡检
python /tools/gate/watchdog.py --quick        # 只做盘健康 + HEAD + 同步（跳过 fsck）
python /tools/gate/watchdog.py --selfcheck    # 注入破坏用例自证
```

**关键判据（实测决定，别改错）**：
- **SMART/`Get-PhysicalDisk` 会报 `Healthy` 而盘正在重试 IO** —— 所以必须看事件日志，
  只看 SMART 会得出「全绿」的错误结论。
- 仓完整性**必须用 `HEAD^{commit}`**：`rev-parse --verify HEAD` **只解析 ref 名、不验证对象存在**，
  导致「objects 全删」「HEAD 写坏」两个破坏用例都被判 OK（自检当场抓出）。
- 无法判定时记 `SKIP` 并计入告警，**不当作通过**（如 `C:` 的 dirty 位因权限读不到）。

---

## 7. 与文档枢纽的关系

- 用法与口径的中文说明、以及「门禁化」在整个治理模式里的位置：见 `/allin/docs/allin治理模式_建设指南.md` §S5、§4.1、§4.2。
- 本目录**不进**文档枢纽（那里只放文档）；门禁自身也遵守「默认值可被参数/环境变量覆盖」的约定。

---

## 与 `/tools/gate/` 的关系（2026-09-26 补充）

本目录是**随仓分发的副本**，与工作区内 `/tools/gate/` 内容一致。

- `/tools/gate/` —— **工作副本**：日常运行、审计明细落盘（`audit/`）、被脚本互相调用时的默认路径。
- `/allin/tools/gate/`（本目录）—— **分发副本**：随公开仓 `siwpan/allin` 发布，
  外部使用者克隆即得，不依赖本机工作区布局。

**修改时两边都要同步**（本目录的存在正是为了让门禁能被外部复现）。
落点差异说明：文档里若出现 `/tools/gate/...` 的默认路径，指的是**工作副本**；
从本仓取用时请按自己机器调整，或用脚本参数覆盖。