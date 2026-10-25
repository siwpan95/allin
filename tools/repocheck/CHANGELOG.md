# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
