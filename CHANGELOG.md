# 变更记录（CHANGELOG）

> 面向**消费本仓产物的人**（尤其 PyPI 上的 `allin-governance`），不是面向仓内开发。
> 仓内的决策与审计留在 `docs/记录/`，这里只记「用户会感知到什么变了」。

## `allin-governance` 0.0.0a3 —— 2026-11-07

一次真实缺陷修复 + 一批门禁判据加固。`init` 的出厂形态不变（仍是 14 道纯标准库
门禁），变的是**判据本身**——包的门禁源码与 allin 仓是同一份（映射，不是复制），
仓内一个月的治理加固随本版整体进入发布物。

### 修复：a2 的 wheel 缺 4 份运行时事实源（本版最大的事）

a2 的 wheel 里**没有** `exceptions.yml`、`registry-known-gaps.txt`、
`preset/allin.patch.yml`、`preset/README.md` —— 这 4 份是 g18 / g17 / g14
的运行时判据文件，缺了它们，装出来的包跑这些门禁会**判不全**（少报，不是报错，
所以不打开对账根本看不见）。

发现方式值得一提：新增的包映射对账脚本（`tools/check_pkg_parity.py`，随 allin 仓
入库并接进 CI 双平台）把「已安装包 ↔ 仓内真身」逐文件 sha256 对账，首跑即对出
12 处红 —— 发布物与源码的漂移，从「一次性实测记录」变成了**退出码**。

本版起这 4 份随 wheel 分发，对账在 CI 的 init 端到端 job 里常驻。

### 门禁判据加固（`init` 生成的骨架随之更新）

- **g03 凭据**：增第三面「机器本地明文凭据文件」，且明文凭据**真正删除**而非仅拉黑；
  另修一处 hex-secret 正则把 Windows 路径误判成密钥的误报。
- **g04 推送证据**：从只核一个远端改为核**所有推送目标**，凭据红线覆盖 `pushurl`
  （双核推送场景的前置补盲）。
- **g20 事实源**：增「本机自述一致性」判据（自述与所属机器不符即红）。
- **g01 路径**：修复 `gov-paths: allow` 同行注记被 WIN_PATH 误判的误报。

### 双平台 / 控制台健壮性

- wheel 包数据 EOL 归一化，Windows 下 `init` 不再因 CRLF/LF 差异假红；
- stdio 编码钉 UTF-8 的路径覆盖补全（延续 a1 的 cp1252 修复线）。

### 测试基线

`pytest packages/allin-governance`：**37 passed**（a2 基线 36 + 新增 1）。

## `allin-governance` 0.0.0a2 —— 2026-10-31

三个新增，一个旧缺陷被真正修掉。

### 新增 `allin-governance verify`

按 `GENERATED.json` 复核快照：每个文件的 sha256 重算一遍，报告「一致 / 改动 / 缺失」。

```bash
allin-governance verify my-repo        # 0 一致 · 1 有改动或缺失 · 3 没有清单
```

在此之前 `GENERATED.json` 只是一份没人读的元数据 —— 快照的全部价值在于**能被核对**，
而没有复核命令时，「这个文件是不是原样」只能靠人肉 `sha256sum`。

它**不**把「你自己加的门禁」算成漂移：给自家仓加门禁是正常行为，
把正常行为报成问题，只会训练人忽略这个命令。

### 新增 `init --with-exceptions`

额外带上 `g18-exceptions` 与 `exceptions.yml` 台账模板（15 道门禁）。
默认不给的原因没变：g18 需要 **PyYAML**，与本包「零运行时依赖」的承诺冲突。
缺 PyYAML 时 g18 会报 `ledger-unusable` 并阻断 —— 刻意的：判据跑不了就不许装作通过。

### 修复：sdist 现在自包含（这是 a0/a1 的真实缺陷）

a0 与 a1 **只发 wheel**，原因是 sdist 是坏的：

- `python -m build --sdist` 打印 `Successfully built`；
- `twine check` 报 `PASSED`；
- 但包里**没有** `_repocheck/` 与 `_gatesuite/` —— 这两棵树靠 `package-dir` 的
  `../../` 映射进包，而 sdist 不能收录项目根之外的文件；
