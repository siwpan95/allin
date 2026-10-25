# repocheck · 离线仓库体检

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

对一个根目录下的多个「项目」做一轮快速体检，找出那些**没版本控制 / 没文档 /
没测试 / 没依赖声明 / 没 License / import 疑似断裂 / 有凭据泄露风险**的工程
卫生问题，给出 **0–10 健康分**，并支持导出 JSON / CSV / HTML 报告。

**全程离线**：只读本地文件 + 只读 git 命令，不联网、不执行被测项目的代码、不
需要任何 token。运行时**零第三方依赖**（纯标准库）。

---

## 为什么需要它

散落在一个工作区里的几十上百个项目，基建完整度往往参差不齐。逐个肉眼检查不
现实，而 OpenSSF Scorecard 这类工具需要联网和仓库权限。repocheck 的定位是
**本地批量体检**：

- 一条命令扫完 `G:\repos` 下 100+ 个仓库，各自打分、并列问题清单；
- 结果能直接进 CI（`--fail-on error` 返回非零退出码）；
- 能查出「仓库迁移后残留的旧路径」「内联引擎副本缺补丁记录」这类本地特有纪律问题。

## 快速开始

```bash
# 图形界面（无参数即启动 GUI）
python main.py

# 命令行体检一个根目录
python main.py G:/repos

# 只看 warn 及以上，并同时导出 HTML
python main.py G:/repos --min-severity warn --format html -o report.html

# 进 CI：发现 error 级问题就失败
python main.py . --fail-on error
```

安装为命令（可选）：

```bash
pip install -e ".[full]"     # full = 可选增强依赖，见下文
repocheck G:/repos
```

## 命令行

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `root` | 无 | 根目录。**省略则启动 GUI**；给出则走命令行模式 |
| `--exclude NAME` | 无 | 额外排除的目录名，可重复或用逗号分隔 |
| `--depth N` | `2` | 识别项目时向下寻找 `.py` 的最大层级 |
| `--format {text,json,csv,html}` | `text` | 输出格式 |
| `--json` | 关 | 等价于 `--format json` |
| `--output PATH` / `-o` | 无 | 写入文件；省略则输出到标准输出 |
| `--fail-on WHEN` | `none` | `none` / `any` / `error` / `warn` / `score:N` |
| `--min-severity LEVEL` | `info` | 只显示该级别及以上，不影响评分 |
| `--skip-rules IDS` | 无 | 逗号分隔的规则 id，临时豁免误报 |
| `--workers N` | `1` | 按项目并发数（IO 与子进程为主，4~8 通常最快） |
| `--no-color` | 关 | 关闭 ANSI 颜色 |
| `--dump-profile` | 关 | 打印规则清单与能力矩阵（不扫描） |
| `--version` | — | 打印版本号 |

`python main.py <目录>` 这种老用法保持兼容。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 通过（默认 `--fail-on none`，即只要扫描跑完就是 0） |
| `1` | 触发了 `--fail-on` 条件 |
| `2` | 参数错误（argparse 原生行为） |
| `3` | 环境或内部错误（根目录不存在、没发现项目、写文件失败） |

`--fail-on` 的五档语义：

| 取值 | 判定 |
| --- | --- |
| `none` | 不判定（默认，保证向后兼容） |
| `any` | 任一规则未通过 |
| `error` | 任一 **error** 级未通过 |
| `warn` | 任一 **error 或 warn** 级未通过 |
| `score:N` | **任一**项目健康分低于 N |

## 健康分怎么算

```
score = 10 × log1p(通过项权重之和) / log1p(全部项权重之和)
权重：error = 3，warn = 2，info = 1
```

这是 best-of 的布尔项累加模型加 0–10 归一化。它的性质是：全通过正好 10 分，
全失败 0 分，单调递增，且**压缩极强** —— 30 条里挂 20 条仍有 9.4 分。

因此报告里同时给出**通过率** `pass_rate`，阈值判断请两者一起看。实践建议：
`--fail-on score:8.0` 到 `score:8.5` 之间比较有意义；不要用 `score:9.5`
这种阈值，几乎抓不到东西。

**跳过项不计入分母，但会压低分数上限**，避免「越残缺分越高」：

| 情形 | 计入分母 | 分数上限 |
| --- | --- | --- |
| 正常通过 / 失败 | 是 | 10.0 |
| 无 `.git`（7 条 git 规则跳过） | 否 | **6.0** |
| git 不可用 / 结果被截断 / 规则自身异常 | 否 | 9.0 |
| 走了内置降级实现 | 是 | 9.0 |

## 30 条规则

### error 级（会阻断 CI）

