# 机器事实 · `SIWPAN`（第三台接入机器，曾改名）

> **时点** 2026-11-24 12:20（**@`SIWPAN` py_test_runner 并入 + 工具随包分发** ——
> 全哥指令「py_test_runner 也合并到 allin，仅保留 pypi，用它增强 repocheck；
> **所有新工具都需要随包分发，这是必然的**；跨仓依赖改内联」。
> 落地：①`scan_repos`/`deps_doctor` 移入 `tools/_shared/` 并映射为 `allin_governance._toolkit`，
> 新增 `allin-governance scan` / `deps` 子命令 —— a8 只提过没做，本版补上；
> ②`repocheck --tests` 测试规则族 51-53，复用上提的 pytrunner 探针内核（548 行，
> 只取 Probe 抽象、不用 ProbeManager —— 后者会 `mkdir(logs)`）；
> ③`gitee_release.py` 的跨仓 `gen_third_party_notices` 已内联；
> ④py_test_runner 远端 DELETE 204、本地删除，PyPI `pytrunner` 1.0.0 保留，
> 完整历史 21 提交存 `<工作区>/_archived/py_test_runner-20261124.bundle`。
> 仓数：`D:\projects
epos` **75** 目录 / 含 `.git` **74** / 含 `origin` **74**；远端 **85** 仓。
> **留痕** [交接卷 2026-11](../../../记录/交接/2026-11.md) §一百九十三（工具随包分发与测试规则族）
> **时点** 2026-11-24 10:20（**@`SIWPAN` foolproof-operation 并入 allin** —— 全哥指令「并入 allin，
> 移除远端和本地，仅保留 pypi；扫盘能力上提增强治理；傻瓜式依赖增强 venv 建设」。
> 两项能力上提为 `tools/_shared/scan_repos.py`（发布区扫盘：项目指纹 / 重复检出 / 迁移残留）与
> `tools/_shared/deps_doctor.py`（依赖体检：声明·实装·import 三者对账）；**未搬**其 764 个包的分类清单
> （那是可选推荐库，与治理无关）。完整历史 33 提交存
> `D:\projects\_archived\foolproof-operation-20261124.bundle`（bundle verify 通过）；
> 远端 DELETE HTTP 204、本地删除；PyPI `foolproof-operation` 1.1.2 保留不动。
> 仓数随之下调：目录 / `.git` / `origin` 三项均按最新时点计（当时为 76/75/75，删 py_test_runner 后为 75/74/74）；
> 远端 Gitee `siwpan` **86** 仓。
> **留痕** [交接卷 2026-11](../../../记录/交接/2026-11.md) §一百九十一（foolproof 并入与能力上提）
> **时点** 2026-11-24（**@`SIWPAN` 冻结仓独立入口大清理** —— 全哥指令「解决 repos 两大痛点：
> 移除冻结仓的远端与本地独立入口、仅保留有用内容进合集；删掉重复内容」。
> 68 个冻结子项（`tiering.yaml` 有 `archive_target` 的）中，**66 个独立仓在册、56 个远端仍活**。
> 处置顺序按「先保全、再合并、后删除」：
> ① **历史保全**：56 个远端活仓逐个 `fetch --unshallow` 后把完整提交链推入所属合集的
> `archive/<名>` 分支（原 archive 分支只有一个 squash 快照，等于没有历史）；
> 逐 SHA 核对 56/56 一致。另 10 个远端早已被删的仓（calculator/test/diablo 等）
> 把本地残留的浅历史一并推入（能救多少救多少）。
> ② **内容合并**：独立仓归档后新增且未被 `.gitignore` 忽略的文件补入合集工作树
> 共 74 个（dev-toolkit 14 / game-prototypes 33 / media-prototypes 17 / music-prototypes 1 /
> players-unified 9）；两边都改过的 161 处保留合集版本（独立仓版本在 archive 分支可查）。
> ③ **删除**：远端 56 个仓经 Gitee API DELETE 全部 HTTP 204；本地 66 个目录删除，
> 释放 1771.6 MB。
> ④ **台账**：registry 151 → 84（删 55 个指向已删仓的条目 + 12 个 id 与目录名不一致的重复登记；
> 误删的 anatomy3d / write-agent / portal 三条已从 git 恢复，anatomy3d 补 `checkout: remote-only`
> ——它建在 @DESKTOP-KQABATS 上）；facts.json 84 条；PORTFOLIO 143 → 87。
> 仓数现场实测：当时 77 个目录，此后经两次删仓降至最新时点的 75（不在此复述数字，以免与现行值冲突）；
> 非 git 目录 1 个（`out`）。远端 Gitee `siwpan` **87** 仓（API 实测，与 `check_repos.mjs` 一致）。
> `@SIWPAN` 未检出的远端仓（`anatomy3d` / `write-agent` 等）按 `checkout: remote-only` 登记，
> 属「各机检出集不同」，不是治理缺陷。）
> **留痕** [交接卷 2026-11](../../../记录/交接/2026-11.md) §一百九十（归档入口清理与历史保全的自留痕）
> **时点** 2026-11-23（**@`SIWPAN` 仓根迁入发布区** —— 全哥指令「将 /allin 转入 /repos」：
> 本仓由 `<工作区>/allin` 迁至 `D:\projects\repos\allin`，与 142 个被管仓同住发布区。
> 搬迁连带修好五处只认同级布局的发布区推导：Python 侧 `g17_registry.repos_root`、
> `tools/license_matrix.py`、`tools/repo_hygiene.py`、`scripts/run_all_gates.sh:detect_repos_root`，
> JS 侧 `@allin/core`、console shell、MCP 白名单；判据一律为「父目录名是 `repos` 则取父目录」。
> ⚠ **修复前 g17 的完备性检查一直 `SKIPPED`（not a pass）** —— 内含布局下
> `<本仓>/../repos` 指向不存在的 `<repos>/repos`，门禁把「没检查」当通过报了出来；
> 修好后首次真正生效，当场判出 `repos/allin` 与 `repos/worldwright` 两个未登记仓
> （后者是长期盲区里的存量，本仓 `206ec7b` 2026-11-23 首发 0.1.0、非残留）。
> 仓数现场实测：当时 77 个目录，此后经两次删仓降至最新时点的 75（不在此复述数字，以免与现行值冲突）；
> 含 `origin` **142** · 非 git 目录 1 个（`out`）；`.git` 总数 **142**（本仓已计入发布区，
> 不再另加 1）。远端 Gitee `siwpan` **143** 仓（`tools/build_portfolio.py` API 实测）。
> 本仓 `.venv` 于同日以 uv 重建（CPython 3.12.13，见 §5）。）
> **留痕** [交接卷 2026-11](../../../记录/交接/2026-11.md) §一百八十五（搬迁与门禁纳入 repocheck 的自留痕）
> **时点** 2026-11-08（**@`SIWPAN` PyPI 凭据收编第 5 条** —— a4 发版暴露 token 无受管
> 落点（a3 上传时交互输入未存）。`D:\projects\pypi.txt` 内两条 token 处置：有效
> token 收进 `~/.dsvault/` 条目 `pypi_upload`（回程字节级一致；密文 `pypi-` 前缀
> 检索零明文痕迹），明文文件已删（回收站）；另一条上传实测 403，判废未收编。
> 全部走 `deepseek_vault.py` CLI（cryptography 依赖在 `E:\Python314`，`.venv` 无）。）
> **留痕** [交接卷 2026-11](../../../记录/交接/2026-11.md) §一百四十三（a4 发版与凭据收编的自留痕）
> **时点** 2026-11-06（**@`SIWPAN` 分区文件夹化** —— 结构治理：本文件由 `机器/SIWPAN.md`
> 迁入 `机器/SIWPAN/SIWPAN.md`（一机一目录，参照业界「一机一档」惯例；收敛口径见
> [`机器分区索引.md`](../../机器分区索引.md) §7 布局沿革）。本文件夹
> `D:\projects\allin\docs\事实源\机器\SIWPAN` 现已存在；文件夹内新增 `附属/`
> （一次性产物随档保管区），收编仓根 `siwpan旧机配置汇总.html`；
> g20 门禁与 verify_facts 已同步升级为双形态收集（顶层与文件夹并存为合法过渡态）。）
> **留痕** [交接卷 2026-11](../../../记录/交接/2026-11.md) §一百三十八（本轮文件夹化与 D16/D17 判据新增的自留痕）
> **时点** 2026-11-01（**@`SIWPAN` 受管密钥库建成** —— 用户批准「建受管库收编」：
> `~/.dsvault/`（`vault.enc` AES-256-GCM + PBKDF2 200k；`deepseek_vault.py` CLI；
> 解锁口令机器生成、DPAPI 封存 `pass.bin`）。**偏差记档**：8RSV60V 走「口令存凭据管理器 +
> git credential fill」，本机 PortableGit **无 credential helper** 且 `~/.gitconfig` 空
> `credential.helper` 掐断 helper 链 ⇒ 改走 crypt32 DPAPI 直封（同一 DPAPI 信任锚，
> 口令不明文落盘、仅当前用户可解，安全实质不变）。收编 4 条：`github_pat_finegrained`
> / `github_pat_classic` / `github_password`（原 `D:\projects\github.txt`，含 GitHub
> 账号口令）/ `deepseek_api_key`（原 `Desktop\deepseek.txt`，实测有效余额 310.17）——
> **4/4 回程一致、密文字节级 0 明文痕迹，两个明文文件已删除**，g03 真红线清零。）
> **时点** 2026-10-31（**@`SIWPAN` 推送配置升级** —— 用户指令「配 GitHub 侧镜像推送」：
> origin 双 pushurl（Gitee + `git@github.com:siwpan95/allin.git` SSH），与 [`DESKTOP-8RSV60V.md`](../DESKTOP-8RSV60V/DESKTOP-8RSV60V.md) §9 同款口径。
> ⚠ 旧值「本机不补配 pushurl」作废 —— 那是 2026-10-29 对 `DESKTOP-KQABATS` 的交代，被错误外推到本机；
> 各机推送配置以用户逐机指令为准。SSH 前提实测：`id_ed25519` 认证通过（`Hi siwpan95!`），
> 双通道首推两行 up-to-date、双侧 ls-remote 与 HEAD 逐字符相等。）
> **时点** 2026-10-30（**@`SIWPAN` 全量复测补录** —— `tools/facts/measure.py` 采集 + 人工裁决；
>   本次补齐盘位卷标、工作区落点、仓数口径、运行时与解释器清单、推送口径，
>   并按 [`机器分区索引.md`](../../机器分区索引.md) §0 归属规则只写本机事实。）
>   ⚠ **订正（取代旧表述）**：commit `4e329c4` 的**提交信息**里写有
>   「`SIWPAN` 分区目前仅标识 + 差异两节，需在其宿主机实测补录」——该表述**已被本补录取代**
>   （本文件现含 §1–§8 七节全量台账 + 可机检断言，`verify_facts` 0 findings；文件树中无该旧表述副本，
>   仅存在于那条不可改写的提交信息里）。引用 SIWPAN 分区完成度时以本文件与
>   `docs/记录/记忆/2026-10.md` 2026-10-30 17:40 取代条为准。
> **时点** 2026-10-30（**@`SIWPAN` 实测登记**（上午）：凭据审计遗留逐条核对本机归属 ——
>   `C:\Users\psw`、`D:\deepseek-harness`、`.dsvault` 均不存在；`remote.origin.pushurl` = **0** 条。）
> **时点** 2026-10-29（**@`SIWPAN` 实测登记** —— 该机与 `DESKTOP-KQABATS` 名对不上，按
>   `机器分区索引.md` §3 纪律第 4 条**先求证后定性**：用户确认 = **第三台机器，且曾改名（现名 `SIWPAN`）**。）
> **观测工具** `tools/facts/measure.py`（`Get-Volume` / `Get-Disk` / `Get-Command` / `git config`）、
>   `Get-CimInstance Win32_*`、`git rev-parse --show-toplevel`、Gitee API 匿名查询
> **失效条件** 换机、加减盘、重装系统、换运行时版本后**立即失效**；每次涉及机器事实的动作前
>   **现场复测**，不要照抄本文件。
> **上位判据** [`../../../规范/SPEC-006-机器与路径约定.md`](../../../规范/SPEC-006-机器与路径约定.md)。
> **本文件只记录 `SIWPAN` 这台**；其他机器见 [`../机器分区索引.md`](../../机器分区索引.md) §1。

