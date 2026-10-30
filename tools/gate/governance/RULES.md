# 治理规则 → 机械保障 映射（RULES.md）

本文件是 `governance/` 的**规则事实源**：左边是这条分发版本要遵守的规则，右边是**哪条门禁把它变成了退出码**。
主代理与维护者改规则时改这里；改判据时改对应门禁脚本与它的自检用例。

## 一、引用契约（先读，避免指错）

规则来自 `siwpan/allin` 治理仓的 `docs/`（该仓是规则的事实源，本目录是它的**可执行落地**）。**2026-09-28 起该仓的文档枢纽已分四类**：`规范/`（约束性，带 `SPEC-NNN` 编号）· `事实源/`（活台账）· `记录/`（证据流水，**不作为约束**）· `md/`（历史树，冻结）。引用必须带限定词：

| 写法 | 含义 | 例子 |
| --- | --- | --- |
| `SPEC-NNN` | **规范编号**（引用规范的首选形式，稳定不随改名漂移） | `SPEC-005` = 文档枢纽契约 |
| `铁律 N`（0–5） | `SPEC-001` 内的**命名铁律** | `铁律 5` = 路径不写死盘符 |
| `调试铁律 N`（**1–62**） | `SPEC-004` 内的工程纪律编号列表（事故驱动沉淀） | `调试铁律 53` = 门禁的排除项最危险 |
| `OPS-*` | 操作规范（`SPEC-10x`）里的清单式要求 | `OPS-E8` = 新建仓收尾四步 |

> ⚠ **两处易错**：① 裸写「铁律 4」同时匹配命名铁律与调试铁律，**引用一律带限定词**；
> ② `调试铁律` 实际末号是 **62** —— 本文件与治理 persona 段里若仍见「1–58」，那是 2026-09-27 之前的过期值，**以 `SPEC-004` 为准**。

**本仓口径（2026-09-27 用户拍板）**：`siwpan/deepseek-harness` 是**独立分发版本**，上游 GitHub 官方仓仅作参考，本仓可自由分叉、可改既有文件；本目录的规则与门禁都按「分发版自有资产」维护。

## 二、门禁契约（g00-meta 逐条机械校验）

`governance/registry.json` 里登记的每个门禁，必须满足下面全部条款，否则 `g00-meta` 变红：

| 条款 | 判据 | 为什么 |
| --- | --- | --- |
| 注册完整 | 条目含 `id`/`title`/`script`/`tier`/`rules`/`platforms`/`requires`/`selfcheck` 八个字段 | 少了字段就没人能复跑它 |
| 脚本存在 | `script` 指向的文件在仓内 | 注册表不是愿望清单 |
| 契约完整 | `--help` 必须列出 `--selfcheck`、`--quiet`、`--baseline`、`--no-baseline`、`--write-baseline`、`--list-all` | 门禁要能**列出来、单独跑、自检**、能被基线棘轮管理 |
| 自证有效 | `--selfcheck` 退出 0，且输出末行含 `SELFCHECK {"caught":N,"clean":M,"misreports":K}`，要求 `N≥1`、`M≥1`、`K==0` | 「打印了」不等于「抓到了」；只能单独跑才过的自检是缺陷 |
| 规则可溯 | 门禁 id 出现在本文件（RULES.md） | 规则必须能找到执行它的那条门禁 |

**退出码词汇（全部门禁统一）**：`0` 干净 · `1` 基线之外的新阻断 · `2` 用法错误 · `3` 环境错误（缺解释器、缺 git 工作树等）。
**SKIP 不是通过**：门禁跑不了的能力（如非 Windows 上的盘健康检查）必须打印 `SKIPPED (not a pass)` 并计数。

## 三、已实现门禁（随批 1 上线）

