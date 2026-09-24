# MOBA 项目记录

## 项目路径
D:/allin/moba — MOBA 英雄数据库 + D&D 5e 角色卡 + 1v1 对战平台

## 2026-06-14 重构记录
- P1: 统一战斗引擎 → battle_platform/engine.py
- P2: 拆分 main.py → config/engine/loader/simulator/ui/main 六模块
- P3: 技能数据外置 → _design/skills/*.json (12游戏+模板, 207条记录)
