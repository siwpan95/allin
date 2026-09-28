# Gitee 本地推送流程（含「绕过确认」全解）

> 维护时间：2026-09-25｜适用账户：`siwpan`｜适用仓库：`gitee.com/siwpan/*`
> 本文是**本地推送 runbook**，重点讲「如何让推送全程不弹确认框、不手工点网页、不肉眼核对密钥」——
> 即「绕过确认」的 9 个手段（见 §3）。配套自动化工单在 `gitee-repo-and-release-flow` skill 的 `tools/gitee_release.py`（零三方依赖）。
>
> **令牌红线**：令牌**绝不进仓库、绝不进提交**。本文出现令牌处一律 `****` 或 `<GITEE_TOKEN>` 占位；本地令牌路径已脱敏。

---

## 0. 当前本地落点（2026-09-25 实测）

| 项 | 现状 |
|---|---|
| 令牌来源 | 旧 `G:\私人令牌.txt` 已随 G 盘移除。**当前令牌由 Windows 凭据管理器（GCM）持有** |
| 凭据存储文件 | **无文件式凭据**：`~/.git-credentials` 不存在，`credential.https://gitee.com.helper=store` 未配 |
| 凭据实际形态 | 系统级 `credential.helper=helper-selector`，全局 `credential.helper=…git-credential-manager.exe`，`credential.helperselector.selected=<no helper>`；令牌落在 **Windows 凭据管理器**内，文件式检查看不到（`~/.gcm/credentials` 等均无） |
| git 身份 | **全局为空**；各仓按**仓库级**各配 `user.name=siwpan`、`user.email=siwpan@users.noreply.gitee.com`（新 clone 的仓须先补配，否则 `commit` 报 `Author identity unknown`） |
| 推送凭据行为 | `git push` 由 GCM 直接取用，**实测不弹窗、可推**（2026-09-25 分支探针 15.6s 成功） |
| 自动化脚本 | `/Python314/python.exe <仓库>/tools/gitee_release.py …`（任意 Python 3 均可，脚本零依赖） |
| ⚠ 脚本取令牌 | `gitee_release.py whoami` **不带 `--token-file` 会直接失败**（本机无 store 文件可读）。需显式给 `--token` / `--token-file` / `GITEE_TOKEN`；**`git push` 能推 ≠ 脚本能取令牌**，二者走的是不同链路 |
| allin 远程状态 | 默认分支 `master` @ `31581683addf5ff193607fd0cf300d202e606c1e`；另有 tag `nothing`（勿动） |
| Python | 本机 `/Python314/python.exe`（3.14.7）；托管 Python 3.13.12 跑纯逻辑 |