| 门禁 id | 覆盖规则 | 判据要点 | 基线 |
| --- | --- | --- | --- |
| `g00-meta` | 调试铁律 30 / 41、OPS-G15、OPS-P3 | 读注册表，逐个校验契约、跑 `--selfcheck`、核对 RULES.md 收录 | 无（必须恒绿） |
| `g01-paths` | 铁律 5、调试铁律 26 / 34 / 53、OPS-E3 | 判「路径的父目录是否存在」得出死路径；按平台归属判「写死本机路径」；命中三分（**只有 CODE 有效行阻断**；`.md/.html` 等文档扩展名只报告不阻断）；每类豁免与跳过都计数打印 | `governance/baseline/g01-paths.txt`（当前为空：存量已清零） |
| `g03-credentials` | 铁律 0、治理准则·敏感信息、调试铁律 52、OPS-P1 / OPS-E8 | 判 `git grep --cached` 的**索引内容**（不是可能有部分暂存的落盘文件）：私有密钥块、厂商令牌形态、URL userinfo、Bearer 头、密钥型赋值；另扫 `.git/config` **全文**（含 `branch.*.remote` 里的令牌与 `credential.*.helper` 空值） | `governance/baseline/g03-credentials.txt`（9 条历史存量：门禁与 `repo_hygiene.py` 的自测夹具、交接记录里引用的合成串，均已复核为误报） |
| `g04-push-evidence` | 铁律 3、调试铁律 25 / 37 / 47、OPS-P8 / OPS-E8 | 远端 URL 无凭据；同步状态**只由 `git ls-remote` 判定**（`IN_SYNC` / `LOCAL_AHEAD` / `REMOTE_AHEAD` / `DIVERGED`）；**远端提交对象不在本克隆时先补取该分支的远端跟踪 ref 再判**（只动 `refs/remotes/*`，本地分支、索引、工作树一律不动；2026-10-29 起），补取失败记 `UNVERIFIED` + **SKIP（不是通过）**，绝不把「没 fetch 过」报成分叉；`DIVERGED` 阻断（分叉后下一步通常是强推），本地领先与远端领先只记账；网络不可达记 **SKIP（不是通过）** | `governance/baseline/g04-push-evidence.txt`（当前为空） |
| `g05-hygiene` | 铁律 0 / 4、治理准则·敏感信息、调试铁律 54、OPS-P2 / C3 / C4 / G3 | 只判**被跟踪**面：根三件套（LICENSE / README.md / .gitignore）、`.gitignore` 必须覆盖凭据面（`.env` / `*.pem` / `*.key` / `__pycache__/`）、无产物目录与字节码/日志/`*.egg-info` 入索引、无超阈值大文件（阈值按本仓实测定为 5 MiB，最大文件 ~2.3 MB）、归档目录必须有 README/MANIFEST | `governance/baseline/g05-hygiene.txt`（当前为空） |
| `g06-numbering` | 调试铁律 45、OPS-G4 / G5 / D7 | 序号版本文件（`v0.*`、`v1.*`…）必须从最小号起连续；中英配对文档的**列表形状必须逐项相等**（列表数、编号标签、条目数），代码围栏内不计 | `governance/baseline/g06-numbering.txt`（当前为空） |
| `g07-doc-freshness` | 调试铁律 57 / 58、OPS-D6 | 文档在**开头 20 行内第一人称自称**环境事实源/快照时，必须带时点；自称「快照」的还必须带失效或「以…为准」条款；Agent Notes 与 vendor 整体排除 | `governance/baseline/g07-doc-freshness.txt`（1 条：2026-08 交接卷自称快照却缺失效条款，已复核） |
| `g08-deletion-evidence` | 治理准则·冗余退役三查、OPS-G5 / G13 | 判指定提交（默认 `HEAD`，可 `--range A..B`）**删了文件却没有「功能面 × 接任者」对照表**（表头标记 + ≥2 行表格）→ 阻断；显式 `gov-deletion: allow` 可豁免并留痕 | `governance/baseline/g08-deletion-evidence.txt`（当前为空） |
| `g14-preset` 的 **profile 探针**（2026-09-27 追加） | 铁律 5、OPS-D4 / D5 | 读 `$DSH_HOME/profiles/web/package.json`（`--profile` 可指定、`--no-profile` 可关）：**本地 `link:`/`file:` bundle 的链接目标必须存在**（仓目录改名/搬动后必然悬空）→ 阻断；profile 里的 `node_modules/<name>` 必须可解析；bundle 声明的 `dsh.bundle.patch` 必须存在；该 patch 的 `GOVERNANCE:BEGIN/END` 必须成对。官方 `@deepseek-ai/*` bundle 从 DSH 安装目录解析，**计数豁免**不动；profile 不存在记 **SKIP（不是通过）**。**聚合默认不读仓外**：`check:governance` 带 `--no-profile`，只转发给注册表声明 `profileProbe` 的门禁；要查部署面就单跑本门禁。起因见下方「profile 探针的由来」 | 无（必须恒绿） |
| `g09-python-hygiene` | 调试铁律 35 / 38 / 43 | 文本 I/O（`open`/`read_text`/`write_text`）必须显式 `encoding=`；非 raw 字符串里的盘符路径（`\d`/`\a` 这类转义伪影）阻断；`-W error::SyntaxWarning` 编译不通过即阻断。上游存量站点已冻进基线，**新增即拦** | `governance/baseline/g09-python-hygiene.txt`（存量 38 条，2026-10-26 复核全部仍复现，待逐步归零） |
| `g10-failloud-probe` | OPS-E1 / E2、调试铁律 39、铁律 5 | 给每条已登记门禁喂一个**不可能存在的 root**，必须非 0 退出**且**有报错信息；静默返回 0 或静默失败都阻断 | 无（必须恒绿） |
| `g11-undef-names` | 调试铁律 32 / 40 | AST 收集全文件的定义名（导入/赋值/函数类/形参/推导式目标/with-except-for 目标/海象/global）与读取名，报「读了但全文件从未定义」；解析失败单独报 | `governance/baseline/g11-undef-names.txt`（当前为空） |
| `g12-integrity` | 调试铁律 51 / 58、OPS-E8 | `HEAD^{commit}` 必须可解析（`rev-parse --verify HEAD` 只解析 ref 名，验证不了对象存在）；HEAD 可达对象必须逐个可读；`--deep` 追加 `git fsck --connectivity-only`。盘健康（事件日志/脏位）**明确不在本门禁**：Windows 专属、另有归属，跑不了的判据不装成通过 | `governance/baseline/g12-integrity.txt`（当前为空） |
| `g13-docs-only` | OPS-D1 / G8 / G17 | `docs/**` 扩展名白名单（`.md/.json/.yaml/.png/...`）；脚本、二进制、归档一律阻断；**可执行位**也阻断 | `governance/baseline/g13-docs-only.txt`（当前为空） |
| `g14-preset` | 铁律 5、调试铁律 42、OPS-D4 / D5 | 治理 preset：`GOVERNANCE:BEGIN/END` 成对有序、治理段内无盘符路径、插件名序列与随门禁出厂的 `tools/gate/governance/preset/allin.patch.yml` **逐项相等**（上游破坏性变更 → 变红）、persona 引用的仓内文件存在、提到的门禁 id 都在注册表里；**外加 profile 探针**（见上一行） | 无（必须恒绿） |
| `g16-skill-preset-parity` | 铁律 1 / 5、调试铁律 42、OPS-D4 / D5 | **多载体一致性**（2026-10-28 新增，2026-10-29 扩到三载体）：三个治理载体必须说同一套事实 —— `.workbuddy/skills/allin-governance-agent/SKILL.md`（WorkBuddy 侧）、`preset/allin/allin.patch.yml` 的 `GOVERNANCE:BEGIN/END` 段（DSH 侧）、`preset/allin/agent.cordis.yml` 的同名段（0.1.6 目录式存档，无人加载 —— 正因如此它静默漂到 2026-09 快照：硬编码盘符根 + 退役文档路径 + 「107 仓」，直到 2026-10-29 才被发现）。判据：① 三侧文件都在且治理面非空；② 两个 preset 侧治理段标记成对，且**按真标记行锚定**（`<!-- GOVERNANCE:BEGIN`），不得用「子串首次出现」定位——注释里写一句 `GOVERNANCE:BEGIN/END 段` 就会把块起点拉到注释上；2026-10-29 实测 preset 侧的核心事实一直靠注释过关，补上第三载体才暴露**真治理段里没有 `npm run check:governance`**（已补进治理内核句）；③ **声明的核心事实（命令 `npm run check:governance`、路径 `docs/INDEX.md` / `preset/allin/allin.patch.yml` / `docs/记录/`）三侧都必须出现**，缺一即漂移；④ 任一载体提到的门禁 id 必须存在于 `registry.json`（不得宣传未发货的检查）；⑤ **三侧都不得携带盘符路径**（URL 先剥离再扫）——这一条补的是 `g01-paths` 对 `.md` 只报不拦留下的洞（2026-10-28 曾让陈旧解释器路径活在 SKILL.md 里）。自检 **8 抓 / 1 干净**，新增 `agent-missing` / `agent-drift` / `agent-machine-path` 三个夹具 | 无（必须恒绿） |
| `g17-registry` | OPS-G5 / G13、调试铁律 46、退役三查 | **注册表完备性与生命周期**（2026-10-28 新增）：① 每条登记必须有 `id` 且 `id` 等于文件名（路径与名字不许漂移）、id 唯一；② 可选 `status` 必须取自 `active / dormant / archived / deprecated` 闭集；③ **完备性**：仓库根（默认 `<仓根>/../repos`，`ALLIN_REPOS_ROOT` 可覆盖）下每个 git 工作树必须已登记，或在 `governance/registry-known-gaps.txt` 里**写明理由地声明**——未登记又未声明即阻断（这条止住 3dworld-globe 那类"克隆了却没登记"的渗漏）；非 git 目录计数豁免；④ **生命周期**（只报告不阻断）：按最后提交天数分为 active / dormant(>90d) / archived-candidate(>365d)。仓库根不存在时记 `SKIPPED (not a pass)` | 无（必须恒绿） |
| `g18-exceptions` | 铁律 2、OPS-G5、调试铁律 46 | **例外治理化**（2026-10-28 新增）：冻结基线键 / 仓库卫生豁免 / 注册表声明缺口都是「被接受的风险」，必须登记成记录。`governance/exceptions.yml` 每条必须有 `id / kind / gate / target / reason / compensating / approver / expires / status`；`kind` 限于 `baseline-freeze / hygiene-exemption / known-gap`，`status` 限于 `open / closed`，id 唯一，**`expires` 过期且仍 open 即阻断**（过期 = 未复核的接受风险）。覆盖率只报告不阻断（首日即拦会逼出一次性五十条记录，门禁会被关掉） | 无（必须恒绿） |
| `g19-docs-refs` | 铁律 2、OPS-G5、调试铁律 46 | **文档即测试（docs-as-tests）**（2026-10-28 新增）：文档是断言集，所以跑断言。三类可验证主张 —— ① **命令目标**：围栏块（bash/sh/console/python/powershell 等）里的 `python x.py` / `node x.js` / `bash x.sh` 必须指向存在的文件（解析基准放宽：仓根 / 文档自身目录 / 上级目录 / 带前导 `/`，存在即过，哪儿都不存在才红）；② **npm 脚本**：`npm run <name>` 必须存在于从文档所在包到根包的 `package.json` 链；③ **路径引用**：`docs/ tools/ scripts/ platform/ kernel/ preset/ architecture/` 开头的仓内相对路径必须存在。**豁免且计数可见**：`docs/md/`（冻结历史树，与 `docs_index` 同一口径）、`vendor/`、`.workbuddy/skills/`（描述的是别仓）、`tools/gate/audit/`（运行时产物，不入库）；`docs/记录/` 与 `audit-fragments/` 是** dated 快照**，豁免路径引用但仍判命令（记录说「当时如此」，规范说「现在为真」）；**头部状态为 `已废弃` 的规范整体免判**（依 SPEC-005 §121「废弃不删除」，废弃件是留档证据不是当下承诺，见 `architecture/adr/ADR-0005-已废弃规范退出文档即测试.md`）。存量曾冻结 20 键（EX-006），**2026-10-28 已清零**：13 处别仓路径补仓名前缀、1 处历史陈述改写、1 处改指本仓真实落点、SPEC-104 改状态为已废弃；基线现为空，只拦新增 | 空（2026-10-28 清零；EX-006 转 `closed` 留档） |
| `g15-docs-contract` | **SPEC-005 全部**、OPS-D6 / D7、调试铁律 45 | 文档枢纽索引契约（**选用制**）：D1 文档未登记索引 / D2 索引指向不存在的文件 / D3 规范缺头部字段 / D4 规范名带日期或记录名无日期 / D5 分类与所在目录不一致 / D6 ASCII 别名缺失或指向错误 / D7 交接卷号有空洞或缺覆盖区间。**本仓 `docs/` 没有 `INDEX.md` 时记 `SKIPPED (not a pass)` 并计数**，不当作通过。判据与 allin 仓 `tools/gate/docs_index.py` 同源 | `governance/baseline/g15-docs-contract.txt`（allin 侧存量为 0） |

