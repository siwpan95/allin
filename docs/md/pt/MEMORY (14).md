# pt/ 项目记忆

## 项目概述
- 项目名：迷失之镜 (Mirror of the Lost)
- 类型：三层架构 TRPG 游戏引擎 → 跑团模拟器
- 位置：D:/allin/pt/
- 架构：GURPS(物理) + Fate(叙事) + Savage Worlds(节奏)
- 核心设计文档：D:/allin/pt/AA/basement.txt
- 升级方案：D:/allin/pt/AA/upgrade_plan.html

## 目录约定
- `AA/` — **实验与归档空间，所有测试/设计/中间文件归入，永不删除**
- `modules/` — 模组池
- `templates/` — Excel 模板母版（玩家+主持人）
- `characters/` — 已导入角色卡 JSON
- `saves/` — 跑团行为存档
- `data/` — 配置数据（enemies/items/traps/events JSON）

## 文件职责
- `mirror_launcher.py` — **启动入口**，模组管理器 + 游戏主循环
- `mirror_mvp.py` — 游戏核心类 MirrorOfLostMVP（不独立运行）
- `system.json` — 全局系统规则（共享）
- `modules/<模组名>/module.json` — 各模组数据

## Excel 生态
- 跑团本质 = 一堆表格。角色卡、敌人、物品、场景、地图全链路用 Excel
- 玩家侧：character.xlsx + 4 个预置角色
- 主持人侧：enemy_builder / item_builder / trap_builder / encounter_table / loot_table / npc_reaction / scene_builder / module_meta / map_grid
- 统一导入器：`data_importer.py`（替代分散的多个 importer）
- Excel 规范：A1 类型标识 / 公式取计算值 / 下拉选项 / 批注不导入

## 运行方式
```bash
cd D:/allin/pt
python mirror_launcher.py               # 正常游玩
python mirror_launcher.py --create-template  # 创建新模组模板
```

## 编码注意
- 全中文输出，Windows 终端用 `sys.stdout.reconfigure(encoding='utf-8')`
- JSON 文件统一 UTF-8
