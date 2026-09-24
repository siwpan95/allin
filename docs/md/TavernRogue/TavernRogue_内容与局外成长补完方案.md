# TavernRogue 内容与局外成长补完方案

> 基于 D&D SRD + 酒馆战棋机制 + 杀戮尖塔爬塔循环
> 评估基准：`be like.txt` 开发路线图第四阶段目标

---

## 一、现状回顾

| 维度 | 当前 | 方案目标 | 缺口 |
|------|------|----------|------|
| 冒险者 | 15 个（1-3 星） | 30+ 个（1-6 星） | -15~18 |
| 敌人 | 7 个（0 精英标注，1 Boss） | 12-15 个（3-5 精英，2-3 Boss） | -5~8 |
| 事件 | 5 个 | 10-15 个 | -5~10 |
| 宝物 | 7 个 | 方案列 7 个（已达标） | 0（建议 +3~5） |
| 局外成长 | 无 | 职业解锁 + 进阶 + 冒险日志 | 全套缺失 |
| 存档系统 | 无 | 本地 JSON | 缺失 |

---

## 二、冒险者补完（3-6 星）

### 2.1 设计原则

- **每个星级每个种族 1 个**，保证 6 种族 x 6 星级 = 36 个（含现有 15 个，需新增 21 个）。
- 星级越高，属性和关键词组合越强；5-6 星为"核心引擎"单位。
- 优先使用战斗引擎已支持的关键词：GUARD、SHIELD、FRENZY、POISON、DODGE、ARMOR、deathrattle、battle_cry。
- 逐步引入新关键词：CLEAVE（横扫）、OVERKILL（过杀）、BLOOD_FURY（血怒/复仇）。

### 2.2 完整冒险者矩阵

#### 1 星（tier: 1，cost: 3, 已完 ✓）

| ID | 名称 | 种族 | ATK/HP | 关键词 |
|----|------|------|--------|--------|
| human_recruit | 人类新兵 | human | 1/2 | — |
| elf_archer | 精灵弓箭手 | elf | 2/1 | — |
| dwarf_warrior | 矮人战士 | dwarf | 1/3 | GUARD |
| dragonborn_scout | 龙裔斥候 | dragonborn | 2/1 | — |
| half_orc_brute | 半兽人暴徒 | half_orc | 3/1 | — |
| tiefling_sorcerer | 提夫林巫师 | tiefling | 1/1 | 亡语:随机1伤 |

#### 2 星（tier: 2，cost: 4, 已完 ✓）

| ID | 名称 | 种族 | ATK/HP | 关键词 |
|----|------|------|--------|--------|
| human_veteran | 人类老兵 | human | 2/3 | — |
| elf_ranger | 精灵游侠 | elf | 3/2 | DODGE |
| dwarf_defender | 矮人防御者 | dwarf | 2/4 | GUARD, ARMOR |
| dragonborn_flamescale | 龙裔焰鳞 | dragonborn | 2/3 | 战吼:随机1伤 |
| half_orc_berserker | 半兽人狂战士 | half_orc | 4/2 | FRENZY |
| tiefling_warlock | 提夫林术士 | tiefling | 2/2 | 亡语:随机2伤 |

#### 3 星（tier: 3，cost: 5, 需补 3 个）

| ID | 名称 | 种族 | ATK/HP | 关键词 | 状态 |
|----|------|------|--------|--------|------|
| human_knight | 人类骑士 | human | 3/5 | GUARD | ✓ |
| elf_assassin | 精灵刺客 | elf | 5/3 | DODGE, POISON | ✓ |
| dwarf_iron_guard | 矮人铁卫 | dwarf | 2/6 | GUARD, ARMOR, SHIELD | ✓ |
| **dragonborn_fire_knight** | **龙裔炎骑士** | dragonborn | 3/4 | GUARD, 战吼:对全体敌人1伤 | **新增** |
| **half_orc_reaver** | **半兽人掠夺者** | half_orc | 5/4 | CLEAVE | **新增** |
| **tiefling_hexer** | **提夫林咒术师** | tiefling | 3/3 | 亡语:随机3伤, 血怒:+1攻 | **新增** |