| `g20-facts` | 调试铁律 57 / 58、OPS-G5 | **机器事实源即断言集**（2026-10-30 新增，**Windows 专属**）：`docs/事实源/机器/*.md` 头部**最新时点块**里的两类可机械判断言 —— ① 机器绝对路径的**存在性声称**（「现已存在/现存/仍在位」须存在；「现已不存在/已不存在/均不存在/MISSING/已删/已移除」须不存在）；② **计数声称**（路径后 `**N**` 或 `N 项` 必须等于实际条目数；口径按单位切换：`项` 数全部条目，无单位或 `个仓`/`个目录` **只数目录** —— `G:\repos` 是 136 目录 + 4 文件，数全部得 140 会假报）。**日期更早的时点块一律不判**（历史留档，判它等于逼人改历史）。判据**只有一份**：定义在本门禁，`tools/facts/verify_facts.py` 反向 import 复用（两套会同时报绿、冲突时无人判定）。起点：2026-10-30 全量复测查出 **9 处断言与磁盘不符，而当时 19 道门禁全绿** | `governance/baseline/g20-facts.txt`（当前为空） |

### 门禁的分层与上下文（2026-10-28 新增，`run.ts --tier`）

`package.json` 的 `check:precommit` 原先手写一份门清单（`--only g01,...,g15`）。
**它漂移过两次**：新增 `g16`/`g17`/`g18` 后没人同步，预提交阶段于是静默地
不再跑那三条新门禁——清单本身成了唯一没有门禁看守的事实。现改为按声明选择：

