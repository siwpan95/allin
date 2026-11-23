# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.2.0] - 2026-11-23

### Added

- **门禁规则族 `--gates`（规则 31–50）**：把 `tools/gate/governance` 的 20 道治理门禁
  纳入同一次体检。此前这套关系是单向的 —— `tools/publish_area_gate.py` 调 repocheck
  去体检发布区，而 allin 自己的 20 道门禁只管本仓，两条评估线互不知情，
  于是有「20 道全绿 / 发布区却是另一种结论」的结构性盲区。

  **判据只有一份**：这 20 条不重写判据、也不 import 门禁的内部函数（私有契约，会随重构演化），
  只复用每道门对外稳定的 CLI 契约（`--root` + 退出码 0/1/2/3）。因此它与 `run.ts`
  跑的是同一份判据文件；`g14-preset` 这类 `profileProbe: true` 的门按 `registry.json`
  声明补传 `--no-profile`，与 `run.ts` 参数等价（实测 20/20 同结论）。

  **按项目裁剪而非逐条 SKIP**：没有治理套件的仓不注册这 20 条。若登录后 SKIP，
  20 条跳过项会把每仓分数上限压到 9.0，发布区健康分 9.5 整体塔到 9.0 ——
  把「没这套东西」错记成「有东西没测」。

  **默认关闭**：每道门一次子进程，实测 90 秒/仓；日常体检 0.26 s/仓 不能被它拖垮。

- `--dump-profile` 新增 `gate_rules` 键（文本与 JSON 同步），让「这次到底能查什么」可自省。

- **`--self`**：把根目录本身也作为一个项目体检。存在的理由不是"方便"——monorepo 的门禁套件
  在仓根，而默认的项目发现只认一级子目录，**仓根从来不是「项目」**，于是 `--gates` 对 allin
  自己恒不生效。没有它，门禁规则族只能测别人、测不了本仓。

- **`--only-gates`**：只跑门禁规则族，不掺 30 条仓体卫生规则。给「用 repocheck 当治理门禁
  单一入口」用：实测不带它时，规则 22/23 会把 `console/.npmrc`（仅 registry 配置）与交接卷里
  「本次扫描了哪些密钥模式」的文档陈述判成 error，让「门禁红」与「仓体脏」混为一谈。
  仓体卫生是另一步的职责，不该混进同一批退出码。

### Fixed

- **g03-credentials 判据补一维（URL 查询参数里的 hex 不是凭据）**：实测误报 —— 微信公众号
  文章链接的 32 位签名（`sn=` / `chksm=`）被当裸 hex 令牌判红。现在只对「URL 查询串内 +
  键名不含凭据词」放行，`?access_token=<hex>` 这类仍报红。自检 caught 16 / clean 9→10 /
  misreports 0，正反例齐备。
- **门禁源码不再被自己判红**：g03 用 `git grep --cached` 扫**索引**，源码里写完整的 30+ 位
  hex 字面量会被自己抓走。判据文档里的示例改为打码、自检夹具改用拆段拼接生成。
  ⚠ 同源陷阱：**跑门禁前不 `git add`，验证的是索引里的旧内容**——本轮实测因此出现过一次假绿。

### Changed

- `check_project()` / `scan()` 新增 `with_gates` 参数；`_safe_check()` 同步透传。
- 规则 7（旧仓库路径残留）的历史归档排除新增两族路径：`docs/md/`（历史快照区，
  allin 的 ASCII 别名「历史/」）与 `docs/facts/机器/`、`docs/事实源/机器/`（他机事实源）。
  两类都不是「照着做会失败」的可执行路径，判红只会逼人篡改历史；与此前 g19/g20
  「每台机只自验自己那份」同口径。

## [2.1.0] - 2026-11-08

### Added

