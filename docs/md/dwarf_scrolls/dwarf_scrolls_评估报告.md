# dwarf_scrolls 项目评估报告

> 评估日期：2026-07-11 ｜ 评估对象：`D:\allin\dwarf_scrolls`（git 仓库）
> 参照物：`D:\allin\allin_engine`（独立引擎包，v1.0.0）
> 评估视角：全哥架构约束——「复制即复用但必须零耦合」「整合=聚合非融合」「清理冗余前先取证」

---

## 0. 一句话总评

**dwarf_scrolls 是个被「融合式副本」污染的游戏项目。** 它本应只是 allin_engine 的薄封装游戏层（约 3784 行自有代码），实际却背着 **23077 行 allin_engine 逐字节死副本（占总量 86%）**；而运行期又 `from allin_engine import` 去引用外部那份真引擎——于是目录内副本**完全无人引用，纯属维护负担**。这正是你在 helminth 项目亲证失败、并写进记忆的「融合式整合」反模式的重演。

好消息是：它的**设计方向是对的**（架构文档优秀、薄封装思路正确、零耦合引用外部引擎），只是**落地脏了**。

---

## 1. 它到底是什么

| 项 | 事实 |
|----|------|
| 定位 | 《矮人要塞风格上古卷轴》游戏原型（TES 为体、DF 为用），Tkinter GUI 首选、ANSI 终端回退 |
| 真实引擎 | `D:\allin\allin_engine`（独立包，经 `dwarf_scrolls/core/engine_bootstrap.py` 把 `D:\allin` 加入 sys.path 后 `import allin_engine`） |
| 运行入口 | `main.py`（`Game` 类）→ `from allin_engine.core import World, EventBus` 等正常使用外部引擎 |
| 代码总量 | **26861 行 / 109 个 .py 文件** |
| 副本占比 | **MIRROR（与 allin_engine 同名）= 76 文件 / 23077 行（86%）** |
| 自有代码 | **UNIQUE（仅 dwarf_scrolls 有）= 33 文件 / 3784 行（14%）** |

**副本死代码证据链（按你的「冗余取证」原则逐条落实）：**
1. grep 全树：dwarf_scrolls 内部**从未**出现 `from dwarf_scrolls.core.ecs / event_bus / serializable / game_loop / data_library` 等引用；`world/`、`systems/`（除自建）、`render/`、`audio/`、`fx/`、`ai/` 也**均未被 `from dwarf_scrolls.xxx` 引用**。
2. 运行引用：游戏实际 `from allin_engine import ...`（指向外部 `D:\allin\allin_engine`），副本不被加载。
3. md5 抽查 34 个代表文件：**33 个与 allin_engine 逐字节相同**，唯一 DIFF 的 `core/serializable.py` 同样无任何内部引用（仍是死副本，删除前需先 diff 确认有无私有改动）。

→ **结论：76 个 MIRROR 文件是 safe-to-remove 的死副本。**

---

## 2. 做得对的地方（先肯定）

- **架构设计文档质量高**：`docs/architecture.md`（45KB，含「引擎能力边界矩阵」「类图」「时序图」）思路清晰，明确写入原则「游戏不修改、**不复制引擎源码**」「游戏侧 core 是薄封装 + 缺失能力的新建子系统」。方向完全正确。
- **自建子系统有章法**：`world_gen / region_nav / agent_needs / growth_system / ecs_bridge / save_manager / event_producers` 是「引擎缺失能力的新建子系统」，抽象合理，是真正的游戏价值所在。
- **零耦合引用姿势本身正确**：通过 sys.path + `import allin_engine` 引用外部独立包（可 pip 安装），这正符合「复制即复用但零耦合」的格局——只是被目录内死副本破坏了。
- **工程素养在线**：有 `docs/`、两套测试、`.github/workflows` CI、MIT LICENSE、`.gitignore`；52MB 字体**未进 git**（`git ls-files` 无 ttf，git log 还有「large-file analysis」说明已警觉）。

---

## 3. 核心问题（按严重度排序）

### 🔴 P0 — 86% 代码是 allin_engine 逐字节死副本（23077 行）
- 现状：`dwarf_scrolls/{core,world,systems,render,audio,fx,ai}` 整包与 `D:\allin\allin_engine` 同名同内容，却**无人 import**。
- 危害：双份引擎代码（外部一份 + 目录内 23077 行）；与 allin_engine 接口必然漂移却无人同步；认知负担、CI 时间、Code Review 成本全翻倍。
- 直接违反它自己 `docs/architecture.md` 第 14-16 行的设计原则。
- **这是「融合式整合」已证伪反模式的重演**：把大引擎（24k 行、接口还在漂移的孵化场）整份塞进下游，比 helminth 更糟——helminth 至少还在 import 副本，这里副本纯死。

### 🟠 P1 — 身份与配置错乱
- `README.md` 与 `pyproject.toml` **自述为 allin_engine 引擎**（描述 ECS/事件总线/卡牌战斗…），但目录是 `dwarf_scrolls`。
- `pyproject.toml`：`name = "allin_engine"`、`packages.find include = ["allin_engine*"]`——但本目录**没有 allin_engine 包，包名是 dwarf_scrolls** → `pip install -e .` 失效/装错。
- `__init__.py` 注释又说「引擎在 `D:\allin\allin_engine`，这里只是项目」。三处说法 + 实际路径，四路不一致。

