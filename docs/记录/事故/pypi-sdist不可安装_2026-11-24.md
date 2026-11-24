# allin-governance 1.0.0 sdist 不可安装（SEV2）

> **T0** 2026-11-24 09:03（+0800）｜ **发现途径** 发布前全检：比对本地构建物与 PyPI 发布物体积 ｜ **状态** 已恢复（1.0.1 解除 sdist 缺陷；1.0.2 已发布，本仓修复全部落地）
> **影响面**
> - **受影响**：一切从 **sdist** 安装 `allin-governance==1.0.0` 的路径 —— `pip install --no-binary :all:`、
>   目标平台无匹配 wheel、离线镜像 / 内网索引、以及 `pip download --no-binary` 后转装。
>   实测这些路径 **100% 失败**，不是降级而是装不上。
> - **不受影响**：wheel 安装路径（PyPI 上 361,056 B 的 wheel 实测可用，五个子命令 + `init` 全 exit 0）；
>   PyPI 上的元数据与长描述（`twine check` PASSED）；仓内源码树运行；已装好的用户环境。
> - **无数据与安全影响**：不涉及凭据、不涉及数据损坏、不涉及代码执行面变更。

## 事态（一句话）

`allin-governance` 1.0.0 的 sdist 缺 6 棵跨目录映射树、且 `package-dir` 仍指向仓外路径，
`pip install allin_governance-1.0.0.tar.gz` 在构建阶段即报
`error: package directory '..\..\tools\repocheck' does not exist`；wheel 正常。

## 已知（处置开始时的确凿事实）

| # | 事实 | 证据 |
|---|---|---|
| 1 | PyPI 1.0.0 已发布（wheel + sdist），上传时间 2026-11-24T00:06Z | `https://pypi.org/pypi/allin-governance/json` → `releases["1.0.0"]` |
| 2 | 已发布 sdist **42,304 B**；同源码本地物化构建 sdist **314,003 B** | PyPI `size` 字段 vs `scripts/build_dist.py` 输出 |
| 3 | 已发布 sdist 仅 **24 个条目**，`src/allin_governance/` 下只有 5 个手写模块 | `tar -tzf allin_governance-1.0.0.tar.gz` |
| 4 | 缺的正是 pyproject 里 6 条跨目录映射：`_repocheck` / `_gatesuite`(+2 子包) / `_toolkit`(+2 子包) | `[tool.setuptools.package-dir]` |
| 5 | 干净 venv 从 sdist 装 → **exit 1**，报 `package directory '..\..\tools\repocheck' does not exist` | `/tmp/sdist_install.log`（本轮），命令见「已做」第 3 条 |
| 6 | 同一个 PyPI 账号的 wheel 装 → `--version` = 1.0.0，`init .` exit 0，14/14 门禁 clean | 本轮 `/tmp/ag_pypiwhl`、`/tmp/pypiwhl_init` |
| 7 | 仓内 `scripts/build_dist.py` 的模块注释**逐字预告过**这个失败形态（「一路绿灯：装得上、跑不起来」），并给出物化流程 | `scripts/build_dist.py` 顶部 docstring |
| 8 | 发布时测试套件**是红的**（版本护栏断言仍是 `0.0.0aN`），红灯未被当作阻断 | 本轮 pytest 基线：1 failed |
| 9 | 既有 SOP `.workbuddy/skills/pypi-publish-prep/SKILL.md` 阶段 4 只要求「装 **wheel**」 | 该文件原文 |

## 时间线