- **`--profile {monorepo,component}`**（2026-11-07）：把「什么场景该跳过哪些规则」
  的口径收编进工具本身，不再散落在各仓跑批脚本里（allin 仓 `run_all_gates.sh`
  曾三处手写 `--skip-rules`，属第二套口径的温床）。`monorepo` = 仓根扫描
  （跳过规则 1 缺 .git、7 旧路径残留——内部中间目录不是独立项目）；`component`
  = monorepo 子件扫描（跳过规则 1,2,4,5——版本控制/README/依赖/LICENSE 由
  仓根统一持有）。与 `--skip-rules` 显式互斥（并存退出码 2），杜绝一次扫描
  两套豁免口径。目录名单仍由 `--exclude` 提供——那是各仓布局事实，不进工具。
  `run_all_gates.sh` 与 CI `gates.yml` 已同步切换为 profile 调用。

### Changed

- **规则 3（无测试）扩口**（2026-10-30）：monorepo workspace 的嵌套
  `test/` / `tests/` 目录（路径段精确匹配，`contest/` 等形近目录不误放行）
  与 JS/TS 测试惯例 `*.test.*` / `*.spec.*`（任意层级）现在被认可，
  不再把「有测试」误报成「无测试」（典型场景：platform 的
  `apps/*/test/*.test.mjs`）。新增 4 条回归用例（嵌套目录 / JS 测试 /
  形近目录不放行），套件 60 项全绿。

## [2.0.0] - 2026-10-21

规则从 8 条扩到 30 条，引入严重度分级与健康分，CLI 全面工程化。
判定口径参照 OpenSSF Scorecard、repolinter、OpenSSF Best Practices、
standard-readme、Keep a Changelog 与 gitleaks 的公开规则集。

### Added

- **健康分**：0–10 分，按 `10 × log1p(通过项权重) / log1p(总权重)` 计算，
  权重 error=3 / warn=2 / info=1；同时输出通过率 `pass_rate`。
- **严重度分级**：每条规则标注 error / warn / info，报告按级别分色与排序。
- **新增 22 条规则**：
  - 文档类 9-16：许可证可识别性、许可证三处声明一致性、README 结构完整性、
    README 相对链接死链、SECURITY.md 存在性与内容评分、CONTRIBUTING、
    CHANGELOG 结构。
  - git 卫生类 17/20/21/22/23/29：CHANGELOG 落后最新 tag、二进制或大文件签入、
    构建产物被跟踪、敏感文件入库、源码硬编码密钥、空壳仓。
  - CI 类 19/24/25/26/27/28：CI 配置存在、危险 workflow 写法、Token 权限过宽、
    依赖未固定、依赖更新工具、SAST 配置。
  - 布局类 30：含 `.py` 的目录名必须是合法 Python 标识符。
- **规则引擎**：规则改为声明式 `Rule(...)` 数据，新增规则只改 `rules_*.py`，
  执行器、评分、报告渲染、自省自动跟进。新增 `rulebase.py` / `scanctx.py` /
  `report.py` / `rules_*.py` / `cli.py` / `_optional.py`。
- **`ProjectContext` 惰性索引**：单次目录遍历替代原来的 6 次重复 `os.walk`；
  git 调用按需触发且带缓存。
- **CLI 工程化**：`--exclude` / `--depth` / `--format` / `--json` / `--output` /
  `--fail-on` / `--min-severity` / `--skip-rules` / `--workers` / `--no-color` /
  `--version`。
- **`--fail-on` 退出码**：`none` / `any` / `error` / `warn` / `score:N`，
  退出码 0/1/2/3 语义明确，可用于 CI 门禁。
- **JSON 报告**：新增 `--format json`，schema 版本 2，含 summary / engine /
  projects 三段，findings 为全量规则判定。
- **可选依赖 + 降级**：`license-expression` / `detect-secrets` /
  `markdown-it-py` / `requirements-parser` / `packaging` 装上即启用二次校验，
  不装走内置实现，结论口径一致。`pyproject.toml` 的 `[full]` 登记。
- **`pyproject.toml`**（PEP 621 元数据）与 `requirements-dev.txt`（依赖用 `==` 锁定）。
- **工程配置**：`.github/workflows/ci.yml`（Python 3.11–3.13 矩阵 + 自检）、
  `.github/dependabot.yml`（依赖与 action 月度更新）、
  `.pre-commit-config.yaml`（ruff + bandit 静态检查）。