- **`--tier P0,P1`** —— 选出 `registry.json` 里 tier 匹配的门禁。层号写在注册表里，
  与门禁同一处声明，新增门禁不必再改任何清单。
- **`context`** —— 默认 `local`（离线可跑）；声明为 `push` 的门禁（`g04-push-evidence`
  需要 `git ls-remote` 的权威远端证据）会被分层选择跳过，
  **没有网络时预提交不会因为拿不到远端而失败**。全量 `check:governance` 仍会跑它。

> 性能预算见 `npm run metrics:gates` 指标 ④：单次聚合当前 p95 约 54s，
> 逼近研究共识的 60s 上限；一旦越线，应把预提交降到 `--tier P0` 而非放宽预算。

### profile 探针的由来（2026-09-27，真实故障）

仓目录由 `allin_push` 改名为 `allin` 后，DSH profile 里那条
`"allin-agent-preset": "link:D:/projects/allin_push/preset/allin/bundle"` 变成**指向已删除目录的死链接**：
符号链接悬空 → 插件管理器解不开 → `plugin list` 直接抛
`cannot resolve profile bundle`，**重启后新会话会挂不上治理 preset**（设计上降级到工厂 `cordis`，不崩但无治理段）。

关键教训：**仓内门禁看不见仓外部署面**。当时 14 条门禁全绿，因为这个故障发生在
`$DSH_HOME/profiles/web/package.json` 里 —— 不在仓库里，任何只扫仓内的判据都扫不到。
因此把「本地 bundle 的链接目标必须存在」提升为机械判据，并做了**真实产物阴性对照**：
把 profile 临时还原成那条坏声明 → 门禁立即报 `bundle-unresolved`（exit 1）；恢复后 exit 0。