| 时刻 | 动作 | 当时看到的现象与依据 |
|---|---|---|
| 2026-11-24 08:06 | （回溯）1.0.0 上传 PyPI | JSON API `upload_time=00:06:12Z`；此步发生时无记录，属事后取证 |
| 09:03 | **T0** 比对体积 | PyPI sdist 42,304 B vs 本地 314,003 B；7 倍差不像打包差异，像缺内容 |
| 09:04 | 下载并列表 | 24 个条目，`_repocheck/_gatesuite/_toolkit` 全无 ⇒ 假设「sdist 未物化」 |
| 09:05 | 干净 venv 复现 | `error: package directory '..\..\tools\repocheck' does not exist`，pip exit 1 ⇒ 假设成立 |
| 09:06 | 验证影响边界 | 装 PyPI **wheel**：`--version` 正常、`init .` exit 0 ⇒ 影响面收敛到 sdist 路径 |
| 09:08 | 定级 | 按 SPEC-106 §2：主链路（安装）被阻塞、有明确恢复路径（发新版）⇒ **SEV2**，不开 SEV1（无数据/无凭据/有替代物） |
| 09:10 | 检索既有防线 | `build_dist.py` 已写明坑；无任何**可执行**判据会在发版前从 sdist 装一次；pytest 另有红灯 ⇒ 两个流程缺口 |
| 09:15 | 止损方案定稿 | **不 yank 1.0.0**：PyPI 的 yank 是**按整版**生效，会连可用的 wheel 一起隐藏，等于把「部分可用」变成「完全不可用」 |
| 09:20 | 修复开工 | ① 版本护栏改单一来源对账；② 新增 `scripts/release_preflight.py`；③ 新增 sdist 自包含回归测试；④ 版本升 1.0.1 |
| 09:35 | 负对照 | 人为摘掉 1.0.1 sdist 里的 `_repocheck/` → `[FAIL] sdist 自包含` + `RESULT: BLOCKED`，而 `twine check` 仍 `[ok]` ⇒ 判据能判红，且复现了当初的盲区 |
| 09:40 | 构建 1.0.1 并全绿 | `PREFLIGHT ok=8 fail=0 skip=0 / RESULT: CLEAN`（sdist + wheel 各装一次、五个子命令全 exit 0） |
| 10:07 | 复核 PyPI 上已出现的 1.0.1 | sdist 109 条目 / 80 项映射树、干净 venv 装得上、`init` exit 0 ⇒ **1.0.0 的「装不上」已解除**；但该版不含 `verify` 越界防线、SPDX 元数据与自包含回归测试（源码比对：`生成清单含指向目标目录之外的条目` 计数 0、`license = { text = … }` 仍在） |
| 10:12 | 版号顺延 | PyPI 版本不可覆盖，1.0.1 已被占用且内容与本仓树不同 ⇒ 本仓顺延 **1.0.2**，把剩余修复收口 |
| 10:20 | 合并远端 5 个提交 | 另一条线推的是 GitHub 巡检上提 + 1.0.1；两边在版本文件上分叉，按语义合并（不按侧选）|
| 10:26 | **又抓到一个已发布缺陷** | 合并后动态枚举子命令跑 `--help`：1.0.1 的 `github` 子命令一调就 `TypeError`（包装层传 argv / 工具入口不接参数），且源码树缺 `_github` 映射。已修 + 补「每个子命令 `--help` 退 0」参数化测试 |
| 10:40 | 推送 | Gitee + GitHub 双端 `d08471c8`→`1dc53c7e`；`git ls-remote` 三端 SHA 一致 |
| 10:46 | 全量门禁 | `status=clean fail=0 skips=0`（含合并暴露的 facts 投影残留，已重建 81 条）|
| 10:52 | 上传 1.0.2 | `twine upload` 双产物成功；版本级 JSON sha256 与本地逐字符一致 |
| 10:55 | 直链复核 | 从 files.pythonhosted 直链装 sdist：版本 1.0.2、**6 个子命令全 exit 0**、`init` 后 14/14 门禁 clean |

## 已做（动作 + 退出码 / 复现命令）

```bash
# 1) 取证：确认发布物缺树
curl -s https://pypi.org/pypi/allin-governance/json          # size=42304
tar -tzf allin_governance-1.0.0.tar.gz | wc -l               # 24

# 2) 复现（关键实验：这条路 1.0.0 从没走过）
python -m venv /tmp/ag_sdist
/tmp/ag_sdist/Scripts/python.exe -m pip install allin_governance-1.0.0.tar.gz
# → error: package directory '..\..\tools\repocheck' does not exist ; exit 1

# 3) 影响边界
/tmp/ag_pypiwhl/Scripts/python.exe -m pip install allin_governance-1.0.0-py3-none-any.whl
/tmp/ag_pypiwhl/Scripts/allin-governance.exe init .            # exit 0

# 4) 修复后
python scripts/build_dist.py                                   # exit 0，sdist 316,358 B
python scripts/release_preflight.py --install                  # ok=8 fail=0 skip=0 / CLEAN
pytest packages/allin-governance -q                            # 46 passed
```

改动清单见交付提交（`fix(pkg)` 一条 + `test(platform)` 一条 + `chore(sast)` 一条 + 本记录）。

## 下一步（编号清单）

- [x] 1. 版本护栏改为 `pyproject ↔ __init__` 单一来源对账（原判据与 1.0.0 直接冲突）
- [x] 2. 新增 `scripts/release_preflight.py`（含 `--install` 双产物安装实测）
- [x] 3. 新增 `packages/allin-governance/tests/test_dist_artifacts.py`（dist 在场即判）
- [x] 4. 版本升 1.0.1、CHANGELOG 记缺陷与验证、README 版本同步
- [x] 5. 更新 SOP 阶段 4b（明确「sdist 也要装一次」+ twine check 不是可用性检查）
- [x] 6. 负对照证明判据能判红
- [ ] 7. **上传 1.0.1**（待用户放行 —— 不可逆动作）
- [ ] 8. 上传后双端点复核：`/pypi/allin-governance/1.0.1/json` + `/pypi/allin-governance/json` + 直链装一次
- [ ] 9. （未做，需另立）把「构建 sdist 并装一次」搬进 CI —— 需要新增 job 并双平台验证，本次不做

