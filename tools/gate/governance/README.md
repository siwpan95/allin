# `governance/` — 分发版的机械保障（可执行门禁）

> **这是什么**：把「工作区治理」的规则从**文字**变成**退出码**，并让这套判据随本分发版本一起交付 —— 克隆下来就能跑，不依赖任何本机路径或私有工具。
> **口径（2026-09-27 用户拍板）**：本仓 `siwpan/deepseek-harness` 是**独立分发版本**；上游 GitHub 官方仓仅作参考，本目录与其全部内容都是**分发版自有资产**，可按分发节奏独立演进。
> **规则事实源**：规则本身来自治理仓 `siwpan/allin` 的 `docs/`；**本目录是它的可执行落地**，逐条对应关系见 [`RULES.md`](RULES.md)。

## 一、为什么需要它

文档写得再全，缺了监工照样一遍遍踩坑。这里的每一条门禁都对应一类**真实发生过**的事故：

| 事故类型 | 代价 | 对应门禁 |
| --- | --- | --- |
| 脚本/配置里写死某台机器的绝对路径 | 换机即坏、克隆即错 | `g01-paths` |
| 门禁自己骗自己（排除项过宽、打印了就返回 0） | 报绿反而更危险 | `g00-meta` + 每个门禁的 `--selfcheck` |
| 凭据写进仓库或 `.git/config` 的 `branch.*.remote` | 公开历史只能吊销重发 | `g03-credentials`（已上线） |
| 用陈旧的 `origin/BR` 判断「推上去没有」 | 以为推了其实没推 / 以为没推其实推了 | `g04-push-evidence`（已上线） |
| 目录被 `.gitignore` 吞掉，`git status` 却沉默 | 克隆副本跑不起来，本地全绿 | `g00-meta` 的 `untracked-support` 检查（已上线） |
| 构建产物、字节码、`*.egg-info` 跟着 `git add` 进库 | 每次构建都产生噪音 diff，并暴露本机路径 | `g05-hygiene`（已上线） |
| 编号重号或缺号、中英两版列表条目对不上 | 引用失效：同一编号指向两条规则 | `g06-numbering`（已上线） |
| 自称「事实源/快照」却没写时点、没过期条款 | 过期结论继续被当作权威 | `g07-doc-freshness`（已上线） |
| 删掉一个功能面却没记「接任者」 | 输出端整片消失（radio 直播面事故） | `g08-deletion-evidence`（已上线） |
| 仓目录改名/搬动后，profile 里的 `link:` bundle 变成死链接 | 插件解不开，重启后新会话**静默失去治理段**（仓内门禁全绿也发现不了） | `g14-preset` 的 **profile 探针**（已上线） |
| `json.load(open(path))` 在中文 Windows 上读写错编码 | 文件被写坏且难查 | `g09-python-hygiene`（已上线） |
| 门禁拿到不可用的输入却静默返回 0 | 跑了等于没跑 | `g10-failloud-probe`（已上线） |
| 改写脚本丢了 `import` / 丢了一行 | 编译通过、运行才炸 | `g11-undef-names`（已上线） |
| 盘在线自愈改坏 git 对象而无人发现 | 4 个仓损坏，全靠人工挖 | `g12-integrity`（已上线） |
| `docs/` 里混进脚本、归档、可执行位 | 生成物与第三方载荷开始泄进公开仓 | `g13-docs-only`（已上线） |
| 治理 preset 与出厂件悄悄漂移 | 升级后会话绑不上治理段 | `g14-preset`（已上线） |
| 文档枢纽里的文档**没登记进总目录**、索引指向不存在的文件、规范没有效力声明头、规范名带日期而记录名不带、ASCII 别名目录丢失、交接卷断号 | 「找不到东西」+「指导性文档被当作产物」——**规矩只写在文档里，没有一条门禁**（2026-09-28 大修前的实测状态） | `g15-docs-contract`（**选用制**：仓内无 `docs/INDEX.md` 即记 SKIP，见 [`RULES.md`](RULES.md) §三） |

