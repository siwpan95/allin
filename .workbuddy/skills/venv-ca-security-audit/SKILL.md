---
name: venv-ca-security-audit
description: >
  G:\repos 下全部 Python venv 的 eMudhra/emSign CA 证书事件（GHSA-6q48-6c7w-9gw2）安全巡检与加固。
  覆盖 certifi / pip vendored certifi / uv 三个必查面，精确判据为 emSign ECC Root CA - G3，
  并处理 Windows 上 pip 自升级遗留的 ~ip 孤儿残留（含过期易受攻击的 CA 捆绑包）。
  触发词：CA 证书、GHSA-6q48、certifi、emSign、eMudhra、venv 安全巡检、根证书加固、MITM 风险、
  certifi 版本、pip vendored certifi、~ip 孤儿、venv 加固。
---

# venv CA 证书安全巡检与加固 SOP

> 工具已并入 allin：`G:\allin\tools\security\venv_ca_audit.py`（纯标准库）
> 统一调度入口：`allin tools venv-audit <scan|apply|verify>`（经 cordis 内核）
> 本技能讲的是**判定口径与踩坑**，脚本负责执行。

## 阶段 0：先搞清事件本身（不要凭印象判风险）

2026-10-20 披露的 **CRITICAL** 事件（CVSS 9.1，CWE-295，**无 CVE 号**）：

- certifi ``>= 2019.03.09, < 2026.10.19`` 的 CA 捆绑包含 **`emSign ECC Root CA - G3`** 根证书。
- eMudhra 签发、链到该根的 **8 张中间 CA 证书私钥已泄露**并被吊销。
- 持泄露私钥者可签发「对任意主机名都像真的」证书；再叠加 on-path 即可 **MITM**。
- 受影响组件：`requests` / `urllib3` / **`pip`** 等一切依赖 certifi 信任链者。
- 修复线：certifi `2026.10.18` 移除**全部** emSign 根；`2026.10.19` **只恢复未受影响的** emSign 根。
  ⇒ 安全版本 = `certifi >= 2026.10.19`。

## ⚠️ 阶段 1：判据必须精确到 G3（最大的误报陷阱）

**certifi 2026.10.19 的捆绑包里仍然有 9~15 处 "emSign"** —— 那是公告**有意恢复**的未受影响根。

⇒ 「包里有没有 emSign」是**错的判据**，会对着 124 个 venv 全量误报。
⇒ **唯一正确判据**：精确匹配字符串 **`emSign ECC Root CA - G3`**，且**只在活跃包目录内**计数。

已实测：pip 26.2.2 的 vendored certifi = 2026.10.19 ⇒ `emSign` 命中 15、G3 命中 **0** ⇒ 合法。

## 阶段 2：三个必查面（缺一面就等于没查）

| # | 面 | 位置 | 为什么不能省 |
|---|---|---|---|
| 1 | 独立 certifi 包 | `site-packages/certifi/cacert.pem` | 用户直接 `import certifi` 的信任源 |
| 2 | **pip 的 vendored certifi** | `site-packages/pip/_vendor/certifi/cacert.pem` | **公告点名的受影响组件**；且多数 venv 根本没装独立 certifi |
| 3 | uv | PATH 上的 `uv` | `uv < 0.13.4` 的 vendored webpki-roots 同含 G3（修复：uv 0.13.4 / webpki-roots 1.0.10） |

**踩坑记录（2026-10-26 修正）**：旧版脚本 `verify` 只做 `python -c "import certifi; ..."`。
多数 venv 没装独立 certifi → `import certifi` 直接失败 → **该面被静默跳过**；
而 pip 的 vendored 那一份（真正要命的面）**从未被检查过**。
结论当时是「clean」，但**依据是 pip 版本下限，不是声明的检查项** —— 侥幸对，不是查对了。

⇒ 判据必须是「在磁盘上直接扫 cacert.pem」，不能依赖 `import` 成功与否。

## ⚠️ 阶段 3：`~ip` 孤儿残留（Windows 特有，2026-10-26 新发现）

Windows 上 pip 自升级时**无法删除正在运行的自身包目录**，于是改名成 `~ip`（dist-info 改 `~ip-<ver>.dist-info`），
升级成功后自行清理；**进程被杀或清理失败就留下孤儿**。

实测（G:\repos 124 个 venv）：

