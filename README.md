# allin —— 个人项目治理与文档索引仓库

[![governance-gates](https://github.com/siwpan95/allin/actions/workflows/gates.yml/badge.svg)](https://github.com/siwpan95/allin/actions/workflows/gates.yml)
[![门面站](https://img.shields.io/badge/%E9%97%A8%E9%9D%A2%E7%AB%99-siwpan95.github.io%2Fallin-1f6feb)](https://siwpan95.github.io/allin/)
[![license](https://img.shields.io/badge/license-MIT--0-blue)](LICENSE)

> do it better than future —— 仓标语，沿用初始提交的原文。

## 项目用途

本仓是一个**单一索引仓库**，承担三件事：

1. **文档枢纽**：[`docs/`](docs/README.md) 承载整个个人工作区的治理说明、规范（SPEC 系列）、
   事实源台账与记录流水。游戏引擎、爬虫、音视频工具、电台服务、AI 项目等全部个人项目的
   约定都从这里索引出去。
2. **治理载体与执行器**：
   - [`platform/`](platform/README.md) —— Node 零依赖集成平台（门户 + 注册表 + 门禁）。
   - [`tools/repocheck/`](tools/repocheck/README.md) —— 离线仓库体检器（30 条规则，零第三方依赖）。
   - [`preset/allin/`](preset/allin/安装说明.md) —— DeepSeek Harness 治理 preset 的声明式可重装副本。
   - [`kernel/`](kernel/README.md) —— Python/Cordis 服务图，[`allin_cli.py`](allin_cli.py) 作统一命令行入口。
3. **可安装包**：[`packages/allin-governance/`](packages/allin-governance/) 把上述通用能力
   发布为 PyPI 包 `allin-governance`（当前版本 `0.0.0a5`，版本演进以根 [`CHANGELOG.md`](CHANGELOG.md) 为准）。

仓库为公开仓，许可 MIT-0（见 [`LICENSE`](LICENSE)）。

## 安装步骤

前置要求：Python 3.9+、Node.js（跑治理门禁套件需要）、Git。

```bash
git clone <本仓远端地址>
cd allin
bash scripts/bootstrap.sh          # 建 .venv、安装 PyYAML/watchdog、重建 docs/ ASCII 别名
```

`scripts/bootstrap.sh` 幂等，可重复执行。可选步骤：

- 跑 platform / website 相关门禁或冒烟前，先装两侧 Node 依赖：
  `npm ci --prefix platform && npm ci --prefix website`
- 以包形态使用（不装仓内环境）：`pip install allin-governance`

## 运行方式

**一键跑齐全部门禁**（推荐）：

```bash
bash scripts/run_all_gates.sh                  # 全部治理门禁 + 文档契约 + 自检
bash scripts/run_all_gates.sh --with-platform  # 额外跑 platform 的 check/test/harness
```

也可以单独运行某一类检查：

```bash
npm run check:governance          # 20 道治理门禁（g00-meta…g20-facts）
npm run check:docs                # 文档索引契约 D1–D17
python tools/repocheck/main.py <目录>   # 离线仓库体检（无参数 = GUI）
```

**统一命令行入口**：经 [`allin.bat`](allin.bat)（或仓内 venv 的 python）运行
[`allin_cli.py`](allin_cli.py)，子命令为 `tools` / `docs` / `platform` / `preset` / `status`。

**平台门户**：按需启动（默认端口 9000，已登记 [`docs/事实源/ports.yaml`](docs/事实源/ports.yaml)）；
website 默认端口 9042，同样以 ports.yaml 登记为准。

> `site/` 与 `website/` 不是一回事：**`site/`** 是 GitHub Pages 门面单页
> （[`deploy-pages.yml`](.github/workflows/deploy-pages.yml) 的部署源，即顶部徽章指向的门面站）；
> **`website/`** 是 ALLIN LAB 开发与维护服务官网（Node 加密站，本地运行，不进 Pages）。

## 使用示例

```bash
# 离线体检某个发布区目录（有 error 级问题即失败，可进 CI）
python tools/repocheck/main.py <发布区> --fail-on error

# allin-governance 包：生成最小治理骨架 / 体检 / 复核快照
allin-governance init <目标目录>
allin-governance repocheck <目录> --fail-on error
allin-governance verify <目录>

# 统一 CLI
allin status --json
allin preset list
allin docs portfolio --apply
```

生成骨架包含 14 道门禁的出厂子集（仓内注册表共 20 道，`init` 按「纯标准库即可运行」裁剪）；
子命令语义以 `allin-governance --help` 与
[`packages/allin-governance/README.md`](packages/allin-governance/README.md) 为准。

## 关键配置说明

| 配置/文件 | 作用 |
|---|---|
| [`kernel/configs/cordis.allin.yml`](kernel/configs/cordis.allin.yml) | Cordis 服务图挂载配置：docs / platform / preset / tools 四大支柱经此装配 |
| `kernel/registry.py` 的 `SERVICES` 白名单 | 把 entry name 钉死为代码边界，防止「配置即代码」评审绕过 |
| [`preset/allin/allin.patch.yml`](preset/allin/allin.patch.yml) | DSH agent preset 治理段（`config.id: allin`）；改后须重跑 `make-bundle.ps1` 刷新 bundle，`refresh-gov-block.py --check` 门禁会拦截落后副本 |
| [`tools/gate/governance/exceptions.yml`](tools/gate/governance/exceptions.yml) | 门禁例外台账（g18 解析，需解释器带 PyYAML） |
| [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md) | 多机检出时，各机仓根 / 发布区落点的**唯一事实源**；本 README 只写跨机共识，不写单一机器路径 |
| `PLATFORM_REPOS_ROOT` 环境变量 | 覆盖 platform 注册表的发布区根；默认解析规则 `repos/<仓名>` → 仓的上一级 |

## 常见问题

- **门禁报 PyYAML 相关错误**：解释器缺 PyYAML。用 `ALLIN_PYTHON=<解释器路径>` 显式指定，
  或先跑 `scripts/bootstrap.sh` 建仓内 `.venv`。
- **门禁失败先看哪一步**：`scripts/run_all_gates.sh` 会逐项打印并汇总失败项；
  仓根 README 自身的机检护栏是 `tools/gate/check_readme_refs.py`（引用路径存在性 + 包版本对账）。
- **smoke:e2e 显示 SKIP**：platform / website 两侧 Node 依赖未安装（`.gitignore` 忽略 node_modules）。
  装依赖后复跑：`npm ci --prefix website && npm ci --prefix platform`。SKIP 不计入失败。
- **repocheck 对本仓自检报「无 .git / 无 README」**：本仓是 monorepo，子目录不是独立仓。
  自检口径见 `scripts/run_all_gates.sh` 中的排除与跳过参数，勿直接对仓根裸跑。
- **Gitee Wiki 怎么改**：Wiki 只能网页编辑，[`wiki/`](wiki/Home.md) 目录是唯一真身，
  改文案改这里再同步过去。

## 已知限制

- **发布区缺席时部分门禁自动 SKIP**：CI（及无同级 `repos/` 的机器）上，发布区卫生检查与
  smoke:e2e 会降级为 skip，不代表检查通过。
- **PORTFOLIO.md 会过期**：它是脚本从 Gitee API 生成的索引（非源码镜像），仓库数量变化后
  需重跑生成脚本刷新。
- **monorepo 结构限制**：`tools/` `packages/` 等是仓库自身的中间目录，直接对其裸跑体检器
  会产生假阳性；正确口径见上文运行方式与门禁脚本。
- **历史路径陈述**：仓内文档中出现的历史盘符 / 路径按「当时的事实」保留备查，
  现行落点以 [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md) 为准。
- **命名沿革**：统一游戏引擎现行名为 `allin_engine`（PyPI 包名 `allin-engine`）；
  仓内文档残留的 `alloy.*` 写法一律按 `allin_engine` 读，接口契约见 `docs/` 规范目录（SPEC-201）。

---

*最后更新：2026-11-08 —— 补 `site/` 与 `website/` 区分说明，
allin-governance 版本口径同步至 `0.0.0a5`。体例沿革（2026-11-07 重写为中性直述）与更早记录见 git 历史与 [`CHANGELOG.md`](CHANGELOG.md)。*