#### 4 星（tier: 4，cost: 6, 全部新增）

| ID | 名称 | 种族 | ATK/HP | 关键词 |
|----|------|------|--------|--------|
| human_paladin | 人类圣武士 | human | 4/6 | GUARD, SHIELD |
| elf_bladedancer | 精灵剑舞者 | elf | 4/4 | DODGE, FRENZY |
| dwarf_runesmith | 矮人符文匠 | dwarf | 3/7 | GUARD, ARMOR, 战吼:友军+1/+1 |
| dragonborn_stormcaller | 龙裔唤雷者 | dragonborn | 4/5 | 战吼:随机3伤, 龙裔共鸣翻倍 |
| half_orc_bloodrager | 半兽人嗜血者 | half_orc | 7/3 | FRENZY, OVERKILL:额外攻击一次 |
| tiefling_soulbinder | 提夫林缚魂师 | tiefling | 3/4 | 亡语:随机4伤, 血怒:+1/+1 |

#### 5 星（tier: 5，cost: 7, 全部新增）

| ID | 名称 | 种族 | ATK/HP | 关键词 |
|----|------|------|--------|--------|
| human_champion | 人类冠军斗士 | human | 6/8 | GUARD, ARMOR |
| elf_moon_warden | 精灵月卫 | elf | 6/5 | DODGE, POISON, FRENZY |
| dwarf_earthbreaker | 矮人裂地者 | dwarf | 4/10 | GUARD, ARMOR, SHIELD, 亡语:召唤2个矮人战士 |
| dragonborn_elderscale | 龙裔古鳞 | dragonborn | 6/7 | GUARD, 战吼:对全体敌人2伤 |
| half_orc_warlord | 半兽人战争领主 | half_orc | 9/6 | FRENZY, CLEAVE |
| tiefling_doombringer | 提夫林末日使者 | tiefling | 5/5 | 亡语:随机6伤, 血怒:+2/+2 |

#### 6 星（tier: 6，cost: 8, 全部新增）

| ID | 名称 | 种族 | ATK/HP | 关键词 |
|----|------|------|--------|--------|
| human_legend | 人类传奇英雄 | human | 8/12 | GUARD, ARMOR, SHIELD, 战吼:全体友军+2/+2 |
| elf_eclipse | 精灵日蚀猎手 | elf | 10/6 | DODGE, POISON, FRENZY, CLEAVE |
| dwarf_ancient_guardian | 矮人远古守护者 | dwarf | 6/16 | GUARD, ARMOR, SHIELD, 亡语:全体友军+2/+2 |
| dragonborn_dragon_lord | 龙裔龙王 | dragonborn | 8/10 | GUARD, 战吼:全体敌人4伤, 龙裔:全体+2攻 |
| half_orc_destroyer | 半兽人毁灭者 | half_orc | 12/8 | FRENZY, CLEAVE, OVERKILL:攻击+2 |
| tiefling_archfiend | 提夫林大魔 | tiefling | 7/7 | 亡语:随机8伤, 血怒:+3/+3, 亡语召唤3/3小鬼 |

### 2.3 关键词补充说明

需要在 `game/engine.py` 中新增的战斗关键词：

| 关键词 | 英文常量 | 效果 | 优先级 |
|--------|----------|------|--------|
| 横扫 | CLEAVE | 攻击时对目标两侧敌人各造成 1 点伤害 | 中 |
| 过杀 | OVERKILL | 若造成超额伤害（目标HP<伤害值），触发额外效果 | 低 |
| 血怒 | BLOOD_FURY | 友方单位死亡后触发效果 | 高（需改战斗引擎） |

### 2.4 JSON 数据示例（新增 3 星补齐）

```json
{
  "id": "dragonborn_fire_knight",
  "name": "龙裔炎骑士",
  "tribe": "dragonborn",
  "tier": 3,
  "attack": 3,
  "health": 4,
  "keywords": ["GUARD"],
  "script": {
    "battle_cry": {
      "type": "damage_all",
      "value": 1
    }
  },
  "cost": 5
}
```

---

