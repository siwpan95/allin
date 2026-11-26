# `/tools/gate` — 可执行门禁（Executable Gates）

> 把「不许写死路径」「不许有未定义名」这类**口头规矩**变成**退出码**，并让它们能被复跑、被自检、被基线棘轮管理。
> 迁移记录：两个脚本原在 `/tools/gate/`（文档枢纽里混了脚本）；2026-09-24 文档枢纽纯文档化时迁到此处，内部默认路径同步更新。
> ⚠ **落点订正（2026-10-08 实测）**：本目录现有 `scan_hardcoded.ps1` / `check_undefined_names.py` / `docs_index.py` /
> `watchdog.py` / `check_ps1_bom.py` / `check_gate_drift.py` / `make_doc_aliases.ps1`；
> **`repo_hygiene.py` 不在本目录** —— 它是 `/tools/repo_hygiene.py`（仓根 `tools/` 下，见 §4）。
> 本节命令里写 `/tools/gate/repo_hygiene.py` 的话会得到 `No such file or directory`。

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

## 4. `repo_hygiene.py` — 仓库卫生门禁（2026-09-25 新增；**实体在 `/tools/repo_hygiene.py`**）

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
python /tools/repo_hygiene.py --repo /repos/cordis-table-app   # 单仓
python /tools/repo_hygiene.py --all                              # 全部（日常，用基线棘轮）
python /tools/repo_hygiene.py --all --no-baseline --list-all     # 普查全部存量
python /tools/repo_hygiene.py --all --write-baseline             # 存量上线
python /tools/repo_hygiene.py --selfcheck                        # 注入破坏用例自证
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

- 用法与口径的中文说明、以及「门禁化」在整个治理模式里的位置：见 `../../docs/规范/SPEC-105-治理模式建设指南.md` §S5、§4.1、§4.2。
- 本目录**不进**文档枢纽（那里只放文档）；门禁自身也遵守「默认值可被参数/环境变量覆盖」的约定。

---

## 8. `docs_index.py` — 文档枢纽「索引契约」门禁（2026-09-28 新增）

把 [`SPEC-005 文档枢纽契约`](../../docs/规范/SPEC-005-文档枢纽契约.md) 从**文字**变成**退出码**。
此前 `docs/` 的规矩（文档要登记、规范要有编号与效力头、记录要带日期）**一条门禁都没有** —— 这正是"指导性文档被当成产物"的机制性原因。

| 判据 | 拦什么 |
| --- | --- |
| **D1 登记完整** | `docs/` 下的文档没在 `INDEX.md` 里登记 |
| **D2 索引有效** | `INDEX.md` 登记了**不存在**的文件（分类导航用的目录链接不计） |
| **D3 规范头部** | `规范/SPEC-*.md` 缺八项字段之一（编号 / 效力 / 状态 / 生效 / 最后修订 / 适用面 / 承载体 / 引用格式） |
| **D4 命名规则** | 规范文件名**带日期**；记录文件名**没日期**且不是按月卷 |
| **D5 分类一致** | 文件所在目录与 `INDEX` 声明的类别不符 |
| **D6 ASCII 别名** | `spec/ facts/ records/ 历史/` 四个别名缺失或指向错误 |
| **D7 卷号连续** | `记录/交接/<YYYY-MM>.md` 有空洞，或某卷缺「覆盖区间」声明 |

```powershell
python /tools/gate/docs_index.py --no-baseline --list-all   # 普查（新规则上线时确认存量真的为 0）
python /tools/gate/docs_index.py                            # 日常（基线棘轮）
python /tools/gate/docs_index.py --selfcheck                # 自证：8 个真实破坏用例 + 1 个干净用例
python /tools/gate/docs_index.py --root <仓根> --no-aliases  # 指向别的仓 / 跳过 D6
```

**退出码**：`0` 干净 · `1` 基线外新增阻断 · `2` 用法错误 · `3` 环境错误。
**纪律**：`blocking` / `baseline` / `new` / `reported` / `skipped` 与**每类豁免计数**每次运行都打印，不静默丢弃；
豁免只在**判据上确实不适用**时添加，且必须配对应的反例用例（调试铁律 53）。

---

## 9. `make_doc_aliases.ps1` — 文档枢纽 ASCII 别名（2026-09-28 新增）

文档枢纽同时提供**中文目录真身**与 **ASCII 别名**（`规范/`↔`spec/`、`事实源/`↔`facts/`、`记录/`↔`records/`、`md/`↔`历史/`）。
内容**只存一份**；别名是 junction、**不入库**（入库即等于把同一份内容存两遍，违反「单一事实源」）。

