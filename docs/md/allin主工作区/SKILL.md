---
name: tavernrogue-project
description: Maintain and evaluate the TavernRogue project (D:/allin/not/OK/TavernRogue). Use when the user asks about TavernRogue, requests evaluation, bug fixes, feature additions, or balance changes for this single-player auto-battler roguelike.
agent_created: true
---

# TavernRogue 项目维护

## 概述

TavernRogue 是一个以《酒馆战棋》为核心机制、以《杀戮尖塔》式单人爬塔为循环、用 D&D SRD 做版权包装的 Roguelike 自走棋。项目使用 Python + pygame-ce 实现，主入口为 `run_gui.py`。

本技能提供项目结构、常见测试命令、已知陷阱和评估/修复流程，帮助后续会话快速接手而不需要重新探索代码库。

## 项目结构

```
D:/allin/not/OK/TavernRogue/
├── run_gui.py              # 主入口
├── game/
│   ├── engine.py           # BattleEngine 自动战斗（事件队列）
│   ├── recruit.py          # RecruitSystem 招募逻辑
│   ├── hero.py             # Hero 基类与 5 职业
│   ├── map_manager.py      # 地图生成
│   ├── node_handler.py     # 节点分发（也可用于 CLI/后端）
│   ├── events.py           # 事件系统
│   ├── relics.py           # RelicSystem 宝物系统
│   ├── rewards.py          # RewardSystem 奖励
│   └── persistence.py      # 局外成长：存档、职业解锁、进阶
├── ui/
│   ├── app.py              # 应用外壳与 SceneManager
│   ├── game_manager.py     # 中央 Model 与状态代理
│   ├── renderer.py         # 共享渲染工具
│   └── scenes/             # 各场景：recruit, map_scene, battle, shop, camp, event_scene, treasure, reward, end_scenes, menu
└── data/
    ├── adventurers.json    # 冒险者（1-6 星，共 36 个）
    ├── enemies.json        # 敌人（含 5 精英、4 Boss，共 21 个）
    ├── relics.json         # 宝物（10 个）
    ├── events.json         # 事件（12 个）
    └── map_templates.json   # 地图模板
```

## 核心状态约定

- `GameManager.health` 与 `GameManager.gold` 是 **property**，代理到 `self.hero.health` 与 `self.hero.gold`。不要直接修改 `self._health` / `self._gold`（除非英雄不存在）。
- `self.gm.board` 是持久阵容；战斗场景使用 `copy.deepcopy(self.gm.board)` 作为临时副本，战斗结果不反向同步损伤（符合 Battlegrounds 模式：每场战斗后阵容重置）。
- `GameManager` 与 `RecruitSystem` 通过 `sync_to_recruit()` / `sync_from_recruit()` 保持手牌/场上/铸币一致。
- `GameManager` 在 `__init__` 时接受 `progress_manager: ProgressManager`；`ui/app.py` 已创建并传入。新游戏会根据当前职业进阶等级应用 `difficulty_params`（敌人属性缩放、英雄额外生命）。
- 单局结束后，`GameOverScene` / `VictoryScene` 的 `enter()` 会自动调用 `gm.record_run()` 写入存档。
- 存档文件位于 `D:/allin/not/OK/TavernRogue/saves/progress.json`，包含 `unlocked_classes`、`advancements`、`best_records`、`run_history`、`relic_unlocks`。

## 常见测试命令

每次修改后优先运行：

```bash
# 语法检查
cd "D:/allin/not/OK/TavernRogue" && python -m py_compile game/*.py ui/*.py ui/scenes/*.py

# 关键模块导入
cd "D:/allin/not/OK/TavernRogue" && python -c "import sys; sys.path.insert(0, '.'); from ui.app import TavernRogueApp; print('ok')"

# 自动战斗测试（无 UI）
cd "D:/allin/not/OK/TavernRogue" && python -c "
import sys; sys.path.insert(0, '.')
from game.engine import BattleEngine
be = BattleEngine()
allies = [{'id':'a1','name':'守卫','attack':2,'health':5,'keywords':['GUARD'],'script':{}}]
enemies = [{'id':'e1','name':'小怪','attack':1,'health':2,'keywords':[],'script':{}}]
print(be.simulate_battle(allies, enemies))
"
```

