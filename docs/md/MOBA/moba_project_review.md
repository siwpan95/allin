# D:/allin/moba 项目评估报告

> 评估时间：2026-06-14 | 全哥的 MOBA 英雄数据与对战模拟平台

---

## 一、项目概览

| 维度 | 数据 |
|------|------|
| 项目定位 | 多游戏 MOBA 英雄数据库 + D&D 5e 角色卡系统 + 1v1 对战 GUI 平台 |
| 数据规模 | **15 款游戏、1503 位英雄、1500 张角色卡** |
| 代码量 | 8 个 Python 文件、3,480 行核心代码 |
| 数据量 | 1518 个 JSON 文件 + 19 个 MD 文档 + 21 个 TXT 列表 |
| 启动方式 | `cd battle_platform && python main.py` |

**一句话总结：** 一个野心勃勃的个人项目，从数据收集、数值体系设计到 GUI 应用全线自建，骨架完整且可运行，但工程化水平有明显提升空间。

---

## 二、架构分析

### 2.1 数据流设计 ⭐⭐⭐⭐

```
原始数据(15个游戏JSON) → 统一分析(all_heroes_unified.json) → D&D角色卡(1500张) → GUI对战平台
```

这是一个非常清晰的数据管道设计，各阶段产出物明确：

| 阶段 | 输入 | 输出 | 模块 |
|------|------|------|------|
| 数据采集 | 各游戏官方数据 | `heroes.json`×15 | 各游戏目录 |
| 数据统一 | 分散的 JSON | `all_heroes_unified.json` | `_analysis/` |
| 数值转换 | 统一英雄表 | 1500张 D&D 角色卡 | `_design/card_generator.py` |
| 交互应用 | 角色卡 | GUI 对战 | `battle_platform/main.py` |

**优点：** 每一步的输入输出都是文件，可独立运行、独立验证，不耦合。

### 2.2 模块职责 ⭐⭐⭐

| 模块 | 职责 | 行数 | 评价 |
|------|------|------|------|
| `hero_calculator.py` | 纯 D&D 数值计算引擎 | 483 | 最干净的模块，职责单一 |
| `card_generator.py` | 角色卡批量生成 | 713 | 技能数据库过大，应拆分为数据文件 |
| `card_tool.py` | CLI 管理工具 | 625 | argparse 规范，命令分离清晰 |
| `main.py` | GUI 对战平台 | 1042 | UI + 逻辑混在一起，单文件过大 |
| `hero_name_mapping.py` | 汉化映射表 | 566 | 纯数据，应该用 JSON/CSV 而非 Python |

### 2.3 主要架构问题

**问题一：代码重复 — 两套战斗引擎**

`hero_calculator.py` → `CombatSimulator` 和 `battle_platform/main.py` → `BattleEngine` 是两个独立实现的 D&D 伤害计算公式。公式相同但实现分离，意味着修改公式需要改两个地方。

**建议：** 将 `CombatSimulator` 提取为共享模块，GUI 直接引用。

**问题二：技能数据库内联在源码中**

`card_generator.py` 第 104-387 行是一个 280+ 行的硬编码字典，包含 LOL/Dota2/王者荣耀/MLBB/SMITE/HOTS/AOV/Pokemon/Onmyoji/VG/Marvel/YHZR 共 12 款游戏的约 300 个英雄技能数据。

**建议：** 每个游戏拆分为独立 JSON 文件 (如 `_design/skills/lol.json`)，按需加载。

**问题三： `main.py` 单文件 1042 行**

UI 构建 (`_create_ui`)、战斗模拟 (`BattleSimulator`)、英雄加载 (`HeroLoader`)、战斗引擎 (`BattleEngine`) 全部塞在一个文件里。

**建议：** 拆分为 `engine.py` / `simulator.py` / `loader.py` / `ui.py`，`main.py` 只做入口。

---

## 三、数值设计 ⭐⭐⭐⭐⭐

这是整个项目最亮眼的部分。

