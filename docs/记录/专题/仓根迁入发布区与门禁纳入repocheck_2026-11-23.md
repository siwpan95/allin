> **本文是 2026-11-23 的一次性记录，不作为约束。**
> **现行规则以** `docs/规范/SPEC-*` 与 `tools/` 代码为准。

# 仓根迁入发布区 + 门禁纳入 repocheck（2026-11-23）

- **时点**：2026-11-23 21:48 ~ 23:10
- **本机**：`@SIWPAN`（hostname `siwpan`）
- **触发**：全哥指令「将 `/allin` 转入 `/repos`，将门禁纳入 repocheck，其余同步进行调整；提交推送放行。」

---

## 零、结论先行

三件事一起落地：**本仓搬进了发布区**、**门禁判据纳入了 repocheck**、**五处只认同级布局的发布区推导全部修好**。

搬迁不是「挪个目录」——它一次暴露了三类机制性缺陷，每一类都属于「门禁报绿但事实是错的」：

| # | 缺陷 | 症状 | 性质 |
|---|---|---|---|
| 1 | `g17` 完备性检查**长期 `SKIPPED`** | 内含布局下 `<本仓>/../repos` → 不存在的 `<repos>/repos`，门禁记 SKIP 却 exit 0 | 修好后**当场判出 2 个未登记仓**（`allin`、`worldwright`） |
| 2 | `repo_hygiene` / `publish_area_gate` 静默降级 | 同上推导，报 `skip(no-publish-area)`，143 仓一个没扫 | 发布区卫生与治理门禁**空转了整段时间** |
| 3 | JS 侧三处 REPOS_ROOT | `@allin/core`、console shell、MCP 白名单指向 `<repos>/repos` | MCP 会对所有 `repos/` 路径**一律拒绝** |

⇒ 纪律：**「跳过」与「通过」必须在汇总里分开计数，且不能被 `--fail-on` 当成绿。** 本轮三道门禁都做到了（`SKIPPED (not a pass)`），所以修好推导后它们立刻开始报真问题 —— 这正是判据该有的行为。

---

## 一、搬迁：三个物理陷阱

物理移动 `<工作区>/allin` → `<工作区>/repos/allin`（同盘 rename）连续失败两次，逐层二分后定位：

### 1.1 junction 让目录不可 rename

`mv` 报 `Permission denied`。逐项 rename 顶层子目录二分，锁定 `docs/` 与 `node_modules` 下的**自引用 junction**：

| 位置 | 数量 | 指向 |
|---|---|---|
| `docs/{facts,records,spec,历史}` | 4 | 仓内 `docs/事实源|记录|规范|md` |
| `console/node_modules/@allin/*` | 3 | 仓内 `console/packages/*`、`platform/packages/core` |
| `platform/node_modules/@allin/*` | 3 | 仓内 `platform/{apps,packages}/*` |

处置：用 `[System.IO.Directory]::Delete(path, false)` 逐个摘链接（**只删链接、不动真身**，比 `Remove-Item -Recurse` 安全），搬迁后按新根重建，`Test-Path <link>/*` 逐个验证可遍历 —— 10/10 通。

### 1.2 `.venv` 的 launcher 内嵌旧绝对路径

`.venv/Scripts/*.exe` 里嵌着 `<旧仓根>\.venv\Scripts\python.exe`，移动后全部失效。`pyvenv.cfg` 的 `home` 指向 uv 托管的 CPython（路径未变），所以 `python.exe` 本体还能跑，但 **console_scripts 全废**。

处置：`uv venv --clear` 重建（CPython 3.12.13）+ `uv pip install -r requirements-dev.txt`，实测 `import yaml/watchdog/pytest/bandit` 全通，`sys.executable` 指向新路径。

### 1.3 一次未预期的阻塞与处置

摘完 junction 后 `docs/` 仍不可 rename（`fsutil` 确认非 reparse、ACL 正常、所有者正确）。判断为瞬时句柄（索引/枚举）。处置：其余顶层项逐个 rename 到新根，`docs` 用 `robocopy /E /COPYALL` 复制 —— **385 文件 / 5,295,997 字节，源与目标逐数一致**；随后旧壳可正常删除。

⚠ **记账**：本次未用工具确认句柄持有者（无 `handle.exe`）。若同类现象复现且非瞬时，应装 Sysinternals `handle64` 定位，而不是继续用 robocopy 绕过。

---

## 二、发布区推导：五处硬编码

全部只认「本仓与 `repos/` 同级」这一种布局。统一判据：

> **本仓父目录名是 `repos` ⇒ 发布区根 = 该父目录；否则维持 `<本仓>/../repos`。**

| 落点 | 改动 |
|---|---|
| `tools/gate/governance/gates/g17_registry.py` | `repos_root()` 加父目录名判据 |
| `tools/license_matrix.py` | 同上（与 g17 同源，单独实现会各自漂） |
| `tools/repo_hygiene.py` | `_default_repos_root()` 加判据（原兜底返回仓根本身 ⇒ `--all` 报 0 个仓） |
| `scripts/run_all_gates.sh` | 抽出 `detect_repos_root()` **单一实现**，`_run_repo_hygiene` 与 `_run_publish_area_gate` 共用 |
| `platform/packages/core/src/registry.js` / `console/apps/shell/config.js` / `platform/apps/mcp/src/index.js` | `DEFAULT_REPOS_ROOT` 与 `REPOS_SIBLING` 加同名判据 |