---

## 1. 本机标识（@`SIWPAN` 复测，2026-10-30）

| 项 | 实测值 | 观测方式 |
| --- | --- | --- |
| **主机名** | **`SIWPAN`** | `Win32_ComputerSystem.Name`（该机 `$env:COMPUTERNAME` = `SIWPAN`，非空） |
| hostname 大小写 | `hostname` 命令输出**小写** `siwpan` | 与 `Win32_ComputerSystem.Name` 的 `SIWPAN` 是**同一台**（Windows 主机名大小写不敏感），勿当两台 |
| 用户目录 | `C:\Users\13122` | `$env:USERNAME` = `13122` |
| CPU | Intel Core **i7-9750H** @ 2.60GHz | `Win32_Processor`（2026-10-29 实测，本轮未复测） |
| 内存 | **31.9 GB** | `Win32_ComputerSystem.TotalPhysicalMemory`（2026-10-29 实测） |
| 系统 | **Windows 11 专业版**，10.0.**26100**（build 26100） | `Win32_OperatingSystem`（measure.py 复测一致） |
| 物理盘 | **1 块**：`M.2 SSD 1TB`（SATA，932 GB）——三卷同盘分区 | `Get-Disk`（measure.py） |
| 本仓仓根 | **`D:\projects\repos\allin`** | `git rev-parse --show-toplevel`（2026-11-23 迁入发布区） |
| 发布区 | **`D:\projects\repos`** | 本仓所在目录（仓根在**发布区内**，不再与发布区同级） |

