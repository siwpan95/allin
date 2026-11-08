# `tools/facts` —— 机器事实的采集与判定

把「机器事实靠人肉复测」变成两条命令。适用于 `docs/事实源/机器/` 下的分区文件 ——
落点双形态（2026-11-06 起）：顶层 `<机器名>.md`，或一机一目录的 `<机器名>/<机器名>.md`
（附属/README 等非同名文件不是分区文件）。

## 为什么有这个目录

2026-10-30 对 `@DESKTOP-8RSV60V` 做全量复测，**9 处断言与磁盘不符，而 19 道门禁 `exit 0`**。
根因不是门禁失灵，是判据没覆盖这三处：

| 现有门禁 | 它验什么 | 它漏什么 |
| --- | --- | --- |
| `g07_doc_freshness` | 事实源**有没有写时点** | **时点之后还成不成立** |
| `g19_docs_refs` | 仓内相对路径（`docs/…` `tools/…`）是否存在 | **机器绝对路径**（`G:\…` 一条都不解析） |
| `g01_paths` | 死盘符（父目录不存在） | **活盘符下的语义过期**（语法合法、目录没了） |

## 两个脚本，职责严格分离

```bash
# 只采集，不做判断 —— 输出可直接贴入分区文件（`机器/<机器名>.md` 或 `机器/<机器名>/<机器名>.md`）
python tools/facts/measure.py
python tools/facts/measure.py --out /tmp/facts.md

# 只判定 —— 解析头部「日期最新的时点块」，校验 PATH-EXISTS 与 COUNT
python tools/facts/verify_facts.py                 # 默认只验**当前机器**那份（与 g20 同口径）
python tools/facts/verify_facts.py --all           # 显式校验全部机器文件（跨机诊断）
python tools/facts/verify_facts.py --file <某份.md>   # 单文件校验
python tools/facts/verify_facts.py --json
python tools/facts/verify_facts.py --selftest         # 造必错样本，证明它真能报
```

| 脚本 | 退出码 |
| --- | --- |
| `measure.py` | 0 成功 / 2 用法错 / 3 环境错（非 Windows、找不到仓根） |
| `verify_facts.py` | **0 干净 / 1 有 finding** / 2 用法错 / 3 环境错 |

**机器过滤（2026-10-30，与 g20 门禁同口径）**：分区文件描述一台机器的磁盘，
在本机验别机文件 = 拿错盘对账、永远假红。默认只验文件名 = 当前主机名（大小写
不敏感）的那份，其余 `[skip]` 留待该机自验；`--all` 显式跨机诊断——其 finding
只说明「该路径在本机不存在」，**不代表别机事实有错**。

**为什么不合一个**：采集不做判断，所以永远可信；判定会被质疑，所以必须能自检。
合并会让人分不清「数据错了」还是「判据错了」。

## 判据（刻意窄，宁缺噪声）

只判两类**可机械判**的断言，其余一律放过 —— 噪声会让门禁被关掉（见 `g19` 源码里的同一取舍）。

### PATH-EXISTS

| 行内含 | 期望 |
| --- | --- |
| `现已存在` `现存` `仍在位` `EXISTS` | 该绝对路径**必须存在** |
| `现已不存在` `已不存在` `均不存在` `MISSING` `已删` `已移除` | 该绝对路径**必须不存在** |

### COUNT

行内出现 `<绝对路径>`，且其后有 `**N**` 或 `N 项 / N 个仓 / N 个目录` ⇒ 实际条目数必须等于 N。

**计数口径按单位自动切换**（这条踩过坑）：
- 单位是 `项` ⇒ 数**全部条目**（含散文件）—— 「归档区 43 项」含文件
- 无单位或 `个仓` / `个目录` ⇒ 只数**目录** —— 「repos 136 个仓」旁边还有 4 个文件，数全部会得 140

## 作用域：只判「日期最新的时点块」

各机文件头部按时间倒序排列 `> **时点**` 块。判定器只读**日期等于最新日期的那批块**，
日期更早的块一律不判 —— 那是历史留档，判它等于逼人改历史。

> ⚠ **约定（重要）**：**每次复测必须把现值写进最新的时点块**。
> 若最新块只是结构性说明、没有数字或路径断言，旧块里的断言就不会被检查 —— 这是设计上的边界，不是 bug。

## 新增一台机器

1. 在该机跑 `python tools/facts/measure.py --out <临时文件>`
2. **人工裁决**：与上一版逐项比对；不符的先复测再改，**旧值以「（原 …）」保留在同一格**
3. 新建 `docs/事实源/机器/<机器名>/<机器名>.md`（**一机一目录**；过渡期允许顶层单文件，两种形态 g20 均兼容），并在 `机器分区索引.md` §1 登记
4. 跑 `verify_facts.py`，应得 `findings 0`

**采集值是原始值，不是事实。** 未经复测裁决的采集结果不得直接覆盖旧值。

