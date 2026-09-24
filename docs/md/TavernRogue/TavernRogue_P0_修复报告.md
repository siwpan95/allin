# TavernRogue P0 修复报告

**日期**: 2026-06-20  
**修复范围**: 3 个 P0 严重问题

---

## P0-1: 种族共鸣效果（龙裔/半兽人/提夫林）

### 问题
`apply_tribe_effects()` 只打日志，不执行实际效果。三个种族共鸣完全无效。

### 修复方案
在 `engine.py` 中：
1. 新增 `_tribe_resonance` 字典，跨方法共享共鸣数据
2. `apply_tribe_effects()` 调用 `_apply_tribe_resonance()` 填充数据
3. `reset()` 不再清空 `_tribe_resonance`（在 `apply_tribe_effects` 开头清空）
4. 在战斗各阶段读取 `_tribe_resonance` 执行效果

### 修改文件
- `game/engine.py`

### 关键修改
```python
# __init__ 中新增
self._tribe_resonance = {}

# reset() 改为不清空
def reset(self):
    self.event_queue.clear()
    self.battle_log.clear()
    # 注意：不清空 _tribe_resonance

# _handle_battle_start 末尾新增龙裔火焰伤害
fire_damage = self._tribe_resonance.get('dragonborn_fire_damage', 0)
if fire_damage > 0 and enemies:
    target = random.choice([e for e in enemies if e['health'] > 0])
    target['health'] -= fire_damage

# _handle_attack 中新增半兽人双倍伤害
half_orc_chance = self._tribe_resonance.get('half_orc_double_chance', 0)
if half_orc_chance > 0 and random.random() < half_orc_chance:
    damage *= 2

# _handle_death 中新增提夫林暗影伤害
tiefling_damage = self._tribe_resonance.get('tiefling_death_damage', 0)
if tiefling_damage > 0 and side == 'ally':
    # 对随机敌人造成暗影伤害
```

### 测试结果
- ✅ 龙裔共鸣：战斗开始造成火焰伤害（等级 1 → 1 点）
- ✅ 半兽人共鸣：25% 几率双倍伤害
- ✅ 提夫林共鸣：友军死亡时造成暗影伤害

---

## P0-2: 血怒/横扫/过杀关键词

### 问题
`_trigger_blood_fury()` 是空方法，三个关键词完全未实现。

### 修复方案

#### 血怒 (BLOOD_FURY)
友方死亡时，所有带 `BLOOD_FURY` 的友军 +2 攻击力。

```python
def _trigger_blood_fury(self, dead_unit, dead_side):
    if not hasattr(self, '_last_battle_state'):
        return
    allies = self._last_battle_state.get('allies' if dead_side == 'ally' else 'enemies', [])
    for unit in allies:
        if unit is dead_unit or unit.get('health', 0) <= 0:
            continue
        if 'BLOOD_FURY' in unit.get('keywords', []):
            unit['attack'] = unit.get('attack', 0) + 2
            self._log(f"{unit['name']} 的血怒触发！攻击力 +2")
```

#### 横扫 (SWEEP)
攻击时对目标两侧敌人造成 1 点伤害。

```python
if 'SWEEP' in attacker.get('keywords', []):
    # 找到 defender 在列表中的位置
    defender_list = self._get_unit_list(defender)
    idx = ... # 找到索引
    # 对 idx-1 和 idx+1 造成 1 点伤害
```

#### 过杀 (OVERKILL)
超额伤害溅射到随机敌人。

```python
if 'OVERKILL' in attacker.get('keywords', []) and defender['health'] < 0:
    excess = -defender['health']
    # 对随机敌人造成 excess 点溅射伤害
```

### 修改文件
- `game/engine.py`

### 测试结果
- ✅ 血怒：友军死亡后，带血怒单位攻击力 +2
- ✅ 横扫：攻击同时对两侧敌人造成 1 点伤害
- ✅ 过杀：超额伤害溅射到随机敌人

---

## P0-3: 牧师职业修复

### 问题
牧师 `has_healing_word` 属性未正确初始化，治疗祷言无法触发。

### 修复方案
1. `Cleric.__init__` 中初始化 `self.has_healing_word = False`
2. `simulate_battle()` 中自动激活 `hero.has_healing_word = True`（被动技能）
3. `_try_cleric_resurrect()` 检查并执行复活逻辑
4. 复活后消耗 `has_healing_word`，每场战斗限一次

### 修改文件
- `game/engine.py`
- `game/hero.py`（确认 `Cleric` 类有 `has_healing_word`）

### 测试结果
- ✅ 无牧师时，友军死亡不复活
- ✅ 有牧师时，友军死亡后复活并恢复全部生命值
- ✅ 每场战斗限一次复活

---

## 其他修改

### `_get_unit_list()` 辅助方法
新增方法，根据单位 side 返回所在列表，供横扫等位置相关效果使用。

```python
def _get_unit_list(self, unit):
    if not hasattr(self, '_last_battle_state'):
        return []
    state = self._last_battle_state
    if unit.get('_side') == 'ally':
        return state.get('allies', [])
    return state.get('enemies', [])
```

### `apply_tribe_effects()` 签名修改
新增 `enemies` 参数（虽然当前未直接使用，但保留扩展能力）。

---

## 测试总结

| 测试项 | 结果 |
|--------|------|
| 龙裔共鸣火焰伤害 | ✅ 通过 |
| 半兽人双倍伤害 | ✅ 通过 |
| 提夫林暗影伤害 | ✅ 通过 |
| 血怒攻击力加成 | ✅ 通过 |
| 横扫两侧伤害 | ✅ 通过 |
| 过杀溅射伤害 | ✅ 通过 |
| 牧师治疗祷言复活 | ✅ 通过 |
| 语法检查 | ✅ 全部通过 |

---

## 后续建议

1. **扩充宝物数量**（当前仅 10 件，作为 Roguelike 偏少）
2. **扩充敌人和冒险者数据**（增加多样性）
3. **优化 AI 逻辑**（当前目标选择较简单）
4. **添加更多种族和职业**（增加可玩性）

---

**修复完成时间**: 2026-06-20 06:30  
**修复人**: WorkBuddy AI Assistant