### g01-paths 的判定口径（易错处留档）

1. **必须泛化到 POSIX**：只认盘符的版本在 Linux/macOS 上恒绿，等于没有门禁；因此判据是「绝对路径的父目录不存在」，Windows 盘符与 `/Users`、`/home`、`/Volumes`、`/mnt`、`/media` 同等对待。
2. **平台归属**：为另一个平台书写的路径（Windows 上的 `/Users/...`、POSIX 上的 `C:\...`）只报告不阻断 —— 本仓三平台分发，Windows 专用脚本里的盘符是合法的。
3. **豁免必须绑定文件类型与目录层级**：测试面只认目录段（`tests/`、`fixtures/`、`__snapshots__/`…）与文件模式（`*.spec.ts`、`*_test.py`、`test_*.py`…），**不做子串匹配**（历史上 `spec/` 子串豁免曾放过一整片）。
4. **转义伪影**：盘符前加负向后顾 `(?<![A-Za-z0-9_])`，并要求分隔符后不是转义尾巴（`\n`/`\t`…），否则 `` `diagnostics:\n` `` 这类字符串会被误判成路径。
5. **计数不静默丢弃**：每次运行都打印 `exempted: 类别=数量`，任何一类豁免膨胀都能在输出里看见。
6. **文档面按扩展名整体降级**：`.md/.mdx/.rst/.txt/.adoc/.html/.htm` 只报告不阻断（`--include-docs` 才阻断）——旧机事实表这类文档里的历史死路径是**证据**，不是缺陷。

