# allin —— 个人项目治理与文档索引仓库

[![governance-gates](https://github.com/siwpan95/allin/actions/workflows/gates.yml/badge.svg)](https://github.com/siwpan95/allin/actions/workflows/gates.yml)
[![门面站](https://img.shields.io/badge/%E9%97%A8%E9%9D%A2%E7%AB%99-siwpan95.github.io%2Fallin-1f6feb)](https://siwpan95.github.io/allin/)
[![license](https://img.shields.io/badge/license-MIT--0-blue)](LICENSE)

> do it better than future —— 仓标语，沿用初始提交的原文。

> **当某件事足够重要时，即使胜算不大，你也要去做。**
> —— Elon Musk，2012 年 CBS《60 Minutes》「SpaceX」片段，记者 Scott Pelley 问
> 「Why even begin?」（那为什么还要开始）时的回答。
> 英文原文 *When something is important enough you do it even if the odds are not in your favor.*
> 出处核实：[Snopes fact-check](https://www.snopes.com/fact-check/elon-musk-when-something-important-quote/)（2022 年 12 月核对 2012-03-18 首播的 CBS 访谈与官方文字稿）；
> CBS 文字稿在 `enough` 后无逗号，流行版本多加了一个。

## 项目用途

本仓是一个**单一索引仓库**，承担三件事：

1. **文档枢纽**：[`docs/`](docs/README.md) 承载整个个人工作区的治理说明、规范（SPEC 系列）、
   事实源台账与记录流水。游戏引擎、爬虫、音视频工具、电台服务、AI 项目等全部个人项目的
   约定都从这里索引出去。
2. **治理载体与执行器**：
   - [`platform/`](platform/README.md) —— Node 零依赖集成平台（门户 + 注册表 + 门禁）。
   - [`console/`](console/README.md) —— 治理控制台（Electron 45）把 151 条登记变成可点操作面：
     项目启停走 `@allin/core` 共享 pid 表，插件经 cordis-js 加命令/面板（[`SPEC-205`](docs/规范/SPEC-205-allin-console契约.md)）。
   - `allin-governance repocheck` —— 离线仓库体检器（30 条仓体规则 + 20 条可选治理门禁规则，零第三方依赖）。
   - `allin-governance scan` —— 发布区扫盘：项目指纹、重复检出、迁移残留（只报告不处置）。**随包分发**为 `allin-governance scan`。
   - `allin-governance deps` —— 依赖体检：`requirements` 声明 · 解释器实装 · 仓内 import 三者对账。**随包分发**为 `allin-governance deps`。
   - `allin-governance secrets-scan` —— **自研离线凭据扫描**：21 条高精度规则（只认已知提供方的固定格式）+ 按字符集分档的熵闸（hex 3.0 / alnum 3.5 / 其它 4.0）+ 占位符与形态降噪，随包分发为 `allin-governance secrets-scan`。**不依赖 gitleaks 二进制**，也不需要出网（不做在线验证 —— 那要把密钥发给服务商）。
   - [`tools/docs_backlinks.py`](tools/docs_backlinks.py) —— 文档反向链接 / 影响面（改一篇文档前先看波及谁）。
   - [`allin-governance gitee`](allin-governance gitee) —— Gitee 建仓 / 转公开 / 发版 / 附件（令牌走 GITEE_TOKEN → GCM）。
   - `allin-governance github` —— GitHub 建仓 / 转公开 / SSH 增量推送 / 独立复核 + 三端增量巡检（**gitee 远端为权威**，单向 gitee → 本地 → GitHub）。随包分发为 `allin-governance github`；SOP 见 [`github-sync-audit`](.workbuddy/skills/github-sync-audit/SKILL.md)。
   - [`preset/allin/`](preset/allin/安装说明.md) —— DeepSeek Harness 治理 preset 的声明式可重装副本。
   - [`kernel/`](kernel/README.md) —— Python/Cordis 服务图，[`allin_cli.py`](allin_cli.py) 作统一命令行入口。
3. **可安装包**：公共核已独立成仓 **[`allin-governance`](https://gitee.com/siwpan/allin-governance)**
   （PyPI 包同名，**当前版本 `2.5.2`**，版本演进见该仓 CHANGELOG）。本仓按版本号消费它，
   [`packages/allin-governance/`](packages/allin-governance/) 只留旧路径指针，不再内嵌源码。

仓库为公开仓，许可 MIT-0（见 [`LICENSE`](LICENSE)）。

### 为什么本仓住在发布区里（2026-11-23）

此前 `allin` 与 `repos/` 是**两条腿走路**：allin 管治理、repos 被治理。但 allin 这条腿迈得
明显更快 —— 治理规则越写越细，被管对象却纹丝不动，两条腿步频不一致就必然互相拉扯：
**allin 声称自己管 repos，而 repos 的真实状况并不参与 allin 的判据**。这就是漂移的来源。

现在 allin 住在 `repos/allin` 里，于是：

- **allin 只治理 `repos/`，而 allin 自身也是 `repos/` 的一员。** 没有"我在系统之外"的特权视角 ——
  门禁对别的仓要求什么，对 allin 自己也一样要求。本轮搬迁后 `g17` 第一个判出的未登记仓
  就是 `repos/allin` 自己。
- **只剩一条腿。** `repos/` 哪怕只有一个成员（就是 allin），治理闭环依然成立，
  不再依赖"另一条腿走多快"。
- 以前不做主要是**技术原因**（发布区根推导只认同级布局、打包态下 `ALLIN_ROOT` 失效等），
  这些已随 2026-11-23 的改动消解（五处推导统一为「父目录名是 `repos` 则取父目录」）。
  剩下的只是方向问题 —— 方向已定。

## 安装步骤

前置要求：Python ≥3.11、Node.js（跑治理门禁套件需要）、Git；kernel 的 Cordis 服务图另要求 Python ≥3.12（见各 `pyproject.toml` 的 `requires-python`）。

```bash
git clone <本仓远端地址>
cd allin
bash scripts/bootstrap.sh          # 建 .venv、安装 PyYAML/watchdog、重建 docs/ ASCII 别名
bash scripts/install_git_hooks.sh  # 装提交钩子（每台机 / 每个 clone 各一次，否则钩子一个都不跑）
```

> **新人第一步是装钩子**：`core.hooksPath` 是仓库本地配置、不入库，`.git/hooks/` 也不入库 ⇒
> 不跑上面这条，仓里 `tools/gate/hooks/` 的 `pre-commit` / `commit-msg` **只是两个普通文件**，
> 门禁不跑、提交也不会自动带 `Machine: <本机 hostname>` trailer（2026-12-01 起强制）。
> 自查：`bash scripts/install_git_hooks.sh --check`。详见[新人指南](docs/新人开发上手指南.md) §3.5。

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
npm run check:docs                # 文档索引契约 D1–D19
allin-governance repocheck <目录>       # 离线仓库体检
```

> **2026-11-26 新增四条归属类判据**（不在 `g00–g20` 序列里，编排在 `scripts/run_all_gates.sh`）：
> `check_machine_trailer`（改了某机分区就必须声明 `Machine: <那台机>`）·
> `check_machine_ledger`（月账引用的节要真实存在 + 归属通道成对 + 「未归属」数与 git 实测一致）·
> `check_conflict_markers`（入库文件不许留冲突标记残骸）·
> `machine_ledger`（归属取证工具，产出唯一口径，不判红）。判据与生效日见[新人指南](docs/新人开发上手指南.md) §4.2.3。

> **门禁入口（2026-11-23 起）**：`scripts/run_all_gates.sh` 默认用 repocheck 的
> 门禁规则族（规则 31-50）跑那 20 道门禁 —— 判据仍是同一份 `gates/*.py`，只是换了编排者。
> `npm run check:governance` 作为**回退与对照**保留（判据没漂的证据），要强制走它：
> `ALLIN_GATES_VIA_NPM=1 bash scripts/run_all_gates.sh`。

**统一命令行入口**：经 [`allin.bat`](allin.bat)（或仓内 venv 的 python）运行
[`allin_cli.py`](allin_cli.py)，子命令为 `tools` / `docs` / `platform` / `preset` / `status`。

**全流程自动推进（定时任务入口）**：`allin tools auto-flow` 把「同步核对 → 门禁全跑 →
发版预检 → 状态汇总」串成一条可重入命令，供 WorkBuddy automation 等无人值守调度调用：

```bash
allin tools auto-flow                 # 全流程
allin tools auto-flow --quick         # 快跑：同步核对 + 状态汇总
allin tools auto-flow --with-platform # 追加 platform check/test/harness
allin tools auto-flow --json          # 机读输出
```

全程只读或本地留痕（结果落 `tools/gate/audit/` 下的 `auto-flow-runs.jsonl`，运行时产物、已 gitignore），
**绝不 push / 建仓 / 自提交** —— 高风险动作仍须人在场逐项放行（SPEC-001 铁律 3）。
汇总行 `ALLIN_AUTO_FLOW_SUMMARY status=clean|finding ... not_applicable=N` 是机器判定
准出；门禁的 `incomplete`（SKIP）按 finding 透传，不冒充通过。发版专属的两项
（twine check / `--install` 安装实测）在无人值守场景记为 `not_applicable` 单列，
既不判红、也不声称已验证 —— 公共核的发版预检与安装实测已随
[`allin-governance`](https://gitee.com/siwpan/allin-governance) 迁出，真要发版在该仓执行。

**平台门户**：按需启动（默认 `PORT=0`，由系统分配临时端口；固定端口 9000 已在 [`docs/事实源/ports.yaml`](docs/事实源/ports.yaml) 记为 `status: retired`，仅手动模式可选）；
website 默认端口 9042，同样以 ports.yaml 登记为准。

> `site/` 与 `website/` 不是一回事：**`site/`** 是 GitHub Pages 门面单页
> （[`deploy-pages.yml`](.github/workflows/deploy-pages.yml) 的部署源，即顶部徽章指向的门面站）；
> **`website/`** 是 ALLIN LAB 开发与维护服务官网（Node 加密站，本地运行，不进 Pages）。

## 使用示例

```bash
# 离线体检某个发布区目录（有 error 级问题即失败，可进 CI）
allin-governance repocheck <发布区> --fail-on error

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
[`allin-governance` 仓的 README](https://gitee.com/siwpan/allin-governance) 为准（该包已独立成仓）。

## 关键配置说明

| 配置/文件 | 作用 |
|---|---|
| [`kernel/configs/cordis.allin.yml`](kernel/configs/cordis.allin.yml) | Cordis 服务图挂载配置：docs / platform / preset / tools 四大支柱经此装配 |
| `kernel/registry.py` 的 `SERVICES` 白名单 | 把 entry name 钉死为代码边界，防止「配置即代码」评审绕过 |
| [`preset/allin/allin.patch.yml`](preset/allin/allin.patch.yml) | DSH agent preset 治理段（`config.id: allin`）；改后须重跑 `make-bundle.ps1` 刷新 bundle，`refresh-gov-block.py --check` 门禁会拦截落后副本 |
| `allin-governance` 包内 `_gatesuite/exceptions.yml` | 门禁例外台账（g18 解析，需解释器带 PyYAML）；随包分发，本仓不再内嵌 |
| [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md) | 多机检出时，各机仓根 / 发布区落点的**唯一事实源**；本 README 只写跨机共识，不写单一机器路径 |
| `PLATFORM_REPOS_ROOT` 环境变量 | 覆盖 platform 注册表的发布区根；默认解析规则 `repos/<仓名>` → 仓的上一级 |

## 运行时可写位置：包内只读，状态落用户目录

> 早期这里只有一句笼统的说法：「装在 Program Files 的程序往安装目录写 → 普通用户写失败 →
> 回退 VirtualStore → 两份配置，非常迷惑」。那句话只描述了其中一种表现，机制与边界比它宽。

### 症状有三种，不止一种

| 环境 | 往安装目录写时会怎样 |
| --- | --- |
| Windows，**32 位**进程，受保护目录（`Program Files` / `Program Files (x86)` / `Windows` / 系统盘根） | **被静默重定向**到 `%LOCALAPPDATA%\VirtualStore\<原路径>`。程序读写自己的副本、看起来一切正常；资源管理器或管理员看到的是另一份。两份长期并存，权限一变旧副本就「突然生效」——最迷惑的一种 |
| Windows，**64 位**进程（现代 Python 绝大多数） | **不重定向**，直接写失败（`PermissionError`）。表现是「保存不了」，比上面好查，但仍是错的 |
| POSIX（`sudo pip install` 进 `/usr`） | 安装目录属 root，普通用户写失败；若有人用 `sudo` 跑过一次，会在安装目录留下 **root 属主**的缓存，之后普通用户读不了或读到旧值 |

另有一个独立来源：**「始终以管理员身份运行」会让人以为自己修好了**——管理员与普通用户读的是不同位置的
同一份配置，换种启动方式就变回默认。这不是权限没配好，是把可变状态放错了地方。

### 根因一条

**安装目录是只读的**——不是权限配置问题，是包规范（setuptools *Data Files Support*）：
包内 data 会被多用户共享、被 zip 导入、被并行实例读取，所以**必须只读**；
可变状态必须落在包外、属于具体用户的位置。

### 正确划分（照系统 API 走，不自己拼路径）

| 内容 | 落点（Windows） | 落点（POSIX） | 获取方式 |
| --- | --- | --- | --- |
| 程序文件 / 只读模板 | 安装目录 | 安装目录 | 随包分发（`package_data`） |
| 每用户配置 | `%APPDATA%`（漫游）/ `%LOCALAPPDATA%` | `~/.config` | `SHGetKnownFolderPath(FOLDERID_RoamingAppData)` / `XDG_CONFIG_HOME` |
| 每用户数据 / 缓存 / 日志 | `%LOCALAPPDATA%` | `~/.local/share`、`~/.cache` | `FOLDERID_LocalAppData` |
| 多用户共享配置 | `%PROGRAMDATA%`（显式给 Users 读权限） | `/etc` | `FOLDERID_ProgramData` |
| 跨平台统一 | — | — | [`platformdirs`](https://pypi.org/project/platformdirs/)（本仓不引入依赖，等价逻辑内联在 `print/config.py`） |

### 本仓是怎么做的（`allin-toolkit` 的 `print`）

- 可写根：`%LOCALAPPDATA%\allin-toolkit\print`（POSIX：`$XDG_DATA_HOME/allin-toolkit/print`）；
- 索引缓存与用户学习词典（`user_dict.json`）都落这里，安装目录零写入；
- 字典读取顺序：**包内只读优先 → 用户目录兜底**；`--auto-download` 与手动放置的字典写用户目录；
- 旧版本写在安装目录的 `user_dict.json`（用户数据、不可重建）首次运行迁移过来；缓存不迁移（可重建）。

### 怎么自证「没有往安装目录写」

```bash
# 装好后跑一遍工具，再看两处：安装目录应无 cache / 用户数据；用户目录应有
python -c "import allin_toolkit,pathlib;print(pathlib.Path(allin_toolkit.__file__).parent)"
ls "$LOCALAPPDATA/allin-toolkit/print"        # 期望：cache/ 与 user_dict.json
```

`dev-toolkit` 仓另带静态侦察脚本 `audit_write_paths.py`（「安装目录锚点 × 写调用」同文件命中即报告），
用于持续发现同款代码——**判据是写目标，不是"能不能跑"**。

## 常见问题

- **门禁报 PyYAML 相关错误**：解释器缺 PyYAML。用 `ALLIN_PYTHON=<解释器路径>` 显式指定，
  或先跑 `scripts/bootstrap.sh` 建仓内 `.venv`。
- **门禁失败先看哪一步**：`scripts/run_all_gates.sh` 会逐项打印并汇总失败项；
  仓根 README 自身的机检护栏是 `tools/gate/check_readme_refs.py`（引用路径存在性 + 包版本对账）。
- **smoke:e2e 显示 SKIP**：platform / website 两侧 Node 依赖未安装（`.gitignore` 忽略 node_modules）。
  装依赖后复跑：`npm ci --prefix website && npm ci --prefix platform`。SKIP 不计入失败。
- **repocheck 对本仓自检报「无 .git / 无 README」**：本仓是 monorepo，子目录不是独立仓。
  加 `--profile monorepo` 与完整 `--exclude` 列表；要对仓根自身体检再加 `--self`。
  具体命令见下文「已知限制」第三条。
- **Gitee Wiki 怎么改**：Wiki 只能网页编辑，[`wiki/`](wiki/Home.md) 目录是唯一真身，
  改文案改这里再同步过去。

## 已知限制

> 每条都写「怎么绕过去」。只写「有这个限制」而不写解法，等于把问题留给下一个人。
> 标注的实测日期是**执行验证那台机器**跑出来的结果，不是推测；具体机器见 `facts/machine/`。

- **发布区不可达时门禁降级为 SKIP —— 那是「没检查」，不是「通过」**：
  发布区路径解析不出来时（父目录名不是 `repos`，且 `<本仓>/../repos` 也不存在，
  例如 CI 上的一次性 clone），`g17` 的完备性检查、`repo_hygiene`、`publish_area_gate`
  会打印 `SKIPPED (not a pass)` 并仍以 0 退出。
  **要用别处的发布区：`ALLIN_REPOS_ROOT=<路径>`。**
  〔2026-11-24 实测：指向不存在的路径时 `g17` 报 `skipped 2 / blocking 0`，
  摘要自带 `SKIPPED (not a pass)` 与 `set ALLIN_REPOS_ROOT` 提示。〕
- **`PORTFOLIO.md` 会过期**：它由 `tools/build_portfolio.py` 从 Gitee API 生成（是索引，
  不是源码镜像）。仓数变化后刷新：`python tools/build_portfolio.py --apply`；
  去掉 `--apply` 是干跑，只打印数字、不写盘。
  〔**别在散文里记这个数**：它是活值，且一天内变过三次（143 → 85 → 77，都是清理动作
  的真实结果）。本行故意不写数字 —— 要看当前值就读 `PORTFOLIO.md` 首部「共 N 个仓库」，
  三处一致性由 `check_arch_assets.py` 逐次对账（`system-architecture.svg` 与 `SPEC-204`
  必须同值）。2026-11-24 复核时 `--apply` 与 Gitee API 分页实测均为 77。〕
- **monorepo 下不能对仓根裸跑体检器**：`tools/` `packages/` `console/` `kernel/` 等是仓内
  中间目录、不是独立仓。裸跑 `repocheck .` 会把它们当成 11 个「项目」逐个判
  「缺 `.git` / 缺 README」，健康分掉到 6.0（2026-11-24 实测）。正确口径：

  ```bash
  # 只查子项目，跳过仓根（仓体卫生的日常口径）
  allin-governance repocheck . --profile monorepo \
    --exclude tools,vendor,preset,packages,scripts,website,tests,facts,deploy,console,kernel,platform

  # 连仓根一起查（--self 是 2026-11-23 新增：默认项目发现只认一级子目录，
  # 仓根从不算「项目」，缺了它门禁规则族对 allin 自己恒不生效）
  python -m allin_governance repocheck . --self --profile monorepo \
    --exclude tools,vendor,preset,packages,scripts,website,tests,facts,deploy,console,kernel,platform
  ```

- **历史路径陈述**：仓内文档中出现的历史盘符 / 路径按「当时的事实」保留备查，
  现行落点以 [`docs/事实源/机器分区索引.md`](docs/事实源/机器分区索引.md) 为准。
- **命名沿革**：统一游戏引擎现行名为 `allin_engine`（PyPI 包名 `allin-engine`）；
  仓内文档残留的 `alloy.*` 写法一律按 `allin_engine` 读，接口契约见
  [`docs/规范/SPEC-201-引擎接口契约.md`](docs/规范/SPEC-201-引擎接口契约.md)。

## 许可

本仓按 **MIT-0**（MIT No Attribution）授权，全文见 [`LICENSE`](LICENSE)；
`package.json` 的 `license` 字段与之一致。`packages/allin-governance/` 随仓同许可。
`vendor/cordis/` 是上游 cordis-py 的源码内联副本，保留其各自的 MIT 许可与出处
（见 `vendor/cordis/VENDOR.md`），**不因本仓的 MIT-0 而改变**。

---

*最后更新：2026-11-24 —— 重写「已知限制」：原第 3 条指向的「上文运行方式」早已不存在
（失效指针），且未给 monorepo 的正确口径；现每条限制都附可执行解法与实测日期。
同日早些时候：本仓迁入发布区 `repos/allin`（原 `<工作区>/allin`）、补「许可」章节、
收入仓格言引言、`allin-governance` 升至当前版本并发布（当日两次：门禁入口切换后一次、
冻结仓归档与 foolproof 并入后再一次）。
体例沿革与更早记录见 git 历史与 [`CHANGELOG.md`](CHANGELOG.md)。*