| # | 规则 | 判定依据 | 需 git |
| --- | --- | --- | --- |
| 1 | 无版本控制（缺 `.git`） | 项目目录内无 `.git` | |
| 2 | 无 README | 根目录无 `README*` | |
| 4 | 无依赖声明 | 无 `requirements.txt` / `pyproject.toml` / `package.json` / `Cargo.toml` | |
| 5 | 无 LICENSE | 根目录无 `LICENSE*` / `LICENCE*` / `COPYING*` / `COPYRIGHT*` | |
| 7 | 旧仓库路径残留 | 代码/配置/文档含旧工作区根路径（形如 `<盘符>:/<旧工作区名>`） | |
| 10 | 许可证三处声明不一致 | LICENSE 文件、README License 章节、项目清单 `license` 字段缺一或互相矛盾 | |
| 11 | README 结构不完整 | 二级标题 <5（≥100 行时）或缺安装/用法/许可三类内容 | |
| 18 | 版本号不一致或非 SemVer | 清单版本 / 源码 `__version__` / 最新 git tag 三处不一致，或不符合 SemVer | ✓ |
| 20 | 二进制/大文件签入 | `git ls-files` 含 `.exe/.dll/.so/.whl/.zip` 等，或单文件 >1MB | ✓ |
| 21 | 构建产物被跟踪 | `.gitignore` 缺失或为空；或跟踪了 `__pycache__/` `dist/` `node_modules/` `*.pyc` 等 | ✓ |
| 22 | 敏感文件入库 | 跟踪了 `.env` / `id_rsa` / `*.pem` / `*.p12` / `credentials.json` / `.npmrc` 等 | ✓ |
| 23 | 源码硬编码密钥 | AWS/GitHub/Slack 前缀、PEM 私钥头，或键名含 key/token/secret 且取值 Shannon 熵 ≥3.5 | ✓ |
| 24 | 危险 workflow 写法 | `pull_request_target` + 检出 PR 头提交，或用户可控输入直接插值进 `run:` | |
| 29 | 空壳仓/单向门面 | 跟踪文件全是元数据；有源码但无 README；源码 <30 行且提交 ≤2 次 | ✓ |

### warn 级

| # | 规则 | 判定依据 | 需 git |
| --- | --- | --- | --- |
| 3 | 无测试 | 无 `tests/` 或 `test/` 目录，也无 `test_*.py` / `*_test.py` | |
| 6 | 疑似 import 断裂风险 | AST 静态扫描：顶层模块不在项目内 / 标准库 / 常见第三方清单 | |
| 8 | 内联引擎副本缺 `engine.patch.yaml` | 存在 `alloy/` `allin_engine/` `tools/alloy/` `vendor/alloy/` 但无 patch 记录 | |
| 9 | 许可证不可识别 | LICENSE 内容匹配不上常见开源许可证特征句（MIT/Apache-2.0/BSD/GPL/MPL/ISC 等） | |
| 12 | README 相对链接死链 | README 中指向本地相对路径的链接/图片在项目内不存在 | |
| 13 | 无 SECURITY.md | 根 / `.github` / `docs` 下均无 `SECURITY.md`（不区分大小写） | |
| 14 | SECURITY.md 内容不足 | 缺有效联系方式 / 自由文本说明 / 漏洞披露与响应期限 | |
| 15 | 无 CONTRIBUTING | 根 / `.github` / `docs` 下无 `CONTRIBUTING*`，或文件内未说明贡献流程 | |
| 16 | CHANGELOG 结构不合格 | 无 `CHANGELOG*`，或缺 `Unreleased` 段与 `## [x.y.z] - YYYY-MM-DD` 条目 | |
| 17 | CHANGELOG 落后最新 tag | 最新语义化 tag 在 CHANGELOG 中检索不到 | ✓ |
| 19 | 无 CI 配置 | 无 `.github/workflows/*.yml`、`.gitee/workflows`、`.gitlab-ci.yml`、`Jenkinsfile` 等 | |
| 25 | Token 权限过宽 | workflow 未声明 `permissions`、声明 `write-all`，或顶层写权限无 job 级收窄 | |
| 26 | 依赖未固定 | `uses:@ref` 非 40 位 commit SHA；`requirements*.txt` 未用 `==` 或 `--hash` 锁定 | |
| 30 | 目录命名不合规 | 含 `.py` 的目录名不是合法 Python 标识符（连字符/空格/中文会导致无法 import） | |

### info 级

| # | 规则 | 判定依据 |
| --- | --- | --- |
| 27 | 无依赖更新工具 | 无 `.github/dependabot.yml` 或 renovate 配置 |
| 28 | 无 SAST 配置 | 无 CodeQL workflow、Semgrep/Sonar 配置，或 pre-commit 里没有静态分析钩子 |