- 从那个 sdist 装出来的包，`repocheck` 与 `init` 会在运行时找不到源码。

**缺陷的形态是一路绿灯**，所以这次不是"改一行"，而是换构建路径：

```bash
python scripts/build_dist.py     # 物化映射树 → sdist + wheel → 自校验
```

脚本把两棵树物化到**临时目录**的项目副本里（仓内不产生副本），改写副本的
`package-dir` 为安装后布局，再构建；构建完**打开 tar 复核每棵树是否真的在里面**。
构建成功而产物不完整，正是它存在的理由。

### 顺带

- `requirements-release.txt`：出包期依赖（build / twine）单列，不再混进开发依赖
- `cli.py` 里重复的 `__version__` 已在 a1 删除；本版只递增一处

## `allin-governance` 0.0.0a1 —— 2026-10-31

**只修一个会让命令假装失败的缺陷，其余与 a0 相同。**

`init` 在 **cp1252 控制台**（西文 Windows、以及 GitHub Actions 的
`windows-latest` runner）上会抛 `UnicodeEncodeError`：

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 2-3
```

原因不是逻辑错了，是**输出的默认编码跟着终端走** —— 这套工具的每一行提示都是中文。
最坏的后果不是崩溃本身，而是它发生在**打印阶段**：文件全部写好了，命令却以
exit 1 收场，用户看到「失败」、磁盘上是成功。

修法：新增 `_stdio.configure()`，把 stdout/stderr 钉成 UTF-8（`errors="replace"`），
在 `cli.main()` 入口统一调用 —— 所有子命令与 `--help` 共用同一条出口。
回归测试用**子进程 + `PYTHONIOENCODING=cp1252`** 复现那个环境，而不是 mock 流。

顺带：`cli.py` 里重复定义的 `__version__` 已删掉，改为从包根取 ——
两处各写一个版本号，「包说 a1、CLI 说 a0」这种漂移没人会在发布前发现。

## `allin-governance` 0.0.0a0 —— 2026-10-31

**占位版本，但可运行。** 发它的直接目的是占住 PyPI 名字（REC-AU-21 D1.3），
不是「功能完备」；因此不承诺 API 稳定，下一版可能改名或改参数。

包含两个子命令：

### `allin-governance init <目录>`

在空目录生成**可跑的最小治理骨架**：14 道可执行门禁 + 文档四分类
（`规范/` `事实源/` `记录/`）+ `registry.json` + 基线棘轮 + 生成清单。

判据是实测的：装 wheel → `init` 一个空目录 → `npm run check:governance`
**exit 0 / 14-14 gate(s) clean**（Windows 与 Linux CI 各验一次）。

出厂 14 道是跑出来的边界，不是挑出来的：

- 20 道里 15 道能在空仓库上 pass；`g18-exceptions` 需 PyYAML，与「零第三方运行时
  依赖」冲突，列为按需；
- `g14/g15/g16/g17/g19` 判的是 allin 自己的 preset / 文档契约 / 平台台账，
  别的仓没有对应物，塞进来只会让新用户第一天看到与他无关的红。

三条行为约定：

- 二次 `--force` **零改动**（幂等）；
- `README.md` / `LICENSE` / `docs/**` **永不覆盖**，只在缺失时创建；
- `package.json` 与 `.gitignore` **合并**而不是取代。

### `allin-governance repocheck <目录>`

离线仓库体检：30 条规则、0–10 健康分、text/JSON/CSV/HTML 四种导出、五档退出码。
不联网、不执行被体检代码、只用标准库。

**已知缺陷**：本版**只发 wheel，不发 sdist**。sdist 构建取不到 `package-dir`
映射进包的两棵源码树（`_repocheck/` 与 `_gatesuite/`），从它装出来的包会在运行时
找不到源码。发一个装得上但跑不起来的 sdist 比不发更坏，所以不发。修法见
`docs/记录/审计/allin自身做大做强方向修正_2026-10-31.md` §7.4。