**为什么取「父目录名」而不是「`../repos` 是否存在」**：后者会在恰好有个无关 `repos` 目录的机器上悄悄切换目标 —— 判据换了地方却不吭声，等于没有证据（调试铁律 65 同型）。

---

## 三、门禁纳入 repocheck（规则 31–50）

### 3.1 形态：委托 CLI 契约，判据只有一份

新增 `tools/repocheck/rules_gate.py`：20 条规则逐条对应 `g00-meta` … `g20-facts`。
**不重写判据、不 import 门禁内部函数**（私有契约会随重构演化），只复用对外稳定的
CLI 契约 `--root` + 退出码 0/1/2/3。因此 repocheck 与 `run.ts` 跑的是同一份判据文件。

参数等价性也照 `registry.json` 复现：`profileProbe: true` 的门（实测 `g14-preset`）
补传 `--no-profile`。**少了这一步，repocheck 会报一条 `run.ts` 同批次里并不存在的红**
—— 两个入口结论不一致，比没有第二个入口更糟。

### 3.2 按项目裁剪，不是按项目跳过

没有治理套件（`tools/gate/governance/gates/` + `runtime/govlib.py`）的仓**不注册**这 20 条。
若注册后逐条 SKIP，20 条跳过项会把每仓分数上限压到 9.0，发布区健康分 9.5 会整体塌到 9.0 ——
那是把「没这套东西」错记成「有东西没测」。

### 3.3 默认关闭

每道门一次子进程，实测 **20 道约 90 秒/仓**。日常体检口径是 0.26 s/仓，不能被拖垮 ⇒
`--gates` 显式启用。`--dump-profile` 新增 `gate_rules` 键（文本 + JSON），让「这次到底能查什么」可自省。

### 3.4 首跑就抓到一个真缺陷（我自己的）

首轮 20 条里 `g09-python-hygiene` 判红，而 `run.ts` 同批次是 clean。根因不是门禁，是**我在
`rules_core.py` 注释里写了转义路径字面量**（`D:\allin\...`），被「转义路径字面量」判据逮住。
改注释文字后转绿 —— 判据零放宽。

---

## 四、门禁修好后暴露的两个存量

| 仓 | 事实 | 处置 |
|---|---|---|
| `repos/worldwright` | `206ec7b`（2026-11-23 首发 `0.1.0`）、`gitee.com/siwpan/worldwright`、52 个跟踪文件、有 README/LICENSE/pyproject/tests | **正式登记** registry（category `engine`，与 `3dworld-globe` 同口径） |
| `repos/allin` | 本仓自己 | 登记 registry（category `automation`，`path: repos/allin`） |

`registry` 148 → **150** 条；`facts.json.projects` 由 `build_projects.py --write` 重生成（+18 行）。

**另外两条发布区阻断**（同样因门禁此前从不覆盖发布区而从未被发现）：

| 仓 | 告警 | 处置 |
|---|---|---|
| `3dworld` | 清单 `0.9.6` / 源码 `__version__ = '0.7.6'` —— 声明 **< 已发布 tag `v0.9.6`** | 改源码为 `0.9.6`（「声明 > tag」才是合法的未发布态，声明 < tag 是真缺陷） |
| `allin` | README 缺可机检的许可章节 | 补 `## 许可`，三处声明（LICENSE / README / 清单字段）齐备 |

规则 7（旧路径残留）同时扩口：历史归档区 `docs/md/` 与他机事实源 `docs/facts/机器/`、
`docs/事实源/机器/` 不再判红 —— 这两类不是「照着做会失败」的可执行路径，判红只会逼人篡改历史
（与 g19/g20「每台机只自验自己那份」同口径）。

---

## 五、验收证据

```
npm run check:governance            → 20/20 clean
scripts/run_all_gates.sh            → ALLIN_GATE_SUMMARY status=clean fail=0
publish_area_gate.py                → verdict=PASS blocking=0 pending=0（142 仓）
repo_hygiene.py --all               → 通过（142 仓，存量 0）
repocheck 门禁规则族（--gates）      → gate rules = 20 | PASS = 20
pytest tools/repocheck/test_scanner → 83 通过
check_arch_assets.py                → 架构资产对账全绿（143 仓三处一致）
g17_registry                        → blocking 0（registered 141 / 清单 150）
g20_facts                           → blocking 0（时点 2026-11-23，0 天前）
g01_paths                           → blocking 0（扫 1023 文件）
platform/scripts/check_repos.mjs    → 通过（150 条清单 × 远端 143 仓锚点一致）
```

---

## 六、未做 / 待办（如实记账）

1. **未把 `run_all_gates.sh` 切到「只走 repocheck」**：规则族已可用且与 `run.ts` 实测同结论，
   但权威入口仍是 `npm run check:governance`。彻底单一入口需要同步 CI（`.github/workflows/gates.yml`）
   与 `RULES.md` 映射，属独立重构，不在本轮擅动。
2. **同盘移动的句柄持有者未定位**（见 §1.3），下次复现应装 `handle64` 查证。
3. **另两台机未复核**：`DESKTOP-8RSV60V` / `DESKTOP-KQABATS` 的发布区仍是旧布局，
   本次推导改动向后兼容（父目录名不是 `repos` 时行为与旧版逐字节相同），但**未在真机验证**。
4. `repos/out` 是非 git 目录，来源未查（不属本轮范围，未动）。