```powershell
pwsh -File /tools/gate/make_doc_aliases.ps1          # 创建 / 修复（幂等）
pwsh -File /tools/gate/make_doc_aliases.ps1 -Check   # 只校验：四个别名就位且指向正确才 exit 0
```

**为什么必须能重建**：junction 不进 git —— **换机 / 克隆 / 目录改名后必须重跑**。
`docs_index.py` 的 D6 会在别名缺失时报红，所以"忘了重建"不会静默通过。`.gitignore` 已显式忽略这四个别名目录。

---

## 与 `/tools/gate/` 的关系（2026-09-26 补充）

本目录是**随仓分发的副本**，与工作区内 `/tools/gate/` 内容一致。

- `/tools/gate/` —— **工作副本**：日常运行、审计明细落盘（`audit/`）、被脚本互相调用时的默认路径。
- `/allin/tools/gate/`（本目录）—— **分发副本**：随公开仓 `siwpan/allin` 发布，
  外部使用者克隆即得，不依赖本机工作区布局。

**修改时两边都要同步**（本目录的存在正是为了让门禁能被外部复现）。
落点差异说明：文档里若出现 `/tools/gate/...` 的默认路径，指的是**工作副本**；
从本仓取用时请按自己机器调整，或用脚本参数覆盖。

---

## 与 DSH 仓 `governance/` 的关系（2026-09-27 新增，2026-10-26 已并入本仓）

> **2026-10-26 状态**：`siwpan/deepseek-harness` 的治理内核（Python 门禁运行时 + 15 条门禁 `g00-meta`~`g15-docs-contract`）**已整体并入本仓门禁套件**（2026-11-25 起该套件住独立仓 `allin-governance`、随 PyPI 包分发），原 DSH 远端已删除。
> 并入后**只有一个落点**（本仓内 `tools/gate/` 与 `tools/gate/governance/` 两棵互补的门禁树），判据同源、形态不同，不是重复建设：

| 落点 | 形态 | 谁在用 |
| --- | --- | --- |
| 本目录（`tools/gate/`，随本仓 `siwpan/allin` 分发） | PowerShell + Python 脚本，多仓扫描、基线在 `audit/` | 本工作区的日常巡检 |
| `allin-governance` 包内 `_gatesuite/`（由 DSH 治理内核并入，2026-11-25 迁出本仓） | **一份 Python 门禁运行时 `runtime/govlib.py` + 15 条门禁**（`g00-meta`~`g15-docs-contract`），单仓、跨平台、每条自带 `--selfcheck`；聚合入口 `node scripts/gates.mjs`（薄壳从包内取 `run.ts`；Node ≥ 22.18 原生类型擦除，不需要 tsx；或根 `package.json` 的 `check:governance`） | 本仓自身的治理门禁，经 `check:governance` 驱动 |

> ⚠ **落点订正**：DSH 治理内核原在 `/repos/deepseek-harness/governance/`（本机去符盘形式）；2026-10-26 已整体并入本仓 `tools/gate/governance/` 并删除 DSH 远端。路径一律以 [`../../docs/事实源/机器分区索引.md`](../../docs/事实源/机器分区索引.md) 的实测值为准。

- **规则事实源是本仓 `docs/规范/`**（2026-09-28 前写 `docs/MEMORY.md`，该文件现已降为路由页）：
  铁律 → `SPEC-001`，调试铁律 → `SPEC-004`，治理准则 → `SPEC-003`，文档枢纽契约 → `SPEC-005`。
  `governance/RULES.md` 是「规则 → 门禁」的**映射表与引用契约**，新增门禁时必须同步改它（`g00-meta` 会校验门禁 id 是否被收录）。
- **判据同源、实现不同**：如死根路径判据在本目录是 `scan_hardcoded.ps1`（只看盘符 + 多仓），
  在 DSH 侧是 `g01-paths`（泛化到「绝对路径父目录是否存在」，跨平台）；
  文档索引契约在本目录是 `docs_index.py`，在 DSH 侧是 `g15-docs-contract`。**改一边时先看另一边是否也要改**。
- 门禁契约（本仓侧的新要求）：每条门禁支持 `--selfcheck`（含**真实破坏用例**）与
  `--baseline/--no-baseline/--write-baseline/--list-all` 四开关，豁免与跳过**计数打印不静默丢弃**；
  DSH 侧由 `g10-failloud-probe` 反过来验证「拿到坏输入必须响亮报错」。

## 10. `check_gate_drift.py` — 门禁双落点漂移检查（2026-10-06 新增）

