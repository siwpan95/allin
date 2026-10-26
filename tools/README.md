# tools/ — Gitee 推送 / 发版配套脚本 + 仓库体检器

本目录放与 `docs/规范/SPEC-101-推送流程.md`、`docs/规范/SPEC-102-发版指南.md` 配套的**可执行脚本**，
以及 2026-10-26 并入的**离线体检器** `repocheck/`（原独立仓 `siwpan/repocheck`）。
脚本类一律**零三方依赖**（仅用 Python 3.x 标准库），拷走即可用，不依赖本仓库其它部分。

## 子件一览

| 子件 | 用途 | 入口 |
| --- | --- | --- |
| `gitee_release.py` | 建仓 / 转公开 / 发版 / 附件 | `python tools/gitee_release.py whoami` |
| `build_portfolio.py` | 从 Gitee API 生成 [`../PORTFOLIO.md`](../PORTFOLIO.md) | `python tools/build_portfolio.py --apply` |
| `repo_hygiene.py` | 仓库卫生巡检 | 见文末 |
| `gate/` | 工作区门禁集合（文档索引契约等） | 见 `gate/README.md` |
| **`repocheck/`** | **离线仓库体检（30 规则 / 0–10 分 / 四格式导出）** | `python tools/repocheck/main.py` |
| **`security/venv_ca_audit.py`** | **venv CA 证书安全巡检与加固（GHSA-6q48-6c7w-9gw2）** | `allin tools venv-audit scan G:/repos` |
| **`verify_projects.py`** | **逐项无头验证 registry 项目（T1 `verify.command` / T2 启动命令 / T3 包导入，其余 T4）** | `python tools/verify_projects.py --workers 8` |

---

## `gitee_release.py` — 建仓 / 转公开 / 发布发行版（分步、可重入）

把"发一个版本"从手工点网页变成可复现的命令。每个子命令都能单独跑，重复跑是**幂等**的
（已存在就跳过，不重复创建），所以中断了可以直接重跑。

### 子命令

```bash
python tools/gitee_release.py whoami                                  # 验证令牌可用
python tools/gitee_release.py create   --name myproj                  # 建私有仓（已存在则跳过）
python tools/gitee_release.py remote   --name myproj --repo /local/myproj   # 配/改 origin
python tools/gitee_release.py public   --name myproj                  # 转公开（已公开则跳过）
python tools/gitee_release.py release  --name myproj --tag v1.0.0 \
                                       --title "myproj v1.0.0" --notes-file notes.md
python tools/gitee_release.py attach   --name myproj --tag v1.0.0 --file dist.zip
python tools/gitee_release.py status   --name myproj
```

默认 `--owner siwpan`。`--repo` 默认取脚本所在目录的上两级（即仓库根），用于探测分支、打 tag、
推送 tag；也可显式指定本地仓库路径。

### 令牌来源（**绝不要写进仓库**）

按以下顺序取，命中即停：

1. `--token HEX`
2. 环境变量 `GITEE_TOKEN`
3. `--token-file <路径>` —— 从中提取**第一段** 32/64 位 hex（本机令牌由
   git credential store 管理，可传 `--token-file "$HOME/.git-credentials"`）。

### 关键实现要点（踩过的平台坑，别再踩）

- **单附件上限 100MB**（Gitee 社区版；GVP 200MB），每仓库总附件 ≤ 1GB。
  大载荷压成**一个 zip** 再 `attach`，不要传散文件（附件名不允许带路径分隔符，会丢目录结构）。
- **`PATCH /repos/{owner}/{repo}` 必须带 `name`**，否则 400 `name is missing`（转公开时会撞上）。
- `GET /releases/tags/{tag}` 在 tag 不存在时返回 **200 + null** 而非 404 —— 只判状态码会误判"已存在"。
- 建仓 `auto_init: false`：否则多一个无关首次提交，默认分支也不再是你推的那个。
- `POST /releases` **必须带 `target_commitish`**（留空时脚本自动从 git 探测当前分支）；
  否则直接 400 `target_commitish is missing`。
- `attach` 走**直连** `HTTPSConnection("gitee.com")`，路径必须带 `/api/v5` 前缀，少了就是静默 404。
- 响应的 `html_url` 可能为 null；发行版网页地址按
  `https://gitee.com/{owner}/{repo}/releases/{tag}` 构造。
- 发布页 Gitee 自动附的源码包链接（`/archive/refs/tags/*.zip`）**不是直链**（匿名取到的是 HTML 页）；
  GPL 义务要求的源码指向应写 `git clone` 地址。
- 附件上传用**流式 multipart**（1MB 分块 `send`），不把上百 MB 读进内存；网络抖动自动重试两次。

### 退出码

`0` 成功；`1` 失败。

