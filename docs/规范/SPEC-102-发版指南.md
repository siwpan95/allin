# Gitee 发版指南（含优先级 + 联网核实）

> **编号** SPEC-102 ｜ **效力** 操作规范 ｜ **状态** 生效
> **生效** 2026-09-25 ｜ **最后修订** 2026-09-28 ｜ **适用面** 发行版（tag / release / 附件）的发布动作
> **承载体** `tools/gitee_release.py`（分步、可重入、幂等）；发版门禁随 DSH 门禁聚合运行
> **引用格式** SPEC-102 §一

> 配套脚本：**本仓库 `tools/gitee_release.py`**（零三方依赖，分步、可重入、幂等），用法与平台坑见 `tools/README.md`；该脚本亦随 `gitee-repo-and-release-flow` skill 提供，两份内容一致。
> 推送篇见同目录 `docs/规范/SPEC-101-推送流程.md`；本篇只讲「发版 / 发行版」。
> **令牌脱敏约定**：全文用 `<GITEE_TOKEN>` / `****` 表示，**绝不写进仓库、不回显**。

---

## 0. 当前本地落点（2026-09-25 实测，已随 F/G 盘移除更新）

| 项 | 现状 |
|---|---|
| 令牌来源 | **Windows 凭据管理器（GCM）**，**无文件式凭据**（`~/.git-credentials` 不存在、`credential.https://gitee.com.helper=store` 未配）。`git push` 由 GCM 直接取用，实测不弹窗可推 |
| 给 API 脚本取令牌 | 本机**没有** `~/.git-credentials` 可提取，故 `--token-file "$HOME/.git-credentials"` **会失败**。须显式提供 `--token <HEX>`、`GITEE_TOKEN` 或真正的凭据文件路径 |
| Python | `/Python314/python.exe`（3.14.7，已在 PATH；含 openpyxl 3.1.5） |
| allin 远程 | `master` @ `bd34ed0`；默认分支 `master`；另有 `nothing` tag |
| git 身份 | **全局未配**；各仓按**仓库级**配 `user.name=siwpan` / `user.email=siwpan@users.noreply.gitee.com` |
| 关联文档 | `docs/规范/SPEC-101-推送流程.md`（推送篇，含「绕过确认」9 手段 + 三层验收）；`docs/规范/SPEC-103-社区协作规范.md`（社区协作 / 分支 / 命名 / 卫生 / 许可证） |

> ⚠ 旧路径 `G:\私人令牌.txt`、`E:\Python314`、`/Users/13122/*` 在新机**均不存在**（新机是 `DESKTOP-8RSV60V` / 用户 `psw`）。
> 本机现为 C / D / F / G 四卷：C 内置、D 外置 exFAT(save)、F 外置 NTFS(trash)、G 外置 NTFS(allin)。
> 本表为**落点事实源**；跨机搬运后须按 §6 复核再照抄。

---

## 1. 发版流程按优先级整理

### 🔴 P0 — 发版前门禁（机器拦，不可跳过）

> 门禁要在**匿名 clone 副本**上也能跑通，本地跑通不算数。

1. **安全门禁（最关键）**：双层扫描暂存区 blob——
   - 令牌**本体**子串匹配（先从凭据文件读出令牌，不回显，再逐文件找它）；
   - 通用凭据**形态**匹配（`access_token|api_key|secret|token` 键值、`https://…:hex@` URL 内嵌、`git-credentials|私人令牌` 路径引用、`sk-…` OpenAI 风格）。
   - 必须带 **selfcheck 破坏用例**（往源塞假令牌 → 必须报红），否则门禁是死的。
   - 一条 32 位 hex 密钥一旦进过公开仓库历史，**只能吊销重发**。
2. **许可核查**：发布物若带第三方二进制，**先读其 LICENSE 原文**（别凭记忆）。
   例：gyan.dev 的 FFmpeg `full_build-shared` = **GPL v3** → 发布物整体受 GPL v3 约束 → 项目 `LICENSE` 只能选 GPL 兼容许可。第三方源码**不入仓**，只在 `docs/REFERENCE.md` 记来源 + 许可 + 取用范围。
3. **全量回归绿**：发版 commit 必须来自绿状态（不是「看起来能跑」）。
4. **匿名验收预演**：`git clone --depth 1 <url> /tmp/x` 能拉全，文件数 / commit 号与本地一致。

### 🟠 P1 — 发版核心动作（顺序执行，幂等可重入）

> 每个子命令重复跑安全（已存在就 SKIP）。中断后直接重跑。

```bash
# 0. 验令牌（最便宜的失败前置；须显式给令牌来源，本机无 store 文件可读）
python tools/gitee_release.py --token "<HEX>" whoami
#   → [OK] login=siwpan ...

# 1. 打 tag（语义化版本，如 v1.2.0）—— 必须先有 tag 才能建 release
git tag -a v1.2.0 -m "v1.2.0" && git push -f origin v1.2.0

# 2. 建 release（API，见 §2 参数与坑）
python tools/gitee_release.py --token "<HEX>" \
       release --tag v1.2.0 --title "v1.2.0" --notes-file RELEASE_NOTES.md

# 3. 传附件（单附件 ≤100MB；压成一个 zip，附件名不带路径分隔符）
python tools/gitee_release.py --token "<HEX>" \
       attach --tag v1.2.0 --file dist.zip --file SHA256SUMS.txt

# 4.（如需）转公开：先私有后公开，避免半成品被看到
python tools/gitee_release.py --token "<HEX>" public
```