## 二、怎么跑

```powershell
pnpm run check:governance          # 全部门禁，**仓内判据**（聚合默认带 --no-profile，不读 host profile）
pnpm run governance:selfcheck      # 证明每个门禁仍能抓到注入的缺陷
pnpm exec tsx governance/run.ts --list                 # 列出 id / 档位 / 覆盖的规则
pnpm exec tsx governance/run.ts --only g01-paths       # 只跑某几条（逗号分隔）
pnpm exec tsx governance/run.ts --no-profile           # 显式声明「只看仓内」（聚合默认已带）
pnpm exec tsx governance/run.ts -- --quiet             # `--` 之后的参数透传给每个门禁
python governance/gates/g01_paths.py --selfcheck       # 单条门禁自检（不经 Node）
python governance/gates/g01_paths.py --no-baseline --list-all   # 看全量存量，忽略基线
python governance/gates/g14_preset.py                  # 单跑：含 profile 探针（读 $DSH_HOME 下 profile）
```

**仓内 vs 仓外的边界（重要）**：`check:governance` 是**仓内**判据 —— 它带 `--no-profile`，只转发给
注册表里声明了 `profileProbe` 的门禁（当前只有 `g14-preset`），其他门禁不会收到这个开关。
**要查「仓外部署面」**（profile 里的 `link:` bundle 是否悬空、挂载的 patch 是否完整）就**单跑** `g14-preset`，
或显式 `tsx governance/run.ts --only g14-preset`（不带 `--no-profile`）。两种模式都有 A/B 实证：
带标志时输出里 0 条 profile 解析行，不带时 1 条。

**退出码（全部门禁统一）**：`0` 干净 · `1` 基线之外的新阻断 · `2` 用法错误 · `3` 环境错误。
`run.ts` 会把各门禁的结果按「最坏优先」聚合（`3` > `2` > `1` > `0`）；任何一条非 0 都不会被吞掉。

**依赖**：Python 3.9+ 与 `git`。解释器按 `DSH_GOVERNANCE_PYTHON` → `python3` → `python` → `py -3` 的顺序探测，**探不到就带名字报错**（`exit 3`），不会静默跳过 —— 静默跳过等于这条门禁不存在。
平台专属能力（如 Windows 事件日志）在别的平台上记 `SKIPPED (not a pass)` 并计数，**SKIP 不算通过**。

## 三、门禁契约

每个登记在 [`registry.json`](registry.json) 的门禁必须满足的全部条款（由 `g00-meta` 逐条机械校验）：

1. 注册表条目含 `id`/`title`/`script`/`tier`/`rules`/`platforms`/`requires`/`selfcheck`；
2. 脚本存在，且 `--help` 暴露 `--selfcheck`、`--quiet`、`--baseline`、`--no-baseline`、`--write-baseline`、`--list-all`；
3. `--selfcheck` 退出 0，并输出 `SELFCHECK {"caught":N,"clean":M,"misreports":K}`，要求 `N≥1`、`M≥1`、`K==0`；
4. 门禁 id 在 [`RULES.md`](RULES.md) 里有记载（规则必须能找到执行它的那条门禁）。

**为什么把自检写进契约**：只能跑阳性、或者「打印了提示就返回 0」的门禁，会把假绿卖给所有人。自检必须用**真实破坏用例**（临时仓里真的写一条死路径、真的删一个字节），不是把判断注释掉。

## 四、规则覆盖情况（三类，不许含糊）

| 类别 | 含义 | 去处 |
| --- | --- | --- |
| **已机械化** | 有门禁，改坏就红 | 本目录 `gates/`；逐条对照表见 `RULES.md` §4 |
| **流程纪律** | 对话与判断层（先问再计划、无人值守不推送、冗余三查的语义拆分） | `RULES.md` 标注 + `preset/` 的治理段；**不要硬编成门禁** |
| **平台专属** | PowerShell/Windows 语言与系统坑、盘健康事件日志 | 标注为平台专属；非该平台记 SKIP，不记通过 |