### 🟠 P1 — 路径硬编码 + 过期路径
- `engine_bootstrap.py`：`ENGINE_PARENT = os.environ.get("ALLIN_ENGINE_PARENT", r"D:\allin")` → 默认硬编码绝对路径，跨机器/沙箱需靠环境变量救。
- `main.py` 与 `engine_bootstrap.py` 注释全写 `D:\allin\example`（已迁移到 `D:\allin`，注释没改）。
- `_verify_ds.py` **已失效**：引用 `D:\allin\example` 与 `D:\allin\example\dwarf_scrolls\core\gui_renderer.py`、`game\gui_window.py`（路径已变），其中 gui_renderer 已挪到 `dwarf_scrolls/core/`，gui_window 已挪到 `dwarf_scrolls/game/`，且前缀 example 错 → 该脚本当前**无法运行**。

### 🟡 P2 — 两套测试框架并存
- `test/`（5025 行，自定义框架 `run_all.py`）+ `tests/`（1153 行，pytest + conftest）。双框架维护负担。
- `test/` 下大量 `test_core/test_world/test_systems/test_combat/test_ai/test_render/test_audio` 实际是在**测死副本引擎**，不是测 dwarf_scrolls 游戏。
- 文档漂移：README 称「292 个测试」、git log 称「269 total」——数字不一致。

### 🟡 P2 — 52MB 字体放大仓根目录
- `BaoCanMouHuiTingShouXieTi2.0-2.ttf`（52MB）直接放 `dwarf_scrolls/` 根。README 明确字体应随 allin_engine 分发（`fonts/`）。`pyproject` 的 `package-data` 也指向 `allin_engine`（本目录不存在）。虽未进 git，但工作区污染 + 语义错位。

---

## 4. 量化快照

```
模块        总行数   性质
─────────────────────────────────────
test/       5025     ⚠ 多在测死副本引擎（自定义框架）
systems/    4625     ❌ 死副本(allin_engine 同名)
ai/         3602     ❌ 死副本
render/     2971     ❌ 死副本
core/       2606     ⚠ 自建子系统(活) + ecs/event_bus/... (死副本)
world/      1595     ❌ 死副本
(root)      1534     ⚠ main.py(活) + example_*(副本) + _verify_ds(失效)
utils/      1197     ❌ 死副本
tests/      1153     ✅ pytest 测游戏侧(活)
audio/      1129     ❌ 死副本
fx/          983     ❌ 死副本
game/        441     ✅ 游戏编排层(活)
─────────────────────────────────────
合计        26861    MIRROR 23077(86%) / UNIQUE 3784(14%)
```

---

## 5. 推荐行动（按零耦合风险排序，可逐步执行）

**① 清理死副本（零风险，建议先做隔离验证）**
- 把 76 个 MIRROR 文件移入项目内隔离区（保留相对结构，如 `dwarf_scrolls/_obsolete_engine_bak/`），**不永久删**。
- 跑 import 冒烟测试：确认游戏侧仅依赖外部 `allin_engine` + 自有 33 文件能正常 `import`、无头 render、tick。
- 唯一例外 `core/serializable.py`（DIFF）删除前先 `diff` 确认无 dwarf_scrolls 私有改动。
- 隔离区验证无碍后，再清空。
- **预期收益：代码量 26861 → ~3784 行（砍 86%），与 allin_engine 恢复零耦合。**

**② 修复身份（同步做）**
- `README.md` / `pyproject.toml` 改为 `dwarf_scrolls`（项目名 + 包名对齐）；`pyproject` 的 `packages.find include = ["dwarf_scrolls*"]`。否则 `pip install -e .` 不可用。
- `__init__.py` 注释与 README 对齐口径。

**③ 去硬编码路径**
- `engine_bootstrap` 的 `ENGINE_PARENT` 默认改为相对推导（从 `__file__` 上溯到 `D:\allin`）或明确靠 `ALLIN_ENGINE_PARENT` 注入；清理 `D:\allin\example` 过期注释。
- 删除或重写失效的 `_verify_ds.py`（它引用的 `D:\allin\example` 路径已不存在）。

**④ 统一测试框架**
- 保留 `tests/`（pytest，测游戏侧）或 `test/`（自定义）其一；删掉**测死副本引擎**的那套。

**⑤ 字体归位**
- 52MB TTF 移入 `dwarf_scrolls/fonts/` 或改为依赖 allin_engine 的 `fonts/`，不放大仓根目录。

---

## 6. 结论

方向正确、落地脏。**最高优先级是 P0：移除 23077 行 allin_engine 死副本**——这一刀下去，项目立刻变回干净的「allin_engine 薄封装游戏层」（3784 行），并彻底消除与引擎的副本耦合。其余 P1/P2 是配置与卫生问题，可紧随其后。

需要我**从 ① 开始动手**（先建隔离区 + 跑冒烟测试验证安全）吗？这一步零耦合风险，符合你的清理原则。