**为什么存在**：同一个门禁在两个落点（`/allin/tools/gate` 与 `/tools/gate`）会**各自演化**。
`SPEC-004 §调试铁律 64` 记过一次因漂移差点丢东西；2026-10-06 又实测到 `scan_hardcoded.ps1`
**互补漂移**（仓内版已修 `core.quotepath=false` / PS 5.1 GBK 中文豁免失效 / `GetExtension` 抛异常三处，
工作副本还写死 `G:\tools\gate` 且 selftest 是旧变体）——两份**都能跑、都"看着对"**，
只有人工 diff 才看得见（而且第一遍还把方向看反了）。**纪律不如门禁。**

```powershell
python /tools/gate/check_gate_drift.py              # 日常：两侧逐个比对，不一致即 exit 1
python /tools/gate/check_gate_drift.py --selfcheck  # 自证：EOL 差异判绿 / 真漂移判红 / 缺对端 SKIPPED
                                                    #      / 单侧存在判"归属差异" / 同目录守卫
```

判据（严格照 `调试铁律 12`）：**先归一化 EOL，再逐字节比** —— 跨副本比对不归一化换行符会得出假差异
（实测差 438 字节全是 CRLF/LF）。只在单侧存在的文件记"**归属差异**"（不算漂移，需人判断）；
对端目录不存在记 `SKIPPED (not a pass)`（换机后没建工作副本时**不许假绿**）；
两侧解析到**同一目录**则**响亮失败**（exit 2）——第一版就是这样"自己跟自己比"而**恒报一致**的
（`调试铁律 65`：恒返回同一值的判据不构成证据，**门禁自己也会犯**）。

> 新增门禁脚本时**必须把文件名加进 `TRACKED`**，否则它会静默漏检。

## 11. 提交前钩子（`hooks/pre-commit`，2026-10-06 新增）

**为什么存在**：`SPEC-004 §调试铁律 66` —— **编辑工具会静默剥掉 `.ps1` 的 UTF-8 BOM**，
`pwsh` 下看不出、**PowerShell 5.1 必炸**（中文乱码 + 假语法错误）。`check_ps1_bom.py` 只能事后扫存量，
本钩子把它提前到**提交前拦住**（该坑三天内被踩三次，含 agent 自己）。

```powershell
# 每台机器/每个 clone 启用一次（core.hooksPath 是仓库本地配置，不入库）
git config core.hooksPath tools/gate/hooks
```

行为：**仅当暂存面含 `.ps1`** 时跑 `check_ps1_bom.py --root .`；不含则秒过（不白等）。
不合规 ⇒ 拒绝提交并打印补 BOM 的**字节级**命令；门禁脚本缺失或跑不起来 ⇒ **明确 FAIL**（不许假绿）。

> 双向实测（2026-10-06）：暂存只有 `.txt` ⇒ 放行；暂存"缺 BOM 的中文 `.ps1`" ⇒ `[pre-commit] FAIL` 且**提交未发生**。
> 顺带实证：**`pathlib` 的 `Read/WriteText(encoding="utf-8")` 往返会保留 BOM**，而编辑工具会剥掉
> ⇒ 批量改 `.ps1` 能用脚本就用脚本。

**`commit-msg` 钩子（2026-11-26 新增，`hooks/commit-msg`）**：给提交信息追加
`Machine: <STEM>` trailer（Git 原生 trailer，`git interpret-trailers --parse` 可机读）。
起因是本仓 author/committer 恒为同一个共享身份，2026-11 有 82% 的提交事后查不出机器 ——
归属只能在**提交那一刻**记下来。行为：**幂等**（已有该 trailer 就跳过，两条钩子路径同时生效也不会叠行）；
**绝不阻断提交**（注入失败只警告，漏写的由判据在跑批时判红）。

```bash
# 两条路径互斥（设了 core.hooksPath 后 git 不看 .git/hooks），装哪条见安装脚本：
bash scripts/install_git_hooks.sh              # A. 零依赖：core.hooksPath=tools/gate/hooks
bash scripts/install_git_hooks.sh --pre-commit # B. 需已装 pre-commit（.pre-commit-config.yaml 里有 local 钩子）
bash scripts/install_git_hooks.sh --check      # 看当前到底哪条生效（"装了但没生效"是本仓老坑）
```

> **网页端提交绕过钩子**：Gitee/GitHub 网页编辑、PR 的 Squash and merge 都不经过本地钩子。
> 所以判据（`check_machine_trailer.py`）不依赖钩子，而是跑批时判 —— 并把
> "技术上去不掉/带不上 trailer"的 merge 与 squash **单列**，不与"忘了写"混为一谈。


## 12. registry 之外的判据（例外必须显式、可读、单点维护）