## 三、敌人补完

### 3.1 设计原则

- 地图有 9 层，目前只有 tier 1-3 普通怪 + 1 个 tier 6 Boss。
- 需要在 `enemies.json` 中增加 `is_elite: true` 字段支持（现有数据无此字段，但 `node_handler` 通过节点类型判断）。
- 每层敌人池应根据地图层数分配。

### 3.2 新增普通敌人

| ID | 名称 | Tier | ATK/HP | 关键词 | 掉落 |
|----|------|------|--------|--------|------|
| giant_rat_swarm | 巨鼠群 | 1 | 2/3 | — | 3 金 |
| zombie | 僵尸 | 1 | 1/4 | 亡语:随机1伤 | 4 金 |
| bandit_archer | 强盗弓箭手 | 2 | 3/3 | DODGE | 5 金 |
| cultist_acolyte | 邪教徒侍僧 | 2 | 2/4 | 战吼:随机1伤 | 5 金 |
| owlbear | 枭熊 | 3 | 5/5 | FRENZY | 8 金 |
| wraith | 幽魂 | 3 | 4/3 | DODGE, POISON | 7 金 |

### 3.3 新增精英敌人

| ID | 名称 | Tier | ATK/HP | 关键词 | 掉落 | 精英 |
|----|------|------|--------|--------|------|------|
| minotaur_champion | 牛头人冠军 | 2 | 5/8 | GUARD, ARMOR | 10 金 + 宝物 | true |
| basilisk | 石化蜥蜴 | 3 | 6/7 | POISON, GUARD | 12 金 + 宝物 | true |
| death_knight | 死亡骑士 | 4 | 7/10 | GUARD, SHIELD, 亡语:全体2伤 | 15 金 + 宝物 | true |
| lich | 巫妖 | 5 | 8/8 | SHIELD, 战吼:全体3伤 | 18 金 + 稀有宝物 | true |
| beholder_kin | 眼魔亚种 | 5 | 6/12 | FRENZY, POISON | 16 金 + 宝物 | true |

### 3.4 新增 Boss

| ID | 名称 | Tier | ATK/HP | 关键词 | 掉落 | Boss |
|----|------|------|--------|------|------|------|
| wyvern | 双足飞龙 | 4 | 7/15 | FLYING, POISON, FRENZY | 15 金 + 宝物 + 升级 | true |
| hydra | 多头蛇蜥 | 5 | 5/25 | REGENERATION, CLEAVE | 18 金 + 稀有宝物 + 升级 | true |
| ancient_white_dragon | 远古白龙 | 6 | 10/18 | FLYING, FROST_BREATH, ARMOR | 20 金 + 史诗宝物 + 升级 | true |

> 注：现有 `ancient_red_dragon` 保留，与 `ancient_white_dragon` 在高层随机出现。

### 3.5 JSON 数据示例

```json
{
  "id": "death_knight",
  "name": "死亡骑士",
  "tier": 4,
  "attack": 7,
  "health": 10,
  "keywords": ["GUARD", "SHIELD"],
  "script": {
    "deathrattle": {
      "type": "damage_all",
      "value": 2
    }
  },
  "reward_gold": 15,
  "is_elite": true
}
```

---

## 四、事件补完

### 4.1 现有事件（5 个）

魔法喷泉、贪婪的宝箱怪、幽灵的恳求、神秘商人、古老祭坛

### 4.2 新增事件（7 个）

#### E6 — 被遗忘的训练场
> 你发现了一座破败的角斗场，训练假人仍在运作。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 训练一名冒险者 | 选择一个冒险者获得 +2/+2 | "你的冒险者在训练中成长了！" |
| 全员热身 | 全体友军 +1 攻击 | "你的队伍完成了热身训练。" |
| 果断离开 | 无效果 | "你决定不在此浪费时间。" |

#### E7 — 赌徒的转盘
> 一个地精赌徒向你展示他的魔法转盘，邀请你试试运气。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 下注 5 铸币 | 50%: 获得 15 铸币；50%: 失去 5 铸币 | "转盘停止……" |
| 下注一件宝物 | 50%: 获得史诗宝物；50%: 失去该宝物 | "璀璨的光芒闪过……" |
| 拒绝赌博 | 无效果 | "赌徒失望地撇了撇嘴。" |