### 3.1 D&D 5e 融合得自然

将桌面 RPG 的六维属性(STR/DEX/CON/INT/WIS/CHA)、购点系统(27点)、熟练加值、豁免检定，全部映射到 MOBA 数值场景。设计文档 (`01_DND数值框架.md`) 质量很高，273 行的深度设计：

- 六维属性 → MOBA 效果映射表有理有据
- 购点模板为六大职业各定制了合理的分配方案
- HP/AC/ATK/AP 公式有明确的数学推导
- 1-18 级成长曲线与 D&D 熟练加值对齐

### 3.2 平衡性设计

```
HP_SCALE = 10          # D&D血量 ×10 = MOBA血量
DAMAGE_SCALE = 0.35    # 伤害倍率，延长战斗回合
物理伤害 = ATK × (1 − AC×0.005)   [最低30%]
法术伤害 = AP × 倍率 × (1 − WIS豁免×0.03)  [最低30%]
暴击率 = 10% + DEX调整×2%   [最低5%]
暴击伤害 = 150% + DEX调整×5%
```

- 有伤害下限保护(30%)，防止高护甲完全免疫
- 暴击概率/伤害与 DEX 挂钩，符合直觉
- 等级补偿机制(`active_damage_scale`)防止高级别战斗过于拖拉

### 3.3 小瑕疵

购点后的 `randomize_scores(variation=3)` 给每个英雄 ±3 的属性随机波动。这在 1500 张卡的规模下会产生显著的数值方差。建议将 variation 降到 1，或者干脆移除随机波动，让同一职业的英雄有统一的基准属性。

---

## 四、代码质量逐文件评估

### 4.1 `hero_calculator.py` — ⭐⭐⭐⭐ 良好

```python
# 亮点
- 使用 @dataclass 定义 HeroStats，类型清晰
- HeroBuilder 的 builder 模式设计合理
- 函数短小，单一职责
- 中文注释与文档字符串齐全

# 不足
- ASI 处理逻辑在 simulate_level_up 中不完整（只计数未真正加属性）
- print_sheet 中硬编码了表格宽度，换到非等宽字体会错位
```

### 4.2 `card_generator.py` — ⭐⭐⭐ 合格

```python
# 亮点
- 技能数据库覆盖面广（12 款游戏，~300 英雄的真实技能）
- get_skills 的回退机制设计合理（真实数据 > 通用模板）
- calc_combat_stats 正确处理了 HP_SCALE

# 不足
- 技能数据库占用 280 行源码，应外置为数据文件
- generate_character_card 函数 78 行，偏长
- random.seed(rng_seed) 虽保证了可复现，但耦合了随机状态
```

### 4.3 `card_tool.py` — ⭐⭐⭐⭐ 良好

```python
# 亮点
- argparse 子命令设计规范，帮助信息完整
- validate 命令检查了必填字段、属性结构、数值范围
- status 命令的可视化输出友好（含进度条和统计）

# 不足
- cmd_info 的卡片加载用了两层 os.path.join 拼接，可封装
- cmd_add_game 里用了 input() 交互，阻塞式不太优雅
```

### 4.4 `main.py` (battle_platform) — ⭐⭐⭐ 合格

```python
# 亮点
- 暗色主题 UI 审美在线（#0d1117 / #161b22 / #21262d）
- 字体加载做了多层回退（项目字体 → 系统字体）
- 动画战斗 + 快速模拟两种模式
- 游戏/位置/搜索 三层筛选逻辑正确

# 不足
- 1042 行全塞一个文件，UI 构建和战斗逻辑完全耦合
- _hero_act 方法 88 行，职责过多（选技能 + 算伤害 + 暴击 + 治疗 + 日志）
- 没有 try/except 保护文件加载，HeroLoader 静默吞异常
- 战斗日志用 Canvas.create_text 逐行绘制，日志多了性能会下降
- self.stats1/self.stats2 在 BattleSimulator 和 BattlePlatform 中通过索引访问，容易出错
```