### g03-credentials / g04-push-evidence 的判定口径（误报治理留档）

1. **扫索引而不是落盘**：候选行来自 `git grep --cached`；`.gitattributes` 做过 EOL 归一化时，落盘内容与索引并不一致，只看工作树会漏。
2. **占位符白名单必须三层**：整体形如 `<...>`/`${...}`/`your-*`/`redacted` 的值；**值内含** `test`/`example`/`mock`/`synthetic`/`e2e`/`do-not-log` 这类合成标记；以及 `process.env.*`、`os.environ`、`getenv(` 这类**环境引用**（读环境是配置，不是泄露）。
3. **泛型赋值要求「长不间断串」**：真实凭据是长串而非分词短语，所以 `plum-galaxy-1791` 这类夹具名不阻断 —— 值里必须出现 ≥16 字符的连续字母数字串，且**含数字**（类型名、标识符、文档标签都没有数字）。
4. **样例主机与样例账号不算泄露**：`example.*`、`*.invalid`、`*.test`、`localhost` 上的 userinfo，以及 `user:password` 这类文档配对，一律豁免；userinfo 的密码位是 `${TOKEN}` 这类**环境展开**时同样豁免（与赋值口径一致）。
5. **行内注记必须与样本同一行**：`gov-credentials: allow` 只豁免它所在的那一行；夹具文件（`*.example`、`*.sample`、`*.template`）整文件豁免。
6. **同步状态只信远端**：`origin/BR` 是缓存，任何一次用 URL 直推都会让它过期；判定必须走 `git ls-remote`，并把方向（本地领先 / 远端领先 / 分叉）分别报出来。
7. **「没 fetch 过」不等于「分叉」**：`merge-base --is-ancestor` 对「不是祖先」与「本地没这个对象」返回同一个非零退出码。凡远端 sha 不在本地对象库，**先补取该分支的远端跟踪 ref 再判**（`git fetch <remote> +refs/heads/<BR>:refs/remotes/<remote>/<BR>`，不动本地分支/索引/工作树）；补取失败就记 `UNVERIFIED` + SKIP 并打印原因。2026-10-29 实证：本仓落后 origin/master **3 笔**却被旧判据报成 `DIVERGED`，提示去 rebase —— 方向反了。
8. **自检夹具要落在被扫的位置**：`g04` 用**真实的本地裸仓**跑通 `IN_SYNC → LOCAL_AHEAD → DIVERGED → REMOTE_AHEAD`（第四态是「克隆后从未 fetch」的回归夹具）；`g03` 的夹具注记必须写进夹具文件内容里（写在生成夹具的代码行上只豁免门禁自身）。