#### E8 — 枯萎花园
> 一座曾经美丽的魔法花园，如今被黑暗能量腐蚀，但仍有残余生机。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 采摘发光果实 | 恢复 8 生命值 | "果实化作温暖的能量流入你的体内。" |
| 收集枯萎荆棘 | 获得一件随机宝物 | "荆棘虽枯，仍蕴含魔法力量。" |
| 尝试净化花园 | 消耗 5 生命值，获得一个随机 4 星冒险者 | "花园感激你的付出，赐予你一位强大的盟友。" |

#### E9 — 回声图书馆
> 墙壁上刻满了会低语的符文，记录着前人冒险者的故事。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 学习战斗技巧 | 选择一个冒险者获得 SHIELD | "你领悟了书中的防御奥义。" |
| 抄录咒语 | 获得 3 个随机 2 星冒险者（1 消耗） | "咒语召唤来几位冒险者！" |
| 销毁禁忌之书 | 获得 12 铸币 | "书页化作金币飘落。" |

#### E10 — 卓尔商队
> 一队来自幽暗地域的卓尔精灵商人，他们的货物不太寻常。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 购买暗影药剂（5 金） | 选择一个冒险者获得 POISON | "药剂滴在武器上，刃锋泛起了绿光。" |
| 购买闪光粉尘（8 金） | 全体友军 DODGE 一回合 | "粉尘让你们的动作变得飘忽不定。" |
| 婉拒交易 | 无效果 | "卓尔商人冷笑一声，消失在阴影中。" |

#### E11 — 流浪的铁匠
> 一个矮人铁匠推着他的移动煅炉，叮叮当当地敲打着什么。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 锻造护甲（5 金） | 选择一个冒险者获得 ARMOR | "铁匠为你打造了一副精良护甲。" |
| 重铸武器（8 金） | 选择一个冒险者攻击翻倍（最高 +5） | "武器焕然一新，锋利无比！" |
| 出售废铁 | 获得 8 铸币 | "铁匠买下了你背包里的废金属。" |

#### E12 — 时之沙漏
> 一个巨大的沙漏悬浮在空中，流沙缓慢下落。触碰它似乎能操纵时间。

| 选项 | 效果 | 结果描述 |
|------|------|----------|
| 逆转沙漏 | 恢复全部生命值，但失去一件宝物 | "时间倒流，你的伤口消失了。" |
| 加速流逝 | 立即获得下一层的铸币（+8），但受到 5 点伤害 | "时间加速飞逝，你感到一阵眩晕。" |
| 不打搅时间 | 获得一件随机宝物 | "沙漏旁掉落了一件遗物。" |

---

## 五、宝物补充（可选）

现有 7 个宝物已覆盖方案列出的全部。建议新增 3 个以丰富池子：

| ID | 名称 | 稀有度 | 效果 |
|----|------|--------|------|
| gauntlets_of_ogre_power | 食人魔力量手套 | common | 你的冒险者获得 +2 攻击力（与巨人腰带 +1 叠加）。 |
| cloak_of_elvenkind | 精灵斗篷 | rare | 战斗开始时：一个随机友军获得永久 DODGE。 |
| ring_of_three_wishes | 祈愿戒指 | epic | 每场战斗一次：一个友军死亡时改为回到手牌（回满 HP）。 |

---

## 六、局外成长系统

### 6.1 架构总览

```
局外成长 = 存档系统 + 解锁系统 + 进阶系统 + 统计系统
```

### 6.2 存档系统

**文件位置**：`%USERPROFILE%/AppData/Local/TavernRogue/save.json`

**数据结构**：

