# -*- coding: utf-8 -*-
"""神器服务 — 纯被动 Buff 池，守卫者掉落 + 地牢清空概率掉落"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Artifact:
    """神器"""
    artifact_id: str
    name: str
    description: str
    effect_type: str    # damage / defense / gold / xp / drop_rate / farm / castle_cost
    effect_value: float
    source: str          # boss / dungeon_clear

    def get_effect_desc(self) -> str:
        pct = int(self.effect_value * 100) if self.effect_value < 1 else int(self.effect_value)
        effects = {
            "damage": f"物理伤害 +{pct}%",
            "defense": f"全队防御 +{pct}%",
            "gold": f"金币获取 +{pct}%",
            "xp": f"经验获取 +{pct}%",
            "drop_rate": f"掉落率 +{pct}%",
            "farm": f"农场产出 +{pct}%",
            "castle_cost": f"城堡价格 -{pct}%",
        }
        return effects.get(self.effect_type, self.description)


# 神器定义
ARTIFACT_DEFS = [
    ("ART_WAR", "战神拳套", "物理伤害永久提升", "damage", 0.15, "boss"),
    ("ART_MAGE", "魔法残页", "法术伤害永久提升", "damage", 0.15, "boss"),
    ("ART_LUCK", "幸运硬币", "掉落率提升", "drop_rate", 0.10, "dungeon_clear"),
    ("ART_GREED", "守财奴钱袋", "金币获取提升", "gold", 0.20, "dungeon_clear"),
    ("ART_SAGE", "贤者之石", "经验获取提升", "xp", 0.25, "boss"),
    ("ART_HUNT", "猎人之眼", "农场产出提升", "farm", 0.50, "dungeon_clear"),
    ("ART_SHIELD", "不朽之盾", "全队防御提升", "defense", 0.15, "boss"),
    ("ART_MERCHANT", "商人之证", "城堡价格降低", "castle_cost", 0.30, "dungeon_clear"),
]


class ArtifactService:
    """神器管理服务"""

    def __init__(self, data_service=None):
        self.owned: Dict[str, Artifact] = {}  # 已获得的神器
        # 尝试从 Excel 加载神器定义
        self._defs = None
        if data_service:
            config = data_service.get_artifact_config()
            if config and any(item.get("artifact_id") for item in config):
                self._defs = config

    def _get_defs(self) -> list:
        """获取神器定义（Excel 优先 → 硬编码回退）"""
        if self._defs:
            return [
                (d["artifact_id"], d["name"], d["description"],
                 d.get("effect_type", ""), d.get("effect_value", 0.0), d.get("source", ""))
                for d in self._defs
            ]
        return ARTIFACT_DEFS

    def try_get_artifact(self, source: str) -> Optional[Artifact]:
        """
        尝试获取一件神器。
        source: "boss" (守卫者, 100%) 或 "dungeon_clear" (地牢清空, 5%)
        """
        import random
        if source == "boss":
            defs = self._get_defs()
            boss_artifacts = [
                (aid, name, desc, etype, evalue, src)
                for aid, name, desc, etype, evalue, src in defs
                if src == "boss" and aid not in self.owned
            ]
            if not boss_artifacts:
                return None
            aid, name, desc, etype, evalue, src = random.choice(boss_artifacts)
        elif source == "dungeon_clear":
            if random.random() > 0.05:
                return None
            defs = self._get_defs()
            all_artifacts = [
                (aid, name, desc, etype, evalue, src)
                for aid, name, desc, etype, evalue, src in defs
                if aid not in self.owned
            ]
            if not all_artifacts:
                return None
            aid, name, desc, etype, evalue, src = random.choice(all_artifacts)
        else:
            return None

        artifact = Artifact(
            artifact_id=aid, name=name, description=desc,
            effect_type=etype, effect_value=evalue, source=src,
        )
        self.owned[aid] = artifact
        return artifact

    def get_effect(self, effect_type: str) -> float:
        """获取某类型效果的累加值"""
        total = 0.0
        for art in self.owned.values():
            if art.effect_type == effect_type:
                total += art.effect_value
        return total

    def get_damage_mult(self) -> float:
        return 1.0 + self.get_effect("damage")

    def get_defense_mult(self) -> float:
        return 1.0 + self.get_effect("defense")

    def get_gold_mult(self) -> float:
        return 1.0 + self.get_effect("gold")

    def get_xp_mult(self) -> float:
        return 1.0 + self.get_effect("xp")

    def get_drop_rate(self) -> float:
        return self.get_effect("drop_rate")

    def get_farm_mult(self) -> float:
        return 1.0 + self.get_effect("farm")

    def get_castle_cost_mult(self) -> float:
        return 1.0 - self.get_effect("castle_cost")

    def get_owned_list(self) -> List[Artifact]:
        return list(self.owned.values())

    def has_artifact(self, artifact_id: str) -> bool:
        return artifact_id in self.owned

    def to_dict(self) -> dict:
        return {
            aid: {"name": a.name, "effect_type": a.effect_type, "effect_value": a.effect_value}
            for aid, a in self.owned.items()
        }

    def from_dict(self, data: dict):
        self.owned.clear()
        for aid, ad in data.items():
            artifact = Artifact(
                artifact_id=aid,
                name=ad.get("name", ""),
                description="",
                effect_type=ad.get("effect_type", ""),
                effect_value=ad.get("effect_value", 0.0),
                source="unknown",
            )
            self.owned[aid] = artifact
