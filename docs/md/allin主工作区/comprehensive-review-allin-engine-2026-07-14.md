# allin_engine 全面工程审查报告

**日期**：2026-07-14
**工作流**：工作流 1（全面代码审查）+ 工作流 5（技术债评估）
**参与成员**：Cody（代码审查师）/ Archi（系统架构师）/ Tessa（测试专家）/ Docu（技术文档师）。Rex（SRE）未参与——本次为审查/债盘点，非事故或部署场景。

**审查对象**：`D:\allin\allin_engine`（约 24.7k 行 / 82 个 `.py` 文件 / 8 个子系统）。
**定位约束（贯穿全报告）**：allin_engine 是「参考实现 / 孵化场」，不是被依赖的中心化共享核；用户一人团队、无跨项目 CI、复制即复用是合理模式。因此**全部结论均针对引擎内部自身**，未出现任何「抽共享库 / monorepo / 中心化核 / 跨项目接口冻结 / 统一治理」类建议（已被各成员 brief 明确禁止）。

---

## 📌 TL;DR（执行摘要）

- **整体结论**：作为「参考实现 / 孵化场」，质量基线**不差**——实测无循环依赖、分层收敛健康、可选依赖门控到位、已有 291 个用例覆盖约 70% 关键路径。但存在 **4 项 🔴 级红线**（1 安全 + 3 工程可靠性），在「复制即复用」分发前必须先修。
- **严重度分布**：🔴严重 4 项 / 🟠高 11 项 / 🟡中 14 项 / 🟢低 11 项（合并去重后；含各维度债）。
- **阻塞 / 非阻塞**：无功能性阻断，但 🔴 中有 2 项（formula_engine 任意代码执行、run_all.py 致 CI 假绿）建议在复制分发前**必修**。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 整体评级 | 🟡 有条件通过（孵化场阶段可接受；4 条红线需先清） |
| 阻塞项数量 | 4（均 🔴 级：1 安全 + CI 假绿 + 核心算法裸奔 + API 契约断裂） |
| 关键行动项 | 11 条（见下方行动清单与分阶段计划） |
| 建议下一步 | 先修 D1（exec 任意代码）/ D3（CI 不报失败）→ 再清 D2/D4/D6（API 契约 / pathfinding 测试 / mod 路径穿越）→ 分批补测试债与文档债 |

---

## 🔍 审查发现（按严重度排序，跨成员已去重合并）

> 来源标记：C=Cody 代码审查 / A=Archi 架构债 / T=Tessa 测试债 / D=Docu 文档债。

### 🔴 严重（4）

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|---------|---------|---------|------|
| R1 | 🔴严重 | 安全 | `render/formula_engine.py:329-363`（exec 在 362） | `_build_fallback_func` 用 `exec(code, ns)` 编译公式，未清 `ns["__builtins__"]`；asteval 为可选依赖，未装时渲染层全部公式走此回退，等于任意代码执行（`__import__('os').system(...)` 可运行）。 | `exec` 前显式 `ns["__builtins__"] = {}`；或直接删 exec 回退、asteval 缺失时抛错/降级，修正「安全求值」措辞。 | C |
| R2 | 🔴严重 | 测试债 | `world/pathfinding.py`（232 行） | A*/Dijkstra/BFS 零测试。作为「参考算法」被复制复用风险极高，一旦被下游 copy-paste 即无保护网。 | 新增 `test_pathfinding.py`：4/8 连通直线/绕障、封闭目标返回 None、`GraphPathFinder.dijkstra/astar` 加权最短路、tie-breaking 确定性。 | T |
| R3 | 🔴严重 | 测试基建 | `test/run_all.py` | `__main__` 仅打印失败数，从不 `sys.exit(1)`；CI 步骤即使全失败也返回 0 → **CI 无法拦回归**，其余 291 用例价值归零。 | 末尾按 `failed>0` 返回非零退出码（仅本项目内，不涉及跨项目平台）。 | T |
| R4 | 🔴严重 | API 契约 | `__init__.py`（import L122–194；`__all__` L413–485） | 根包 `__all__` 声明了 **15 个实际不可导入**的名字（`from allin_engine import X` → ImportError）：StackableInventory/EquipmentSlots/ItemRegistry/CraftingSystem/Recipe、GameLogPanel/StatusBar/QuickCommandBar/GameInputBar/GameWindow/GameTheme、SimpleCombat/MobTemplate/CombatResult/MobLibrary；反向也有 2 个有用名（GraphPathFinder/NumpyParticleSystem）未列入。 | 对齐 import 与 `__all__`：补 `from allin_engine.systems...`、`from allin_engine.render...`、`from allin_engine.systems.simple_combat...`；`systems/combat/__init__.py` 补 simple_combat re-export；把 GraphPathFinder/grid_astar/NumpyParticleSystem 写进对应 `__all__`。 | D + A |

