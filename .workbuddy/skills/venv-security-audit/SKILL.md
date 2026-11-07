---
name: venv-security-audit
description: >
  通用 Python venv 安全巡检与加固：版本基线（pip/certifi/uv）、活跃 CA 捆绑包的
  emSign ECC Root CA - G3（GHSA-6q48）、离线已知漏洞基线、venv 结构完整性、
  Windows 上 pip 自升级遗留的 ~ip 孤儿残留。纯标准库、离线、不删文件。
  触发词：venv 安全巡检、venv 加固、CA 证书、GHSA-6q48、certifi、emSign、E-mudhra、
  根证书加固、MITM 风险、依赖漏洞基线、venv 完整性、~ip 孤儿、pip 损坏、home 失效。
---

# venv 安全巡检与加固 SOP（通用检查框架）

> 执行器：`tools/security/venv_security.py`（纯标准库，可拷走即用）
> 统一入口：`allin tools venv-audit <scan|apply|verify> [root] [jobs] [--check ID]`
> 本技能讲**判定口径与踩坑**，脚本负责执行。检查项按注册表组织，新增一类风险 = 加一个检查类。

## 检查框架（7 项）

| id | 作用 | 自动修复 |
|---|---|---|
| `pip-bootstrap` | pip 缺失/损坏 → `ensurepip` 引导（损坏先改名 `.bak` 备份） | 是 |
| `broken-home-repair` | `pyvenv.cfg` 的 `home` 指向失效基准解释器 → 按版本映射修复 | 是 |
| `pip-certifi-uv-baseline` | pip ≥ 26.2.2 / certifi ≥ 2026.10.19（**uv 已移到全局层**，见下） | 是 |
| `ca-emsign-g3` | 活跃 CA 捆绑包内 `emSign ECC Root CA - G3` 残留（GHSA-6q48） | 是（强制重装 pip） |
| `dep-vuln-baseline` | 离线已知漏洞基线（内置 `ADVISORIES` 表） | 否（只报告） |
| `venv-integrity` | 解释器 / 元数据 / 重复 dist-info | 否（只报告） |
| `orphan-quarantine` | `~` 孤儿残留改名隔离 / 边界还原 | 是 |

- `scan` 只读 site-packages 元数据，**不启动解释器**；`verify` 才实跑解释器做功能级确认。
- `apply` 只处理**可修项**，幂等；只报告项（`dep-vuln-baseline` / `venv-integrity`）不参与 apply 成败。
- **绝不删除任何文件**：损坏的 pip 改名 `.bak`，孤儿改名移入 `<venv>/.orphan/`。

## ⚠️ CA 检查（ca-emsign-g3）——判据必须精确到 G3

2026-10-20 披露的 **CRITICAL** 事件（CVSS 9.1，CWE-295，**无 CVE 号**）：

- certifi `>= 2019.03.09, < 2026.10.19` 的 CA 捆绑包含 **`emSign ECC Root CA - G3`** 根证书。
- eMudhra 签发、链到该根的 **8 张中间 CA 证书私钥已泄露**并被吊销。
- 持泄露私钥者可签发「对任意主机名都像真的」证书；再叠加 on-path 即可 **MITM**。
- 受影响组件：`requests` / `urllib3` / **`pip`** 等一切依赖 certifi 信任链者。
- 修复线：certifi `2026.10.18` 移除**全部** emSign 根；`2026.10.19` **只恢复未受影响的** emSign 根。
  ⇒ 安全版本 = `certifi >= 2026.10.19`。

**最大的误报陷阱**：certifi 2026.10.19 的捆绑包里**仍然有 9~15 处 "emSign"** —— 那是公告**有意恢复**的未受影响根。
⇒ 「包里有没有 emSign」是**错的**判据，会对着全部 venv 误报。
⇒ **唯一正确判据**：精确匹配字符串 **`emSign ECC Root CA - G3`**，且**只在活跃包目录内**计数。

**三个必查面（缺一面就等于没查）**：

| # | 面 | 位置 | 为什么不能省 |
|---|---|---|---|
| 1 | 独立 certifi 包 | `site-packages/certifi/cacert.pem` | 用户直接 `import certifi` 的信任源 |
| 2 | **pip 的 vendored certifi** | `site-packages/pip/_vendor/certifi/cacert.pem` | **公告点名的受影响组件**；且多数 venv 根本没装独立 certifi |
| 3 | uv（**全局**） | PATH 上的 `uv`（全机 1 个，非 venv 内） | `uv < 0.13.4` 的 vendored webpki-roots 同含 G3（修复：uv 0.13.4 / webpki-roots 1.0.10）；由 `UV_BASELINE` 单独报告一次 |

**踩坑记录（2026-10-26 修正）**：旧版 `verify` 只做 `python -c "import certifi; ..."`。
多数 venv 没装独立 certifi → `import certifi` 直接失败 → **该面被静默跳过**；
而 pip 的 vendored 那一份（真正要命的面）**从未被检查过**。
⇒ 判据必须是「在磁盘上直接扫 `cacert.pem`」，不能依赖 `import` 成功与否。

## ⚠️ `~ip` 孤儿残留（Windows 特有）

Windows 上 pip 自升级时**无法删除正在运行的自身包目录**，于是改名成 `~ip`（dist-info 改 `~ip-<ver>.dist-info`），
升级成功后自行清理；**进程被杀或清理失败就留下孤儿**。