- **测试套件**：`pytest` 57 个用例 + 无 pytest 时的兜底冒烟；
  `test_fixtures.py` 提供声明式假仓库构造器，新增规则只需在用例表加一行。

### Changed

- **`check_project()` 返回结构升级为 v2**：新增 `findings` / `score` /
  `pass_rate` / `severity_counts` / `skipped` / `rule_errors`，`metrics` 扩充
  `git_ok` / `git_files` / `skipped_count` / `degraded` / `truncated`。
- **`issues` 只收 error 与 warn 级**，info 级只进 `findings`，避免报告刷屏。
- **`RULES` 由 `(label, criteria)` 二元组改为 `Rule` 数据类**，`id` 固定 1–30。
- **`dump_profile()` 升到 schema 2**：`rules` 每条前三个键仍为
  `id` / `label` / `criteria` 且顺序不变（向后兼容），其后追加
  `key` / `severity` / `requires_git` / `requires` / `status`。
- **`DEFAULT_EXCLUDE` 大幅扩充**：补入 `.venv` / `venv` / `.tox` / `.eggs` /
  `site-packages` / `target` / `.pytest_cache` / `.ruff_cache` / `.idea` /
  `.vscode` 等。原先不排除虚拟环境会让索引与 import 扫描严重失准。
- **去本地化**：`G:\` 硬编码全部移除，GUI 默认取当前工作目录，CLI 默认 `.`。
- **GUI 升级**：新增健康分列与 E/W/I 计数列，按分数分档着色，扫描过程显示进度。
- **导出复用 `report.py`**：GUI 的 CSV/HTML 与 CLI 输出完全同源，不再各写一套。

### Fixed

- 规则 6（import 断裂）在「项目根本身是包」时稳定误报自己的包名
  —— `my_pkg/__init__.py` + `tests/test_x.py` 里 `from my_pkg import x` 被标为断裂。
- `discover_projects` 的 `max_py_depth` 存在 off-by-one：超限的那一层仍会被检查文件，
  与文档语义不符。
- CSV 输出到 stdout 时，`csv` 模块产生的 `CRLF` 被 Windows 文本模式二次转换，
  变成 `CR CRLF` 导致管道读取多出空行。
- CSV 的「问题数」列与「问题标签」列不同源（一处含 info、一处不含），出现
  「问题数 10 但列了 12 条」的自相矛盾。
- windowed exe（`console=False`）下 `sys.stdout` 为 `None` 时任何 `print` 会崩。
- GUI 内调用 git 会弹出控制台窗口（统一 `CREATE_NO_WINDOW`）。
- 扫描老代码时 `ast.parse` 的 `SyntaxWarning` 会刷屏，干扰报告阅读。

### Security

- 规则 22/23 引入凭据检测：敏感文件名黑名单 + AWS/GitHub/Slack 前缀 +
  PEM 私钥头 + 高熵键值对（Shannon 熵 ≥3.5）。
- 规则 24 检测 `pull_request_target` 配合检出 PR 头提交、以及用户可控输入
  直接插值进 `run:` 的脚本注入写法。
- 所有 git 调用走统一封装：`GIT_TERMINAL_PROMPT=0`（绝不等待凭据输入）、
  `GIT_OPTIONAL_LOCKS=0`（不抢索引锁）、10 秒超时、失败即整体停用。

### 破坏性变更说明

以下三项叠加后已不满足 minor 版本的严格向后兼容定义，故升主版本：

1. 默认退出码策略虽保持 `0`，但 `--fail-on` 一旦启用即可能返回非零；
2. `issues` 内容由「8 条固定项」变为「30 条规则中 error/warn 级未通过项」，
   文本消费方（脚本、Agent 提示词）会看到不同内容；
3. `dump_profile()["rules"]` 长度由 8 变为 30，且 `RULES` 不再是可解包的二元组。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：Windows 可执行程序（PyInstaller，Python 3.14）。
- 发布面：gitee [siwpan/repocheck](https://gitee.com/siwpan/repocheck) release `v1.0.0`（仓库体检 v1.0.0）。