## 四、规则 → 机械保障 总表

三分类口径：**已机械化**（有门禁，改坏会红）· **流程纪律**（对话/判断层，不可机械化，写入 `governance/README.md` 与 preset 治理段）· **平台专属**（本仓不适用，或只在特定平台生效）。

### 4.1 命名铁律

| 规则 | 状态 | 承载体 |
| --- | --- | --- |
| 铁律 0 开源优先（公开 + MIT；随上游 GPL 例外） | 已机械化（DSH 既有） | `verify-dsh-package-licenses`（312 包全 MIT）+ 本目录 g03（待批 3） |
| 铁律 1 README 优先 | 部分机械化（DSH 既有） | 包级 README 小节门禁（`verify-package-readme-summaries` 等）；「先读」本身 = 流程纪律 |
| 铁律 2 协作工作流程（先问→计划→review→执行→复盘） | 流程纪律 | 不可机械化的对话节奏；放行与高风险动作口径见 preset 治理段 |
| 铁律 3 推送在场前提 | 部分机械化（批 2） | 「无人值守不推送」是流程纪律；技术前提（远端证据、凭据残留、分叉检测）由 `g04-push-evidence` 机械化 |
| 铁律 4 建仓三件套 | **已机械化（批 3）** | `g05-hygiene`：根 LICENSE / README.md / .gitignore 存在性 + `.gitignore` 凭据面覆盖 |
| 铁律 5 去符盘 | **已机械化（批 1）** | `g01-paths` |
| **SPEC-005 文档枢纽契约**（2026-09-28 新增） | **已机械化（批 5）** | `g15-docs-contract`（D1–D7）；**选用制**：仓内无 `docs/INDEX.md` 即记 SKIP |
| **SPEC-006 机器与路径约定**（2026-09-28 新增） | **部分机械化** | `g01-paths`（死路径/写死本机路径）、DSH 既有 `verify-*` 编码类门禁；「盘位是在位性动态事实」为流程纪律 |

### 4.2 治理准则（创新三原则 / 三查 / 敏感信息）

| 规则 | 状态 | 承载体 |
| --- | --- | --- |
| 借鉴必记账（来源 + 许可 + 借用范围） | 部分机械化 | DSH 既有 `verify-third-party-notices` + `THIRD_PARTY_NOTICES.md`；补充判据待批 3 |
| 调整必同步（推远端 / 更新引用 / 跑黄金值） | 部分机械化（批 2） | g04-push 的远端同步判定 + `run-gates` 全量聚合 |
| 推倒重来只用于结构层；补优于删 | 流程纪律 | 删除/归档证据门禁（g08，批 3）把它变成可检查项 |
| 冗余/退役判定三查（功能面 × 接任者） | 部分机械化（批 3） | **语义拆分仍靠人**；`g08-deletion-evidence` 机械要求删除类提交附「功能面 × 接任者」对照表（或显式 `gov-deletion: allow` 留痕） |
| 敏感信息检查（令牌/密钥/cookie 绝不入库） | **已机械化（批 2）** | `g03-credentials`（索引面 + `.git/config` 全文） |
| 新建三查（查存量 × 查覆盖 × 查冲突） | 流程纪律（2026-10-30 新增） | **语义判断不可机械化**；唯一可复核点是「证据行是否被贴出」（提交信息 / 计划文档）。反向约束由 `g00-meta` 的 `untracked-support`（新建了却没入索引）+ `rules-map`（新建门禁却没写进本文件）部分兜住 |
| 机器事实源现值与磁盘一致 | **已机械化（2026-10-30，Windows）** | `g20-facts`：机器绝对路径存在性 + 目录计数；判据唯一来源在门禁内，`tools/facts/verify_facts.py` 复用 |