## 2. 盘位（2026-10-30 实测）

| 盘 | 卷标 | 文件系统 | 容量 GB | 可用 GB | 角色 |
| --- | --- | --- | --- | --- | --- |
| `C:` | `system` | NTFS | 118 | 41 | 系统盘 |
| `D:` | `dalang` | NTFS | 405 | 326 | **工作区盘**（仓根 + 发布区） |
| `E:` | `erlang` | NTFS | 407 | 389 | 数据盘（主 Python `E:\Python314` 在此） |

- **仅 C / D / E 三卷，无 F: / G:**（2026-10-29 与 10-30 两轮实测一致）。
- `C:\Users\psw` **现已不存在**（8RSV60V 侧的用户目录，本机从未有）。
- `D:\deepseek-harness` **已不存在**（8RSV60V 侧的 DSH 现役 checkout；本机无 DSH 检出）。

## 3. 工作区落点（2026-10-30 实测）

| 落点 | 内容 |
| --- | --- |
| `D:\projects\repos\allin` | **本仓**（治理仓，`origin` = `https://gitee.com/siwpan/allin.git`；2026-11-23 起住在发布区内） |
| `D:\projects\repos` | **发布区**（Gitee 仓的本地检出，**全量检出**，含本仓；仓数见 §4） |

- 便携工具链：`C:\Users\13122\.workbuddy\binaries\`（Node / Python / 等，随 WorkBuddy）；
  git 走 WorkBuddy vendor 的 PortableGit（见 §5）。
- WorkBuddy 会话工作区按日期目录管理（`C:\Users\13122\WorkBuddy\<日期时间>\`）。

## 4. 仓数口径（2026-10-30 实测；2026-11-03 复测）

| 项 | 值 | 依据 |
| --- | --- | --- |
| **远端仓总数**（Gitee `siwpan`） | **85** | `tools/build_portfolio.py` API 实测（2026-11-24：公开 85 / 私有 0；比 11-23 的 143 少 58 —— 冻结子项的独立仓已删除，内容与完整历史已归档进 4 个合集仓）；跨机共识值唯一登记处见 [`../机器分区索引.md`](../../机器分区索引.md) §5 |
| **本机发布区目录数** | **75** | `D:\projects\repos` **75** 个目录（含本仓 `allin`，2026-11-24 删 66 冻结仓 + foolproof + py_test_runner 后实测） |
| 含 `.git` | **74 / 75** | 逐目录实测（唯一非 git 目录是 `out`） |
| 含 `origin` | **74 / 74** | 逐仓 `git remote get-url origin`（2026-11-24 实测） |
| 本机 `.git` 总数 | **74** | 全部位于发布区内（本仓已计入） |

- 口径：本机是**全量检出**（2026-11-23 实测 143 = 远端 143）；提「远端仓数」一律查索引 §5；
  提「本机发布区仓数」一律**现场实测**。
- ⚠ **与 `DESKTOP-KQABATS` 的差异**：那机是**部分检出**（23 仓，2026-11-03 复测），本机是全量检出 143 仓 ——
  「哪仓在哪台」以各机分区文件为准，勿跨机假设。

## 5. 运行时与工具链（2026-10-30 实测；PATH 实际解析，非文档声称）

| 工具 | 现值 | 备注 |
| --- | --- | --- |
| Python | **`E:\Python314\python.exe` → 3.13.14（有 tkinter，Tk 8.6）** | **本机主 Python**，唯一带 tkinter 的；仓内 `.venv`（ 3.12.13）优先，其余走 PATH 便携解释器 |
| Node | `C:\Users\13122\.workbuddy\binaries\node\versions\22.22.2-6\node.exe`（v22.22.2） | WorkBuddy 便携工具链 |
| npm | 同目录（10.9.7） | 与 node 同版本目录 |
| git | `C:\Users\13122\AppData\Local\Programs\WorkBuddy\resources\vendor\PortableGit\mingw64\bin\git.EXE`（**2.55.0.windows.3**） | WorkBuddy vendor 版**在 PATH**（与 KQABATS 的「系统安装版在 PATH」不同） |
| pwsh | **`C:\Program Files\PowerShell\7\pwsh.exe`（7.6.6）** | 在 PATH；`powershell` = 系统 Windows PowerShell 5.1 |
| `.venv` | 本仓 `D:\projects\repos\allin\.venv` **存在**（CPython **3.12.13**，uv 建，含 PyYAML / pytest / bandit 等） | 2026-11-23 搬迁时重建 —— 旧 venv 的 console_scripts 内嵌旧绝对路径，移动后全失效；`run_all_gates.sh` 的仓内 `.venv` 优先策略从此真正生效 |

### 5.1 Python 解释器清单（2026-10-30 实测；选型前先测 `import tkinter`）

| 解释器 | 版本 | tkinter | 定位 |
| --- | --- | --- | --- |
| `E:\Python314\python.exe` | **3.13.14** | **有**（Tk 8.6） | ✅ **本机主 Python**（唯一带 tkinter 的；`E:\Python314` 现存） |
| `C:\Users\13122\.workbuddy\binaries\python\versions\3.13.12\python.exe` | 3.13.14 | **无** | WorkBuddy 便携工具链（**精简构建**）；路径里的 `3.13.12` 是**目录名**，判版本一律 `python -V` |
| `C:\Users\13122\AppData\Local\Microsoft\WindowsApps\python.exe` | —— | —— | ⚠ **Microsoft Store 占位符**（存在），执行即报「Python was not found」—— **不是解释器**，脚本里别误选 |

- ⚠ **依赖 tkinter 的项目（GUI / repocheck GUI 模式）只能用 `E:\Python314\python.exe`**。
- ✅ **`repocheck` CLI 与本仓门禁在便携解释器上可跑**（tkinter 仅 GUI 分支需要）；本轮 19+1 道门禁实测全绿。

## 6. 跨仓环境变量（2026-10-30 实测）

| 变量 | 本机状态 |
| --- | --- |
| `KONTAKT_TRANSCODE_ROOT` | 未设置 |
| `RIME_SRC` | 未设置 |
| `GITEE_TOKEN` | 未设置（`gitee_release.py` 走 `~/.git-credentials` 首段 hex 的 `--token-file` 口径） |

- **读法约定**：跨仓脚本引用数据根时**优先环境变量、未设则按 cwd 相对解析**（铁律 5 同口径）。

## 7. 推送与远端镜像（@`SIWPAN` 侧，2026-10-31 实测）

| 项 | 现值 |
| --- | --- |
| `remote.origin.url` | `https://gitee.com/siwpan/allin.git` |
| `remote.origin.pushurl` 条数 | **2**：Gitee + `git@github.com:siwpan95/allin.git`（2026-10-31 用户指令补配，与 `@DESKTOP-8RSV60V` §9 同款） |
| 独立 remote | `github` = `git@github.com:siwpan95/allin.git`（fetch/push） |
| SSH 前提 | `~/.ssh/id_ed25519` 认证通过（`Hi siwpan95!`）；`~/.ssh/config` 含 `ssh.github.com:443` 备用口 |
| 推送口径 | **一次 `git push` 依次打两条**（Gitee + GitHub 镜像） |
| 核对口径 | **Gitee 与 GitHub 两侧 `ls-remote` 都要核**（与 KQABATS 的单核口径不同，勿跨机套用） |

