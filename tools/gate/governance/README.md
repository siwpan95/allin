# `governance/` — 治理内核的可执行门禁（allin 侧）

> **这是什么**：把「工作区治理」的规则从**文字**变成**退出码**，并随本仓一起交付 —— 克隆下来就能跑，不依赖任何本机路径或私有工具。
> **口径（2026-10-26 并入）**：本目录原是 `siwpan/deepseek-harness` 的 `governance/` 内核，于 2026-10-26 整体并入 `allin` 的 `tools/gate/governance/`，原 DSH 远端已删除。
> **规则事实源**：规则本身来自本仓 `docs/规范/` 与 `docs/事实源/`；**本目录是它的可执行落地**，逐条对应关系见 [`RULES.md`](RULES.md)。
> **哲学与事故表**：见 [`docs/记录/专题/治理门禁哲学与事故表_2026-10-26.md`](../../docs/记录/专题/治理门禁哲学与事故表_2026-10-26.md)；粘合剂模式见 [`docs/规范/SPEC-105-治理模式建设指南.md`](../../docs/规范/SPEC-105-治理模式建设指南.md) §9。

## 一、怎么跑（allin 侧命令）

```powershell
npm run check                        # 一条命令：治理门禁 + 文档契约 + .ps1 编码
npm run check:governance            # 全部门禁，仓内判据（聚合默认带 --no-profile，不读 host profile）
npm run check:governance:selfcheck  # 证明每个门禁仍能抓到注入的缺陷
node tools/gate/governance/run.ts --list            # 列出 id / 档位 / 覆盖的规则
node tools/gate/governance/run.ts --only g01-paths # 只跑某几条（逗号分隔）
node tools/gate/governance/run.ts --no-profile     # 显式声明「只看仓内」（聚合默认已带）
node tools/gate/governance/run.ts -- --quiet       # `--` 之后的参数透传给每个门禁
python tools/gate/governance/gates/g01_paths.py --selfcheck       # 单条门禁自检（不经 Node）
python tools/gate/governance/gates/g01_paths.py --no-baseline --list-all  # 看全量存量，忽略基线
python tools/gate/governance/gates/g14_preset.py                  # 单跑：含 profile 探针（读 preset 安装点）
```

**仓内 vs 仓外的边界（重要）**：`check:governance` 是**仓内**判据 —— 它带 `--no-profile`，只转发给
注册表里声明了 `profileProbe` 的门禁（当前只有 `g14-preset`），其他门禁不会收到这个开关。
**要查「仓外部署面」**（preset 安装点的 `link:` bundle 是否悬空、挂载的 patch 是否完整）就**单跑** `g14-preset`，
或显式 `node tools/gate/governance/run.ts --only g14-preset`（不带 `--no-profile`）。两种模式都有 A/B 实证：
带标志时输出里 0 条 profile 解析行，不带时 1 条。

**提交时自动跑**：`pre-commit` 钩子会执行 `npm run check:precommit`（13 条快速子集，约 8 秒）：
排除 `g00-meta`（契约自检要跑完 15 条门禁的 `--selfcheck`，约 20 秒）与 `g04-push-evidence`（要连远端，离线会等超时）。
这两条与其余全量核查仍由 `npm run check` 覆盖；子集清单只在 `package.json` 里定义一处，钩子不复制。

**退出码（全部门禁统一）**：`0` 干净 · `1` 基线之外的新阻断 · `2` 用法错误 · `3` 环境错误。
`run.ts` 按「最坏优先」聚合（`3` > `2` > `1` > `0`）；任何一条非 0 都不会被吞掉。

**依赖**：Python 3.9+、`git`、Node.js ≥ 22.18（`run.ts` 用 Node 原生类型擦除直接运行，**不需要 `npm install`、不需要 tsx**）。
Python 解释器按 `DSH_GOVERNANCE_PYTHON` → `python3` → `python` → `py -3` 顺序探测，**探不到就带名字报错**（`exit 3`），不会静默跳过。
平台专属能力在别的平台上记 `SKIPPED (not a pass)` 并计数，**SKIP 不算通过**。

## 二、门禁契约（由 `g00-meta` 逐条机械校验）

每个登记在 [`registry.json`](registry.json) 的门禁必须满足：

1. 注册表条目含 `id`/`title`/`script`/`tier`/`rules`/`platforms`/`requires`/`selfcheck`；
2. 脚本存在，且 `--help` 暴露 `--selfcheck`、`--quiet`、`--baseline`、`--no-baseline`、`--write-baseline`、`--list-all`；
3. `--selfcheck` 退出 0，输出 `SELFCHECK {"caught":N,"clean":M,"misreports":K}`，要求 `N≥1`、`M≥1`、`K==0`；
4. 门禁 id 在 [`RULES.md`](RULES.md) 里有记载。

