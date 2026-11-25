# 变更记录（CHANGELOG）

> 面向**消费本仓产物的人**，不是面向仓内开发。
> 仓内的决策与审计留在 `docs/记录/`，这里只记「用户会感知到什么变了」。
> 口径更新（2026-11-25）：`allin-governance` 已迁至独立仓，本仓不再发行该包；
> 下方 1.1.2 及更早条目是包仍在本仓时的历史记录，保留不改。
> 当前版本与后续变更以 [独立仓 CHANGELOG](https://gitee.com/siwpan/allin-governance/blob/master/CHANGELOG.md)
> 及 [PyPI](https://pypi.org/project/allin-governance/) 为准。
>
> **订正（2026-11-25，文档死引用清零）**：历史条目里出现的 `tools/…` / `scripts/…` 一类
> 仓内落点**今日已不存在**（公共核提仓 `2727fb3`）。为不改写历史，正文只把这些写法改成
> 「某目录下的某文件」（如「`tools/` 下的 `gitee_release.py`」），
> **版本号、判据、教训一字未动**；这些工具的现行落点见上面「口径更新」与独立仓。

## `allin-governance` 2.0.2 —— 2026-11-25

**公共核已独立成仓，本仓改为按版本消费；PyPI 当前版本为 `2.0.2`。**

- 源码、门禁套件与发版链路迁至 <https://gitee.com/siwpan/allin-governance>；
  本仓 `packages/allin-governance/` 仅留旧路径指针，不再内嵌源码。
- 本仓通过 `pip install allin-governance==<版本>` 消费公共核；README 的「当前版本 `2.0.2`」、
  独立仓 `VERSION` / `pyproject.toml` / `__init__.py` 与 PyPI `info.version` 五处一致。
- 2.0.2 的实际变更（包内形态门禁入口修复、台账不随包分发）见独立仓 CHANGELOG；
  PyPI 发布序列从 `1.1.2` 直接到 `2.0.2`，**没有 2.0.1**。

## `allin-governance` 1.1.2 —— 2026-11-25

**统一 CLI 参数契约：`--root` 现在对所有子命令都成立。**

换机 E2E 实测发现两种写法并存：`scan` / `deps` 用 `--root`，`repocheck` / `verify` 只收位置参数——
同一次验收里照着文档写，前者跑通、后者 `exit 2`。这不是用法问题，是接口契约不一致。

### 有什么

- `repocheck` / `verify` 接受 `--root <目录>`（作为位置参数的别名，**旧写法仍然有效**）；
- 实现只在包装层做参数归一，底层工具与判据**一行未动**；
- 判据：`allin-governance repocheck --root <目录>` 与 `allin-governance repocheck <目录>` 等价。

### 升级

```bash
pip install -U allin-governance
```

## `allin-governance` 1.1.1 —— 2026-11-25

**修 1.1.0 的包内容缺失：`ledger/` 没随包，装完包跑门禁时豁免表会静默落空。**

`check_pkg_parity` 在 1.1.0 发布后报两条红：
`ledger/publish_area_exemptions.csv` / `ledger/repo_hygiene_exemptions.csv` 仓内有、包内无。
根因是台账从 `tools/gate/audit/` 迁到 `governance/ledger/` 时改了 6 处读取方，
但 `_gatesuite` 的 `package-data` 没跟着改（glob 还是 `baseline/*.txt`）。

### 有什么

- `package-data` 补 `ledger/*` —— 5 份基线/豁免台账随包分发；
- 影响面：换机后 `pip install allin-governance` 再跑门禁，**豁免不再落空**；
- 仓内开发同时受益：`check_pkg_parity` 由红转绿。

### 升级

```bash
pip install -U allin-governance
```

## `allin-governance` 1.1.0 —— 2026-11-24

**新增第 8 个子命令 `facts`：换机第一件事——先问这台机器长什么样。**

这一版的主题是「装完包、不用 clone 仓也能开工」。此前包里 7 个子命令有 6 个默认
「你身边有一个治理仓」，`facts` 是唯一一个**没有仓也成立**的：它采集的是机器事实
（盘位 / 运行时 / PATH 实际解析 / 环境变量有无），不是仓库状态。

### 有什么

- **`allin-governance facts measure [--root <仓根>] [--out <文件>]`**
  —— 采集本机事实，输出 Markdown（可直接贴进机器分区文件）。
  **无仓模式**：找不到仓根时只采集本机部分，`仓与归档`、`推送与远端` 两段显式写
  「**未采集（不是 0，是没查）**」，退出码仍 0。给了 `--root` 却是错目录 ⇒ 仍 fail-loud（exit 3）。
- **`allin-governance facts verify [--file|--all|--json|--selftest]`**
  —— 校验机器事实源里**可机检**的断言（`PATH-EXISTS` / `COUNT`）。
  判据不另写：装包后从包内 `_gatesuite.gates.g20_facts` 取，未装包时退回仓内相对路径，
  两条路是同一份源码。
- **`_facts` 包映射**：`tools/facts/` 经 `package-dir` 映射进 wheel，仓内仍只有一份源码。

### 修了什么（对已有用户可见）

- **装包后 `verify_facts` 不再恒 `ENV ERROR`**：原实现用 `parents[2]/tools/gate/...`
  定位判据，在 `site-packages` 里那条路径指向 pip 自己的目录树，永远不存在。
  装包的用户根本没有仓，于是在那种环境下等于「装了也没这个能力」。
- `tools/facts` 三个入口的 `from exit_codes import ...` 改为**相对导入优先、平铺导入兜底**，
  使同一份源码在「包内」与「仓内直跑」两种形态下都能加载。

### 边界（刻意不做）

- **`_facts.cli`（facts.json 的 SQLite 查询面）不进公共核边界**：它依赖仓内
  `tools/runtime_defaults.py` 与仓根布局，属「仓内形态」能力。装包后请勿直接调用它，
  可用的是 `facts measure` / `facts verify` 两条。

## `allin-governance` 1.0.3 —— 2026-11-24

**新增第 7 个子命令 `secrets-scan`：离线凭据扫描，不需要 gitleaks 二进制。**

为什么要自研而不随包带 gitleaks：它是 Go 编译产物（单平台 22 MB），进不了
`py3-none-any`；从源码构建又要 Go 工具链，等于把「下二进制」换成「现场编译」。
移植它的 222 条规则在技术上可行（实测 221/222 可编译），但那等于把 200+ 条长尾
规则的维护成本全继承下来。

### 有什么

- **21 条高精度规则**：只认已知提供方的固定格式（AWS / GitHub / GitLab / PyPI /
  OpenAI / Anthropic / Slack / Stripe / Google / 腾讯云 / 阿里云 / DockerHub / npm /
  SendGrid / Twilio + PEM 私钥 / JWT / URL 内嵌账密 / 泛化赋值兜底）。
- **五层降噪**：关键词预筛 → 结构化正则 → 捕获组提取 → **按字符集分档的熵阈值**
  （hex 3.0 / alnum 3.5 / 其它 4.0）→ 占位符与形态降噪（示例值、纯数字、版本号、
  UUID、无数字的标识符）。
- **仓库自有注解**：`gov-credentials: allow` / `repo-hygiene: allow`，与 `g03`、
  `scan-secrets.sh` 共用同一套词汇；**只在 `scripts/secret-scan-allowlist.txt`
  登记过的文件里生效**（否则外部贡献者加个注释就能绕过）。
- **`--rules <toml>`**：可挂 gitleaks 格式规则文件，同一套引擎吃两种规则。
- **`--exclude` / `--only`**：按路径子串跳过、只跑指定规则。

### 明确不做

- **不做在线验证**（把密钥发给服务商 API 校验）：治理工具本身不该外泄凭据，
  且 CI 无出网时会全部降级为 unknown。
- **不做格式未知令牌的强判定**：那类只由泛化规则 + 熵兜底，标 `low`。

### 验证（2026-11-24）

- 自造语料 40 个泄露样本（8 种文件类型 × 20 类）→ **40/40**；
- Python 标准库 636 个 `.py`（纯负样本）→ **0 误报**，18.7 s；
- 本仓自扫 → 6 条，全部落在历史记录与自检夹具里，且都是 `low`（已在 §「已知」写明）；
- 包内 29 条判据覆盖每条规则的正例 + 三类反例（占位符 / 无数字标识符 / 未登记文件的注解）。

> ⚠ **sdist 与 tag 树的一行差异（如实记录）**：`1.0.3` 上传 PyPI 的 sdist 里，
> `packages/allin-governance/tests/test_secrets_scan.py` 还有一行**合成** AWS 键的字面量
> （`AKIAQ7Z2…`，测试夹具，非真凭据）。发布后为了通过 GitHub push protection，
> 该行也改成了运行期拼接，因此仓库 tag 树比 PyPI sdist 多这一处差异。
> **不影响包的任何代码与规则**（只差一条测试夹具的写法）；下次发版（1.0.4）的 sdist 会是干净的。

### 同时新增（流程固化）

- **`scripts/sync-before-push.sh`**：推送前先 fetch，落后则 ff-only 拉取，分叉则停下报人；
  推完逐端 `ls-remote` 核对 SHA。配套纪律见 `SPEC-004` 第 71 条与 `SPEC-101` §4.5。

## `allin-governance` 1.0.2 —— 2026-11-24

**1.0.0 缺陷线的收口版。** 1.0.1 已把 sdist 物化修好（109 文件、实测可装）并随包分发
`github` 子命令；本版补齐同一缺陷线上剩下的几项。

### 与已发布的 1.0.1 的差别（实测口径）

| 项 | 1.0.1（已发布） | 1.0.2（本版） |
|---|---|---|
| sdist 自包含 | ✅ 109 条目 / 80 项映射树，干净 venv 装得上 | ✅ preflight 逐棵核对 |
| `github` 子命令 | ❌ **一调就崩**：`TypeError: main() takes 0 positional arguments but 1 was given` | ✅ 修好（见下），六个子命令逐个 `--help` 回归 |
| `verify` 拒绝越界清单 | ❌ 清单里 `..` 仍会读仓外文件并回「快照未被改动」 | ✅ fail closed（exit 3）+ 回归用例 |
| license 元数据 | ❌ `license = { text = … }`（setuptools 77 起弃用） | ✅ SPDX 表达式 + `license-files` |
| 发版前置校验 | ❌ 无 | ✅ `scripts/release_preflight.py`（`--install` 双产物各装一次） |
| sdist 自包含回归测试 | ❌ 无 | ✅ `tests/test_dist_artifacts.py` |
| 版本护栏 | ❌ 仍断言「必须是 `0.0.0aN`」 | ✅ 改为 pyproject ↔ `__init__` 对账 |

> 为什么不是「重传 1.0.1」：PyPI 的版本号不可覆盖也不可删除。1.0.1 已被占用，
> 内容与本仓当前树不同，只能顺延。

### 本版修掉的 `github` 子命令缺陷（1.0.1 已发布版本实测）

1.0.1 的招牌能力在发布态**完全不可用**：

```
$ allin-governance github --help
TypeError: main() takes 0 positional arguments but 1 was given
```

两个原因叠加：

1. **包装层与工具入口签名不一致**：`_cmd_github(argv)` 把 argv 传给
   `github_release.main()`，而后者当时是 `def main():`（只读 `sys.argv`）。
2. **源码树形态缺映射**：`from ._github import ...` 只在 wheel 里成立，
   `_github/` 由 `package-dir` 映射产生，源码树里不存在 ⇒ 开发态与
   `pytest packages/allin-governance` 直接 `ModuleNotFoundError`。
   同族存量缺口：`scan` / `deps` 的 `_toolkit` 自 a8 起就有一样的问题，
   只是从来没人在源码树里跑过它们。

修法（不复制源码）：两个工具入口改 `main(argv=None)`；包装层加
`_github_modules()` / `_toolkit_modules()`，安装态走包内、源码态按仓内路径加载
（与 `_repocheck_dir()` 同一纪律）。并补一条**逐个子命令**的 `--help` 回归测试 ——
此前只测了 `repocheck --help`，剩下五个从未被「跑一下」。

### 验证（2026-11-24）

- `python scripts/release_preflight.py --install` → `PREFLIGHT ok=8 fail=0 skip=0` / `RESULT: CLEAN`
- 负对照：从 sdist 摘掉 `_repocheck/` → `[FAIL] sdist 自包含` + `BLOCKED`，同次 `twine check` 仍 `[ok]`
- 包测试 53 passed（含六个子命令逐个 `--help`）；全仓 pytest 391 collected / 0 failed；platform 75/75；SAST 0 条
- 双形态实测：sdist 与 wheel 各在干净 venv 安装，**6 个子命令**（deps/github/init/repocheck/scan/verify）
  + `init --dry-run` 全部 exit 0 —— 1.0.1 的 `github` 缺陷正是这条实验抓出来的

## `allin-governance` 1.0.1 —— 2026-11-24

**GitHub 建仓推送 + 三端增量巡检随包分发**（gitee 远端为权威源）。

- 新增 `github` 子命令：`allin-governance github <whoami|list|create|public|remote|push|verify|sync>`，
  以及 `allin-governance github github-sync <list|pull|drift|sync>`（三端巡检）。
- 令牌纪律：优先 `GITHUB_TOKEN` 环境变量，否则 Windows GCM `git credential fill(host=github.com)`；
  **不指向令牌文件、不回显、不入库**。
- 权威关系单向：**gitee 远端 → 本地 → GitHub**；不向 gitee 推送（原 pushorigin 废止，改为只读 `drift`）。
- 判据按 GitHub 平台差异实现（先私后公、SSH 通道、shallow 补全、5000/h 主限流 + 次级退避），
  **不照搬 Gitee 的 `public` 整数 / 空仓 PATCH / 保守退避口径**。
- 修 `verify` 的 ref 格式错配假红（本地 `refs/...` vs 远端去前缀 `heads/...`），修后单仓实测 `[SKIP] 无差异`。
- 修 `check_readme_refs` 正式版摘要显示 bug（`extract_versions` 未传 actual，导致明明含真值却显示 False）。

## `allin-governance` 1.0.0 —— 2026-11-24

**第一个正式版。** 从此不再叫 `0.0.0aX` 占位系列。

> ⚠ **事后订正（2026-11-24，不改原文）**：本版 **sdist 装不上**，下表「装出来能跑」
> 只对 wheel 成立。缺陷与修复见上方 `1.0.1`。原文保留，方便对照当初的判据漏在哪。

### 为什么现在够 1.0

不是因为功能多，而是因为**发版这件事本身可信了**：

| 条件 | 状态 |
|---|---|
| 唯一确定的版本号 | 一个来源（`pyproject.toml`），`--version` 与包元数据一致，R2 门禁盯着文档里的版本声明 |
| 产物可重复构建 | wheel/sdist 每次都能出，sha256 与 PyPI 逐字符核对 |
| 装出来能跑 | 每次发版都在**干净 venv 里装一遍**再验（这条是 a9 事故换来的） |
| 副作用可控 | `init` 只写目标目录；`repocheck` 只读；`scan`/`deps` 只报告 |
| 破坏性操作需显式确认 | 删除类提交必须带「功能面 × 接任者」表（g08）；改名默认 dry-run |

### 能力清单（1.0 冻结的接口）

```bash
allin-governance init [目录]      # 生成最小治理骨架：14 道门禁 + 文档四分类 + registry + 基线
allin-governance repocheck [路径] # 离线仓库体检：30 条仓体规则 + 20 条门禁规则(--gates) + 3 条测试规则(--tests)
allin-governance verify           # 复核 init 快照与 GENERATED.json 是否一致
allin-governance scan             # 发布区扫盘：项目指纹 / 重复检出 / 迁移残留
allin-governance deps             # 依赖体检：声明 · 实装 · import 三者对账
```

### 1.0 起承诺什么、不承诺什么

**承诺**：上面五个子命令的名字与「退出码 0/1/2/3」的语义，在 1.x 内不变。
**不承诺**：规则集只增不减 —— 门禁规则会随治理实践增加（id 追加，不改旧 id 的含义）。

### 自 a10 以来的变化

无代码变更；本版是把 a10 的能力正式定版。a10 修的两个缺陷（嵌套子包未声明、
双环境 import 路径）已在上个版本说明里记过。

## `allin-governance` 0.0.0a10 —— 2026-11-24

**修 a9 的一个发布缺陷：测试规则族在包装版里根本不可用。**

### 缺陷实况（a9 已发布，不能覆盖，故发 a10）

`a9` 的 `--dump-profile` 在仓内能看到测试规则族，但**从 PyPI 装出来的包看不到**，
`repocheck --tests` 直接崩。两个独立原因叠加：

1. **嵌套子包没声明**：`_toolkit` 目录映射进了包，但它的子包 `_toolkit/pytrunner/`
   不在 `packages` 列表里 ⇒ wheel 里没有它 ⇒
   `ModuleNotFoundError: No module named 'allin_governance._toolkit.pytrunner'`。
   （与 allin-toolkit 的 `calculator/calculator/` 是**同一个坑**，本轮第二次踩。）
2. **双环境 import 路径**：`rules_tests.py` 只写了仓内那条
   `from _shared.pytrunner import Probe`；装进包后 `_shared` 不存在，需回退到
   `allin_governance._toolkit.pytrunner`。现改为 try/except 双路径。

### 顺带修一个判据误判

环境没装 pytest 时，`python -m pytest` 以 returncode 1 退出并打 `No module named pytest`，
原实现会把它判成「项目的测试已腐烂」。现识别该情形并跳过 ——
**「本机没装工具」不是「项目有问题」**，这条在体检器里必须分清。

### 验证（这次验的是装出来的包，不是仓内）

```
从 PyPI 装干净 venv → repocheck --dump-profile 显示 [51][52][53]
                     → repocheck <含坏测试的目录> --tests 报收集错误
                     → wheel 内含 _toolkit/pytrunner/{__init__,error_types,log_manager,test_probe}.py
```

教训：**「仓内能跑」不等于「发布物能跑」**。a9 的验收只看了仓内 `--dump-profile`，
没在装出来的包里验 —— 这跟 a8 那次「提了没做」是同一类失误：**验的地方不对**。

## `allin-governance` 0.0.0a9 —— 2026-11-24

这版**有实质内容**：两个工具真正进了 wheel，repocheck 多了一族测试规则。

### 新增子命令 `scan` / `deps`（终于随包分发）

a8 时提过一件事：`scan_repos.py` / `deps_doctor.py` 只在仓内，没进映射。
本版把这两个能力收进 `tools/_shared/`（setuptools 的 `package-dir` 只能映射**目录**，
散放的单文件打不进 wheel），映射为 `allin_governance._toolkit`：

```bash
allin-governance scan --deep     # 发布区扫盘：项目指纹 / 重复检出 / 迁移残留
allin-governance deps            # 依赖体检：声明 · 实装 · import 三者对账
```

源码仍只有一份（映射不复制）。

### 新增 `repocheck --tests`：测试规则族（51-53）

前 30 条规则都是静态的。这族补「测试还能不能跑」：

| id | 判据 |
|---|---|
| 51 | 有测试文件或 `tests/` 目录（没有则 skip，不算缺陷） |
| 52 | `pytest --collect-only` 能收到用例（有测试却收不上来 = 测试已腐烂） |
| 53 | 有 pytest 配置或 Makefile 的 `test` 目标 |

默认关闭：要拉两次子进程，比仓体规则慢两个数量级。
判据复用内联的探针内核（上提自 py_test_runner / PyPI `pytrunner`）。

### 内联跨仓依赖

`tools/` 下的 `gitee_release.py` 的 `--release` 此前 `import gen_third_party_notices` ——
该模块**不在本仓**，住 pluginplayer 仓的 tools/ 下。本版把
`is_runtime_artifact()` / `dist_payload()` 与两个常量原样内联。
注：常量描述的是 pluginplayer 的 dist 结构，内联消除的是「import 不到」的硬失败，
没有消除语义耦合 —— 注释里已写明。

### 并入 py_test_runner

远端起本地仓均删除，仅保留 PyPI `pytrunner` 1.0.0；
探针内核（548 行）上提为 `tools/_shared/pytrunner/`，完整历史 21 提交存 bundle。
本仓仓数 86 → 85。

## `allin-governance` 0.0.0a8 —— 2026-11-24

**本版不含包内工具代码变更。** 发布的目的是把一次结构性治理对齐到版本线上，
让「你装的包对应的仓是什么形态」有据可查。

### 变了什么（对消费者）

- **CLI / API 零变更**：`init` / `repocheck` / `verify` 的用法与 a7 完全一致。
- **仓规模发生变化**：本仓从 143 个仓收敛到 **86 个**。
  - 68 个冻结子项的**独立仓入口全部清除**（远端 56 个 + 本地 66 个目录），
    内容并入 4 个合集仓（dev-toolkit / game-prototypes / media-prototypes / music-prototypes）
    与 players-unified；每个子项的**完整提交历史**保全在合集的 `archive/<名>` 分支。
  - `foolproof-operation` 并入本仓后删除，仅保留 PyPI 发行。
- 若你的项目里断言过「allin 管 143 个仓」，需要改。

### 两个新工具（仓内，暂未随包分发）

- `tools/_shared/` 下的 `scan_repos.py` —— 发布区扫盘：项目指纹、重复检出、迁移残留。只报告不处置。
- `tools/_shared/` 下的 `deps_doctor.py` —— 依赖体检：`requirements` 声明 · 解释器实装 · 仓内 import 三者对账。

它们目前**只在仓内**，不在 wheel 的 package-dir 映射里。若后续要随包分发，
需在 `pyproject.toml` 增加映射并跑 `check_pkg_parity`（当时在 `tools/` 下）逐文件 sha256 对账
（a3 的教训：漏收 4 份运行时事实源，对账 12 处红）。

## `allin-governance` 0.0.0a7 —— 2026-11-24

让 `repocheck` 能直接跑治理门禁，并修掉两类「判得太粗」的误报。CLI 形态不变，a6 的命令全部照旧。

### 新增：`repocheck` 门禁规则族（`--gates` / `--self` / `--only-gates`）

此前 `repocheck`（仓体卫生）与治理门禁（`g00`–`g20`）是两套东西，互不知情 ——
于是会出现「门禁全绿、体检却说凭据泄露」这种各说各话。现在 `repocheck` 能把门禁纳入同一次评估：

```bash
repocheck <仓> --gates              # 仓体 30 条 + 门禁 20 条（规则 id 31-50）
repocheck . --self --only-gates     # monorepo 仓根：只跑门禁结论
```

- **判据只有一份**：这 20 条不重写任何判据、也不 import 门禁内部函数，只复用每道门
  对外稳定的 CLI 契约（`--root` + 退出码 0/1/2/3）。门禁改了判据，这里立刻跟着变。
- **`--self` 是 monorepo 必需品**：`repocheck` 的默认项目发现只认一级子目录，
  仓根从来不是「项目」；少了它，门禁套件在仓根而仓根永远测不到。
- **默认关闭**：每道门一次子进程，实测约 90 秒/仓；日常体检 0.26 秒/仓 的口径不能被拖垮。

### 修复：规则 22（敏感文件）不再只看文件名

`.npmrc` / `.pypirc` 此前一律判敏感 —— 但纯镜像配置（`registry=…`）根本不含凭据，
这条误报等于逼每个用镜像源的项目加豁免。改为**看内容**：出现 `_authToken` / `_auth` /
`_password` / `username|email` 才算。

### 修复：规则 23（硬编码密钥）不再把「讲解」当「泄露」

文档里「按 `sk-` / `ghp_` / AKIA 等 11 类模式扫描」这类陈述，此前会被判成硬编码密钥。
改为看**同行语境**：仅 `.md` / `.rst` / `.html` 且该行含「模式 / 扫描 / 示例 / 夹具」等
说明词时放行。**代码文件与 `.txt` 不享受**这个豁免 —— 注释里写「示例 token」不是免死金牌，
随手记的 `notes.txt` 里贴真 token 恰恰是最常见的事故形态。

### 修复：规则 7（旧路径残留）补齐两类语境

历史归档区（`docs/md/`）与他机事实源（`docs/事实源/机器/<HOST>/`）里的旧路径是出处标注，
不是「照着做会失败」的可执行路径，不再判红 —— 与「每台机只自验自己那份事实」同口径。

### 顺带

`repocheck` 版本 2.1.0 → 2.2.0；`--dump-profile` 新增 `gate_rules` 键（文本与 JSON），
让「这次到底能查什么」可自省。体检自检用例 83 → 87（两条判据各配一正一反）。

## `allin-governance` 0.0.0a6 —— 2026-11-22

把 a5（2026-11-08）之后积累的**门禁与体检器修复**收口成一个可安装版本。
本版不改 CLI 形态，命令与 a5 完全兼容；变化都在「判得更准」。

### `repocheck` 规则 6（依赖声明）：消除大批假阳性

此前规则 6 看到源码 `import` 了某个模块，但没在依赖声明里找到对应包名就报缺依赖 ——
而真实情况往往是「名字不一样」。本轮把映射口径补齐：

- 数字前缀包名（`3dworld` → `world3d`）与 `src-layout` 包目录识别；
- namespace 目录、本地可编辑依赖、dist→import 别名映射；
- 常见别名：`python-vlc`/`PyInstaller`、`PyExecJS`→`execjs`、LibreOffice `uno` 宿主模块；
- 新增 `# r6-local` 声明，供「确实只在本地用」的模块显式豁免。

效果：实测 21 仓的缺依赖误报清零。

### 许可判据：两个长期误判

- GPL 项目**自报 GPL** 此前被判「缺许可声明」——已修；
- **MIT-0 被认成 MIT**（`mit` 子串命中）——标题型许可现在只在文件前 500 字符匹配，
  避免 GPL v3 全文第 13 条标题含「Affero」导致被认成 AGPL-3.0 的同类误判。

### 门禁套件

- 跨机可移植性收口：Windows 装入点防护下的 D6 假绿/误报，子进程编码统一钉死；
- 自检不再泄漏临时 git 仓库（Windows 上残留目录）；
- 发布区治理闭环：门禁覆盖扩到 139 仓，error 285 → 9 → 2，待裁决清零；
  配套三个工具缺陷的修法（历史留档不可改写、路径按归一化名逐段解析、
  许可字段复用门禁判据）见仓内 `docs/新人开发上手指南.md` §4.9。

### 兼容性与升级

命令面（`init` / `repocheck` / `verify` / `agent-manifest`）与 a5 一致，
零第三方运行时依赖不变。直接 `pip install -U allin-governance` 即可。

## `allin-governance` 0.0.0a5 —— 2026-11-08

一次深度安全审核后的防线加固，变化集中在「凭据防线不再有后缀后门」与
「门禁不再把没检查当成通过」。

### 修复：样例文件后缀不再是凭据豁免权

`g03-credentials` 此前对任意 `*.example / *.sample / *.template / *.dist`
整文件豁免，CI 增量扫描也把同后缀当作仓库夹具 —— 新建样例文件并加一行注解
即可把真实令牌从扫描面抹掉。两侧现统一改为**按内容判定**：占位符保持安静，
真实令牌形状即使藏在 `.env.example` 里也报红；内联注解豁免只认
`scripts/secret-scan-allowlist.txt` 登记的路径。

### 修复：SKIP 不再以退出码 0 冒充通过

`govlib.Report.exit_code()` 在严格模式下把「整类未检查」暴露为非零；跑批区分
「环境不适用」与「本应跑却没跑」，CI 增加 `status=clean` 机器准出断言；聚合器
把平台跳过的门禁数量与 clean 分子同屏显示；harness 的组件报错不再被
informational 用例吞掉。

### 其余

- `repocheck` 规则 28：配置文件不可读不再判为「已配置 SAST」；
- 仓内门禁源码与 `init` 出厂骨架同步更新。

## `allin-governance` 0.0.0a4 —— 2026-11-08

两个消费者可感知的新能力，全部来自一次外部 README 评审的落地（评审→再平衡裁决→实现）。

### 新增：`repocheck --profile {monorepo,component}`（repocheck 2.1.0）

「什么场景该跳过哪些规则」的口径收编进工具本身，不再散落在各仓跑批脚本里：

- `--profile monorepo`：monorepo 仓根扫描，自动跳过规则 1（缺 .git）与
  7（旧仓库路径残留）——内部中间目录不是独立项目，这两条必然假阳性；
- `--profile component`：monorepo 子件扫描，跳过规则 1,2,4,5——版本控制 /
  README / 依赖声明 / LICENSE 由仓根统一持有；
- 与 `--skip-rules` **显式互斥**（并存退出码 2），杜绝一次扫描出现两套豁免口径；
- 被排除的目录名单属各仓布局事实，仍由 `--exclude` 提供，不进工具。

### 新增：门禁失败时的修法提示（remediation）

20 道治理门禁的注册表逐条登记了「失败时该怎么修」，聚合器（`run`）在门禁
失败时直接把对应修法打在失败项下面，不再需要去翻规范文档。修法与门禁
同处 `registry.json` 声明，没有第三份清单可漂移；字段缺失时降级为指向
`RULES.md` 的通用提示。

### 其余

- 包内同步：本次 wheel 收录仓内 2026-11-07 治理批次之后的 `registry.json` /
  `run.ts` / `cli.py` 真身（映射 sha256 对账口径不变）。

## `allin-governance` 0.0.0a3 —— 2026-11-07

一次真实缺陷修复 + 一批门禁判据加固。`init` 的出厂形态不变（仍是 14 道纯标准库
门禁），变的是**判据本身**——包的门禁源码与 allin 仓是同一份（映射，不是复制），
仓内一个月的治理加固随本版整体进入发布物。

### 修复：a2 的 wheel 缺 4 份运行时事实源（本版最大的事）

a2 的 wheel 里**没有** 4 份运行时判据文件：`exceptions.yml`、`registry-known-gaps.txt`，
以及包内 `preset/` 目录下的 `allin.patch.yml` 与 `README.md`（这三类路径均指 wheel
内部的布局，不是本仓路径）—— 对应 g18 / g17 / g14 的运行时判据。缺了它们，装出来的包
跑这些门禁会**判不全**（少报，不是报错，所以不打开对账根本看不见）。

发现方式值得一提：新增的包映射对账脚本（`check_pkg_parity`，当时在 `tools/` 下、随 allin 仓
入库并接进 CI 双平台）把「已安装包 ↔ 仓内真身」逐文件 sha256 对账，首跑即对出
12 处红 —— 发布物与源码的漂移，从「一次性实测记录」变成了**退出码**。

本版起这 4 份随 wheel 分发，对账在 CI 的 init 端到端 job 里常驻。

### 门禁判据加固（`init` 生成的骨架随之更新）

- **g03 凭据**：增第三面「机器本地明文凭据文件」，且明文凭据**真正删除**而非仅拉黑；
  另修一处 hex-secret 正则把 Windows 路径误判成密钥的误报。
- **g04 推送证据**：从只核一个远端改为核**所有推送目标**，凭据红线覆盖 `pushurl`
  （双核推送场景的前置补盲）。
- **g20 事实源**：增「本机自述一致性」判据（自述与所属机器不符即红）。
- **g01 路径**：修复 `gov-paths: allow` 同行注记被 WIN_PATH 误判的误报。

### 双平台 / 控制台健壮性

- wheel 包数据 EOL 归一化，Windows 下 `init` 不再因 CRLF/LF 差异假红；
- stdio 编码钉 UTF-8 的路径覆盖补全（延续 a1 的 cp1252 修复线）。

### 测试基线

`pytest packages/allin-governance`：**37 passed**（a2 基线 36 + 新增 1）。

## `allin-governance` 0.0.0a2 —— 2026-10-31

三个新增，一个旧缺陷被真正修掉。

### 新增 `allin-governance verify`

按 `GENERATED.json` 复核快照：每个文件的 sha256 重算一遍，报告「一致 / 改动 / 缺失」。

```bash
allin-governance verify my-repo        # 0 一致 · 1 有改动或缺失 · 3 没有清单
```

在此之前 `GENERATED.json` 只是一份没人读的元数据 —— 快照的全部价值在于**能被核对**，
而没有复核命令时，「这个文件是不是原样」只能靠人肉 `sha256sum`。

它**不**把「你自己加的门禁」算成漂移：给自家仓加门禁是正常行为，
把正常行为报成问题，只会训练人忽略这个命令。

### 新增 `init --with-exceptions`

额外带上 `g18-exceptions` 与 `exceptions.yml` 台账模板（15 道门禁）。
默认不给的原因没变：g18 需要 **PyYAML**，与本包「零运行时依赖」的承诺冲突。
缺 PyYAML 时 g18 会报 `ledger-unusable` 并阻断 —— 刻意的：判据跑不了就不许装作通过。

### 修复：sdist 现在自包含（这是 a0/a1 的真实缺陷）

a0 与 a1 **只发 wheel**，原因是 sdist 是坏的：

- `python -m build --sdist` 打印 `Successfully built`；
- `twine check` 报 `PASSED`；
- 但包里**没有** `_repocheck/` 与 `_gatesuite/` —— 这两棵树靠 `package-dir` 的
  `../../` 映射进包，而 sdist 不能收录项目根之外的文件；
- 从那个 sdist 装出来的包，`repocheck` 与 `init` 会在运行时找不到源码。

**缺陷的形态是一路绿灯**，所以这次不是"改一行"，而是换构建路径：

```bash
python scripts/build_dist.py     # 物化映射树 → sdist + wheel → 自校验
```

脚本把两棵树物化到**临时目录**的项目副本里（仓内不产生副本），改写副本的
`package-dir` 为安装后布局，再构建；构建完**打开 tar 复核每棵树是否真的在里面**。
构建成功而产物不完整，正是它存在的理由。

### 顺带

- `requirements-release.txt`：出包期依赖（build / twine）单列，不再混进开发依赖
- `cli.py` 里重复的 `__version__` 已在 a1 删除；本版只递增一处

## `allin-governance` 0.0.0a1 —— 2026-10-31

**只修一个会让命令假装失败的缺陷，其余与 a0 相同。**

`init` 在 **cp1252 控制台**（西文 Windows、以及 GitHub Actions 的
`windows-latest` runner）上会抛 `UnicodeEncodeError`：

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 2-3
```

原因不是逻辑错了，是**输出的默认编码跟着终端走** —— 这套工具的每一行提示都是中文。
最坏的后果不是崩溃本身，而是它发生在**打印阶段**：文件全部写好了，命令却以
exit 1 收场，用户看到「失败」、磁盘上是成功。

修法：新增 `_stdio.configure()`，把 stdout/stderr 钉成 UTF-8（`errors="replace"`），
在 `cli.main()` 入口统一调用 —— 所有子命令与 `--help` 共用同一条出口。
回归测试用**子进程 + `PYTHONIOENCODING=cp1252`** 复现那个环境，而不是 mock 流。

顺带：`cli.py` 里重复定义的 `__version__` 已删掉，改为从包根取 ——
两处各写一个版本号，「包说 a1、CLI 说 a0」这种漂移没人会在发布前发现。

## `allin-governance` 0.0.0a0 —— 2026-10-31

**占位版本，但可运行。** 发它的直接目的是占住 PyPI 名字（REC-AU-21 D1.3），
不是「功能完备」；因此不承诺 API 稳定，下一版可能改名或改参数。

包含两个子命令：

### `allin-governance init <目录>`

在空目录生成**可跑的最小治理骨架**：14 道可执行门禁 + 文档四分类
（`规范/` `事实源/` `记录/`）+ `registry.json` + 基线棘轮 + 生成清单。

判据是实测的：装 wheel → `init` 一个空目录 → `npm run check:governance`
**exit 0 / 14-14 gate(s) clean**（Windows 与 Linux CI 各验一次）。

出厂 14 道是跑出来的边界，不是挑出来的：

- 20 道里 15 道能在空仓库上 pass；`g18-exceptions` 需 PyYAML，与「零第三方运行时
  依赖」冲突，列为按需；
- `g14/g15/g16/g17/g19` 判的是 allin 自己的 preset / 文档契约 / 平台台账，
  别的仓没有对应物，塞进来只会让新用户第一天看到与他无关的红。

三条行为约定：

- 二次 `--force` **零改动**（幂等）；
- `README.md` / `LICENSE` / `docs/**` **永不覆盖**，只在缺失时创建；
- `package.json` 与 `.gitignore` **合并**而不是取代。

### `allin-governance repocheck <目录>`

离线仓库体检：30 条规则、0–10 健康分、text/JSON/CSV/HTML 四种导出、五档退出码。
不联网、不执行被体检代码、只用标准库。

**已知缺陷**：本版**只发 wheel，不发 sdist**。sdist 构建取不到 `package-dir`
映射进包的两棵源码树（`_repocheck/` 与 `_gatesuite/`），从它装出来的包会在运行时
找不到源码。发一个装得上但跑不起来的 sdist 比不发更坏，所以不发。修法见
`docs/记录/审计/allin自身做大做强方向修正_2026-10-31.md` §7.4。