- **首推实测（2026-10-31）**：配置后 `git push origin master` 两行 `Everything up-to-date`（exit 0）；
  随后的记账提交经双通道真实推送，双侧 `ls-remote` 与 `rev-parse HEAD` 逐字符相等。
- **另一台的对照**（口径相反，勿套用）：[`DESKTOP-KQABATS.md`](../DESKTOP-KQABATS/DESKTOP-KQABATS.md) §7「推送与远端镜像」（该机 pushurl 0 条、
  用户 2026-10-29 明确不补配——**逐机指令，不外推**）。
- ⚠ **跨机漂移现行（2026-10-30 实证）**：本机作业期间远端两次被其它机推进
  （`5a1d767→c9586d3` DIVERGED、`8b46e67→7f3fecc` PURE_BEHIND）——
  **动手前 fetch 对齐是硬纪律**，DIVERGED 时 g04 会拦。

## 8. 与 `DESKTOP-KQABATS` 的实测差异（仅列事实，不作定性）

CPU 代际（9th i7-9750H vs 13th i5-13420H）、内存（31.9 vs 15.7 GB）、系统版本（专业版 26100 vs
家庭版 26300）、仓根/发布区盘位（D: vs E:）、发布区规模（**全量 137 vs 部分 22**）、
git 来源（PATH 上是 WorkBuddy vendor PortableGit vs 系统安装版）、pwsh（7.6.6 在 PATH vs 不在 PATH）。
**关系定性（用户 2026-10-29 求证）：`SIWPAN` 是第三台机器，曾改名（现名 `SIWPAN`）。**