> 该脚本亦随 `gitee-repo-and-release-flow` skill 提供（路径 `<skill>/tools/gitee_release.py`），
> 两份内容一致；本仓库内以 `tools/gitee_release.py` 为准。

---

## 监工三件套（2026-09-25 新增）

> **为什么有这一节**：用户提出「文档 + 门禁 + 看门狗」三件套 —— **图纸之外还要有监工**。
> 起因是 2026-09-25 的真实事故：G: 盘 NTFS 在线自愈改坏了 4 个 git 仓
> （`allin` / `novel` / `novel-down` / `ncmturnmp3`），**全程没有任何机制第一时间叫**，
> 全靠事后人工开挖。文档再多，缺了监工照样一遍遍踩坑。

三个脚本**零三方依赖**（仅 Python 3 标准库），**各自带 `--selfcheck`**：
往临时目录造破坏用例，逐条断言门禁能抓住、且干净样例零误报 ——
**没有 selfcheck 的门禁等于没有门禁**（无法证明它是活的）。

### `repo_hygiene.py` — 仓库卫生门禁

把 `docs/gitee推送流程_2026-09-25.md` §1 的「仓库卫生六项」从**文字**变成**退出码**
（此前实测：6 项要求 → **0 项**有门禁）。另加两项本工作区沉淀：

| 项 | 判据 |
| --- | --- |
| H1 LICENSE 唯一 | 判**路径**（`_ref/ThirdParty/LICENSE` 也要可见，只判 basename 会漏） |
| H2 无第三方源码目录 | `_ref/ vendor/ node_modules/ third_party/` |
| H3 无产物目录 | `output/ state/ cache/ dist/ build/ release/` |
| H4 无归档/大文件 | `*.zip *.tar.gz *.7z`；单文件 > 5 MiB（**blob 口径**） |
| H5 无凭据 | 令牌**本体子串**（从凭据文件读，不回显）+ 通用**形态** + URL 内嵌凭据 |
| H6 文档一致性 | `docs/` 下借鉴记账须含「上游URL + 许可证 + 不入仓声明」 |
| H7 仓名=目录名 | 本地目录名须等于 origin 仓名 |
| H8 行尾一致性 | 「内容逐字节相同却被标 modified」的假改动检测 |

```bash
python repo_hygiene.py --repo <仓>              # 单仓
python repo_hygiene.py --all                    # 全部（日常，基线棘轮）
python repo_hygiene.py --all --no-baseline --list-all   # 普查全部存量
python repo_hygiene.py --all --write-baseline   # 存量一次性上线
python repo_hygiene.py --selfcheck              # 自证
```

### `check_ps1_bom.py` — PowerShell 编码门禁

`/tools/README.md` 纪律 1「`.ps1` 必须存成 UTF-8 带 BOM」此前**只是文字**。
本次当场踩中：编辑工具改脚本后 **BOM 被剥掉**，导致 `scan_hardcoded.ps1` 在
PowerShell 5.1 下报假语法错误（`Unexpected token '}'`）——**该门禁在 PS 5.1 下完全不可用**。

```bash
python check_ps1_bom.py            # 扫默认根
python check_ps1_bom.py --fix      # 就地补 BOM（默认干跑）
python check_ps1_bom.py --selfcheck
```

判据：含非 ASCII 却无 BOM → 阻断；纯 ASCII 无 BOM → 合法；有 BOM 但非合法 UTF-8 → 阻断。

### `watchdog.py` — 工作区看门狗

| 职责 | 判据 |
| --- | --- |
| W1 盘健康 | 卷 dirty 位 / HealthStatus；**事件日志里的 IO 重试与 NTFS 自愈计数** |
| W2 仓完整性 | `.git/objects` 可读性（**事故指纹**）、`HEAD^{commit}` 可解、fsck |
| W3 同步漂移 | 本地 HEAD vs 远端 ref（**只信 `git ls-remote`**） |

```bash
python watchdog.py                # 全量巡检
python watchdog.py --quick        # 跳过 fsck（快）
python watchdog.py --selfcheck
```

**两条别改错的判据**：
- **SMART 会报 `Healthy` 而盘正在重试 IO** —— 必须看事件日志（`disk` id 153 + `Ntfs` id 130/132），只看 SMART 会得出「全绿」的错误结论。
- 仓完整性**必须用 `HEAD^{commit}`**：`rev-parse --verify HEAD` 只解析 ref 名、**不验证对象是否存在**，会把「objects 全删」「HEAD 写坏」判成 OK（自检当场抓出）。

> 开发中的 `/tools/gate/` 是同一批脚本的工作副本；**本目录（随仓分发）是给外部使用者的一份**。
> 两份内容一致，修改时需同步。


---

## `security/venv_ca_audit.py` — venv CA 证书安全巡检与加固（GHSA-6q48-6c7w-9gw2）