### 4.3 调试铁律（1–58）

| 规则 | 状态 | 承载体 |
| --- | --- | --- |
| 调试铁律 30 / 41 / 53（门禁必须能自证、退出码如实、排除项最危险） | **已机械化（批 1）** | `g00-meta`（元契约）+ 各门禁的 `--selfcheck` 反例 |
| 调试铁律 26 / 34（判死口径、豁免绑定层级） | **已机械化（批 1）** | `g01-paths` 判定口径 1–5 |
| 调试铁律 35 / 38 / 43 / 50（编码与转义） | 待批 4（g09-python-hygiene） | Python 侧 `encoding=`/SyntaxWarning/`reconfigure` |
| 调试铁律 45（编号唯一连续） | **已机械化（批 3）** | `g06-numbering`：序号版本序列连续 + 中英配对列表形状逐项相等 |
| 调试铁律 54（`git add -A` 把产物提交进去） | **已机械化（批 3）** | `g05-hygiene`：产物目录、字节码、`*.egg-info` 只要进索引就阻断 |
| 调试铁律 52（`-u` 把凭据写进 `branch.*.remote`） | **已机械化（批 2）** | `g03-credentials` 扫 `.git/config` 全文，不只 remote 段 |
| 调试铁律 25 / 37 / 47（提交与推送的判定只认实证） | **已机械化（批 2）** | `g04-push-evidence`（`ls-remote` 三态 + `credential.helper` 空值检测） |
| 调试铁律 57 / 58（事实源时效、观测带时点与工具） | **已机械化（批 3）** | `g07-doc-freshness`：自称环境事实源 → 必须带时点；自称快照 → 必须带失效/「以…为准」条款 |
| 调试铁律 6 / 8 / 10 / 11 / 17 / 20 / 23 / 29 / 50 / 55 / 56 | 平台专属（不适用） | PowerShell / Windows 语言与系统坑，本仓无对应面 |
| 其余条目 | 见 §4.4 与后续批次 | 逐条在批次落地时补入 |

### 4.4 DSH 既有门禁（不重造，只引用）

本仓已有一批与治理规则同源的机械保障，**不要另造更弱的版本**：

| 治理规则 | 既有门禁 |
| --- | --- |
| 铁律 0（公开 + MIT） | `verify-dsh-package-licenses` |
| 双语事实源一致性 | `verify-translation-pairing`（blob 哈希 + 结构签名） |
| 文档链接与锚点有效 | `verify-md-links` |
| 源码注释里的文档路径存在 | `verify-doc-refs` |
| 文档体量上限 | `verify-doc-budgets` |
| 禁真实提交号进维护文件 | `verify-repository-references` |
| 禁已下线仓 URL（含转义绕过） | `verify-public-repository-links` |
| 冻结存量、只拦新增（基线棘轮范式） | `verify-no-unknown-casts` |
| 包 manifest / workspace 协议 / 层级 | `check-workspace-constraints.ts` |

## 五、维护约定

1. **加规则**先改本文件，再写门禁；门禁必须自带 `--selfcheck`，且**每条豁免都要有对应的反例用例**。
2. **改判据**要同时改自检，并确认「零误报」用例仍通过（调试铁律 53）。
3. **刷新基线**前先 `--no-baseline --list-all` 看全量；基线只在存量确实清完时才重置，且基线文件随仓提交，收紧与放宽都要在提交信息里写明理由。
4. **不可机械化的条目**必须留在这里并标注「流程纪律」，不要硬编成门禁（硬编只会制造假绿）。
