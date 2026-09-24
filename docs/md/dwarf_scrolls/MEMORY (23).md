# 项目级长期记忆：dwarf_scrolls

## 项目定位
- `D:\allin\dwarf_scrolls` 是以 `allin_engine` 为**地基**构建的游戏项目（矮人要塞画风的
  上古卷轴 kalpic 编年史 + 可玩泰姆瑞尔游历）。本质是**测引擎能力边界**的试验场，
  不是把引擎当外部依赖。引擎物理内联于 `dwarf_scrolls/allin_engine/`，自包含。
- 验证必须用**本地 Python**（`C:/Users/13122/AppData/Local/Programs/Python/Python314/python.exe`，
  有 tkinter + DISPLAY 可真跑 GUI）；托管 Python 忽略 PYTHONPATH，不可用。
- 运行前需 `sys.path.insert(0, r'D:/allin')`；`core/engine_bootstrap.py` 触发内联引擎优先。

## git 提交约定（重要）
- 历史用**英文 conventional commits + 阶段标签**：`chore:` / `fix(Px):` / `test(Px):` /
  `feat:` / `refactor:`。参考 `git log`。
- 大块相关改动按**逻辑拆成多个提交**而非一坨（如 引擎内联地基 / 游戏特性 分两次）。
- `.gitignore` 忽略 `__pycache__/`、`saves/`、`data/`、`assets/`、`config/`、`logs/`；
  `allin_engine/fonts/`（约 51M）**不**在忽略列表，随引擎内联进仓库。
- 提交前清理临时脚本（如 `gen_shots.py`），勿一起提交。

## 游历模式（play_core.py）架构速查
- `PlayEngine` 装配 `GameEngine`（ECS World + EventBus + FixedTimestepLoop）。
  玩家实体组件：Position/Health/Clock/Alignment/Allegiance/Gear/Satchel/Pack/Lore/PlayLog/CommandQueue。
- 系统：TravelSystem(高优) / RestSystem / ExplorationSystem / EncounterSystem /
  CombatSystem。事件：PLAYER_MOVED/MOB_SPAWNED/MOB_DEFEATED/COMBAT_START/PLAYER_DIED/SHARD_FOUND/SHARD_HIDDEN。
- 誓言：`Allegiance(kind, prince)`。aedric 封锁 evil 省；daedric 封锁 good 省，且 `prince`
  取五大魔神之一（azura/dagon/molag/sheo/mora），各带战斗/探索修正。
- **主线分歧**：`HIDDEN_CHAPTER`(中立默认) / `AEDRIC_EPILOGUE`(圣灵) / `PRINCE_EPILOGUE[prince]`
  (五大魔神)。`_epilogue_for(allegiance)` 分流；`build_lore_view` 终章横幅随誓言变。
  九省隐秘集齐（`Lore.revealed`）即揭示对应主线终章。
- 邻接：`ADJACENCY` 为**显式字典**（贴合 TES 真实地理），视觉 `MAP_GRID` 仅装饰，勿再由地图推导。
- 存档：`to_snapshot/from_snapshot` + `core/save_manager.PlaySaveManager`（saves/play.json），
  GUI 启动续局 + "🆕新游戏"。
- 测试：`tests/test_play_core.py`（66 passed 全套）覆盖装配/移动/事件/死亡/四特性/邻接/隐藏剧情/魔神分支/主线分歧/快照。