> ⚠️ 旧文档里出现的 `F:\Python314`（旧机盘位）、`G:\私人令牌.txt`、`/Users/13122/*` 等路径**均已失效**；`E:\` 卷在新机**不存在**。照着跑会失败。
> 落点事实源以本表为准，跨机搬运前请先按「本机实测」一节复核（见 §8）。

---

## 1. 推送前准备（安全门禁 = 自动绕过「肉眼确认有没有泄密」）

「绕过确认」不代表「跳过安全检查」。相反，检查交给**机械门禁**，比人手更可靠：

1. **凭据双层扫描**（读暂存区 blob，不是工作区文件）：
   - 令牌**本体子串匹配**：从凭据文件读令牌（不回显）逐文件找它——形态匹配会漏掉「不像密钥」的自定义令牌，本体匹配 100% 命中。
   - 通用形态匹配（键名在前，避免 sha256 误报）：
     ```
     (access_token|api_key|password|secret|token)\s*[=:]\s*["']?[0-9a-zA-Z_\-]{16,}
     https://[^/\s]+:[0-9a-fA-F]{32,}@          # URL 内嵌令牌
     //私人令牌                                # 本机令牌文件路径（已失效，仍拦）
     sk-[0-9a-zA-Z]{20,}                        # OpenAI 风格
     ```
2. **仓库卫生六项**（均配 `--selfcheck` 注入破坏用例，证明门禁不是死的）：
   - LICENSE 唯一（判**路径**，`_ref/ThirdParty/LICENSE` 的 basename 也是 LICENSE，只判文件名会漏）
   - 无第三方源码目录（`_ref/ vendor/ node_modules/ third_party/`）
   - 无产物目录（`output/ state/ cache/ dist/ build/ release/`）
   - 无归档（`*.zip *.tar.gz *.7z`）且无 >5MiB 大文件
   - 无凭据
   - 文档一致性（借鉴记账每项都有「上游 URL + 许可证 + 不入仓声明」）
3. **门禁要在匿名 clone 副本上也能跑通**——本地有 `.gitignore` 完整上下文，本地跑通不算数。

> 为什么必须机械拦：一条 32 位 hex 一旦进过公开仓库历史，即使后来删掉也留在历史里，只能**吊销重发**。

---

## 2. 标准推送顺序（先私有再公开，避免半成品被看到）

```bash
# —— 本机落点（2026-09-25 实测；换机后先按 §8 复核）——
PY="/Python314/python.exe"                  # E: 卷不存在；F: 盘上的 Python 3.14.7 在 PATH
SKILL="/allin/tools/gitee_release.py"       # 脚本随 allin 仓分发，不再依赖 skill 目录

# 0. 验令牌（本机无 store 文件可读，**必须显式给令牌**，否则直接报错）
$PY $SKILL --token "<HEX>" whoami
#   → [OK] login=siwpan ...

# 1. 本地：git init → 跑门禁 → 提交（消息落文件，见 §3.5）
#    ⚠ 新 clone 的仓须先配**仓库级**身份，否则 commit 报 Author identity unknown：
#      git config --local user.name siwpan
#      git config --local user.email siwpan@users.noreply.gitee.com
git init -b main && git add -A
#   （门禁 PASS）
git commit -F /tmp/msg.txt

# 2. 建仓（私有, auto_init=false）→ 配 remote → 推送 → 转公开
$PY $SKILL --token "<HEX>" --name myproj create
$PY $SKILL --token "<HEX>" --name myproj remote
#    推送：**实测本机 GCM 可自动取用**（2026-09-25 分支探针 15.6s 成功），下面这条最稳：
GIT_TERMINAL_PROMPT=0 git -c credential.helper= push "https://siwpan:<HEX>@gitee.com/siwpan/myproj.git" main:main
$PY $SKILL --token "<HEX>" --name myproj public
#   → private=False default_branch=main

# 3. （可选）发版 + 传附件
$PY $SKILL --token "<HEX>" --name myproj release --tag v1.0.0 --title ... --notes-file notes.md
$PY $SKILL --token "<HEX>" --name myproj attach  --tag v1.0.0 --file x.zip --file SHA256SUMS.txt
```

- 各子命令**幂等**（已存在就 SKIP），中断直接重跑。`--token` / `--token-file` / `--owner` / `--name` / `--repo` 等**全局参数必须写在子命令之前**，否则 `unrecognized arguments`。
- **凭据现状（与原文不同，实测订正）**：本机**未配** `credential.https://gitee.com.helper=store`，`~/.git-credentials` 也不存在；凭据由 **Windows 凭据管理器（GCM）** 持有。
  ⇒ `git push` 实测**能推**（GCM 自动取用），但 `gitee_release.py` **取不到**（脚本只认 `--token` / `--token-file` / `GITEE_TOKEN`）——**两条链独立，别互相推断**。
- 一次性 URL 形式（`https://siwpan:<HEX>@…` + `GIT_TERMINAL_PROMPT=0` + `-c credential.helper=`）用于「事后不留 `.git/config` 凭据」的场景；实测推送后本机各仓 `.git/config` 均无凭据残留 ✅。

---

## 3. 「绕过确认」的 9 个手段（重点）

推送流程里凡是「本来要人点一下 / 输一下 / 肉眼核一下」的环节，都用下面手段自动化掉：

| # | 环节（原本要确认什么） | 绕过手段 | 关键命令/配置 |
|---|---|---|---|
| 1 | **令牌从哪来**（弹窗要你贴令牌） | 脚本从 `--token-file` 或 `GITEE_TOKEN` 读，自动 `whoami` 验令牌，全程不弹窗 | `gitee_release.py … whoami` |
| 2 | **git push 凭据**（每次要输用户/密码，或 GCM 弹窗） | ①一次性 URL 把令牌塞进 URL，事后不留 `.git/config`；②本机已配 `credential.https://gitee.com.helper=store`，`git push` 直接复用 | `https://siwpan:****@gitee.com/...` + `GIT_TERMINAL_PROMPT=0` + `-c credential.helper=` |
| 3 | **凭据错误时挂起等输入**（卡死） | `GIT_TERMINAL_PROMPT=0` 让 git 在凭据不对时**立即失败**，不阻塞 | 同上 |
| 4 | **网页逐一点「新建仓库 / 转公开 / 打 tag / 传附件」** | `gitee_release.py` 子命令全自动化 Gitee API；`PATCH` 的 `name` / `target_commitish` 等坑由脚本自动填 | `create` / `remote` / `public` / `release` / `attach` |
| 5 | **提交信息编辑器弹窗确认** | 提交信息落文件用 `git commit -F`，避开编辑器；同时规避 Windows 路径反斜杠被 bash 吃掉（`//repos//x` → `//repos//x`） | `git commit -F /tmp/msg.txt`（分隔符用引号包裹的 `<<'EOF'`，不做变量展开） |
| 6 | **每个子项目单独确认是否推送** | allin 类「整仓推送」约定：`git add -A` + 整仓 commit，一次推完（代价是更依赖 §1 门禁） | `git add -A`（allin 必须整仓，不可仅推部分子目录） |
| 7 | **「有没有把密钥提交进去」肉眼核对** | §1 机械门禁（令牌本体 + 形态双层扫描，含 selfcheck 破坏用例）自动拦 | 门禁脚本，FAIL 即阻断提交 |
| 8 | **「我到底有没有写权限」靠 `--dry-run` 猜** | `--dry-run` 在本地已最新时输出 `Everything up-to-date` **根本没走鉴权**，会误判。改用**分支探针**：建临时分支 push 再删，用 `ls-remote` 确认远端只剩目标分支 | `git branch -f __probe main` → push → `git push --delete origin __probe` → `git ls-remote --heads` |
| 9 | **「推上去没」靠开网页逐个确认** | §4 三层硬证据全自动比对（ref 相等 + blob sha 字节级 + 工作区干净） | `git rev-parse` + `git ls-remote` + `git cat-file` |

> 第 2 条的「store helper」本身也是一种绕过确认（凭据落明文文件 `~/.git-credentials`，之后零输入）。
> 风险点：该文件若被 `git add` 进仓库就泄密——所以 §1 门禁专门拦 `.git-credentials` 类路径与 URL 内嵌令牌。

---

## 4. 推送后验收：三层硬证据（自动绕过「开网页确认」）

⚠ **Gitee 陷阱**：未登录访问 `https://gitee.com/siwpan/<repo>/commit/<sha>` 返回 **HTTP 302 跳登录页**——这不是 404、**更不代表没推上去**。拿它当验收依据会得出错误结论。仓库主页 `/siwpan/<repo>` 是 200 但只能证明仓在。

三层证据，从强到弱（前两层足够下结论）：

```bash
# ① 远端 ref 与本地 HEAD 逐字符相等（最强）
git rev-parse HEAD
git ls-remote origin refs/heads/main          # 两串必须完全相同

# ② 新文件「字节级」在远端：比对 blob sha + 大小（公开仓无需令牌）
git rev-parse HEAD:<path>                     # 本地 blob sha
git cat-file -s <上面那个 sha>                # ⚠ 用 blob 口径，别用 os.path.getsize
curl -s "https://gitee.com/api/v5/repos/siwpan/<repo>/contents/<path>?ref=main"
#   → .sha 与上面一致，.size 与 blob 大小一致

# ③ 工作区干净（确认无漏提交改动）
git status --short                            # 必须为空
```

> 若仓库有 `.gitattributes`（`* text=auto eol=lf` 等），工作区是 CRLF、git 里存 LF，`os.path.getsize()` 会比远端 `size` 每行大 1 字节（实测 20277 vs 19950）——**先比 blob sha**，sha 相同就是同一份内容。更稳的做法：`git worktree add /tmp/verify HEAD` 检出一份跑全量测试 + 门禁。

---

## 5. allin 专属：整仓推送约定

- allin 是**单一索引大仓**，必须**整仓推送**，禁止只推送部分子目录/子项目（会破坏「整仓即事实」的治理模型）。
- 本地工作副本原位（G 盘移除前是 `G:\allin` 根；当前本地以远程 `master` 为准）。新增治理/流程文档直接落到 `docs/`，随整仓一起提交推送。
- 推送前务必跑 §1 门禁；推送后用 §4 三层证据验收；最后复查 `.git/config` 无凭据残留、远端只剩 `master`。

---

## 6. 平台坑速查表（都实测撞过）

| 坑 | 现象 | 应对 |
|---|---|---|
| `PATCH /repos/{o}/{r}` 必须带 `name` | 转公开 `400 {"messages":["name is missing"]}` | body 带 `{"name":<repo>,"private":false}` |
| `GET /releases/tags/{tag}` 对不存在 tag | 返回 **200 + `null`**（非 404） | 判 `isinstance(d,dict) and d.get("id")` |
| 建仓 `auto_init:true` | 多一个无关初始提交，默认分支不是你要推的 | `auto_init:false`，推完再 `PATCH default_branch` |
| 单附件上限 100MB / 仓库总附件 1GB | 大 zip 可能超限 | 压成一个 zip（通常 2.5–3x）；附件名不带路径分隔符 |
| `assets` 里没有 `id` 字段 | 想删传错的附件无从下手（API 只回 `name`+`browser_download_url`） | 删整个 release 再重建：`DELETE /releases/{id}` → 204，附件随之清 |
| 附件上传路径漏 `/api/v5` | 返回 **404 的 HTML 页**（非 JSON），附件静默失败 | `upload_file` 直连，路径自己带 `/api/v5` |
| 建 release 不带 `target_commitish` | `400 {"messages":["target_commitish is missing"]}` | 脚本自动探测当前分支；手调也要显式带 |
| 响应 `html_url` 可能为 `null` | 拿不到发行版网页地址 | 自己拼 `https://gitee.com/{o}/{r}/releases/{tag}` |
| 提交信息里的 Windows 路径 | `//repos//x` 经 bash 变 `//repos//x`，公开仓很扎眼 | 提交信息落文件 `-F` |
| `git push --dry-run` 不能证写权限 | 本地最新时输出 `Everything up-to-date`，没走鉴权 | 用 §3.8 分支探针 |

---

## 7. 一键速查（令牌均脱敏）

```bash
# 验令牌
/Python314/python.exe /allin/tools/gitee_release.py --token-file "<凭据文件路径>" whoami

# 推代码（本机 store helper 已配，自动取凭据；下面这条用于「不留 .git/config 凭据」）
GIT_TERMINAL_PROMPT=0 git -c credential.helper= push "https://siwpan:****@gitee.com/siwpan/<repo>.git" main:main

# 写权限探针
git branch -f __probe main && git push origin __probe && git push --delete origin __probe && git ls-remote --heads origin

# 验收 ref 相等
git rev-parse HEAD && git ls-remote origin refs/heads/main
```

> 所有 `****` 处：本机**没有** `~/.git-credentials` 可读；`git push` 由 **Windows 凭据管理器（GCM）** 自动取用（实测可推、不弹窗），
> 而 `gitee_release.py` **必须显式给令牌**（`--token` / `--token-file` / `GITEE_TOKEN`）。
> 二者是**两条不同的链路**：`git push` 能推，**不代表**脚本能取到令牌。

---

## 8. 落点复核（换机后第一件事）

本文档表格里的绝对路径都属于**某台机器**，不是通用事实。2026-09-25 实测发现：
本文原写「`E:\Python314`、`/Users/13122/.git-credentials`、`helper=store`」——
在新机（`DESKTOP-8RSV60V` / 用户 `psw`）上**三条全部不成立**，照抄必失败。

换机后先跑这段**只读**复核，再照抄后面的命令（完整判读表见发版指南 §6）：

```powershell
"host=$env:COMPUTERNAME user=$env:USERNAME"
(Get-Command python -ErrorAction SilentlyContinue).Source
Test-Path "$env:USERPROFILE\.git-credentials"
git config --global --get credential.helper
git config --local --get user.name
git ls-remote origin "refs/heads/$(git rev-parse --abbrev-ref HEAD)"
```

> **通用纪律**：绝对路径先复核、再使用；发现不符就地更正本文档并记账。