```json
{
  "meta": {
    "version": 1,
    "total_runs": 42,
    "total_wins": 3,
    "highest_ascension": 2
  },
  "unlocks": {
    "heroes": ["warrior", "rogue", "cleric"],
    "relics": ["regeneration_amulet", "boots_of_speed", "force_field_ring"]
  },
  "stats": {
    "best_team": ["远古龙裔龙王", "矮人远古守护者", "人类传奇英雄"],
    "max_damage_dealt": 156,
    "favorite_tribe": "dwarf",
    "fastest_win_layers": 8,
    "total_gold_earned": 12345,
    "total_adventurers_recruited": 312
  },
  "ascension": {
    "warrior": 0,
    "rogue": 1,
    "cleric": 0,
    "wizard": 0,
    "warlock": 0
  },
  "current_run": null
}
```

**实现模块**：新建 `game/persistence.py`

```python
class PersistenceManager:
    def save_meta(self, data): ...
    def load_meta(self): ...
    def save_run(self, game_state): ...  # 跑团中存档
    def load_run(self): ...              # 读取跑团存档
    def delete_run(self): ...            # 清除跑团存档
```

### 6.3 职业解锁

**流程**：
1. 初始可用：战士
2. 用战士通关 → 解锁游荡者
3. 用游荡者通关 → 解锁牧师
4. 用牧师通关 → 解锁法师
5. 用法师通关 → 解锁术士

**实现**：
- `game/hero.py` 的 `get_all_hero_classes()` 增加 `unlocked: bool` 字段
- 菜单场景 `ClassSelectScene` 显示锁定/解锁状态
- 通关 `VictoryScene` 时调用 `persistence.unlock_next_hero()`

### 6.4 进阶系统

**概念**：每个职业独立进阶等级 0-5，每级增加难度。

| 进阶等级 | 敌人增益 | 特殊规则 |
|----------|----------|----------|
| 0 (普通) | — | — |
| 1 | 敌人 +1/+1 | 起始铸币 -1 |
| 2 | 敌人 +2/+2 | Boss 额外 +5 HP |
| 3 | 敌人 +3/+3 | 精英出现率 +20%，营地治疗 -50% |
| 4 | 敌人 +4/+4 | 商店价格 +50% |
| 5 | 敌人 +5/+5, Boss 额外 +10 HP | 每一场战斗后英雄受 1 伤 |

**实现**：
- `GameManager` 在 `new_game()` 时读取当前职业的进阶等级
- `MapManager` 生成敌人时根据进阶等级调整属性
- UI 在职业选择界面显示进阶等级

### 6.5 冒险日志（统计面板）

**位置**：主菜单新增 "冒险日志" 按钮

**显示内容**：
- 总游戏次数 / 总胜利次数 / 胜率
- 各职业最高进阶等级
- 最佳通关阵容（最近一次胜利的队伍）
- 最高单次伤害 / 最爱种族 / 最快通关层数
- 累计招募冒险者数 / 累计获得铸币数

**实现**：新建 `ui/scenes/journal.py`

### 6.6 宝物渐进解锁

- 初始宝物池：common 宝物全部可用
- 首次获得某 rare 宝物 → 永久解锁
- 首次获得某 epic 宝物 → 永久解锁
- 在存档中记录已解锁的宝物 ID 列表

---

## 七、实现阶段

### Phase A：内容填充（优先）

| 任务 | 预估工作量 | 产出 |
|------|-----------|------|
| A1. 补齐 3 星冒险者（3 个） | 小 | adventurers.json 新增 3 条 |
| A2. 新增 4 星冒险者（6 个） | 中 | adventurers.json 新增 6 条 |
| A3. 新增 5 星冒险者（6 个） | 中 | adventurers.json 新增 6 条 |
| A4. 新增 6 星冒险者（6 个） | 中 | adventurers.json 新增 6 条 |
| A5. 新增普通敌人（6 个） | 小 | enemies.json 新增 6 条 |
| A6. 新增精英敌人（5 个）+ 支持 is_elite 字段 | 中 | enemies.json + node_handler 适配 |
| A7. 新增 Boss（3 个）+ boss 随机选择 | 中 | enemies.json + map_manager 适配 |
| A8. 新增事件（7 个） | 中 | events.json 新增 7 条 |
| A9. 新增宝物（3 个） | 小 | relics.json 新增 3 条 |

### Phase B：局外成长（次优先）