## 已知陷阱

1. **事件宝物拼写**：`game/events.py` 中的 `gain_relic` 分支曾把 `relics` 拼成 `reics`，已修复。后续若出现 `NameError` 优先检查此处。
2. **RelicSystem import**：`game/node_handler.py` 需要 `from game.relics import RelicSystem`，否则实例化报错。
3. **健康/铸币不同步**：任何 UI 状态条与英雄实际状态不一致，先检查 `GameManager.health` / `GameManager.gold` 是否正确代理到 `hero`。
4. **BattleScene 手动战斗**：旧版本 `BattleScene` 是手动点击打人，未调用 `BattleEngine`。若发现关键词/宝物不生效，检查是否误改回手动逻辑。
5. **种族共鸣与宝物**：`BattleEngine.apply_tribe_effects()` 和 `RelicSystem.apply_battle_start_effects()` 需要在战斗开始前调用；`BattleScene` 已自动处理，`node_handler` 也已处理。
6. **牧师技能未接入**：`Hero.on_ally_death()` 存在但战斗引擎尚未调用，需要后续接入。
7. **DODGE / double attack 未生效**：战斗引擎没有使用 `dodge_chance` 和 `double_attack_chance`，需要后续接入。
8. **新增战吼/亡语类型**：`engine.py` 现支持 `damage_random`、`damage_all`、`heal_all`、`buff_all` 战吼，以及 `damage_random`、`damage_all` 亡语。添加新 script 类型时需要同步扩展 `_trigger_battle_cry` / `_handle_deathrattle`。
9. **事件新效果**：`events.py` 现支持 `damage_hero`、`heal_hero`、`upgrade_board`、`purify_board`、`enchant_board`、`regenerate_map`。`ui/scenes/event_scene.py` 也需要同步处理，否则 UI 事件不生效。
10. **难度缩放**：`GameManager.scale_enemies()` 在 `BattleScene.enter()` 中调用。若直接测试 `BattleEngine` 而不经 `GameManager`，需要手动缩放。
11. **存档覆盖**：`ProgressManager` 默认写入 `saves/progress.json`。测试时建议传入 `save_file` 参数指向临时文件，避免污染真实进度。

## 评估与修复流程

当用户要求“评估 TavernRogue”或“对照方案检查进度”时：

1. 读取 `D:/allin/not/OK/TavernRogue/be like.txt`（项目方案）作为基准。
2. 统计 `data/*.json` 的内容数量：冒险者、敌人、宝物、事件、地图模板。
3. 检查 `game/engine.py` 支持的关键词与方案对照。
4. 检查 `ui/scenes/battle.py` 是否调用 `BattleEngine.simulate_battle()`。
5. 检查 `GameManager` 与 `Hero` 状态同步。
6. 运行语法检查和模块导入测试。
7. 输出评估报告到 `C:/Users/13122/WorkBuddy/<workspace>/TavernRogue_项目评估报告_修订版.md`（或用户指定路径）。

## 扩展建议

- 内容缺口已大幅补齐：冒险者 36 个（1-6 星）、敌人 21 个（5 精英 4 Boss）、事件 12 个、宝物 10 个。后续可着重做数值平衡和美术/音效。
- 局外成长已实现核心：存档、职业解锁链、进阶 0-5 级难度缩放、最佳记录、最近历史。可继续扩展：冒险日志 UI、成就系统、宝物解锁限制、每日挑战。
- 战斗引擎仍缺的机制：DODGE 闪避、double_attack_chance 先攻/连击概率、牧师 `on_ally_death()` 接入、召唤（亡语 `summon` 尚未真正生成单位）、CLEAVE / BLOOD_FURY 等高级关键词。
- 招募 UI 缺少手动站位调整与术士生命分流按钮；事件 UI 已支持多选项分支，但缺少结果反馈弹窗。