### 🟠 高（11）

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|---------|---------|---------|------|
| O1 | 🟠高 | 正确性 | `core/serializable.py:97-111` | `_deserialize_field_value` 依赖 `field_def.type` 做嵌套反序列化，但 `from __future__ import annotations` 让注解成字符串，`hasattr`/`_is_list_of_serializable` 恒 False，嵌套 Serializable 反序列化静默失效（仅回传原始 dict）。对外 advertised 的「通用序列化基类」一旦被消费即数据损坏。 | 用 `typing.get_type_hints(cls)` 运行时解析真实类型；或维护「类名→类型」注册表。 | C |
| O2 | 🟠高 | 安全 | `systems/mod_loader.py:458,522` | `_apply_map`/`_load_map_entities` 将清单 `map_file`/`objects_file` 直接拼接 `mod.root_dir / ...` 并 `open()`，无路径穿越校验；恶意/疏忽 mod.json 可用 `../` 或绝对路径读引擎目录外任意文件。 | 拼接后 `Path.resolve()` + `os.path.commonpath([str(mod.root_dir), str(target)]) == str(mod.root_dir)` 校验，越界拒绝并告警。 | C |
| O3 | 🟠高 | 安全/误导 | `systems/save_load.py:97,125-130,136` | `encrypt` 参数与文档称「Base64 编码加密/轻量加密」，实为仅 base64 编码，零机密性；用户误以为存档被加密保护。 | 改名 `b64_encode`/`encode`，去除「加密」措辞；确需保密用 `cryptography.Fernet` 并妥善管密钥。 | C |
| O4 | 🟠高 | 架构/爆炸半径 | `__init__.py:69-249`（无条件 import 全部子系统） | 包级 `import allin_engine` 强制拉起 render/audio/ai/fx 全部（render 引 tkinter、audio 引 pygame、ai 引 requests/ollama），与「core 纯净、可选依赖门控、子系统可独立演化」的自包含定位**自相矛盾**，也破坏 dwarf_scrolls 只内联物理子集的预期。 | 重子系统（render/audio/ai）改为惰性/可选导入（函数内或 try 门控），顶层只稳定导出 core/world/systems 常用名。 | A |
| O5 | 🟠高 | 测试债 | `fx/particle.py`(949)+`fx/particle_np.py`(208) | 1198 行粒子系统（生命周期/发射器/预设工厂/numpy 后端）零测试。 | 测 Particle 生灭、Emitter 发射率、ParticleSystem.update 积分、particle_np 与纯 Python 后端结果一致性。 | T |
| O6 | 🟠高 | 测试债 | `render/animation.py`（404 行） | 动画系统零测试（被 `render/__init__.py` 直接导入）。 | 测帧插值、缓动函数、loop/once 模式、基于时间轴的进度。 | T |
| O7 | 🟠高 | 测试债 | `systems/`：crafting(231)+input(320)+simple_combat(381)+stackable_inventory(408) | 1340 行 gameplay 逻辑零测试。 | 优先补 simple_combat 伤害结算、stackable_inventory 堆叠/拆分、crafting 配方解析、input 键位映射。 | T |
| O8 | 🟠高 | 测试基建 | `test/runner.py`+`test/test_font.py` | 运行器无 skip/xfail 机制；pygame 缺失时 font 测试**静默 pass**（注释自承「缺失时直接 pass」）→ CI 假绿。 | 实现 skip 报告，缺失依赖用例标 SKIPPED 而非 PASSED。 | T |
| O9 | 🟠高 | 文档债 | 全仓库（仅 3 个 example） | 受众是「复制此引擎」的项目，但 crafting/stackable_inventory/simple_combat/save_load/mod_loader/world(render/audio/ai/fx) 等多数子系统无任何可运行示例。 | 优先补 4 个高复用 example：`example_combat.py`、`example_crafting_inventory.py`、`example_mod_authoring.py`、`example_audio_synth.py`/`example_ai_narrative.py`，均含「最小可运行 + 预期输出注释」。 | D |
| O10 | 🟠高 | 文档债 | `systems/mod_loader.py`(L1–579)+`card.py`+`enemy.py` | 数据驱动管线（卡牌/敌人/地图 JSON 经 ModManager 载入）是核心复用路径，但**无 JSON schema 文档**，仅有测试隐式覆盖。 | 新增 `systems/MOD_SCHEMA.md`，用最小示例说明 cards/enemies/maps 三类 JSON 的必填/可选字段与载入入口。 | D |
| O11 | 🟠高 | 测试债 | `render/formula_engine.py`（363 行） | 仅 1 个 `import` 断言；表达式求值/后备纯 Python 分支未测（与 R1 安全回退直接相关）。 | 测 `evaluate()` 已知公式、numpy vs 纯 Python 一致性、坏表达式报错。 | T |