## 判据在哪（2026-10-30 12:35 起）

判据**不在本目录**，在门禁 `tools/gate/governance/gates/g20_facts.py`。
`verify_facts.py` 只是把它包成 CLI，通过 `import g20_facts` 复用。

**依赖方向是刻意反过来的**：

- 门禁必须**自包含** —— `g00-meta` 把每个 `--selfcheck` 放进只有 `governance/` 的沙箱里跑，
  够不到 `tools/facts/`；判据放这边会在沙箱里报「not importable」；
- 而判据**只能有一份** —— 两套会同时报绿、冲突时无人判定谁为准（`SPEC-003 §新建三查`）。

所以：**门禁定义判据，CLI 复用门禁。** 改判据改 `g20_facts.py`，别在这里加第二份。

## 已知边界（不掩盖）

- 只判头部最新的时点块；章节体内的表格（如 `§1 盘位表`）不判
- 只判 `PATH-EXISTS` / `COUNT`；**版本号、行为观测、语义判断不判**
- **不查章节引用完整性** —— `§5` 悬空那类问题（路径引用 `g19` 管，章节引用无人管）本工具不管
- **Windows 专属**：判据基于盘符绝对路径，`platforms: ["nt"]`；非 Windows 直接 `ENV ERROR` 退出 3
- 已接入 `scripts/run_all_gates.sh`（作为 `g20-facts`，`tier P1`）

## 自检记录（2026-10-30）

| 样本 | 期望 | 实测 |
| --- | --- | --- |
| 现值（3 份机器文件） | 0 | **0**，exit 0 |
| 把 `**136**` 改成 `**135**` | 1 条 COUNT | **1 条**，exit 1 |
| 把 `**43 项**` 改成 `**40 项**` | 1 条 COUNT | **1 条**，exit 1 |
| `--selftest`（合成样本） | 2 条（COUNT + PATH-EXISTS） | **2 条**，PASS |

## 安装 / 快速开始

**零第三方依赖**（纯标准库），无 pip 安装步骤，在本仓任意 Python 3.9+ 解释器下直接进入第二步即可 ——
推荐用 `scripts/run_all_gates.sh` 钉死的那个解释器（便携 Python 无 PyYAML 会让 `g18` 假红，`g20` 同理依赖它能否解析分区文件）。

最快的两步：

```bash
# ① 采集本机事实（输出可直接贴进分区文件：`机器/<机器名>.md` 或 `机器/<机器名>/<机器名>.md`）
python tools/facts/measure.py
# ② 判定本机分区文件：0 = 干净，1 = 有 finding
python tools/facts/verify_facts.py
```

⚠ 本工具是 **Windows 专属**（判据基于盘符绝对路径，`platforms: ["nt"]`），非 Windows 直接 `ENV ERROR` 退出 3。

## 结构化事实源 CLI（2026-11-09 起，离线地基）

[`cli.py`](cli.py) 是**跨平台只读查询面**，与上面两个 Windows 专属脚本职责分离：

| 子命令 | 作用 |
|---|---|
| `validate` | 结构化真身过 JSON Schema（闭集 / 必填 / 未声明字段拦截） |
| `build` | 从真身生成 `facts/build/facts.sqlite`（派生物、不入库、可重建） |
| `get` / `asof` / `query` / `diff` | 查现值、历史值、受限只读 SQL、两份真身差异 |
| `render` / `render --check` | 生成/校验 Markdown 生成区的 marker 哈希 |
| `offline-check` | **离线北极星**：拔网 + 停三栈 + 删派生库后仍可读事实、跑判据 |
| `selftest` | 16 个夹具用例（含 SCD-2 as-of、FTS5 trigram、漂移拦截、JSON 回落） |

- **真身在仓根 [`facts/facts.json`](../../facts/facts.json) + [`facts/facts.schema.json`](../../facts/facts.schema.json)**，
  与 `docs/` 枢纽并列的**数据面**；不放进 `docs/事实源/` 是为了避免生成物与真身混成「两份事实」，
  也不让文档索引契约 D1/D8/D11 把数据文件当文档计数。
- `--source auto|sqlite|json`：`auto` 在派生库缺失时自动回落纯 JSON 真身，响应显式标注
  `source=json(readonly)` 与 `state_kind=declared`；JSON 档下 `query` **明确拒答**而非伪装查过库。
- `measure.py` / `verify_facts.py` 的采集与判定口径**不变**（仍只判当前机器那份分区文件）；
  `cli.py` 不写事实，只读取与校验。
- 门禁接线见 `scripts/run_all_gates.sh`：`cli.py validate`（g22）、`tools/gate/facts_parity.py`（g23）、
  `tools/gate/relative_refs_gate.py`（g24），全部照 `g21` 的独立脚本模式接入，**g00–g20 的 20 道聚合口径不变**。

## 许可

本目录是 allin 仓的子件（非独立仓），许可随**仓根 LICENSE**（MIT-0）覆盖。
