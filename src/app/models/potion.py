# -*- coding: utf-8 -*-
"""药水数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class PotionType(Enum):
    """药水类型"""
    DOUBLE_GOLD = ("双倍金币", "怪物多掉一堆金币", 120.0)
    DOUBLE_ITEM = ("双倍物品", "怪物多掉一件装备", 120.0)
    FRAIL_MONSTER = ("脆弱怪物", "怪物属性降低50%", 90.0)
    DOCILE_MONSTER = ("温顺怪物", "怪物几乎不还手", 90.0)
    ITEM_VALUE = ("物品价值提升", "装备品质权重上移", 120.0)
    GUARANTEED_DROP = ("必掉装备", "每只怪物必掉装备", 90.0)
    MORE_MONSTERS = ("更多怪物", "每房间怪物+5", 120.0)
    FREE_CAST = ("免费施法", "技能不消耗精神力", 90.0)
    SPEED_EXPLORE = ("加速探索", "房间推进间隔减半", 120.0)
    MORE_EXP = ("更多经验", "经验获取+50%", 120.0)


@dataclass
class Potion:
    """药水实例"""
    potion_type: PotionType
    remaining_time: float = 0.0   # 剩余持续时间
    active: bool = False

    @property
    def name(self):
        return self.potion_type.value[0]

    @property
    def description(self):
        return self.potion_type.value[1]

    @property
    def max_duration(self):
        return self.potion_type.value[2]

    def activate(self):
        """激活药水"""
        self.active = True
        self.remaining_time = self.max_duration

    def tick(self, dt: float):
        """更新冷却，返回是否已过期"""
        if self.active and self.remaining_time > 0:
            self.remaining_time = max(0.0, self.remaining_time - dt)
            if self.remaining_time <= 0:
                self.active = False
                return True  # 过期
        return False

    def is_active(self) -> bool:
        return self.active and self.remaining_time > 0


# 药水掉落权重（稀有度）
POTION_DROP_WEIGHTS = {
    PotionType.DOUBLE_GOLD: 15,
    PotionType.DOUBLE_ITEM: 15,
    PotionType.FRAIL_MONSTER: 10,
    PotionType.DOCILE_MONSTER: 8,
    PotionType.ITEM_VALUE: 12,
    PotionType.GUARANTEED_DROP: 8,
    PotionType.MORE_MONSTERS: 5,
    PotionType.FREE_CAST: 5,
    PotionType.SPEED_EXPLORE: 12,
    PotionType.MORE_EXP: 10,
}