### 🟡 中（14，已合并同类）

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 | 来源 |
|---|--------|------|---------|---------|---------|------|
| Y1 | 🟡中 | 正确性/可观测 | `core/event_bus.py` + 生产未见发射 | **EventBus 三重问题**：①`emit` 对订阅回调异常统一 `except Exception` 后仅 `print`，错误被吞（C:97-111 区）；②全引擎真实 emit 仅 puzzle/mod_loader/brain 几处，且 PUZZLE_SOLVED/MAP_LOADED/brain_tick 等基本无订阅者（A）；③零真实测试覆盖（T）。50+ 事件含整段「《我的世界》」遗留/臆测事件类型。 | 二选一：①给核心流程（房间进入/物品/战斗/存档）接真实事件流；②明确标注为「参考扩展点」并删无订阅者臆测事件。 | C+A+T |
| Y2 | 🟡中 | 正确性 | `utils/json_loader.py:64-80,176` + 零测试 | `load()` 直接返回缓存 dict 引用；调用方就地修改污染缓存影响后续读者（跨模块隐性状态共享）。另无测试。 | 返回 `copy.deepcopy` 或 `dict.copy()`；或文档明确「返回共享引用，禁止修改」。补单测。 | C+T |
| Y3 | 🟡中 | 正确性 | `core/data_library.py:126` | `_load_from_list` 用 `if item_id:` 判断，静默丢弃 `id` 为 `0`/空串/`None` 的合法数据项。 | 改为 `if item_id is not None`；覆盖写入补告警日志。 | C |
| Y4 | 🟡中 | 性能/一致性 | `utils/logger.py` + 散落 print | `_write` 每条日志 `open(path,"a")` 开闭文件，高频 I/O 开销大；`debug/info/warning` 接受 `*args` 却不格式化，仅 `error` 格式化（API 不一致）；全引擎 `_log` 在 logger 缺失时回退 `print`，缺乏统一日志出口（多处散落 print 兜底）。 | 在 `__init__` 打开并保持 `_file_handle`；统一在 `_write` 按 `args` 格式化；约定统一日志接入点（默认挂 `utils.logger.Logger` 或标准 `logging`），消除散落 print。 | C |
| Y5 | 🟡中 | 正确性/UX | `render/gui_base.py:224,747-756` + 冗余/零单测 | `switch_theme` 通过 `self.__init__(...)` 重建样式对象，但已构建 tk 控件不刷新（bg/fg 构造时即定），切主题后旧控件仍旧配色；215-216 行重复调用 `get_default_fonts()` 为死代码；无单测。 | 重建 Styles 后遍历 `apply_to_widget` 刷新已创建控件或销毁重建窗口内容；删重复分支；抽纯布局/几何计算做单测。 | C+A+T |
| Y6 | 🟡中 | 可维护性 | `ai/narrative.py:73` ↔ `world/game_state.py` | `ai/narrative.py` 定义与 `world.GameState` 完全无关的 `GameState` 类，二者同名导出，易在 `from allin_engine.ai import GameState` 时被误用/遮蔽。 | 叙事状态类重命名为 `NarrativeState`/`StoryState`，消除冲突。 | C |
| Y7 | 🟡中 | 代码债 | `core/ecs.py:24-31` | `_global_entity_id` 模块级可变全局状态，跨所有 World 实例共享 ID 计数器；虽提供 `reset_id_counter` 仍属隐式全局可变状态。 | 将计数器收进 `World` 实例或显式 `IdGenerator`；当前单进程/单线程可接受，属债务。 | C |
| Y8 | 🟡中 | 依赖债 | `pyproject.toml:26` | `asteval>=0.9` 作为「安全」公式求值边界被依赖，旧版本有已知沙箱逃逸，下限过松且未锁安全版本。 | 明确依赖较新安全版本（如 `asteval>=1.0`）并注明仍非绝对安全；同时修复 R1 的 exec 回退。 | C |
| Y9 | 🟡中 | 分层越界 | `render/console_renderer.py:27` | 渲染层直接 `from allin_engine.world.map_data import MapData`，构成唯一跨层硬依赖，把表现层绑死到世界数据模型（实测依赖图唯一越界）。 | 渲染函数改由调用方注入 map 数据/快照（构造参数或 render(world_snapshot)），不再 import `world.map_data`。 | A |
| Y10 | 🟡中 | 架构/缺指引 | `systems/combat/` vs `systems/simple_combat.py` | **双战斗并存**：卡牌制 `CombatEngine`（被 `add_combat` 接线、example/tests 实际使用）与 `SimpleCombat`（三选一回合制）并列；grep 全量 SimpleCombat 从未被实例化，仅定义+导出。 | 以 CombatEngine 为规范战斗，SimpleCombat 降级到 `examples/` 或标「替代范式演示」；不要两者并列当官方 API。 | A+D |
| Y11 | 🟡中 | 架构/缺指引 | `systems/inventory.py:111` vs `systems/stackable_inventory.py` | **双背包并存**且文档自陈「与现有 Inventory 区别」，对下游（dwarf_scrolls 等）缺「何场景用哪个」指引，易选错基底。 | docstring/README 写明：Inventory=文字冒险 RPG 固定格；StackableInventory=沙盒/生存堆叠。 | A |
| Y12 | 🟡中 | 架构/文档 | `core/config.py` + `core/paths.py` | 渲染/控制台专属常量（WINDOW_W/WINDOW_H/FPS/FILL_CHAR…）住在 core.config，混进「引擎核心配置」（A 称越界）；且这些常量与 paths 各 helper 均无说明/单位/默认值/跨打包差异（D 称缺文档）。 | 渲染相关常量移到 `render/` 自有配置；core.config 仅留真正跨子系统项；两模块补「可调常量表」「各路径语义 + PyInstaller/开发态差异」docstring。 | A+D |
| Y13 | 🟡中 | 文档/一致性 | `README.md`（L66/L114-128/L80/L124）+ `__init__.py:57` | README 数据陈旧：测试数写 292 实际 309；核心模块行数表已漂移（ecs 434→462 等）；决策表列 `build_behavior_tree`（未导出、不可导入，可用工厂是 `build_brain_from_spec`）；根包 docstring 列 Pillow 依赖但全仓无 PIL import、`pyproject.toml` 也无；L124 行尾悬空脚注 `#` 无对应文本。 | README 改动态生成测试数/删易漂移行数列；决策表改列 `build_brain_from_spec` 或补导出；删 Pillow 说明；删/补脚注。 | D |
| Y14 | 🟡中 | 打包债 | `pyproject.toml` → `[project.scripts] allin-test` | 指向 `allin_engine.test.run_all:main`，但 `run_all.py` **无 `main()`** → 控制台脚本损坏（与 R3 同源）。 | 补 `def main(): ...; sys.exit(code)` 或改指向现有 `__main__` 入口。 | T |
| Y15 | 🟡中 | 测试债 | `utils/text_fmt.py`（265 行） | CJK 宽度/换行/对齐格式化零测试（多处 UI 复用）。 | 测全角宽度计算、定宽换行、CJK 填充对齐。 | T |
| Y16 | 🟡中 | 文档债 | `systems/save_load.py` + `core/world_serial.py` + `core/serializable.py` | 序列化/存档机制已实现但无文档说明格式、存放目录、版本兼容策略（与 O1/Y1 同源）。 | `systems/save_load.py` docstring 补「存档位置(get_save_dir)、文件命名、序列化协议、向前兼容」要点。 | D |