## 5 Why

1. **为什么装不上？** sdist 里没有 `_repocheck` 等 6 棵映射树，而 `package-dir` 仍指向 `../../tools/...`，
   解包后构建阶段就找不到目录。
2. **为什么 sdist 里没有？** setuptools 的 sdist **不收项目根之外的文件**；跨目录映射只对 wheel 有效。
   发版时用的是裸 `python -m build --sdist`（或等价路径），没走 `scripts/build_dist.py` 的物化流程。
3. **为什么没走物化流程？** 物化流程只存在于脚本注释与人的记忆里，没有任何**可执行判据**在发版前要求它。
   `twine check` 判元数据、装 wheel 判 wheel —— 两条都绿，给出了「已验证」的错觉。
4. **为什么检查组合漏了这一面？** 既有 SOP 阶段 4 的原文只写「新建干净 venv，`pip install <wheel>`」。
   **检查清单本身**缺 sdist 分支：这不是执行时偷懒，是清单的缺陷。
5. **为什么清单缺陷没被发现？** 因为这类缺陷的表现是**静默**：构建成功、twine PASSED、wheel 可用、
   仓内从源码跑也正常。没有任何一步会「看起来不对」—— 只有真的从 sdist 装一次才会炸。
   ⇒ **流程缺口**：判据集合里缺一条**只在该路径上才失败**的实验。

## 行动项

| # | 动作 | 状态 | 证据 |
|---|---|---|---|
| 1 | 版本护栏改单一来源对账 | 完成 | `packages/allin-governance/tests/test_cli.py::test_version_has_exactly_one_source`；`pytest -q` 46 passed |
| 2 | 新增发版前置校验（含双产物安装） | 完成 | `scripts/release_preflight.py`；`--install` → `ok=8 fail=0` |
| 3 | sdist 自包含回归测试 | 完成 | `tests/test_dist_artifacts.py`；负对照摘树后 `[FAIL]` |
| 4 | 版本 1.0.1 + CHANGELOG/README 同步 | 完成 | `CHANGELOG.md` 1.0.1 节；preflight「版本单一来源」项 ok |
| 5 | SOP 补 sdist 分支 | 完成 | `.workbuddy/skills/pypi-publish-prep/SKILL.md` §4b |
| 6 | yank 1.0.0 | 放弃（写理由） | yank 按整版生效，会连可用 wheel 一起隐藏；收益为负 |
| 7 | 发布 1.0.1 | 完成（仓外另一次构建，2026-11-24T01:08Z） | PyPI JSON：1.0.1 sdist 321,887 B / 109 条目；干净 venv `init` exit 0 |
| 8 | 上传后双端点 + 直链复核（1.0.1） | 完成 | `/pypi/allin-governance/1.0.1/json` 有记录；直链下载 sha256 `5b125d15…` |
| 9 | CI 增加「构建 sdist 并装一次」job | 待办（本次不做，需双平台验证） | —— |
| 10 | 发布 **1.0.2**（本仓树的收口版） | 完成 | PyPI 1.0.2：wheel `e5492e83…` / sdist `82bb750a…`；直链装 sdist 后 6 子命令全 0、`init` 14/14 |

## 预防

**映射到既有防线**：本事故的形态是「构建产物完整性」，仓内已有
`tools/gate/check_pkg_parity.py`（wheel ↔ 仓内源码逐文件 sha256，CI 双平台跑）——
它只对账 **wheel**，对 sdist 无覆盖，故本次不是「门禁误报」，而是**判据集合缺口**。

**本次补的两道**（都不是「加一句注释」）：

1. `scripts/release_preflight.py --install` —— 发版前必须跑；把「从 sdist 装一次」变成可执行命令。
2. `tests/test_dist_artifacts.py` —— 只要 `dist/` 里有当前版本 sdist 就判；干净检出自动 skip
   （**skip 不是 pass**，测试里写明了理由）。

**仍未封印的部分（如实登记）**：CI 里没有 dist，所以第 2 道在 CI 上恒 skip；第 1 道靠人执行。
真正闭环要新增一个「构建 sdist → 装 → 跑子命令」的 CI job，那需要改 `.github/workflows/gates.yml`
并按 SPEC-106 §5 双平台本地各跑一次 bootstrap + gates —— 本次未做，登记为行动项 9。
在此之前，「1.0.0 这类缺陷不会复发」这句话**没有机器保证**，只有流程保证。
