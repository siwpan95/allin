# -*- coding: utf-8 -*-
"""世界数据模型"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random


@dataclass
class Terrain:
    """地形"""
    FOREST = ("森林", "森林")
    MOUNTAIN = ("山脉", "山脉")
    SWAMP = ("沼泽", "沼泽")
    DESERT = ("沙漠", "沙漠")
    TUNDRA = ("苔原", "苔原")
    PLAIN = ("平原", "平原")
    COAST = ("海岸", "海岸")
    ISLAND = ("岛屿", "岛屿")


@dataclass
class Biome:
    """生物群系"""
    TEMPERATE = "温带"
    TROPICAL = "热带"
    POLAR = "极地"
    SUBTROPICAL = "亚热带"


@dataclass
class Settlement:
    """定居点"""
    name: str
    settlement_type: str  # 村庄/城镇/城市
    population: int
    features: List[str] = field(default_factory=list)


@dataclass
class Landmark:
    """地标"""
    name: str
    landmark_type: str  # 山/河/湖/遗迹
    description: str = ""


@dataclass
class WorldEvent:
    """世界历史事件"""
    year: int
    description: str
    impact: str = ""  # 政治/战争/灾难/发现


@dataclass
class Region:
    """区域"""
    name: str
    danger_level: int
    terrain: str
    biome: str
    enemies: List[Dict] = field(default_factory=list)
    settlements: List[Settlement] = field(default_factory=list)
    landmarks: List[Landmark] = field(default_factory=list)
    history: List[WorldEvent] = field(default_factory=list)

    def get_random_enemy(self) -> Optional[Dict]:
        """随机获取一个敌人模板"""
        if not self.enemies:
            return None
        return random.choice(self.enemies)


@dataclass
class World:
    """世界数据模型"""
    seed: int = 0
    regions: List[Region] = field(default_factory=list)
    all_settlements: List[Settlement] = field(default_factory=list)
    all_landmarks: List[Landmark] = field(default_factory=list)
    history_events: List[WorldEvent] = field(default_factory=list)

    def get_all_regions(self) -> List[Region]:
        """获取所有区域"""
        return self.regions

    def get_region_by_danger(self, level: int) -> Optional[Region]:
        """根据等级获取合适的区域"""
        suitable = [r for r in self.regions if abs(r.danger_level - level) <= 3]
        if suitable:
            return random.choice(suitable)
        return random.choice(self.regions) if self.regions else None