### 🟢 低（11，合并展示）

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议 | 来源 |
|---|--------|------|---------|---------|------|------|
| G1 | 🟢低 | 死代码 | `core/event_bus.py:129` | `_max_recursion_depth=5` 声明但从未读取（实际循环检测用祖先栈 `_recursion_guard`），属死代码/误导（注：当前基于祖先栈的循环检测本身正确）。 | 删除该属性或真正接入深度控制。 | C |
| G2 | 🟢低 | 正确性(次) | `utils/logger.py:75-89` | `debug/info/warning` 接受 `*args` 却不格式化，仅 `error` 用 `.format(*args)`，传参被静默忽略。 | 统一在 `_write` 中按 `args` 格式化（已并入 Y4）。 | C |
| G3 | 🟢低 | 正确性(次) | `systems/combat/combat_engine.py:256-258` | `nerve_cost` 仅 `player_nerve >= nerve_cost` 时扣减，不足时不拦截出牌（软资源）；若意图是「神经不足不可出牌」则逻辑缺失。 | 明确语义：消耗型资源缺额应阻止出牌并返回失败；若可选加成则补注释。 | C |
| G4 | 🟢低 | 可维护性 | `render/gui_base.py:212,215-216` | `__init__` 212 已 `self.fonts = get_default_fonts()`，215-216 又在 `theme=="light"` 重复同调用，冗余死代码（已并入 Y5）。 | 删除重复分支。 | C |
| G5 | 🟢低 | 可维护性 | 多文件（mod_loader:154/save_load:111/json_loader:50/event_bus:275 等） | 各模块 `_log` 在 logger 缺失时回退 `print`，全引擎缺乏统一日志出口（已并入 Y4）。 | 统一日志接入点。 | C |
| G6 | 🟢低 | 正确性(次) | `fx/particle.py:295-296` | `Emitter.emit` 累加器用「当前 boosted rate」而非实际发射速率扣减，音频驱动使 rate 逐帧变化时发射节奏有微小漂移（视觉无碍）。 | 记录发射瞬时速率并在扣减时保持一致。 | C |
| G7 | 🟢低 | 代码组织 | 包根 `example_*.py` ×3 | 示例脚本直接躺包根，污染包命名空间、随 `import allin_engine` 被索引。 | 迁到 `examples/` 目录。 | A |
| G8 | 🟢低 | 内聚/可读 | `fx/particle.py`(949)/`render/gui_base.py`(904)/`ai/narrative.py`(812) | 超大单文件，单文件职责偏重，影响复用与阅读。孵化场可接受；若被高频复制建议按职责拆分（如 particle 拆 emitter/field/io）。 | 参考实现可接受；勿过度工程。 | A |
| G9 | 🟢低 | 运行时耦合 | `ai/dialogue.py:502` | DialogueEngine 调用时才惰性引 ContentGenerator 做 LLM 兜底——合理惰性模式，但把叙事/对话绑死到具体 generator 后端。 | 可抽极薄 `GeneratorBackend` 协议（仅本包内），让对话不依赖具体实现；非必须。 | A |
| G10 | 🟢低 | 死 API 面 | `core/ecs.py:388-415`（set_data/get_data/has_data/clear_data） | World 全局共享数据字典整套 API 在生产中无调用（仅文档示例），是「应为松耦合提供」的预留面（与 Y1 EventBus 同源）。 | 要么接上真实使用，要么降级为可选调试工具并标注。 | A |
| G11 | 🟢低 | 文档/README | `README.md:124` | 状态机行尾悬空脚注标记 `#`（`#` 无对应脚注文本，已并入 Y13）。 | 删除该 `#` 或补脚注。 | D |