实测（/repos 124 个 venv）：**201 个孤儿项**分布在 99 个 venv；孤儿里 `~ip/_vendor/certifi` 停在
**2026.06.17**（在受影响区间内，含 3 份 G3 根），而同一 venv 的**活跃** `pip/_vendor/certifi` 已是 2026.10.19。

风险定性（实测）：活跃信任链**干净**（`import pip` → `pip/`；`importlib.metadata.version("pip")` 返回活跃版本），
但磁盘上确实留着一份**过期易受攻击的 CA 捆绑包**，且会让任何「扫 cacert.pem」的审计工具反复误报。

⇒ 处置 = **改名隔离出 site-packages，不删除**：移到 `<venv>/.orphan/<name>.<时间戳>/`。
⇒ 边界情形：若活跃 `pip` 目录缺失而 `~ip` 存在（孤儿顶掉了唯一 pip，venv 已损坏），
  则**还原** `~ip` → `pip`（修 venv）而不是隔离。

## 离线漏洞基线（dep-vuln-baseline）

`ADVISORIES` 是脚本内置的**离线**已知坏版本表（`pkg` / `ranges` / `fixed` / `note`），
初始播种 GHSA-6q48（certifi）等；**不联网**，因此 CI/离线机可跑。
新增事件 = 按官方公告核对后往表里加一行（`lo <= v < hi`）。
该项**只报告不自动升级**：自动改任意依赖版本风险高，交由使用者决策。

## venv 完整性（venv-integrity）

只报告项：缺 `Scripts/python.exe`、`pyvenv.cfg` 缺 `version`、同名包出现多份不同版本 dist-info。
用于发现「半损坏/升级中断」的 venv，不自动改动。

## 执行（统一调度，不要手敲脚本路径）

```bash
allin tools venv-audit --list                  # 列出 7 项检查
allin tools venv-audit scan   /repos           # 只读扫描
allin tools venv-audit apply  /repos 8         # 加固（幂等）
allin tools venv-audit verify /repos 8         # 功能级审计（实跑解释器）
allin tools venv-audit scan   /repos --check ca-emsign-g3   # 只跑单项
```

**home 映射**（`broken-home-repair`）：按 `pyvenv.cfg` 的 `version` 取基准解释器根，
由各机环境变量注入，**不写死路径**：

- 3.14.x → `PYTHON314_ROOT`
- 3.13.x → `PYTHON313_ROOT`
- 3.12.x → `PYTHON312_ROOT`

未设置对应变量时该版本跳过 home 修复（不影响 `scan` / 其余检查）。

## 全局 uv 基线（2026-11-08 修正计数口径）

`uv` 是 PATH 上的独立二进制，**全机只有 1 个**，不属于任何 venv；`apply` 不处理它。
旧实现把 `standalone_uv_version()` 的结果注入每个 venv 的上下文，导致同一条全局 issue
被记 N 次（`verify issue=N/N` 假象）。现行口径：

- `uv_baseline_status()` 是唯一判据；`scan` / `apply` / `verify` 各打印**一次**
  `UV_BASELINE status=<ok|ISSUE|not-found|unparseable> ...`，汇总行追加 `uv_status=`。
- 逐 venv 的 `issue` / `vulnerable` **不再包含 uv**；`--check` 只过滤 venv 级检查，
  不影响全局层报告。
- `uv_status=ISSUE` 时 `verify` 返回 2（即使 `issue=0`），避免「报告了却 exit 0」被当绿灯；
  全局 uv 须单独升级：standalone 用 `uv self update`，pip 安装的用
  `pip install --upgrade uv`（**先备份旧二进制**）。
- 检查 id `pip-certifi-uv-baseline` 含 `uv` 仅为兼容既有 `--check` 调用保留。

## 完成判据（硬性）

**真正完成 = `verify` 作为独立前台命令完整跑完，且输出里 `VERIFY_SUMMARY ... issue=0`
与 `uv_status=ok` 同时实际可见（或 `UV_BASELINE status=ok` 可见）。**

- 本环境后台 Bash 任务不跨轮存活（轮次结束即杀）。
- 完成通知、后台退出码、"Successfully installed" 字样、被截断的输出**都不是**完成证据。
- 只有 `issue=0` 但 `uv_status=ISSUE` ⇒ 全局 uv 未达标，本轮**未完成**（此时 exit 2）。
- 未看到完整汇总行即本轮未完成，下轮从头重跑（脚本幂等无副作用）。
- 禁止据中间输出宣称完成。

## 已知环境异常（2026-10-21 发现，源头未定位）

`/repos` 的 venv 文件会被**外部进程间歇改动**（pip 元数据或包体无故消失、旧版本回退）。
若同一轮内修复后立刻又坏，按「外部进程干扰」如实记录，**不要无限重试**。

## 边界

只动扫描根下的 venv；**不删除任何文件**（损坏的 pip / 孤儿仅改名备份或隔离）；
不碰 Node；不碰扫描根之外的 Python 环境。

## 记账

- 2026-10-26：工具从外部脚本吸收进 `tools/security/venv_ca_audit.py`；补齐「pip vendored certifi」「uv」「~ip 孤儿」三个旧版缺口。
- 2026-10-26 首轮实跑：124 venv，101 个含孤儿，加固后 `VERIFY_SUMMARY total=124 clean=124 issue=0`；
  另修复 2 个 venv 失效 home、1 个 pip 26.2.1→26.2.2。
- 2026-11-07：**重写为通用检查框架** `venv_security.py`（7 项检查：新增离线漏洞基线与 venv 完整性），
  技能/路由更名为 `venv-security-audit`；撤掉外部每周自动化，改为按需调用；文档去符盘。