**为什么把自检写进契约**：只能跑阳性、或「打印了提示就返回 0」的门禁，会把假绿卖给所有人。自检必须用**真实破坏用例**（临时仓里真的写一条死路径、真的删一个字节）。

## 三、规则覆盖情况（三类，不许含糊）

| 类别 | 含义 | 去处 |
| --- | --- | --- |
| **已机械化** | 有门禁，改坏就红 | 本目录 `gates/`；逐条对照表见 `RULES.md` §4 |
| **流程纪律** | 对话与判断层（先问再计划、无人值守不推送、冗余三查的语义拆分） | `RULES.md` 标注 + `preset/` 的治理段；**不要硬编成门禁** |
| **平台专属** | PowerShell/Windows 语言与系统坑、盘健康事件日志 | 标注为平台专属；非该平台记 SKIP，不记通过 |

## 四、基线棘轮（让门禁「现在就能绿」）

存量没清完就上线的门禁，通常的结局是被绕过。因此每条门禁都支持基线：存量一次性写进 `baseline/<gate>.txt`，此后**只拦新增**。

```powershell
python tools/gate/governance/gates/g01_paths.py --no-baseline --list-all   # 先看全量
python tools/gate/governance/gates/g01_paths.py --write-baseline           # 再冻结存量
git diff tools/gate/governance/baseline/                                    # 基线变化必须可评审
```

**纪律**：刷新基线前必须先看全量；基线文件随仓提交（收紧与放宽都要在提交信息里写明理由）；`g01-paths` 的基线当前**为空**，即存量已清零。

## 五、新增一条门禁（五步，缺一步就会在 `g00-meta` 变红）

1. 写 `tools/gate/governance/gates/gNN_<name>.py`，`import govlib`（`sys.path` 指向 `../runtime`），核心判定写成 `scan(...) -> Report`；
2. 在文件末尾加 `selfcheck()`：注入真实破坏用例 → `check.detects(...)`；干净样例 → `check.quiet(...)`；末尾 `return check.finish()`；
3. 在 `tools/gate/governance/registry.json` 登记（含 `rules` 与 `baseline` 路径）；
4. 在 `tools/gate/governance/RULES.md` §三/§四 写清它覆盖哪条规则、判据与已知豁免；
5. 跑 `npm run check:governance:selfcheck` 与 `npm run check:governance`，两条都绿才算完成。

## 六、与既有门禁的关系（不要重复造）

本工作区 `tools/` 与 `platform/` 已有一批同源的机械保障，**新门禁只在它们没覆盖的地方造**：
仓根 `tools/repo_hygiene.py`（`H1`–`H8`）、`tools/gate/` 下的 `scan_hardcoded.ps1` / `check_undefined_names.py` /
`docs_index.py` / `check_ps1_bom.py` / `watchdog.py` / `check_gate_drift.py` / `make_doc_aliases.ps1`，
以及 `platform/scripts/check.mjs`。逐条对应关系见 `RULES.md` §4.4 与 SPEC-105 §9。

## 七、文件清单

| 路径 | 作用 |
| --- | --- |
| [`RULES.md`](RULES.md) | **规则 → 门禁映射（规则事实源）**，含引用契约与维护约定 |
| [`registry.json`](registry.json) | 门禁注册表（`g00-meta` 的输入） |
| [`run.ts`](run.ts) | 派发器：解释器发现、聚合退出码、`--list`/`--only`/`--selfcheck-all` |
| [`runtime/govlib.py`](runtime/govlib.py) | 共享运行时：退出码、仓根发现、基线棘轮、报告、自检夹具 |
| [`gates/`](gates) | 门禁本体（Python，每条自带 `--selfcheck`）：`g00` 契约自证、`g01` 路径、`g03` 凭据、`g04` 推送实证、`g05` 仓库卫生、`g06` 编号契约、`g07` 事实源时效、`g08` 删除证据、`g09` Python 编码/转义、`g10` 失败要响亮、`g11` 未定义名、`g12` 对象库完整性、`g13` docs 只放文档、`g14` preset 结构、`g15` 文档契约 |
| [`preset/`](preset) | 治理 persona 的可重装载体（`allin.patch.yml` + 安装/校验/回滚说明）；结构由 `g14-preset` 守住 |
| [`baseline/`](baseline) | 基线棘轮文件（随仓提交，变化可评审） |
