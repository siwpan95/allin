# 项目记忆：轮盘酒馆

## 项目概述
《轮盘酒馆：德州轮盘自走棋》— 融合德州扑克+俄罗斯轮盘+自走棋+瑞士轮的策略生存游戏。

## 架构 (v2.0)
```
core/        → card_engine, shotgun, game_logic
entities/    → player, ai_player
systems/     → chess_pieces, tournament, events
ui/          → components (Button/PieceCard/BulletWidget), renderer
config/      → *.xlsx + config_loader.py (自动Excel↔JSON)
audio/       → sound_manager.py (读取 D:\allin\tools\sfx\sounds)
main.py      → 入口（完整交互+音效+状态机）
```

## 配置修改流程
修改 config/*.xlsx → 运行游戏自动检测并转换JSON → 即时生效

## 音效素材
位于 D:\allin\tools\sfx\sounds，映射表在 audio/sound_manager.py

## 键盘快捷键
- M: 静音
- Esc: 返回菜单
- 空格: 界面切换（debug模式）

## 已知改进方向
- 7轮可能无人淘汰（调 INITIAL_LIFE 或 LIVE_ROUNDS_MAX）
- 商店交互可增强（拖拽棋子、右键出售）
- 粒子特效/动画可加入