### 4.5 `hero_name_mapping.py` — ⭐⭐ 数据文件冒充代码

566 行全是字典常量 `HERO_NAME_CN = {"英文名": "中文名", ...}`，没有逻辑。这不是 Python 代码的职责，建议改为 `hero_names.json`。

---

## 五、数据规模与完整性

| 维度 | 数值 | 评价 |
|------|------|------|
| 游戏覆盖 | 15 款 | 覆盖面广，从主流到小众 |
| 英雄总数 | 1503 | 规模可观 |
| 角色卡 | 1500 张 | 覆盖率高 |
| 汉化映射 | 526 条 (6 款游戏) | 还剩 9 款游戏未完全汉化 |
| 真实技能 | ~300 位知名英雄 | 覆盖率约 20%，其余为模板填充 |
| 设计文档 | 2 份深度文档 | 质量高 |
| 测试 | 0 | 没有任何测试 |

**数据亮点：** 跨游戏角色统一归类（六大通用角色）做得很扎实，`角色框架分析.md` 中的分布统计和克制矩阵有实际参考价值。

---

## 六、综合评价

| 评估维度 | 分数 | 评语 |
|----------|:----:|------|
| 创意与野心 | 9/10 | 从零搭了一个 MOBA 数值宇宙，思路独特 |
| 数值设计 | 8/10 | D&D 融合自然，公式体系完整，有平衡考量 |
| 文档质量 | 8/10 | 设计文档和 README 写得很认真 |
| 代码结构 | 5/10 | 单文件过大、代码重复、UI 耦合严重 |
| 代码质量 | 5/10 | 能跑，但缺测试、缺错误处理、魔术数字多 |
| 数据工程 | 6/10 | 数据量大，但部分数据内联在源码中 |
| 可维护性 | 4/10 | 公式改一处需同步两处，技能改需改源码 |
| 可扩展性 | 5/10 | 新增游戏流程清晰，但引擎耦合制约 |

**总评：6.1/10 — 及格偏上，骨架扎实但欠打磨**

---

## 七、改进路线图（按优先级）

### 🔴 高优先级 — 影响可维护性

1. **提取共享战斗引擎。** 将 `hero_calculator.py` 的 `CombatSimulator` 提取为独立模块，让 GUI 引用而非重写。
2. **拆分 `main.py`。** 按类拆成 4 个文件：`engine.py` / `simulator.py` / `loader.py` / `ui.py`。
3. **技能数据库外置。** 将 `card_generator.py` 中的 12 个技能字典拆为 `_design/skills/*.json`。

### 🟡 中优先级 — 提升代码质量

4. **添加错误处理。** `HeroLoader.load_all_heroes()` 的 `try/except: continue` 应该至少打印警告。
5. **移除随机变异或降低幅度。** `randomize_scores(variation=3)` → `variation=1`，减少数值方差。
6. **添加类型注解。** `card_generator.py` 基本没有类型注解，`generate_character_card` 返回 `dict` 而非 TypedDict。

### 🟢 低优先级 — 锦上添花

7. **写几个基础测试。** 至少测 `ability_modifier()`、`calc_combat_stats()` 等纯函数。
8. **`hero_name_mapping.py` → `hero_names.json`。** 纯数据文件不应是 Python 代码。
9. **日志性能优化。** `Canvas.create_text` 逐行追加 → 使用 `tk.Text` 或虚拟滚动。
10. **打包成 exe。** 用 PyInstaller 打包，方便分发（你已经会这个）。

---

## 八、一句话说给全哥

> 这项目的地基打得不错——15 款游戏、1500 张卡、一套自洽的 D&D 数值体系——但代码组织还在「能跑就行」的阶段。把战斗引擎统一了、把 1042 行的巨无霸拆了、把技能数据提出去，这个项目就能从「个人玩具」升级成「可维护的工程」。骨架是对的，该打磨了。

---

*WorkBuddy 评估 | 2026-06-14*