> 旧写法 `--token-file "$HOME/.git-credentials"` 在本机**必失败**（该文件不存在，凭据在 Windows 凭据管理器里）；
> 台账里的 `****` 一律替换成 `--token "<HEX>"` 或先 `export GITEE_TOKEN=<HEX>`（再省掉 `--token`）。

**写权限确认用分支探针**（不要 `--dry-run`，本地最新时它根本不走鉴权，会误判）：
`git branch -f __probe master` → push 该分支 → `push --delete __probe` → `git ls-remote --heads` 确认远端只剩 master。

### 🟢 P2 — 收尾与验收

1. **发行说明该写什么**：系统要求 → 安装步骤 → **许可与对应源码** → 完整性校验（附件 SHA-256 + 逐文件 `SHA256SUMS.txt`）→ 本版本实测数据 → **已知限制（如实列）**。
2. **三层硬证据验收**（见推送篇 §4；前两层足够下结论）：
   - ① 远端 ref 与本地 HEAD 逐字符相等：`git rev-parse HEAD` == `git ls-remote origin refs/heads/master`；
   - ② 新文件**字节级**在远端：本地 `git rev-parse HEAD:<path>` 的 blob sha == 匿名 contents API 返回的 `.sha`、`.size` 一致（**比大小用 `git cat-file -s`，别用 `os.path.getsize`**，避开 `.gitattributes` 的 CRLF/LF 坑）；
   - ③ 工作区 `git status --short` 为空。
3. 附件**回下载 SHA-256 与本地一致**（只比大小不够）。
4. 发行版指向的 commit 就是全量回归通过的那个。
5. `.git/config` 无凭据残留；推送后复查没把令牌/大文件带进去。

---

## 2. 联网核实的现行限制（help.gitee.com / Gitee Open API v5，2026-09-25）

| 项 | 现行规则（已核实） |
|---|---|
| 单附件上限 | **100 MB**（社区版）；**GVP 项目 200 MB** |
| 每仓库总附件 | **1 GB**（推荐项目 5 GB；GVP 20 GB）。**附件总容量 = 仓库附件 + 发行版附件** |
| 建 release 前置 | **必须先有 tag**（系统不允许跳过 Tag 直接建 release） |
| 建 release API | `POST https://gitee.com/api/v5/repos/{owner}/{repo}/releases`，formData：`tag_name*`（提倡 `v` 前缀）、`name*`、`body*`、`prerelease`、`target_commitish*`（分支或 commit SHA，默认当前默认分支）。鉴权：`Authorization: token <TOKEN>` 或 query `?access_token=` |
| 编辑 / 删除 | 草稿可删；**已发布** release 在网页端不可直接删（需先取消「最新发布」再联系管理员）。但本机 **2026-09-22 实测 `DELETE /releases/{id}` → 204 仍可删**（含附件随之清空）——以 API 实测为准，网页端限制仅影响人工操作 |
| 速率限制 | 平台有 API rate limit，大规模发版需合规，避免突发高频 |
| 源码包链接 | 发布页自动附的 `/archive/refs/tags/*.zip` **不是直链**（匿名拿到的 HTML），GPL 义务要求的源码指向应当写 `git clone` 地址 |

> 应对 100MB 上限：把发布载荷**压成一个 zip**（实测 127MB 载荷 → 47.9MB zip，约 2.65x）。**别发一堆散文件**——附件名不允许带路径分隔符，会丢目录结构。

---

## 3. 平台坑速查（发版相关，均实测）

完整坑表见 `docs/规范/SPEC-101-推送流程.md`「平台坑」。聚焦发版：

| 坑 | 现象 | 应对 |
|---|---|---|
| `PATCH /repos/{o}/{r}` 转公开缺 `name` | 400 `{"messages":["name is missing"]}` | body 带 `{"name":<repo>,"private":false}` |
| `GET /releases/tags/{tag}` 对不存在 tag | 返回 **200 + `null`**（不是 404） | 判 `isinstance(d,dict) and d.get("id")`，别只判状态码 |
| **`assets` 无 `id` 字段** | 想删传错的附件无从下手（API 只回 `name`+`browser_download_url`） | 正确做法：**删整个 release 再重建**（`DELETE /releases/{id}` → 204，附件随之清），再 `release`+`attach` |
| **附件上传路径漏 `/api/v5`** | 返回 404 的 HTML 页（非 JSON），静默失败 | `upload_file` 直连 `gitee.com`，路径必须自带 `/api/v5`（脚本已修） |
| **建 release 不带 `target_commitish`** | 400 `{"messages":["target_commitish is missing"]}` | 脚本已改**自动探测当前分支**；手写 API 也要显式带 |
| 响应 `html_url` 可能为 `null` | 拿不到发行版网页地址 | 自己拼 `https://gitee.com/{o}/{r}/releases/{tag}` |
| 单附件 100MB / 仓库总附件 1GB | 大 zip 超限 | 压缩比 2.5–3x；别发散文件（丢目录结构） |