2026-10-20 披露的 **CRITICAL** 事件（CVSS 9.1，CWE-295，无 CVE）：certifi `>= 2019.03.09, < 2026.10.19`
的 CA 捆绑包含 `emSign ECC Root CA - G3` 根证书，eMudhra 签发并链到该根的 **8 张中间 CA 私钥已泄露**并被吊销；
持泄露私钥者可签发「对任意主机名都像真的」证书，叠加 on-path 即可 **MITM**。
受影响组件含 `requests` / `urllib3` / **`pip`**。修复：certifi `>= 2026.10.19`、pip `>= 26.2.2`、uv `>= 0.13.4`。

**统一调度入口**（走 cordis 内核）：

```bash
allin tools venv-audit scan   G:/repos        # 只读扫描
allin tools venv-audit apply  G:/repos 8      # 加固（幂等）
allin tools venv-audit verify G:/repos 8      # 功能级审计
```

### 两条别判错的判据

1. **判据必须精确到 G3**：certifi 2026.10.19 起**合法保留** 9~15 处未受影响的 emSign 根
   （公告只恢复未受影响的那些）。所以「包里有没有 emSign」是**错的**判据，会对着全部 venv 误报；
   唯一正确判据是精确匹配 `emSign ECC Root CA - G3`，且**只在活跃包目录内**计数。
2. **必须查 pip 的 vendored certifi**：多数 venv 根本没装独立 certifi ⇒ 靠 `import certifi` 判断会
   **静默跳过**这一面，而 pip 的 vendored 那一份（真正要命的）从未被检查过。
   ⇒ 判据是「在磁盘上直接扫 cacert.pem」，不依赖 import 成不成功。

### 额外处置：`~ip` 孤儿残留（Windows pip 自升级遗留）

Windows 上 pip 自升级时删不掉正在运行的自身包目录，于是改名成 `~ip`（dist-info 改 `~ip-<ver>.dist-info`），
清理失败就留下孤儿。实测 124 个 venv 里 **201 个孤儿项 / 99 个 venv**，
其 `~ip/_vendor/certifi` 停在 **2026.06.17**（在受影响区间内，含 3 份 G3 根）。

风险定性（实测）：**活跃信任链干净**（`import pip` 走 `pip/`；`importlib.metadata.version('pip')`
在全部 100 个受影响 venv 都返回活跃版本 26.2.2，`~` 前缀不遮蔽元数据），
但磁盘上留着过期易受攻击的 CA 捆绑包，且让扫 `cacert.pem` 的工具反复误报。
⇒ 处置 = **改名隔离出 site-packages** 到 `<venv>/.orphan/<name>.<时间戳>/`，**一个字节都不删**。
（边界：若活跃 `pip` 目录缺失而 `~ip` 存在，说明孤儿顶掉了唯一 pip ⇒ 改为**还原** `~ip`→`pip` 修 venv。）

> 完整判据推导、踩坑与完成判据见项目级技能
> [`.workbuddy/skills/venv-ca-security-audit/SKILL.md`](../.workbuddy/skills/venv-ca-security-audit/SKILL.md)。

---

## 新建仓收尾清单（2026-09-25 沉淀）

> 来源：`docs/MEMORY.md` 调试铁律 52 —— 用一次性 URL 推送时踩到「凭据写进
> `branch.<名>.remote`」这一最难发现的残留。建仓/推送后的收尾**逐项过**：

```powershell
$repo = '/repos/<仓名>'

# ① 凭据残留：必须扫 config **全文**，不能只看 remote 段
#    （`git remote -v` 只显示 remote.origin.url，看不见 branch.*.remote）
Select-String -Path "$repo\.git\config" -Pattern 'https://[^/\s]+:[0-9a-zA-Z]{20,}@'
# 命中就修（两条都要改）：
#   git remote set-url origin "https://gitee.com/<owner>/<repo>.git"
#   git config --file "$repo\.git\config" branch.<branch>.remote origin

# ② 远端 ref 与本地 HEAD 逐字符相等（最强证据）
git -C $repo rev-parse HEAD
git -C $repo ls-remote origin "refs/heads/$(git -C $repo rev-parse --abbrev-ref HEAD)"

# ③ 新文件**字节级**在远端（比 blob sha，不比工作树大小 —— autocrlf 会让它不等）
git -C $repo rev-parse "HEAD:<path>"
git -C $repo cat-file -s <上面的 sha>
# 对照匿名 API：https://gitee.com/api/v5/repos/<owner>/<repo>/contents/<path>?ref=<branch>

# ④ 工作区干净
git -C $repo status --short
```

**用一次性 URL 推送时不要加 `-u`**；若已加，务必执行 ① 的第二条修正。
**`git config` 与文件读取一律用绝对路径** —— 相对路径会静默作用到会话 cwd（本机实测踩过）。