---

## 🏗️ 架构影响评估（Archi 产出 + 主理人汇编）

### 正向结论（验证通过，应保留）
- **实测无循环依赖**：82 模块 Tarjan SCC 全部 size=1；子系统级环检测 = none。
- **分层收敛健康**：L0 core（纯净·0 依赖）→ L1 world → L2 systems → L3 render/audio/fx/ai/utils。除「render→world」外全指内聚。
- **纯净核心 + 可选依赖门控到位**：core/audio/fx/utils 对其他子系统零硬依赖；各子包 `__init__.py` 用 `try/except ImportError` 守卫 tkinter/numpy/pygame，顶层 `import allin_engine` 韧性好（Cody 亦列为亮点）。
- **GameEngine 薄装配器**（add_core/world/systems/combat/audio/ai_brain）让消费者按需组合，契合「复制即复用、自包含」。

### 需要调整（均为内部改动，与自身定位冲突）
- **A1 / O4**：god `__init__` 无条件 import 全部子系统，**直接架空了「可选依赖门控 + 薄装配」的自包含收益**——必须让重子系统在包顶层惰性/可选。
- **A2 / Y1**：EventBus/全局数据目前是「参考范式」而非「承重结构」——要么接真实事件流，要么明确降级为扩展点并瘦身臆测事件。
- **A3 / Y9**：render→world 越界，注入数据而非 import 领域类。
- **A4 / R4**：同步 `__all__` 与实际导出，消除「广告取不到」。

