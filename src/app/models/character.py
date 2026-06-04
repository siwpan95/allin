# -*- coding: utf-8 -*-
"""角色数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Race(Enum):
    """种族 — (名称, 描述, 属性修正)"""
    HUMAN = ("人类", "适应力强", {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1})
    ELF = ("精灵", "敏捷与智力出众", {"str": -1, "dex": 2, "con": -1, "int": 2, "wis": 1, "cha": 0})
    DWARF = ("矮人", "体质与力量见长", {"str": 2, "dex": -1, "con": 2, "int": -1, "wis": 1, "cha": -1})
    HALFLING = ("半身人", "幸运与敏捷并存", {"str": -2, "dex": 2, "con": 0, "int": 1, "wis": 0, "cha": 2})
    GNOME = ("侏儒", "智力与感知出众", {"str": -2, "dex": 1, "con": 0, "int": 2, "wis": 0, "cha": 1})
    HALFORC = ("半兽人", "力量与体质混合", {"str": 2, "dex": 0, "con": 1, "int": -2, "wis": -1, "cha": -1})
    TIEFFLING = ("提夫林", "魅力与智力兼具", {"str": 0, "dex": 1, "con": 0, "int": 1, "wis": -1, "cha": 2})
    DRAGONBORN = ("龙裔", "力量与魅力并存", {"str": 2, "dex": 0, "con": 1, "int": -1, "wis": 0, "cha": 1})


class CharClass(Enum):
    """职业"""
    WARRIOR = ("战士", "战士")
    MAGE = ("法师", "法师")
    CLERIC = ("牧师", "牧师")
    ROGUE = ("盗贼", "盗贼")
    RANGER = ("游侠", "游侠")
    PALADIN = ("圣骑士", "圣骑士")
    WARLOCK = ("术士", "术士")
    MONK = ("武僧", "武僧")
    DRUID = ("德鲁伊", "德鲁伊")
    BARBARIAN = ("野蛮人", "野蛮人")


@dataclass
class CharacterStats:
    """角色六维属性"""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


@dataclass
class Skill:
    """技能"""
    name: str
    description: str
    effect_type: str  # magic_damage / heal / buff / etc.
    effect_value: float
    cooldown: float
    current_cooldown: float = 0.0
    level_req: int = 1

    def use(self):
        self.current_cooldown = self.cooldown

    def tick(self, dt: float):
        if self.current_cooldown > 0:
            self.current_cooldown = max(0.0, self.current_cooldown - dt)

    def is_ready(self) -> bool:
        return self.current_cooldown <= 0


# ======== 职业技能定义 ========
# 每个职业 3 个技能：(name, description, effect_type, effect_value, cooldown, level_req)
CLASS_SKILL_DEFS = {
    "WARRIOR": [
        {"name": "猛击", "description": "强力一击，伤害×1.5", "effect_type": "damage_multiplier", "effect_value": 1.5, "cooldown": 3.0, "level_req": 1},
        {"name": "防御姿态", "description": "防御提高50%", "effect_type": "defense_buff", "effect_value": 0.5, "cooldown": 30.0, "level_req": 5},
        {"name": "旋风斩", "description": "范围攻击×1.2", "effect_type": "area_damage", "effect_value": 1.2, "cooldown": 15.0, "level_req": 10},
    ],
    "MAGE": [
        {"name": "火球术", "description": "发射火球，法术伤害×1.8", "effect_type": "magic_damage", "effect_value": 1.8, "cooldown": 2.5, "level_req": 1},
        {"name": "冰锥术", "description": "喷射冰锥，减速敌人", "effect_type": "magic_damage_slow", "effect_value": 1.2, "cooldown": 4.0, "level_req": 5},
        {"name": "闪电链", "description": "闪电弹射×2.0", "effect_type": "lightning_chain", "effect_value": 2.0, "cooldown": 8.0, "level_req": 10},
    ],
    "CLERIC": [
        {"name": "治疗术", "description": "恢复生命", "effect_type": "heal", "effect_value": 1.0, "cooldown": 5.0, "level_req": 1},
        {"name": "神圣之光", "description": "神圣伤害×1.5", "effect_type": "holy_damage", "effect_value": 1.5, "cooldown": 8.0, "level_req": 5},
        {"name": "庇护所", "description": "防护罩减伤50%", "effect_type": "shield", "effect_value": 0.5, "cooldown": 20.0, "level_req": 10},
    ],
    "ROGUE": [
        {"name": "背刺", "description": "背后暴击×2.0", "effect_type": "damage_multiplier", "effect_value": 2.0, "cooldown": 4.0, "level_req": 1},
        {"name": "毒刃", "description": "涂毒持续伤害", "effect_type": "poison", "effect_value": 0.3, "cooldown": 12.0, "level_req": 5},
        {"name": "隐身", "description": "潜行必暴击", "effect_type": "stealth", "effect_value": 1.0, "cooldown": 30.0, "level_req": 10},
    ],
    "RANGER": [
        {"name": "精准射击", "description": "必中要害", "effect_type": "guaranteed_crit", "effect_value": 1.0, "cooldown": 6.0, "level_req": 1},
        {"name": "陷阱", "description": "放置陷阱", "effect_type": "trap", "effect_value": 1.0, "cooldown": 15.0, "level_req": 5},
        {"name": "野兽伙伴", "description": "召唤野兽助战", "effect_type": "summon", "effect_value": 1.0, "cooldown": 60.0, "level_req": 10},
    ],
    "PALADIN": [
        {"name": "审判", "description": "神圣审判×1.5", "effect_type": "holy_damage", "effect_value": 1.5, "cooldown": 5.0, "level_req": 1},
        {"name": "圣光术", "description": "治疗", "effect_type": "heal", "effect_value": 1.0, "cooldown": 8.0, "level_req": 5},
        {"name": "无敌", "description": "无敌3秒", "effect_type": "invincible", "effect_value": 3.0, "cooldown": 120.0, "level_req": 15},
    ],
    "BARBARIAN": [
        {"name": "狂暴", "description": "攻击×1.5 防御降低", "effect_type": "berserk", "effect_value": 1.5, "cooldown": 20.0, "level_req": 1},
        {"name": "斩杀", "description": "低血量额外伤害×2", "effect_type": "execute", "effect_value": 2.0, "cooldown": 5.0, "level_req": 5},
        {"name": "战吼", "description": "全体buff+30%", "effect_type": "battle_cry", "effect_value": 0.3, "cooldown": 30.0, "level_req": 10},
    ],
    "WARLOCK": [
        {"name": "暗影箭", "description": "暗影伤害×1.5", "effect_type": "shadow_damage", "effect_value": 1.5, "cooldown": 2.5, "level_req": 1},
        {"name": "生命汲取", "description": "吸血50%伤害", "effect_type": "life_drain", "effect_value": 0.5, "cooldown": 4.0, "level_req": 5},
        {"name": "恶魔召唤", "description": "召唤恶魔", "effect_type": "summon_demon", "effect_value": 1.0, "cooldown": 60.0, "level_req": 10},
    ],
    "MONK": [
        {"name": "疾风连击", "description": "连续攻击×1.3", "effect_type": "flurry", "effect_value": 1.3, "cooldown": 3.0, "level_req": 1},
        {"name": "振魂掌", "description": "真气伤害×1.5", "effect_type": "chi_damage", "effect_value": 1.5, "cooldown": 6.0, "level_req": 5},
        {"name": "金钟罩", "description": "减伤80%", "effect_type": "shield", "effect_value": 0.8, "cooldown": 45.0, "level_req": 10},
    ],
    "DRUID": [
        {"name": "变形术", "description": "变熊+生存", "effect_type": "shape_shift", "effect_value": 1.0, "cooldown": 10.0, "level_req": 1},
        {"name": "荆棘术", "description": "缠绕敌人", "effect_type": "entangle", "effect_value": 1.0, "cooldown": 8.0, "level_req": 5},
        {"name": "自然之怒", "description": "自然伤害×2.0", "effect_type": "nature_wrath", "effect_value": 2.0, "cooldown": 20.0, "level_req": 10},
    ],
}


@dataclass
class Character:
    """角色数据模型"""
    name: str
    race: Race
    char_class: CharClass
    level: int = 1
    exp: int = 0
    exp_to_next: int = 100
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    gold: int = 0
    stats: CharacterStats = field(default_factory=CharacterStats)
    skills: List[Skill] = field(default_factory=list)
    equipment: Dict[str, Optional[object]] = field(default_factory=dict)
    inventory: List[object] = field(default_factory=list)
    kills: int = 0
    deaths: int = 0
    quests_completed: int = 0
    total_play_time: float = 0.0
    buffs: Dict[str, float] = field(default_factory=dict)

    _STAT_MAP = {"str": "strength", "dex": "dexterity", "con": "constitution",
                  "int": "intelligence", "wis": "wisdom", "cha": "charisma"}

    @classmethod
    def create(cls, name: str, race: Race, char_class: CharClass, seed: int = None) -> "Character":
        """工厂方法：创建角色并应用种族和职业加成"""
        import random as _random
        rng = _random.Random(seed) if seed is not None else _random

        # 基础属性 + 种族修正
        base = {"strength": 10, "dexterity": 10, "constitution": 10,
                "intelligence": 10, "wisdom": 10, "charisma": 10}
        bonuses = race.value[2]  # 种族属性修正字典
        for stat_abbr, bonus in bonuses.items():
            full = cls._STAT_MAP.get(stat_abbr, stat_abbr)
            if full in base:
                base[full] += bonus

        # 职业主属性 +2
        primary = cls._get_primary_stats(char_class)
        for stat in primary:
            if stat in base:
                base[stat] += 2

        # 随机微调 ±1~2
        for stat in base:
            base[stat] += rng.randint(-1, 2)

        # 限制范围
        for stat in list(base):
            base[stat] = max(3, min(30, base[stat]))

        stats = CharacterStats(**base)

        # 计算 HP/MP
        s = stats
        class_hp_bonus = cls._get_class_hp(char_class)
        max_hp = class_hp_bonus + s.constitution * 2
        max_mp = 10 + s.intelligence + s.wisdom

        # 初始化技能
        skills = cls._init_skills(char_class, 1, rng)

        char = cls(
            name=name,
            race=race,
            char_class=char_class,
            stats=stats,
            max_hp=max_hp,
            hp=max_hp,
            max_mp=max_mp,
            mp=max_mp,
            skills=skills,
            exp_to_next=int(1 ** 2 * 50 + 50),
        )
        return char

    @staticmethod
    def _get_primary_stats(char_class: CharClass) -> list:
        """获取职业主属性"""
        mapping = {
            "WARRIOR": ["strength", "constitution"],
            "MAGE": ["intelligence"],
            "CLERIC": ["wisdom", "charisma"],
            "ROGUE": ["dexterity", "intelligence"],
            "RANGER": ["dexterity", "wisdom"],
            "PALADIN": ["strength", "charisma"],
            "WARLOCK": ["charisma", "constitution"],
            "MONK": ["dexterity", "wisdom"],
            "DRUID": ["wisdom", "constitution"],
            "BARBARIAN": ["strength", "constitution"],
        }
        return mapping.get(char_class.name, ["strength"])

    @staticmethod
    def _get_class_hp(char_class: CharClass) -> int:
        """获取职业基础HP"""
        hp_map = {
            "WARRIOR": 12, "BARBARIAN": 12, "PALADIN": 10,
            "RANGER": 10, "MONK": 8, "CLERIC": 8, "DRUID": 8,
            "ROGUE": 8, "WARLOCK": 8, "MAGE": 6,
        }
        return hp_map.get(char_class.name, 8)

    @staticmethod
    def _init_skills(char_class: CharClass, level: int, rng) -> list:
        """初始化角色技能"""
        from .character import CLASS_SKILL_DEFS
        skills = []
        for skill_def in CLASS_SKILL_DEFS.get(char_class.name, []):
            if skill_def["level_req"] <= level:
                skills.append(Skill(**skill_def))
        return skills

    # ======== 战斗/属性方法 ========

    def get_attack_power(self) -> int:
        """计算攻击力"""
        weapon = self.equipment.get("WEAPON")
        base = weapon.damage if weapon and hasattr(weapon, "damage") else 5 + self.level // 2
        bonus = self.stats.strength // 2
        mult = self.buffs.get("damage_multiplier", 1.0)
        bonus += int((mult - 1.0) * base)
        return max(1, int(base + bonus))

    def get_defense(self) -> int:
        """计算防御力"""
        total = 0
        for slot in ["HEAD", "CHEST", "HANDS", "LEGS", "FEET"]:
            item = self.equipment.get(slot)
            if item and hasattr(item, "defense"):
                total += item.defense
        bonus = self.stats.constitution // 3 + self.stats.dexterity // 5
        return max(1, total + bonus)

    def take_damage(self, damage: int) -> int:
        """受到伤害，返回实际伤害值"""
        actual = max(0, damage - self.get_defense() // 3)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.deaths += 1
            self.hp = int(self.max_hp * 0.5)
        return actual

    def heal(self, amount: int) -> int:
        """治疗，返回实际恢复量"""
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old

    def gain_exp(self, amount: int):
        """获得经验，触发升级"""
        self.exp += amount
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.max_hp += 10
            self.hp = self.max_hp
            self.max_mp += 5
            self.mp = self.max_mp
            self.exp_to_next = int(self.level ** 2 * 50 + 50)
            # 检查新技能解锁
            for skill_def in CLASS_SKILL_DEFS.get(self.char_class.name, []):
                if skill_def["level_req"] == self.level:
                    self.skills.append(Skill(**skill_def))

    # ======== 装备方法 ========

    def can_equip(self, item) -> bool:
        """检查是否可以装备"""
        if not item or not hasattr(item, "level_req"):
            return False
        return item.level_req <= self.level

    def _get_equip_slot(self, item) -> Optional[str]:
        """获取物品对应的装备槽位键"""
        from .item import Weapon as WeaponModel, Armor as ArmorModel, Accessory as AccessoryModel
        if isinstance(item, WeaponModel):
            return "WEAPON"
        elif isinstance(item, ArmorModel):
            return item.slot.name if hasattr(item.slot, "name") else str(item.slot)
        elif isinstance(item, AccessoryModel):
            return item.slot.name if hasattr(item.slot, "name") else str(item.slot)
        return None

    def try_auto_equip(self, item) -> bool:
        """尝试自动装备物品，返回是否成功装备"""
        if not self.can_equip(item):
            return False

        slot = self._get_equip_slot(item)
        if slot is None:
            return False

        current = self.equipment.get(slot)
        # 比较品质：装备品质更高才替换
        if current and hasattr(current, "quality") and hasattr(item, "quality"):
            item_quality = item.quality.value[1]
            cur_quality = current.quality.value[1]
            if cur_quality > item_quality:
                return False
            if cur_quality == item_quality:
                if hasattr(current, "damage") and hasattr(item, "damage"):
                    if current.damage >= item.damage:
                        return False
                if hasattr(current, "defense") and hasattr(item, "defense"):
                    if current.defense >= item.defense:
                        return False

        self.equipment[slot] = item
        return True

    # ======== 序列化 ========

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "name": self.name,
            "race": self.race.name,
            "char_class": self.char_class.name,
            "level": self.level,
            "exp": self.exp,
            "exp_to_next": self.exp_to_next,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "gold": self.gold,
            "stats": {
                "strength": self.stats.strength,
                "dexterity": self.stats.dexterity,
                "constitution": self.stats.constitution,
                "intelligence": self.stats.intelligence,
                "wisdom": self.stats.wisdom,
                "charisma": self.stats.charisma,
            },
            "kills": self.kills,
            "deaths": self.deaths,
            "quests_completed": self.quests_completed,
            "total_play_time": self.total_play_time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """从字典恢复"""
        stats = CharacterStats(**data.get("stats", {}))
        race = getattr(Race, data.get("race", "HUMAN"))
        char_class = getattr(CharClass, data.get("char_class", "WARRIOR"))
        return cls(
            name=data["name"],
            race=race,
            char_class=char_class,
            level=data.get("level", 1),
            exp=data.get("exp", 0),
            exp_to_next=data.get("exp_to_next", 100),
            hp=data.get("hp", 100),
            max_hp=data.get("max_hp", 100),
            mp=data.get("mp", 50),
            max_mp=data.get("max_mp", 50),
            gold=data.get("gold", 0),
            stats=stats,
            kills=data.get("kills", 0),
            deaths=data.get("deaths", 0),
            quests_completed=data.get("quests_completed", 0),
            total_play_time=data.get("total_play_time", 0.0),
        )


# ======== 组队系统 ========

class Party:
    """队伍管理 — 主角 + 队友，最小侵入现有单角色逻辑"""

    MAX_MEMBERS = 4

    def __init__(self, hero: Character):
        self.hero = hero          # 主角（主要角色）
        self.members: List[Character] = [hero]  # 队伍列表，第一个永远是主角

    @property
    def party_size(self) -> int:
        return len(self.members)

    @property
    def is_full(self) -> bool:
        return len(self.members) >= self.MAX_MEMBERS

    def add_member(self, char: Character) -> bool:
        """添加队友，返回是否成功"""
        if self.is_full:
            return False
        self.members.append(char)
        return True

    def remove_member(self, char: Character) -> bool:
        """移除队友（主角不可移除）"""
        if char == self.hero:
            return False
        self.members.remove(char)
        return True

    def replace_member(self, old: Character, new: Character) -> bool:
        """替换队友"""
        if old == self.hero:
            return False
        self.members[self.members.index(old)] = new
        return True

    def get_alive(self) -> List[Character]:
        """获取所有存活成员"""
        return [m for m in self.members if m.hp > 0]

    def get_defeated(self) -> List[Character]:
        """获取所有阵亡成员"""
        return [m for m in self.members if m.hp <= 0]

    def get_member_names(self) -> List[str]:
        """获取所有成员名字"""
        return [f"{m.char_class.value[0]}·{m.name}" for m in self.members]