## 五、基线棘轮（让门禁「现在就能绿」）

存量没清完就上线的门禁，通常的结局是被绕过。因此每条门禁都支持基线：存量一次性写进 `baseline/<gate>.txt`，此后**只拦新增**。

```powershell
python governance/gates/g01_paths.py --no-baseline --list-all   # 先看全量
python governance/gates/g01_paths.py --write-baseline           # 再冻结存量
git diff governance/baseline/                                    # 基线变化必须可评审
```

**纪律**：刷新基线前必须先看全量；基线文件随仓提交（收紧与放宽都要在提交信息里写明理由）；`g01-paths` 的基线当前**为空**，即存量已清零。

## 六、新增一条门禁（五步，缺一步就会在 `g00-meta` 变红）

1. 写 `governance/gates/gNN_<name>.py`，`import govlib`（`sys.path` 指向 `../runtime`），核心判定写成 `scan(...) -> Report`；
2. 在文件末尾加 `selfcheck()`：注入真实破坏用例 → `check.detects(...)`；干净样例 → `check.quiet(...)`；末尾 `return check.finish()`；
3. 在 `governance/registry.json` 登记（含 `rules` 与 `baseline` 路径）；
4. 在 `governance/RULES.md` §三/§四 写清它覆盖哪条规则、判据与已知豁免；
5. 跑 `pnpm run governance:selfcheck` 与 `pnpm run check:governance`，两条都绿才算完成。

## 七、与 DSH 既有门禁的关系（不要重复造）

本仓已有一批同源的机械保障，**新门禁只在它们没覆盖的地方造**：`verify-dsh-package-licenses`（MIT 许可面）、`verify-translation-pairing`（双语事实源）、`verify-md-links`、`verify-doc-refs`、`verify-doc-budgets`、`verify-repository-references`、`verify-public-repository-links`、`verify-no-unknown-casts`（基线棘轮范式）、`check-workspace-constraints.ts`。逐条对应关系见 `RULES.md` §4.4。

## 八、接进聚合门禁

`scripts/run-gates.ts` 暴露 `governance` 聚合，并已挂进 `check:all`：

```powershell
pnpm exec tsx scripts/run-gates.ts governance   # 只跑治理门禁
pnpm run check:all                              # 全量本地回归（含治理门禁）
```

## 九、文件清单

| 路径 | 作用 |
| --- | --- |
| [`RULES.md`](RULES.md) | **规则 → 门禁映射（规则事实源）**，含引用契约与维护约定 |
| [`registry.json`](registry.json) | 门禁注册表（`g00-meta` 的输入） |
| [`run.ts`](run.ts) | 派发器：解释器发现、聚合退出码、`--list`/`--only`/`--selfcheck-all` |
| [`runtime/govlib.py`](runtime/govlib.py) | 共享运行时：退出码、仓根发现、基线棘轮、报告、自检夹具（**不要放进 `lib/`**：仓根的 `lib/` 忽略规则会把它整个吞掉） |
| [`gates/`](gates) | 门禁本体（Python，每条自带 `--selfcheck`）：`g00` 契约自证、`g01` 路径、`g03` 凭据、`g04` 推送实证、`g05` 仓库卫生、`g06` 编号契约、`g07` 事实源时效、`g08` 删除证据、`g09` Python 编码/转义、`g10` 失败要响亮、`g11` 未定义名、`g12` 对象库完整性、`g13` docs 只放文档、`g14` preset 结构 |
| [`preset/`](preset) | 治理 persona 的可重装载体（`allin.patch.yml` + 安装/校验/回滚说明） |
| [`baseline/`](baseline) | 基线棘轮文件（随仓提交，变化可评审） |
| `preset/` | 治理 persona 的可重装载体（`allin.patch.yml` + 安装/校验/回滚说明），结构由 `g14-preset` 守住 |