| 任务 | 预估工作量 | 产出 |
|------|-----------|------|
| B1. 实现存档系统 PersistenceManager | 中 | game/persistence.py |
| B2. 职业解锁流程 | 小 | 菜单/通关场景适配 |
| B3. 进阶系统 + 难度调整 | 中 | GameManager + MapManager 适配 |
| B4. 冒险日志 UI | 中 | ui/scenes/journal.py |
| B5. 宝物渐进解锁 | 小 | 商店/事件奖励适配 |
| B6. 跑团中存档/读档 | 中 | 主菜单"继续冒险"按钮 |

### Phase C：战斗引擎深化（低优先，但要跟上）

| 任务 | 优先级 | 说明 |
|------|--------|------|
| C1. 实现 CLEAVE（横扫） | 中 | 攻击时对相邻敌人造成溅射伤害 |
| C2. 实现 BLOOD_FURY（血怒） | 高 | 友方死亡事件队列钩子 |
| C3. 实现 OVERKILL（过杀） | 低 | 超额伤害触发额外效果 |
| C4. 实现 DODGE 闪避计算 | 高 | 目前 DODGE 关键词已赋值但引擎未计算 |
| C5. 实现 double_attack_chance | 中 | 宝物"速度之靴"效果未生效 |
| C6. 牧师技能接入战斗引擎 | 高 | on_ally_death() 在引擎中未被调用 |
| C7. 英雄受击：友军全灭后敌方攻击英雄 | 中 | simulate_battle 末尾补逻辑 |

---

## 八、冒险者 JSON 完整新增清单

### 3 星补齐（+3）

```json
{"id":"dragonborn_fire_knight","name":"龙裔炎骑士","tribe":"dragonborn","tier":3,"attack":3,"health":4,"keywords":["GUARD"],"script":{"battle_cry":{"type":"damage_all","value":1}},"cost":5}
{"id":"half_orc_reaver","name":"半兽人掠夺者","tribe":"half_orc","tier":3,"attack":5,"health":4,"keywords":["CLEAVE"],"script":{},"cost":5}
{"id":"tiefling_hexer","name":"提夫林咒术师","tribe":"tiefling","tier":3,"attack":3,"health":3,"keywords":[],"script":{"deathrattle":{"type":"damage_random","value":3}},"cost":5}
```

### 4 星（+6）

```json
{"id":"human_paladin","name":"人类圣武士","tribe":"human","tier":4,"attack":4,"health":6,"keywords":["GUARD","SHIELD"],"script":{},"cost":6}
{"id":"elf_bladedancer","name":"精灵剑舞者","tribe":"elf","tier":4,"attack":4,"health":4,"keywords":["DODGE","FRENZY"],"script":{},"cost":6}
{"id":"dwarf_runesmith","name":"矮人符文匠","tribe":"dwarf","tier":4,"attack":3,"health":7,"keywords":["GUARD","ARMOR"],"script":{"battle_cry":{"type":"buff_all","value":1}},"cost":6}
{"id":"dragonborn_stormcaller","name":"龙裔唤雷者","tribe":"dragonborn","tier":4,"attack":4,"health":5,"keywords":[],"script":{"battle_cry":{"type":"damage_random","value":3}},"cost":6}
{"id":"half_orc_bloodrager","name":"半兽人嗜血者","tribe":"half_orc","tier":4,"attack":7,"health":3,"keywords":["FRENZY","OVERKILL"],"script":{},"cost":6}
{"id":"tiefling_soulbinder","name":"提夫林缚魂师","tribe":"tiefling","tier":4,"attack":3,"health":4,"keywords":[],"script":{"deathrattle":{"type":"damage_random","value":4}},"cost":6}
```

### 5 星（+6）

