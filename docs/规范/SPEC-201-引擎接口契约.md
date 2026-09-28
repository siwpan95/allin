# SPEC-201 · 引擎（`allin_engine`）接口契约

> **编号** SPEC-201 ｜ **效力** 准则（跨项目复用契约） ｜ **状态** 生效
> **生效** 2026-08-23 ｜ **最后修订** 2026-09-24 ｜ **适用面** 所有使用统一引擎的项目（含内联副本 dwarf-scrolls / sandbox）
> **承载体** 各仓自身测试与黄金值（`python -m allin_engine.test.run_all`）；引擎改名与双写不变量由人工核对，未机械化
> **引用格式** SPEC-201 §统一引擎

---

## 统一引擎（2026-08-23 起改名 alloy）
> ⚠ **2026-09-22 现盘核对：包名已由 alloy 再次改名 `allin_engine`** —— 提交 `72c1d63`（2026-09-19，`refactor!: 引擎改名 alloy -> allin_engine`）；本机实测为 `/repos/an-engine/allin_engine/`（根层 `core/ world/ systems/ trpg/ …` 为双写镜像），入口现为 **`from allin_engine import GameEngine`**，PyPI 包名 **allin-engine 1.0.0**。
> **本段下方所有 `alloy.*`、`from alloy import`、`pip install -e …\alloy`、`python -m alloy …` 的写法，一律按 `allin_engine` 读**（内联副本 `dwarf-scrolls`/`sandbox` 亦已是 `allin_engine/`）。详见《会话交接_2026-08-27.md》§六十二与《文档与现盘核对报告_2026-09-22.md》。
- 本体路径: /repos/an-engine/（旧名 allin_engine → alloy；过渡 shim 已归档 /archive/allin-engine-shim-2026-08-27；远程仓 siwpan/an-engine）
- 入口: `from alloy import GameEngine`
- 新项目应优先复用 alloy 的模块, 而非从其他项目复制代码
- 示例文件: /repos/an-engine/example_quickstart.py
- 装配: `engine.add_core()/add_world()/add_systems()/add_combat()/add_audio()/add_ai_brain()`，新增 `mount(plugin)/unload(key)`；服务注册表在 `engine.ctx`（Context：注册即回滚）
- **fork 双作用域（2026-08-27 落地）**: `ctx.fork(name)` 命名子作用域（销毁自动摘除、同名重复抛 DuplicateScopeError）；`ctx.fork_install(plugin)` = outer 钩子父作用域只执行一次 + apply 每次独立 fork（多实例玩法复用）；引擎级 `engine.mount_scoped(plugin, config, name=)` / `engine.unmount(name)`，WorldLog 记 plugin.mount/plugin.unmount；依赖方向唯一（fork 可见引擎服务，反向不可见，实例服务走 fork 句柄）
- **TRPG 规则内核（R2，2026-08-27 晚并入；阶段 1/2 已完成）**: D20（D&D-GURPS 角色构建器）的 14 Service + 数据中枢并入 `alloy/trpg/`；入口 `from alloy.trpg import Character, preset_trpg`——`preset_trpg(ctx)` 已注册 `STANDARD_PRESETS["trpg"]`（幂等），`Character(..., ctx=)` 支持注入宿主 Context；多角色 = `ctx.fork(name)` + preset（每角色独立作用域）。适配层 `TrpgContext`（alloy/trpg/context.py）：容器复用 alloy Context、事件骑宿主共享 EventBus、注册即回滚、dispose 逆序退订；D20 的 mini-Cordis/YAML loader/condition 子系统不进引擎。套件 484/484 全绿（`python -m alloy.test.run_all`）。**阶段 1（2026-08-27 深夜完成，已建仓）**：D20 已 shim 化并独立建仓 siwpan/d20（公开+MIT，本地 /repos/d20；d20/ 只剩 5 个转发文件 → alloy.trpg，老 API 100% 兼容；.venv/tests/内核 16 文件/composition.yml 已删；黄金样例 盗贼.txt 12 字段命中）。**阶段 2（深夜完成，5787a9f）**：running-group-simulator 接入 alloy.trpg.dice（core/dice.py 接入层 + success_chance + roll_info 直通；546/546 全绿）。**阶段 3（深夜完成，六仓全推送）**：地城簇六仓（random-dungeon-/dungeon/tavern-rogue/sandbox/text-adventure/hell-below）逐仓勘查结论=**均无 D&D/GURPS 同构骰系**（区间随机/Savage Worlds 骰系/百分比判定/谜题引擎/卡牌驱动）→ 按铁律原则全部「不接入 + README 记账」（各仓 README「规则内核接入判定（R2）」节）；dungeon 恢复标准 MIT、hell-below 修 5 个旧桌面路径探针（_test_all_games 被 s→y 污染已重写）。**阶段 4 + moba 补盘点 + sandbox 同步（2026-08-28 完成）**：dwarf-scrolls/project-root/novel-reader 三仓同样无同构骰系 → 记账不接入（dwarf-scrolls 顺带修复迁仓拍平致应用损坏——包名桥 dwarf_scrolls.py）；**moba_battle_platform（用户补盘点）为 D&D 5e 同构需求方**——内核反向增强（rng 注入 + 通用 NdS roll_dice，an-engine 8b5713a/446ee86）后 moba 接入（cc9b32f），并恢复其被局部回退的 R0 密钥修复；**sandbox 内联 alloy 经 engine.patch.yaml patch 重放升级到当前版（含 trpg，5de8e0b）**——sync 流程：`git archive HEAD alloy` 提取旧版基线作 --reference → `python -m alloy sync <项目> --reference <基线> --dry-run/--apply`；**dwarf-scrolls 同流程升级完成（ae3b342，2026-08-28）**，至此两个内联副本均为当前版。project-root 既有断言失败已修（dd69acb：E1 材料门禁上线后 gui_advanced_flow 未同步，先 _do_gather_materials 再晋升；45/45 全绿）。**反向重构原则（阶段 2 沉淀，铁律级）**：只接真正同构的规则原语（骰子/成功率表等纯函数），模型与专有规则保留仓内——alloy.trpg 是 D&D 六属性口径，与 GURPS 4e 四属性模型异构，绝不为了「接入」破坏行为契约与数据模型；勘查后「无同构原语→记账声明不接入」是合法结论，不是偷懒（阶段 3/4 九仓即此）。**推仓纪律（2026-08-28 沉淀）**：推任何仓前先 `git ls-remote` 查默认分支（moba 是 main 不是 master，曾误推垃圾分支）；`git add -A` 前核对 .gitignore 覆盖 build/dist/egg-info；文档治理后必须实跑一次应用/测试（dwarf-scrolls 损坏被 README 治理遗漏）。
- **an-engine 双写不变量**: 仓库根层（__init__.py/core/test/...）是 alloy/ 规范目录的**镜像，两者都跟踪、必须同步**（fork 提交 6b3dbe7 为双写先例；R2 曾漏改根镜像，3a5afea 补齐）。改 alloy/ 后逐个 Copy-Item 到根并哈希核对。
- **alloy 安装**: `pip install -e /repos/an-engine`（**仓根**，不是 ...\alloy——后者 packages.find 找不到包会装空）；装后 import alloy 全局可用（指向 alloy/ 规范目录，含 trpg）。
- 自省: `python -m alloy dump-profile [--json]`；审计: `python -m alloy dump-log <path>`；副本同步: `python -m alloy sync <项目> --dry-run|--apply`
- 项目内联副本的升级用 patch 重放（engine.patch.yaml + sync --reference/--take-base），定制保留、冲突可见
- 世界事件日志 WorldLog（engine.log）是事实源：存档=快照+日志增量（SaveLoadManager.save_with_log/load_with_log）
- GameState 的玩家状态通过 `gs.player` 访问 (PlayerState), 不是 `gs.state.player_state`
- MapData 创建空地图用 `MapData.empty(cols, rows)`, 不是 `MapData(cols=, rows=)`