---

## 4. 验收清单（别停在「上传成功」）

- [ ] `whoami` 通、`release` 返回 201（或 SKIP 已存在）
- [ ] tag 已推送，`target_commitish` 指向全量回归通过的 commit
- [ ] 附件**回下载 SHA-256 与本地一致**（只比大小不够）；单附件 ≤100MB、仓库总附件 ≤1GB
- [ ] `private=False` 时**匿名**（不带令牌）能打开仓库页 / raw / 发行版页 / 下载附件
- [ ] **匿名 clone 能拉全**：文件数 + commit 号与本地一致（比「网页能开」强得多，且验证无私有依赖）
- [ ] 发行版指向的 commit 即绿状态那个
- [ ] 仓库卫生门禁在**匿名 clone 副本**上跑通（本地不算）
- [ ] `.git/config` 无凭据残留；写权限用**分支探针**确认
- [ ] 发行说明含：系统要求 / 安装 / 许可与对应源码 / SHA-256 / 实测 / 已知限制

---

## 5. 一键速查

```bash
# —— 取令牌：本机无 store 文件，须用真正的凭据文件路径或环境变量 ——
# 旧写法 --token-file "$HOME/.git-credentials" 在本机必失败（该文件不存在）
export GITEE_TOKEN=<HEX>          # 或不入环境，直接给 --token <HEX>

# —— 发版（幂等，中断可重跑）——
python tools/gitee_release.py whoami
git tag -a v1.2.0 -m "v1.2.0" && git push -f origin v1.2.0
python tools/gitee_release.py release --tag v1.2.0 --title "v1.2.0" --notes-file RELEASE_NOTES.md
python tools/gitee_release.py attach  --tag v1.2.0 --file dist.zip --file SHA256SUMS.txt

# —— 三层验收（前两层足够）——
git rev-parse HEAD                                  # ① 本地 HEAD
git ls-remote origin refs/heads/master              # ① 远端 ref 须逐字符相等
git rev-parse HEAD:docs/规范/SPEC-102-发版指南.md            # ② 本地 blob sha
# ② 匿名比对：curl "https://gitee.com/api/v5/repos/siwpan/<repo>/contents/docs/规范/SPEC-102-发版指南.md?ref=master"
git status --short                                  # ③ 须为空
```

> 令牌打印前替换成 `<REDACTED>`：`... 2>&1 | sed -E "s/${TOKEN}/<REDACTED>/g"`。
> 提交信息**落文件再 `-F`**，避免 Windows 路径被 bash 吃掉反斜杠。

---

## 6. 落点复核（照抄本文档前先跑一遍）

**教训（2026-09-25 实测）**：本文档与推送篇原先写的是**原型机落点**（`E:\Python314`、
`/Users/13122/.git-credentials`、`helper=store`、F/G 盘已移除）。换机后照抄**必失败**——
`E:\` 卷不存在、`~/.git-credentials` 不存在、全局 git 身份为空。

下面这段**只读**命令在任何机器上跑一遍，即可核出本文档哪些落点需要就地修正：

```powershell
"host=$env:COMPUTERNAME user=$env:USERNAME"
"python = " + (Get-Command python -ErrorAction SilentlyContinue).Source
& python -c "import sys;print('py',sys.version.split()[0]);print('stdio',sys.stdout.encoding)"
"git identity: global=[" + (git config --global --get user.name) + "] local=[" + (git config --local --get user.name) + "]"
"cred file  : " + (Test-Path "$env:USERPROFILE\.git-credentials")
"cred helper: " + (git config --global --get credential.helper) + " selector=" + (git config --global --get credential.helperselector.selected)
"drives     : " + ((Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Name -match '^[C-Z]$'}).Name -join ',')
git rev-parse --abbrev-ref HEAD; git rev-parse HEAD; git ls-remote origin "refs/heads/$(git rev-parse --abbrev-ref HEAD)"
```

判读要点：

| 现象 | 含义 | 处置 |
|---|---|---|
| `python` 路径与本文档不符 | 文档落点基于别的机器 | 就地更正本文档，**并记账** |
| `stdio=gbk` | 中文 Windows 默认编码 | 相关 Python 入口须 `reconfigure(encoding="utf-8")`，否则中文经 stdio 必乱码 |
| `local=[]` 且 `global=[]` | 本仓无提交身份 | `git config --local user.name/user.email`（照同机其它仓对齐） |
| `cred file=False` | 无文件式凭据 | 脚本取令牌须显式 `--token`/`GITEE_TOKEN`；但 `git push` 仍可能由凭据管理器正常取用 |
| `ls-remote` 两串不等 | 本地与远端不同步 | 先对齐再发版 |

> **通用纪律**：文档里的绝对路径都属于**某台机器**，不是"事实"。换机后先跑本节复核，
> 再照抄后面的命令。