### ADR 角度
- ✅ 合理：纯净 core、可选依赖门控、薄装配器、无环分层、双背包/双战斗作「范式展示」——均契合孵化场定位。
- ⚠️ 需调：上述 A1–A4（内部改动即可，无需任何中心化治理）。

---

## 🧪 测试覆盖评估（Tessa 产出）

### 现有结构
- `test/` 下 14 文件：11 个 `test_*.py`（约 291–309 用例）+ `run_all.py`（编排器）+ `runner.py`（自研运行器，含超时）+ `probe.py`（smoke）。
- 框架为**自研**（`TestRunner`，非 pytest/unittest）；CI 仅装 `numpy`，**未集成 coverage**。
- 每个测试文件质量**整体偏高**：有真实 assert、覆盖正常路径 + 边界（越界/空输入/非法事件/clamp）+ 序列化往返。

### 各子系统覆盖
| 子系统 | 生产行数 | 测试 | 评价 |
|---|---|---|---|
| core (ECS/事件总线/循环) | 1,775 | test_core+test_decision | ✅ 好（含边界） |
| world | 1,834 | test_world | ✅ 好 |
| systems | 4,625 | test_systems+combat+command+mod_loader | ✅ 好（crafting/input/simple_combat/stackable 缺） |
| render | 2,971 | test_render | ⚠️ 中（animation 0 测试、formula_engine 仅 import 冒烟） |
| audio | 1,142 | test_audio | ✅ 好 |
| ai | 3,602 | test_ai | ✅ 好（网络生成路径未测，可接受） |
| fx | 1,198 | — | ❌ 完全无测试 |
| utils | 1,197 | test_font(仅 font) | ❌ text_fmt/json_loader/logger 全缺 |

### 关键风险裸奔点
- ✅ ECS / 事件总线 / AI·Decision / Combat / Command / ModLoader / Audio / World / 渲染核心 —— 测试充分，**不应**列入债。
- ❌ **`world/pathfinding.py`（R2）**：核心算法裸奔，复制复用风险最高。
- ❌ **`render/animation.py` + `formula_engine.py`**（O6/O11）：渲染管线延伸无保护。
- ❌ **`fx/particle*` + `systems` gameplay**（O5/O7）：约 6.5k 行无测试。
- ⚠️ **CI 假绿**（R3/O8）：run_all 不返回非零 + font 静默 pass，使现有 291 用例价值归零。

---

## 💳 债务清单 + 优先级（工作流 5，Priority = (Impact + Risk) × (6 − Effort)）

> Impact/Risk/Effort 均 1–5 评分；优先级越高越先修。