```json
{"id":"human_champion","name":"人类冠军斗士","tribe":"human","tier":5,"attack":6,"health":8,"keywords":["GUARD","ARMOR"],"script":{},"cost":7}
{"id":"elf_moon_warden","name":"精灵月卫","tribe":"elf","tier":5,"attack":6,"health":5,"keywords":["DODGE","POISON","FRENZY"],"script":{},"cost":7}
{"id":"dwarf_earthbreaker","name":"矮人裂地者","tribe":"dwarf","tier":5,"attack":4,"health":10,"keywords":["GUARD","ARMOR","SHIELD"],"script":{"deathrattle":{"type":"summon","summon_id":"dwarf_warrior","count":2}},"cost":7}
{"id":"dragonborn_elderscale","name":"龙裔古鳞","tribe":"dragonborn","tier":5,"attack":6,"health":7,"keywords":["GUARD"],"script":{"battle_cry":{"type":"damage_all","value":2}},"cost":7}
{"id":"half_orc_warlord","name":"半兽人战争领主","tribe":"half_orc","tier":5,"attack":9,"health":6,"keywords":["FRENZY","CLEAVE"],"script":{},"cost":7}
{"id":"tiefling_doombringer","name":"提夫林末日使者","tribe":"tiefling","tier":5,"attack":5,"health":5,"keywords":[],"script":{"deathrattle":{"type":"damage_random","value":6}},"cost":7}
```

### 6 星（+6）

```json
{"id":"human_legend","name":"人类传奇英雄","tribe":"human","tier":6,"attack":8,"health":12,"keywords":["GUARD","ARMOR","SHIELD"],"script":{"battle_cry":{"type":"buff_all","value":2}},"cost":8}
{"id":"elf_eclipse","name":"精灵日蚀猎手","tribe":"elf","tier":6,"attack":10,"health":6,"keywords":["DODGE","POISON","FRENZY","CLEAVE"],"script":{},"cost":8}
{"id":"dwarf_ancient_guardian","name":"矮人远古守护者","tribe":"dwarf","tier":6,"attack":6,"health":16,"keywords":["GUARD","ARMOR","SHIELD"],"script":{"deathrattle":{"type":"buff_all","value":2}},"cost":8}
{"id":"dragonborn_dragon_lord","name":"龙裔龙王","tribe":"dragonborn","tier":6,"attack":8,"health":10,"keywords":["GUARD"],"script":{"battle_cry":{"type":"damage_all","value":4}},"cost":8}
{"id":"half_orc_destroyer","name":"半兽人毁灭者","tribe":"half_orc","tier":6,"attack":12,"health":8,"keywords":["FRENZY","CLEAVE","OVERKILL"],"script":{},"cost":8}
{"id":"tiefling_archfiend","name":"提夫林大魔","tribe":"tiefling","tier":6,"attack":7,"health":7,"keywords":[],"script":{"deathrattle":{"type":"damage_random","value":8}},"cost":8}
```

---

## 九、图标图例

由于当前项目用 "🏪" 等 emoji 来标识节点类型，建议保持一致的视觉语言：

| 节点类型 | 图标建议 | 说明 |
|----------|---------|------|
| 怪物巢穴 | ⚔️ | 普通战斗 |
| 精英守卫 | 💀 | 高难度战斗 |
| 旅行商人 | 🏪 | 商店 |
| 古老祭坛 | 🔮 | 事件/奇遇 |
| 安全营地 | 🏕️ | 恢复 |
| Boss | 🐉 | 首领战 |
| 宝藏密室 | 💎 | 稀有奖励 |

---

## 十、总结

| 指标 | 当前 | 完成后 | 新增量 |
|------|------|--------|--------|
| 冒险者 | 15（1-3 星） | 36（1-6 星） | +21 |
| 敌人 | 7（0 精英, 1 Boss） | 18（5 精英, 4 Boss） | +11 |
| 事件 | 5 | 12 | +7 |
| 宝物 | 7 | 10 | +3 |
| 局外成长 | 无 | 完整（解锁/进阶/存档/统计） | 全套 |
| 战斗关键词 | 6 个有效 | 9 个（+DODGE/CLEAVE/BLOOD_FURY） | +3 |

**建议执行顺序**：Phase A（内容）→ Phase B（局外成长）→ Phase C（引擎深化）。

Phase A 可以并行推进——多个 JSON 文件独立编辑，每个种族的 3-6 星数据格式一致。Phase B 需要串行开发：先做存档系统，再在其上构建解锁、进阶和统计。
