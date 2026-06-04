# -*- coding: utf-8 -*-
"""城堡农场服务 — 城堡购买/守护/农场产出/入侵滋生"""
from typing import List, Dict, Optional


class CastleService:
    """城堡与农场管理"""

    def __init__(self, dungeon_service):
        self.dungeon_service = dungeon_service
        self.secured_regions: set = set()        # 已购买城堡的区域ID
        self.farm_regions: Dict[str, int] = {}    # 农场区域 → 危险等级（用于产出计算）
        self._farm_accumulator: float = 0.0       # 农场产出累积器

    def try_buy_castle(self, region: dict, gold_ref: List[int]) -> str:
        """
        尝试自动购买城堡。
        gold_ref[0] 是可变金币引用（通过列表模拟引用传递）
        返回日志消息
        """
        region_id = region["region_id"]
        if region_id in self.secured_regions:
            return ""

        cost = region.get("danger_level", 1) * 500
        if gold_ref[0] >= cost:
            gold_ref[0] -= cost
            self.secured_regions.add(region_id)
            # 标记该区域地牢为已守护
            for d in self.dungeon_service.get_region_dungeons(region_id):
                d.secured = True
            return f"🏰 购买了 {region['name']} 城堡（{cost}金币）— 此地牢永不滋生"
        else:
            return f"💸 {region['name']} 城堡需 {cost} 金币（当前:{gold_ref[0]}）— 地牢将重新滋生"

    def setup_farm(self, region_id: str, danger_level: int) -> str:
        """将区域设置为农场"""
        if region_id not in self.farm_regions:
            self.farm_regions[region_id] = danger_level
            return f"🌾 {region_id} 已设为农场（等级:{danger_level}）"
        return ""

    def tick_farm(self, dt: float) -> int:
        """
        农场产出计算 — 每秒累积，达到整数时返回产出金币数。
        """
        self._farm_accumulator += dt
        total_production = 0
        for danger_level in self.farm_regions.values():
            # 每秒产出 = 危险等级 * 0.5
            production_rate = danger_level * 0.5
            # 守护区域效率 +50%
            # farm_regions 中可能包含已守护的，简化处理：所有农场一视同仁
            total_production += production_rate

        # 每秒产出累积
        if total_production > 0 and self._farm_accumulator >= 1.0:
            coins = int(self._farm_accumulator * total_production)
            self._farm_accumulator = 0.0
            return coins

        return 0

    def get_farm_count(self) -> int:
        return len(self.farm_regions)

    def get_secured_count(self) -> int:
        return len(self.secured_regions)

    def get_highest_conquered(self) -> int:
        """获取已征服最高危险等级"""
        if not self.secured_regions:
            return 0
        max_danger = 0
        for rid in self.secured_regions:
            for d in self.dungeon_service.get_region_dungeons(rid):
                if d.danger_level > max_danger:
                    max_danger = d.danger_level
        return max_danger

    def to_dict(self) -> dict:
        return {
            "secured_regions": list(self.secured_regions),
            "farm_regions": self.farm_regions,
        }

    def from_dict(self, data: dict):
        self.secured_regions = set(data.get("secured_regions", []))
        self.farm_regions = data.get("farm_regions", {})
