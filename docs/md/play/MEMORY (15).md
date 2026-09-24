# Play Project Memory

## 项目概览
- 路径: D:/allin/play
- 类型: 放置挂机 RPG（放置拼好团 ASCII 版）
- 技术栈: Python + Tkinter + openpyxl
- 代码量: ~3,500 行 / 17 模块

## 已修复问题 (2026-06-05)
- `Rarity.order` 属性：支持数值比较，修复 `_auto_equip` 装备替换 bug
- `_make_bar`：颜色分支用 █/▓/░ 区分
- `GameState.item_dict`：公开属性替代 `state._item_dict`
- `GameState.load()`：合并 roster 链接 + legacy bonus + 首次解锁，返回完整可用状态
- `data_loader.py`：`except pass` → `logger.warning()`
- `narrative.py`：f-string → 普通字符串模板
- `DungeonPanel`：`dungeons` 移入构造函数，`render()` 无参数，统一接口
- `__init__.py`：5个包添加模块导出

## 战斗系统策略 (2026-06-05)
- BossAttackStrategy 协议 + 2实现: `default_boss_attack`(随机), `focused_boss_attack`(集火低血)
- HealerStrategy 协议 + 2实现: `default_healer_ai`(奶最弱), `tank_priority_healer_ai`(优先坦克)
- `BattleSystem(strategy=...)` 可注入策略

## 架构特点
- Core / Systems / UI 三层分离
- 数据驱动: Excel → JSON → 内置默认 三级回退
- AutoPlayController 回调模式
- logging 统一日志 (DEBUG stderr)