| 债务项（合并后） | I | R | E | 优先级 | 阶段 |
|------|---|---|---|--------|------|
| D1 formula_engine exec 任意代码（R1） | 5 | 5 | 2 | **40** | P0 |
| D3 run_all 不报失败 → CI 假绿（R3） | 4 | 4 | 1 | **40** | P0 |
| D2 `__all__` 契约断裂 15 不可导入（R4） | 4 | 4 | 2 | **32** | P0 |
| D4 pathfinding 核心算法裸奔（R2） | 4 | 4 | 2 | **32** | P0 |
| D6 mod_loader 路径穿越（O2） | 4 | 4 | 2 | **32** | P0 |
| D7 save_load 伪加密 base64（O3） | 3 | 3 | 1 | **30** | P1 |
| D8 serializable 嵌套反序列化坏（O1） | 4 | 3 | 2 | **28** | P1 |
| D14 mod JSON schema 未文档化（O10） | 3 | 3 | 2 | **24** | P1 |
| D15 CI 缺失依赖静默 pass（O8） | 3 | 3 | 2 | **24** | P1 |
| D5 god __init__ 无条件 import（O4） | 4 | 3 | 3 | **21** | P2 |
| D13 子系统示例缺失（O9） | 3 | 2 | 2 | **20** | P2 |
| D9 EventBus 三重问题（Y1） | 3 | 3 | 3 | **18** | P2 |
| D10 fx 粒子无测试（O5） | 3 | 3 | 3 | **18** | P2 |
| D11 render animation 无测试（O6） | 3 | 3 | 3 | **18** | P2 |
| D12 systems gameplay 无测试（O7） | 3 | 3 | 4 | **12** | P3 |

> 其余 🟡/🟢 项（Y2–Y16、G1–G11）多为局部正确性/一致性/组织类，建议并入对应阶段或作为日常清理，不单列优先级公式。

---

## 🗓️ 分阶段修复计划

**P0（复制分发前必修，约 1–2 天）**
1. D1：formula_engine 删/加固 exec 回退 + asteval 锁版本（Y8）。
2. D3 + D15：run_all 加 `sys.exit(failed>0)` + runner 实现 SKIPPED 报告（顺带修 Y14 脚本损坏）。
3. D2 + R4：对齐 `__all__` 与顶层 import，补 combat/__init__ re-export。
4. D4：新增 `test_pathfinding.py`（4/8 连通、封闭返回 None、加权最短路、确定性）。
5. D6：mod_loader 加路径穿越校验。

**P1（稳定性与可信度，约 2–3 天）**
6. D7：save_load 改名去「加密」措辞。
7. D8：serializable 用 `get_type_hints` 解析真实类型。
8. D14：新增 `systems/MOD_SCHEMA.md`。
9. D15 已在 P0 覆盖。

**P2（可维护性，约 3–5 天）**
10. D5：重子系统惰性/可选导入。
11. D13：补 4 个高复用 example。
12. D9：EventBus 接真实事件流或降级+瘦身臆测事件。
13. D10/D11：补 particle / animation 测试。

**P3（测试补强，持续）**
14. D12 及 Y2/Y3/Y4/Y15 等：systems gameplay 测试、json_loader 深拷贝+测试、data_library id 判定、logger 统一、text_fmt 测试。

---

## ✅ 行动清单（按优先级排序）

| # | 行动 | 负责角色 | 紧急度 | 预期完成 |
|---|------|---------|--------|---------|
| 1 | 修 `formula_engine.py` 的 exec 任意代码执行（清 `__builtins__` 或删回退），并锁 `asteval>=1.0` | Cody（代码） | P0 | 复制分发前 |
| 2 | `run_all.py` 加 `sys.exit(failed>0)` + runner 实现 SKIPPED 报告，修 `pyproject` 的 `allin-test` 脚本损坏 | Tessa（测试）+ Cody | P0 | 复制分发前 |
| 3 | 对齐根包 `__all__` 与顶层 import（补 15 个不可导入名 + combat re-export） | Cody + Docu | P0 | 复制分发前 |
| 4 | 新增 `test_pathfinding.py` 覆盖 A*/Dijkstra/封闭返回 None | Tessa | P0 | 复制分发前 |
| 5 | `mod_loader.py` 加路径穿越校验（commonpath 守卫） | Cody | P0 | 复制分发前 |
| 6 | `serializable.py` 用 `get_type_hints` 修复嵌套反序列化；`save_load` 去「加密」误导措辞 | Cody | P1 | 1 周内 |
| 7 | 重子系统（render/audio/ai）改为惰性/可选导入，保住可选依赖门控收益 | Archi + Cody | P2 | 2 周内 |
| 8 | 补 4 个高复用 example + `systems/MOD_SCHEMA.md` | Docu | P2 | 2 周内 |
| 9 | EventBus 接真实事件流或明确降级为扩展点并瘦身臆测事件 | Archi + Cody | P2 | 3 周内 |
| 10 | 补 particle / animation / systems gameplay 测试 + json_loader 深拷贝 + logger 统一出口 | Tessa + Cody | P2–P3 | 持续 |
| 11 | README 数据刷新（测试数/行数/Pillow/决策表名）+ 双战斗/双背包补「何时用哪个」指引 | Docu + Archi | P2 | 2 周内 |