---

*本文件是 `SIWPAN` 这台的**唯一**事实源。改前先复测，并把旧值以"（原 …）"形式留在同格内。*

## 9. 本机事件台账（指针，2026-11-24 起）

> 各机事故的**完整记录**住交接卷；本节只列「发生在本机、对复验有用」的条目指针。
> 指南正文（操作手册）不带各机事故 —— 提炼后的通用案例才进手册。

| 日期 | 事件 | 详录 |
| --- | --- | --- |
| 2026-11-24 | `publish_area_gate` 豁免表静默落空：`repo_hygiene.py` 的 `_default_audit_file()` 只认旧落点，台账迁 `governance/ledger/` 后报 239 条假红（全在别仓，非本仓内容问题） | 交接卷 §205.4 |
| 2026-11-24 | 发 `allin-governance` 时发现 PyPI `1.0.1` 已被另一条线占用 —— 版本号必须单一来源（`pyproject`），先查线上再定版本 | 交接卷 §202.1 |
| 2026-11-24 | 本机 `files.pythonhosted.org` 直连读超时（索引可达、文件不可达）⇒ 发版后「索引可见」与「本机已装」是两个判据，等镜像同步复验 | 交接卷 §202.4 / §204 |
| 2026-11-24 | `check_pkg_parity`（6 组映射）抓出 `_gatesuite` 漏收 `ledger/*` —— 台账迁移连带缺口 | 交接卷 §211 前的总进度复核 |
| 2026-11-11 | 全链复跑（仓内 `.venv` 3.12.13，基线 `910be05`）：主链 47 条全绿；`platform test` 75/75；同时校准本文 13 处数字漂移 | 交接卷 §181 前身 / `记录/审计/新人开发上手指南校准_2026-11-11.md` |
| 2026-11-24 | 本机已装 `pwsh` 7.6.6 ⇒ `bootstrap.sh` 走 pwsh 分支重建别名（与 KQABATS 的无 pwsh 编码坑互为对照） | 指南 §0.1 历史版 / 分区 §7 |
