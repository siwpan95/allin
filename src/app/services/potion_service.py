# -*- coding: utf-8 -*-
"""药水服务 — 拾取/自动激活/计时/效果查询"""
import random
from typing import List, Dict, Optional
from ..models.potion import Potion, PotionType, POTION_DROP_WEIGHTS


class PotionService:
    """药水管理服务"""

    MAX_ACTIVE = 3  # 同时激活上限

    def __init__(self, data_service=None):
        self.active_potions: Dict[PotionType, Potion] = {}  # 激活中的药水
        # 尝试从 Excel/数据服务加载配置
        if data_service:
            config = data_service.get_potion_config()
            if config:
                new_weights = {}
                for item in config:
                    for pt in PotionType:
                        if pt.value[0] == item.get("name", ""):
                            new_weights[pt] = item.get("weight", 10)
                            break
                if new_weights:
                    POTION_DROP_WEIGHTS.clear()
                    POTION_DROP_WEIGHTS.update(new_weights)

    def random_potion_type(self) -> PotionType:
        """按权重随机选择一种药水"""
        types = list(POTION_DROP_WEIGHTS.keys())
        weights = list(POTION_DROP_WEIGHTS.values())
        return random.choices(types, weights=weights)[0]

    def pickup_potion(self, potion_type: PotionType) -> str:
        """
        拾取药水并自动激活。
        如果同类型已在激活中 → 刷新持续时间（叠加）
        如果激活数达上限 → 替换剩余时间最短的
        返回触发消息
        """
        if potion_type in self.active_potions:
            existing = self.active_potions[potion_type]
            existing.remaining_time = existing.max_duration
            return f"✨ {existing.name} 时间已重置（{int(existing.remaining_time)}s）"

        # 检查是否超过上限
        if len(self.active_potions) >= self.MAX_ACTIVE:
            # 替换剩余时间最短的
            shortest = min(self.active_potions.values(), key=lambda p: p.remaining_time)
            old_name = shortest.name
            del self.active_potions[shortest.potion_type]

        potion = Potion(potion_type=potion_type)
        potion.activate()
        self.active_potions[potion_type] = potion

        msg = f"✨ 自动使用了【{potion.name}】（{int(potion.remaining_time)}s）"
        if len(self.active_potions) >= self.MAX_ACTIVE:
            # 检查是否是因为替换了新药水
            pass
        return msg

    def tick(self, dt: float) -> List[str]:
        """更新所有激活药水的计时器，返回过期消息列表"""
        expired = []
        for pt, potion in list(self.active_potions.items()):
            if potion.tick(dt):
                expired.append(f"⏰ 【{potion.name}】效果已结束")
                del self.active_potions[pt]
        return expired

    def has_effect(self, potion_type: PotionType) -> bool:
        """检查某药水效果是否激活中"""
        if potion_type in self.active_potions:
            return self.active_potions[potion_type].is_active()
        return False

    def get_active_list(self) -> List[Potion]:
        """获取所有激活中药水的列表"""
        return [p for p in self.active_potions.values() if p.is_active()]

    def get_effect_value(self, potion_type: PotionType) -> float:
        """获取药水效果值（用于战斗/掉落计算）"""
        if not self.has_effect(potion_type):
            return 1.0

        # 效果倍率
        effects = {
            PotionType.DOUBLE_GOLD: 2.0,
            PotionType.DOUBLE_ITEM: 2.0,
            PotionType.FRAIL_MONSTER: 0.5,
            PotionType.DOCILE_MONSTER: 0.1,
            PotionType.ITEM_VALUE: 1.5,
            PotionType.GUARANTEED_DROP: 1.0,  # 布尔型，检查时用 has_effect
            PotionType.MORE_MONSTERS: 5,
            PotionType.FREE_CAST: 1.0,
            PotionType.SPEED_EXPLORE: 0.5,
            PotionType.MORE_EXP: 1.5,
        }
        return effects.get(potion_type, 1.0)

    def to_dict(self) -> dict:
        """序列化"""
        data = {}
        for pt, potion in self.active_potions.items():
            data[pt.name] = {
                "remaining_time": potion.remaining_time,
            }
        return data

    def from_dict(self, data: dict):
        """反序列化"""
        self.active_potions.clear()
        for pt_name, pd in data.items():
            try:
                pt = PotionType[pt_name]
                potion = Potion(potion_type=pt, remaining_time=pd.get("remaining_time", 0))
                if potion.remaining_time > 0:
                    potion.active = True
                self.active_potions[pt] = potion
            except (KeyError, ValueError):
                continue