- **201 个孤儿项**，分布在 99 个 venv（`~ip` 99 个、`~ip-26.2.1.dist-info` 94 个，另有零星旧版本号）。
- 孤儿里 `~ip/_vendor/certifi` 版本 **2026.06.17** ⇒ **在受影响区间内**，含 **3 份 G3 根**。
- 同一 venv 的**活跃** `pip/_vendor/certifi` 是 2026.10.19 ⇒ G3 = 0。

**风险定性（实测，别凭猜）**：

- ✅ 活跃信任链**干净**：`import pip` → `pip/`（不是 `~ip/`）；`pip._vendor.certifi` = 2026.10.19。
- ✅ `importlib.metadata.version('pip')` 在全部 100 个受影响 venv 里都返回 **26.2.2**（活跃版本）
  ⇒ `~ip-*.dist-info` **不会遮蔽**元数据（`~` 前缀使其规范化后不匹配 `pip`）。
- ⚠️ 但磁盘上确实留着一份**过期易受攻击的 CA 捆绑包**，且会让任何「扫 cacert.pem」的审计工具反复误报。

⇒ 处置 = **改名隔离出 site-packages，不删除**：
移到 `<venv>/.orphan/<name>.<时间戳>/`（脱离 import 路径与 glob 视野，**一个字节都没删**）。
⇒ 边界情形：若活跃 `pip` 目录缺失而 `~ip` 存在（孤儿顶掉了唯一 pip，venv 已损坏），
  则**还原** `~ip` → `pip`（修 venv）而不是隔离。

## 阶段 4：执行（统一调度，不要手敲脚本路径）

```bash
# 只读扫描
allin tools venv-audit scan G:/repos
# 加固（幂等）
allin tools venv-audit apply G:/repos 8
# 功能级审计（实跑解释器）
allin tools venv-audit verify G:/repos 8
```

`apply` 的三类自动处置：

1. `pyvenv.cfg` 的 `home` 指向失效基准解释器 → 按版本映射改写
   （3.14→`G:\Python314`；3.13→`C:\Users\psw\.workbuddy\binaries\python\versions\3.13.12`；
   3.12→`C:\Users\psw\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none`）
2. pip 残缺 → `python -m ensurepip` 引导；若 ensurepip 误判 "Requirement already satisfied" 空转，
   先把损坏的 `pip` 目录与 `pip-*.dist-info` **改名加 .bak 备份**再引导（**不删除**）
3. pip/certifi 低于基线 → `pip install --upgrade`；升级后活跃捆绑包仍有 G3 → 强制重装 pip
4. `~` 孤儿项 → 改名隔离进 `<venv>/.orphan/`

## 完成判据（硬性）

**真正完成 = `verify` 作为独立前台命令完整跑完，且输出里 `VERIFY_SUMMARY ... issue=0` 实际可见。**

- 本环境后台 Bash 任务不跨轮存活（轮次结束即杀）。
- 完成通知、后台退出码、"Successfully installed" 字样、被截断的输出**都不是**完成证据。
- 未看到 `issue=0` 即本轮未完成，下轮从头重跑（脚本幂等无副作用）。
- 禁止据中间输出宣称完成。

## 已知环境异常（2026-10-21 发现，源头未定位）

`G:\repos` 的 venv 文件会被**外部进程间歇改动**（pip 元数据或包体无故消失、旧版本回退）。
若同一轮内修复后立刻又坏，按「外部进程干扰」如实记录，**不要无限重试**。

## 边界

只动 `G:\repos` 下的 venv；**不删除任何文件**（损坏的 pip / 孤儿仅改名备份或隔离）；
不碰 Node；不碰 `G:\repos` 之外的 Python 环境。

## 记账

- 2026-10-26：工具从 `C:\Users\psw\WorkBuddy\2026-10-21-08-00-53\venv_security.py` 吸收进
  `G:\allin\tools\security\venv_ca_audit.py`；补齐「pip vendored certifi」「uv」「~ip 孤儿」三个旧版缺口。
- 2026-10-26 首轮实跑：124 venv，101 个含孤儿，加固后 `VERIFY_SUMMARY total=124 clean=124 issue=0`；
  另修复 2 个 venv 失效 home（`F:\Python314` → `G:\Python314`）、1 个 pip 26.2.1→26.2.2。