---

## ⚠️ 待完善 / 已知局限

- **未跑实际测试/coverage**：本次为静态全量审查，未执行 `python -m allin_engine.test.run_all` 或 `coverage.py`（且 CI 未集成 coverage）。覆盖率数字为 Tessa 基于文件/用例的结构化估算（~70% 关键路径），非实测。
- **未运行代码**：所有发现基于静态精读 + AST import 图解析，未在 dwarf_scrolls 等下游验证「复制即复用」实际受影响面（R4/D2 的「取不到」是经 `from allin_engine import X` 验证的，其余为结构推断）。
- **严重度为主观对齐**：四位成员原始评级口径略有差异（如 `__all__` 断裂 Docu 评🔴、Archi 评🟡），主理人按「最高严重度 + 跨成员合并」原则统一，可能与单一成员原评不同。
- **孵化场定位特殊**：本报告刻意排除了所有「中心化治理」类建议；若未来 allin_engine 转为被多项目依赖的「正式核」，结论需重评（届时需要跨项目 CI/接口冻结，当前约束明确排除）。

---

## 📚 数据来源 & 成员产出索引

- **Cody（代码审查师 / code-reviewer）原始产出**：全量代码审查（安全/性能/正确性/可维护性）+ 代码债/依赖债扫描。🔴1 / 🟠3 / 🟡8 / 🟢6 = 18 条，含 formula_engine exec、serializable 反序列化、mod_loader 路径穿越、save_load 伪加密、EventBus 吞异常、json_loader 共享引用、data_library id 丢弃、logger 缺陷、narrative GameState 冲突、ecs 全局 ID、asteval 下限、各低危项。亮点：零硬依赖 + 可选依赖门控 + 全仓无 eval/pickle/subprocess 等危险 sink。
- **Archi（系统架构师 / architect）原始产出**：架构债 + 架构影响评估。🔴0 / 🟠1 / 🟡5 / 🟢5 = 11 条。正向：无环、分层健康、纯净 core、可选依赖门控。债：god `__init__` 爆炸半径、EventBus 不发射、双战斗/双背包、render→world 越界、示例躺包根、超大单文件、dialogue 惰性引、config 越界、死 API。含 ADR 评估。
- **Tessa（测试专家 / testing-expert）原始产出**：测试覆盖 + 测试债。🔴2 / 🟠5 / 🟡7 = 14 条（绿项不计债）。结构盘点 + 各子系统覆盖率表 + pathfinding 裸奔 + run_all 不退出 + CI 静默 pass + fx/animation/gameplay 无测试 + formula_engine 仅冒烟 + 序列化/json_loader/text_fmt/logger/config 无测试 + pyproject 脚本损坏。附可直接落地的 `test_pathfinding.py` 示例。
- **Docu（技术文档师 / tech-writer）原始产出**：文档债评估。🔴1 / 🟠2 / 🟡7 / 🟢1 = 11 条。亮点：82/82 文件 100% 模块级 docstring。债：`__all__` 契约断裂（🔴）、示例缺失、mod JSON schema 未文档化、README 数据陈旧、build_behavior_tree 名称错、Pillow 无效依赖、config/paths 缺说明、存档格式未说明、悬空脚注。

---

> 本报告由工程保障团队 AI 协作生成，关键决策请由人类工程负责人（全哥）复核。