`governance/registry.json`（包内 `<site-packages>/allin_governance/_gatesuite/registry.json`）
描述的是**「判仓库」的 20 道套件契约**（g00–g20，缺 g02）。有些判据**不在这份契约里**，
但它们确实在跑、确实会红 —— 不能靠"代码里没写"来当成"不存在"（那正是死门的生成方式）。

本节是它们**唯一的清单**。`tools/gate/check_blind_gates.py` 直接**从本节的机器可读块读取**，
不硬编码任何一条 —— 以后新增 registry 外的判据，只有这一处要改。

<!-- registry-external-gates:begin -->
# 格式：每行 `id | 入口文件（相对本目录） | 为什么不在 registry`；# 开头为注释，空行忽略。
g21-agent-parity | agent_parity.py | 编排层判据：routes.yaml ⇄ SKILL.md 锚点 ⇄ GOVERNANCE 段锚点三方对账 + skill 入口存在性。它判的是**载体之间**是否一致，不是判仓库；registry 是「判仓库」的 20 道套件契约，装不下它。已由 run_all_gates.sh 与 npm run check 两处接线（本轮改动接进 npm check）
check_blind_gates | check_blind_gates.py | 元判据：判的是那 20 道门禁**有没有真的量了东西**（scanned 0 + exit 0 + 无 SKIP ⇒ 判红），以及它们的自检是否两半都验。判据对象是门禁自己，不是被管仓；不占 g 编号 —— 给它编号会让「20 道」这个被 README / ADR / SVG 多份文档引用的计数漂移，一个为了防漂移而引入的漂移源是净负收益
check_machine_ledger | check_machine_ledger.py | 月账一致性判据：A 月账对交接卷的节引用必须落在真实存在的节上（D9 只判 docs/ 树内锚点、D18 只判交接卷最新一节有没有标 @机名，没有一道判「月账引的那一节还在不在」）；B 每份月账卷首必须声明归属通道（本机自持 / 代整理+待该机复核），「代整理」不配复核承诺就是拿铁律 6 的合法通道当免检章；C 「未归属提交」一节的数字必须与 git rev-list --count 实测一致。判的是**各机自持的运行时记录**，且 B 条的作用域是异机卷（与 g20「只判本机分区」相反），装不进「判仓库」的套件契约。三条各配负对照 + --mutate a/b/c 变异验证
conflict-markers | check_conflict_markers.py | 冲突标记残留判据：`git ls-files` 的文本文件行首出现 `<<<<<<<` / `|||||||` / `>>>>>>>` 即红（不要求尾随空格 —— 被编辑器吞掉空格的残骸同样是没清干净）；`=======` 只在同文件已命中前三者之一时才算（单独判会把 Markdown 的 setext 标题与分隔线全打成误报）。它判的是**文件内容里的合并残骸**，不是仓库结构契约：事故现场 `docs/记录/交接/2026-11.md` 残留一行 `||||||| parent of fbb7940` 长期存活，而 docs_index（索引契约）/ relative_refs（链接）/ g15（节结构与锚点）三类判据都不看它，registry 里也没有一处安放这条口径。6 例负对照（含代码块内仍红、`=======` 单独不判）
machine-trailer | check_machine_trailer.py | 机器归属一致性判据：凡改动 `docs/事实源/机器/<STEM>/…` 的提交必须带 `Machine: <STEM>` trailer（铁律 6：只有该机可改自己的分区 ⇒「改了谁的分区」与「我是哪台机」必须一致），缺则红、跨机越权红、机名拼错也红（拼错放行等于给拼写错误发免检证）。它判的是**提交历史里的跨机归属声明**，不是「仓库长得合不合规」——registry 装的是后者；而且 merge / 平台 squash 属「技术上无法带 trailer」，必须单列而不能与「忘了写」混为一谈，这条区分口径在套件契约里无处安放。只判 EFFECTIVE_FROM（2026-12-01）之后的提交，历史不追溯（D18/D19 同先例）；14 例负对照 + 变异探针（摘掉判红分支后自检必须变红）
<!-- registry-external-gates:end -->

**为什么 g21 不登记进 registry**：登记会把"20 道"改成 21，牵连 SPEC-204 架构图、SVG 对账、
`g00` 契约与多处文档数字 —— 为一个归属问题制造一轮大涟漪，不值得。**归属靠本节显式列出即可，
不靠编号。** 代价是要接受一条纪律：新增 registry 外判据必须在本节登记，否则
`check_blind_gates.py` 无法称它"已接线"（它只认本节声明过的条目）。

**为什么 `check_blind_gates.py` 不占 g 编号**：g00–g20 判被管仓，它判门禁自己，属编排层。
把它编进 g 序列，等于把「判据的判据」混进「判据」的清单。
