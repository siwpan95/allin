# -*- coding: utf-8 -*-
"""城堡农场服务 — 城堡维护/守护/农场产出/入侵滋生

改动说明：
  原：一次性购买城堡 → 永久免疫入侵。
  新：城堡需持续花费金币维护，维护到期后失去守护，地牢可被怪物重新侵占。
      此设计解决金币通货膨胀问题，提供长期金币消耗出口。
"""
from typing import List, Dict, Optional


class CastleService:
    """城堡与农场管理

    核心变更:
      - secured_regions (set) → castle_maintenance (Dict[str, float])
        记录每个区域城堡的剩余维护时间（秒）。
      - try_buy_castle() → try_maintain_castle()
        改为按周期付费，而非一次性购买。
      - 新增 tick_maintenance()：每帧倒计时，到期自动扣费续期；金币不足则失去守护。
      - 失去守护时同时移除该区域的农场和地牢 secured 标记，使其可重新滋生。
    """

    # ── 维护参数 ──────────────────────────────────────────
    MAINTENANCE_DURATION: float = 300.0    # 每次续期时长（秒）= 5 分钟
    MAINTENANCE_COST_PER_LEVEL: int = 200  # 每危险等级续期费用

    def __init__(self, dungeon_service):
        self.dungeon_service = dungeon_service
        # region_id → 剩余维护时间（秒）；>0 表示仍处于守护状态
        self.castle_maintenance: Dict[str, float] = {}
        self.farm_regions: Dict[str, int] = {}      # 农场区域 → 危险等级
        self._farm_accumulator: float = 0.0          # 农场产出累积器

    # ── 辅助方法 ──────────────────────────────────────────

    def _get_cost(self, danger_level: int) -> int:
        """计算单次续期费用"""
        return danger_level * self.MAINTENANCE_COST_PER_LEVEL

    def _set_dungeons_secured(self, region_id: str, secured: bool):
        """批量设置某区域所有地牢的 secured 标记"""
        for d in self.dungeon_service.get_region_dungeons(region_id):
            d.secured = secured

    # ── 城堡维护 ──────────────────────────────────────────

    def is_maintained(self, region_id: str) -> bool:
        """检查区域城堡是否正在被维护"""
        return self.castle_maintenance.get(region_id, 0) > 0

    def try_maintain_castle(self, region: dict, gold_ref: List[int]) -> str:
        """
        尝试为城堡支付一次维护费用（首次激活或手动续期）。
        gold_ref[0] 是可变金币引用（通过列表模拟引用传递）。
        返回日志消息。

        已在维护中的区域 → 直接返回空字符串（不重复扣费）。
        """
        region_id = region["region_id"]
        if self.is_maintained(region_id):
            return ""

        danger = region.get("danger_level", 1)
        cost = self._get_cost(danger)

        if gold_ref[0] >= cost:
            gold_ref[0] -= cost
            self.castle_maintenance[region_id] = self.MAINTENANCE_DURATION
            self._set_dungeons_secured(region_id, True)
            return (
                f"🏰 城堡维护 {region['name']}"
                f"（{cost}金币 / {int(self.MAINTENANCE_DURATION)}秒）— 到期自动续费"
            )
        else:
            remaining = int(self.MAINTENANCE_DURATION)
            return (
                f"💸 {region['name']} 城堡维护需 {cost} 金币"
                f"（当前:{gold_ref[0]}）— 未守护区域将被怪物重新侵占"
            )

    def tick_maintenance(self, dt: float, party) -> List[str]:
        """
        每帧更新维护倒计时，到期自动扣费续期。
        若英雄金币不足 → 失去该区域城堡守护，地牢可被入侵。
        返回日志消息列表。
        """
        messages: List[str] = []
        expired_ids: List[str] = []

        # 倒计时减量
        for region_id, remaining in list(self.castle_maintenance.items()):
            remaining -= dt
            if remaining <= 0.0:
                expired_ids.append(region_id)
            else:
                self.castle_maintenance[region_id] = remaining

        # 处理到期区域
        for region_id in expired_ids:
            danger = self.farm_regions.get(region_id, 1)
            cost = self._get_cost(danger)

            hero = party.hero if party else None
            if hero and hero.gold >= cost:
                # 自动续期
                hero.gold -= cost
                self.castle_maintenance[region_id] = self.MAINTENANCE_DURATION
                messages.append(f"🏰 城堡自动续期 -{cost}金币（{region_id}，{int(self.MAINTENANCE_DURATION)}秒）")
            else:
                # 金币不足 → 失去守护
                self._set_dungeons_secured(region_id, False)
                self.farm_regions.pop(region_id, None)
                del self.castle_maintenance[region_id]
                gold_str = f"当前:{hero.gold if hero else 0}"
                messages.append(
                    f"⚠️ 金币不足！{region_id} 城堡已失去守护"
                    f"（需{cost}，{gold_str}），怪物即将滋生！"
                )

        return messages

    def setup_farm(self, region_id: str, danger_level: int) -> str:
        """将区域设置为农场（仅已在维护中的城堡可设农场）"""
        if not self.is_maintained(region_id):
            return ""
        if region_id not in self.farm_regions:
            self.farm_regions[region_id] = danger_level
            return f"🌾 {region_id} 已设为农场（等级:{danger_level}）"
        return ""

    # ── 农场产出 ──────────────────────────────────────────

    def tick_farm(self, dt: float) -> int:
        """农场产出计算 — 每秒累积，达到整数时返回产出金币数。"""
        self._farm_accumulator += dt
        total_production = 0.0
        for danger_level in self.farm_regions.values():
            total_production += danger_level * 0.5

        if total_production > 0 and self._farm_accumulator >= 1.0:
            coins = int(self._farm_accumulator * total_production)
            self._farm_accumulator = 0.0
            return coins

        return 0

    # ── 查询 ──────────────────────────────────────────────

    def get_farm_count(self) -> int:
        return len(self.farm_regions)

    def get_maintained_count(self) -> int:
        """获取当前正在维护的城堡数量（替代原 get_secured_count）"""
        return len(self.castle_maintenance)

    # 兼容旧接口
    def get_secured_count(self) -> int:
        return self.get_maintained_count()

    def get_highest_conquered(self) -> int:
        """获取已维护城堡中的最高危险等级"""
        if not self.castle_maintenance:
            return 0
        max_danger = 0
        for rid in self.castle_maintenance:
            for d in self.dungeon_service.get_region_dungeons(rid):
                if d.danger_level > max_danger:
                    max_danger = d.danger_level
        return max_danger

    # ── 序列化 ────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "castle_maintenance": self.castle_maintenance,
            "farm_regions": self.farm_regions,
        }

    def from_dict(self, data: dict):
        self.castle_maintenance = data.get("castle_maintenance", {})
        self.farm_regions = data.get("farm_regions", {})
        # 兼容旧存档：如果读到旧格式的 secured_regions，转换为维护数据
        if not self.castle_maintenance and "secured_regions" in data:
            from src.config.settings import REGION_CHANGE_INTERVAL
            for rid in data.get("secured_regions", []):
                self.castle_maintenance[rid] = self.MAINTENANCE_DURATION
