# allin_engine 修复执行记录

**日期**：2026-07-14
**依据**：comprehensive-review-allin-engine-2026-07-14.md
**执行结果**：全部 P0（红区）+ P1 + 安全 P2 修复完成，测试套件 326/326 通过，退出码 0。
**约束遵循**：allin_engine 定位为「参考实现 / 孵化场」，未引入任何跨项目共享核 / monorepo / 中心化治理建议；复制即复用保持有效。

---

## ✅ 已修复（P0 红区）

| # | 文件 | 修复 |
|---|------|------|
| R1 | `render/formula_engine.py` | `_build_fallback_func` 编译前注入 `ns["__builtins__"] = {}`，阻断通过公式字符串执行任意代码（`__import__('os')` 等）。新增回归校验：恶意 `open(...)` 表达式不再产生副作用。 |
| R2 | `test/test_pathfinding.py`（新） | 补齐 `world/pathfinding.py` 测试覆盖：grid_astar（基础/墙内/封闭/越界/对角）+ GraphPathFinder（BFS/Dijkstra/A*/不可达/同节点/锁节点绕行），共 12 例，已全部注册进 `run_all`。 |
| R3 | `test/run_all.py` + `test/runner.py` | `run_all` 末尾补 `sys.exit(1 if failed>0 else 0)`，并新增 `def main()`（对齐 pyproject `allin-test` 入口）；runner 实现 SKIP 机制（`@skip` / `@skip_if_missing`、报告/SKIP 符号、`summarize` 统计 skipped）。修复「假绿」。 |
| R4 | `__init__.py` + `systems/combat/__init__.py` | 对齐 `__all__` 与顶层导入：补导入 9 个 systems 名称（StackableInventory/EquipmentSlots/ItemRegistry/CraftingSystem/Recipe/SimpleCombat/MobTemplate/CombatResult/MobLibrary）+ 6 个 render 名称（GameLogPanel/StatusBar/QuickCommandBar/GameInputBar/GameWindow/GameTheme），`NumpyParticleSystem` 补入 `__all__`；combat 子包 re-export simple_combat 4 个类。原 15 个不可导入名称现已全部可访问。 |

---

## ✅ 已修复（P1）

| 文件 | 修复 |
|------|------|
| `systems/save_load.py` | 误导性 `encrypt` 参数重命名为 `b64_encode`，文档明确「仅编码、非加密、不提供安全性」。无外部调用方，零破坏。 |
| `core/serializable.py` | 修复 `from __future__ import annotations` 下 `field.type` 退化为字符串、导致嵌套 dataclass / `list[Dataclass]` 反序列化失效；改用 `typing.get_type_hints` 解析真实类型（带缓存 + 失败回退）。 |
| `systems/MOD_SCHEMA.md`（新） | 补 Mod 清单 `mod.json` Schema 文档（ModManifest/MapDef/PortalDef/MechanismDef + 路径安全说明）。 |

---

## ✅ 已修复（P2 安全子集）

| 文件 | 修复 |
|------|------|
| `core/data_library.py` | 修复 `if item_id:` 将合法 `id==0` 数据项 falsy 丢弃 → 改为 `if item_id is not None:`（register / _load_from_list 两处）。 |
| `utils/json_loader.py` | `load` 对缓存与返回值均做 `copy.deepcopy`，杜绝调用方修改返回对象污染缓存（共享可变状态）。 |
| `__init__.py` 文档 | 移除陈旧 `Pillow` 依赖说明，补准确的 `asteval>=1.0` 可选依赖。 |
| `systems/__init__.py` 文档 | 新增双战斗系统 / 双背包系统选型使用指南。 |
| `pyproject.toml` | `asteval` 约束由 `>=0.9` 提升至 `>=1.0`（render + all 两组）。 |
| `render/console_renderer.py` | 核验：`draw_grid(map_data: MapData, ...)` 已正确接收 MapData，本项原建议已满足，无需改动。 |
| `test/test_serializable.py`（新） | 嵌套反序列化回归测试 3 例。 |
| `test/test_data_library.py`（新） | `id==0` 注册 + json_loader 独立副本回归测试 2 例。 |

---

## ✅ 已修复（架构级改动 — 你确认后执行）

| # | 文件 | 修复 |
|---|------|------|
| A1 | `ai/narrative.py` + `ai/__init__.py` + `test/test_ai.py` | `ai/narrative` 的叙事状态类 `GameState` → `NarrativeState` 重命名（消除与 `world.GameState` 的命名混淆）。保留 `GameState = NarrativeState` 废弃别名以维持下游复制副本兼容；`ai/__init__.py` 同时导出两者并注明废弃。全量引用（类定义、类型注解、`NarrativeEngine.state`、测试）已同步更新。 |
| A2 | `core/ecs.py` + `core/__init__.py` + `__init__.py` | ECS 实体 ID 计数器由模块级全局（`_global_entity_id`/`_next_id`/`reset_id_counter`）移入 `World` 实例（`self._next_entity_id`）。`World.create_entity` 分配实例级 id；`Entity` 直接构造时回退到轻量模块级孤儿计数器；新增 `World.reset_id_counter(start=0)` 实例方法替代原全局函数。删除顶层 `reset_id_counter` 导出（原全局语义在多 World 下无意义）。不同 World 的 ID 现互相隔离、可确定性重置。 |

---

## ⏸ 仍暂缓（需你确认后再动）

以下 1 项属**语义 / 架构级改动**，按你的架构约束我先标记、待你拍板：

1. **`__init__.py` 对 render/audio/ai 做惰性/可选导入** —— 当前顶层已做内部 try/except 守护，收益有限、重构面较大。原暂缓清单中的「GameState 重命名」「ECS 计数器移入 World」两项已按你的确认执行完毕（见上）。

---

## 🧪 验证

- 导入冒烟：`import allin_engine` 通过；15 个原不可导入名称 + `NumpyParticleSystem` 均可访问。
- 安全：`FormulaEngine` 恶意表达式被 `__builtins__={}` 阻断（标记文件未生成）。
- 路径安全：`_safe_join` 拒绝 `../etc/passwd` 与绝对路径穿越。
- 跳过机制：`@skip` 测试记为 `SKIP`，`summarize` 正确统计。
- 全量回归：`python -m allin_engine.test.run_all`（经 `main()`）共 **326/326 通过，退出码 0**（架构改动后复跑，零回归）。
- 架构改动专项校验：
  - `ai.NarrativeState` 可导入，`ai.GameState` 废弃别名 `is NarrativeState`；`world.GameState` 与 `ai.NarrativeState` 确认为两个不同类。
  - 两个 `World` 实例各自从 id=1 独立分配、互相隔离；`w1.reset_id_counter()` 仅作用于 w1、不影响 w2；脱离 World 直接 `Entity("solo")` 仍获有效 id（孤儿回退计数器）；`allin_engine` 不再导出 `reset_id_counter`。
