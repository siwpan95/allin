# -*- coding: utf-8 -*-
"""数据模型定义 - 与 JSON 数据解耦"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ItemQuality(Enum):
    """物品品质"""
    CRUDE = ("粗糙的", 0, "#9d9d9d")
    NORMAL = ("普通的", 1, "#ffffff")
    FINE = ("精良的", 2, "#1eff00")
    SUPERIOR = ("优秀的", 3, "#0070dd")
    EXCELLENT = ("卓越的", 4, "#a335ee")
    MASTER = ("大师的", 5, "#ff8000")
    LEGENDARY = ("传说的", 6, "#e6cc80")
    ARTIFACT = ("神器的", 7, "#ff4040")


class EquipmentSlot(Enum):
    """装备槽位"""
    WEAPON = "武器"
    OFFHAND = "副手"
    HEAD = "头部"
    CHEST = "胸甲"
    HANDS = "手套"
    LEGS = "护腿"
    FEET = "靴子"
    NECK = "项链"
    RING = "戒指"
    ACCESSORY = "饰品"


class WeaponType(Enum):
    """武器类型"""
    SWORD = "剑"
    AXE = "斧"
    MACE = "锤"
    DAGGER = "匕首"
    STAFF = "法杖"
    BOW = "弓"
    CROSSBOW = "弩"
    POLEARM = "长柄武器"
    SHIELD = "盾牌"


class ArmorType(Enum):
    """护甲类型"""
    LIGHT = "轻甲"
    MEDIUM = "中甲"
    HEAVY = "重甲"
    ROBE = "法袍"


@dataclass
class Item:
    """物品基类"""
    name: str
    item_type: str
    quality: ItemQuality
    level_req: int
    value: int
    description: str = ""
    item_id: str = ""

    def get_display_name(self) -> str:
        return f"{self.quality.value[0]}{self.name}"


@dataclass
class Weapon(Item):
    """武器"""
    weapon_type: WeaponType = WeaponType.SWORD
    damage: int = 10
    speed: float = 2.0
    crit_chance: float = 0.05
    durability: int = 100
    max_durability: int = 100
    bonuses: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.item_type = "weapon"


@dataclass
class Armor(Item):
    """护甲"""
    armor_type: ArmorType = ArmorType.MEDIUM
    defense: int = 5
    slot: EquipmentSlot = EquipmentSlot.CHEST
    durability: int = 100
    max_durability: int = 100
    bonuses: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.item_type = "armor"


@dataclass
class Accessory(Item):
    """饰品"""
    slot: EquipmentSlot = EquipmentSlot.NECK
    effect: str = ""
    bonuses: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.item_type = "accessory"