**未纳入（需要联网）**：分支保护、release 签名、贡献者组织分布、CVE/OSV 比对、
webhook secret、CI 真实运行记录、包发布状态、CII 徽章等级、外链是否 200。

## 可选依赖

核心是纯标准库。装了下面这些会用更严格的库做**二次校验**，不装则走内置实现，
**结论口径一致，差别只在置信度**：

| PyPI 包 | 用途 | 许可证 |
| --- | --- | --- |
| `license-expression` | SPDX 表达式解析与规范化 | Apache-2.0 |
| `detect-secrets` | 密钥扫描二次校验 | Apache-2.0 |
| `markdown-it-py` | README 标题与链接解析 | MIT |
| `requirements-parser` | `requirements*.txt` 解析 | Apache-2.0 |
| `packaging` | 版本号比较 | Apache-2.0 OR BSD-2-Clause |

```bash
pip install "repocheck[full]"
python main.py --dump-profile      # 查看哪些能力已就绪
```

`pygit2` 是 GPL-2.0，**不引入**；git 操作统一走 `subprocess` 调系统 git。

## 项目识别口径

只看根目录的**直接一级子目录**，满足任一条件即算项目：

1. 自身含 `.git`；
2. 自身含 `package.json` / `Cargo.toml` / `pyproject.toml`；
3. 其子树（限 `--depth` 层）内存在任意 `.py` 文件。

默认跳过 `__pycache__`、`.git`、`.venv`、`venv`、`node_modules`、`dist`、`build`、
`target`、`.tox`、`.idea`、`.vscode` 等目录（可用 `--exclude` 追加）。

## 已知限制

- **无 `.git` 的项目拿不到 tags 类结论**：规则 17/18/20/21/22/23/29 会跳过，
  分数被压到 6.0 封顶 —— 这是有意的，不允许「没测」被当成「没问题」。
- **import 断裂是启发式**：只看顶层模块名是否在项目内 / 标准库 / 内置第三方清单
  （约 45 个）。少见但没收录的合法第三方库会误报，用 `--skip-rules 6` 豁免。
- **巨型仓库会截断**：文件索引上限 2 万、import 解析上限 800 个 `.py`、密钥与旧路径
  扫描上限 1500 个文件。触发截断时结果标 `degraded`，分数上限 9.0。
- **规则 10 对非 Python/Node/Rust 项目会报缺清单**：纯脚本仓既无 `pyproject.toml`
  也无 `package.json` 时，三处声明必然缺一处。可用 `--skip-rules 10` 豁免。
- **只识别一级子目录**：单项目目录本身不会被当作项目扫（请对视作父目录的路径调用）。
- **性能**：实测 124 个仓库（含若干上万文件的仓）串行 33 秒、`--workers 8` 约 27 秒。
  单个仓库平均约 0.26 秒，主要花在 git 子进程上。

## 文件结构

```
repocheck/
├── main.py          入口分发 + Tkinter GUI（唯一 import tkinter 的地方）
├── cli.py           argparse / 四种输出 / 退出码
├── scanner.py       门面：__version__ / discover_projects / check_project / dump_profile
├── scanctx.py       ProjectContext 懒加载索引 + 只读 git 封装 + 文本解码
├── rulebase.py      Severity / Rule / CheckResult / 执行器 / 评分
├── rules_core.py    规则 1-8   核心工程基建 + import 启发式
├── rules_docs.py    规则 9-16  许可证 / README / SECURITY / CONTRIBUTING / CHANGELOG
├── rules_vcs.py     规则 17-29 git 卫生 / 版本 / 二进制 / 敏感文件 / 密钥 / 空壳仓
├── rules_ci.py      规则 19-28 CI 与 workflow 安全
├── rules_misc.py    规则 30    目录命名规范
├── report.py        text / csv / html / json 渲染 + 汇总
├── _optional.py     可选依赖能力探测（find_spec，不真 import）
├── test_scanner.py  测试套件（含无 pytest 时的兜底冒烟）
└── test_fixtures.py 声明式假仓库构造器
```

设计原则：**复制优于共享** —— 本目录独立运行，不 import 其他工具目录，也不依赖
任何中心化共享核。**规则即数据** —— 新增一条规则只需在 `rules_*.py` 里追加一个
`Rule(...)`，执行、评分、报告渲染、`--dump-profile` 自省都会自动跟上。

## 开发与测试

```bash
python -m pytest test_scanner.py -q    # 57 个用例
python test_scanner.py                 # 无 pytest 时的兜底冒烟
python main.py --dump-profile          # 看规则清单与能力矩阵
python main.py . --fail-on error       # 自检（dogfood）
```

## 许可

[MIT](LICENSE) © 2026 siwpan

变更记录见 [CHANGELOG.md](CHANGELOG.md)，Agent 维护说明见 [SKILL.md](SKILL.md)。
