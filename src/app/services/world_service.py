# -*- coding: utf-8 -*-
"""
世界生成服务 - 程序化世界生成
矮人要塞风格：生成区域、定居点、地标、历史事件
"""
import json
import os
import random
from typing import List, Dict, Optional


class WorldService:
    """世界生成服务"""
    
    def __init__(self, data_dir: str = None, seed: Optional[int] = None):
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(os.path.dirname(current_dir), "resources", "data")
        self.data_dir = data_dir
        self.seed = seed or self._rng.randint(1, 999999)
        self._rng = random.Random(self.seed)  # 独立随机实例，不污染全局状态
        self.regions = []
        self.history_events = []
        self._settlements = []
        self._landmarks = []
        self._generate_world()
    
    def _generate_world(self):
        """生成世界"""
        self._generate_regions()
        self._generate_settlements()
        self._generate_landmarks()
        self._generate_history()
    
    def _generate_regions(self):
        """生成区域"""
        region_names = [
            "艾森伍德", "黑岩山脉", "白银平原", "暗影沼泽", "烈焰沙漠",
            "霜冻山谷", "翡翠森林", "遗忘沙漠", "巨人之巅", "月光林地",
            "风暴海湾", "幽暗深渊", "黄金草原", "龙骨荒原", "薄雾群岛",
        ]
        terrains = ["平原", "森林", "丘陵", "山脉", "沙漠", "沼泽", "冻土", "海洋", "河流", "洞穴"]
        biomes = ["温带", "热带", "干旱", "极地", "火山", "沿海"]
        resources_pool = ["铁", "铜", "金", "银", "宝石", "草药", "木材", "石材", "水晶", "龙鳞"]
        
        for i, name in enumerate(region_names):
            region = {
                "region_id": f"region_{i:02d}",
                "name": name,
                "terrain": self._rng.choice(terrains),
                "biome": self._rng.choice(biomes),
                "x": i % 5,
                "y": i // 5,
                "danger_level": self._rng.randint(1, 10),
                "resources": self._rng.sample(resources_pool, k=self._rng.randint(2, 5)),
                "settlements": [],
                "landmarks": [],
                "neighbors": [],
                "history": [],
                "enemies": [],
            }
            self.regions.append(region)
        
        # 设置邻居关系
        for region in self.regions:
            nx, ny = region["x"], region["y"]
            for other in self.regions:
                if other["region_id"] == region["region_id"]:
                    continue
                if abs(other["x"] - nx) + abs(other["y"] - ny) <= 1:
                    region["neighbors"].append(other["region_id"])
    
    def _generate_settlements(self):
        """生成定居点"""
        settlement_types = ["村庄", "城镇", "城市", "要塞", "驿站"]
        races = ["人类", "精灵", "矮人", "半身人", "侏儒", "半兽人"]
        
        for region in self.regions:
            if self._rng.random() < 0.6:
                settlement = {
                    "name": f"{region['name']}{self._rng.choice(settlement_types)}",
                    "type": self._rng.choice(settlement_types),
                    "population": self._rng.randint(50, 5000),
                    "race": self._rng.choice(races),
                    "founded_year": self._rng.randint(-500, 0),
                    "description": f"一个{self._rng.choice(races)}{self._rng.choice(settlement_types)}，位于{region['name']}。"
                }
                region["settlements"].append(settlement)
                self._settlements.append(settlement)
    
    def _generate_landmarks(self):
        """生成地标"""
        landmark_templates = [
            ("古老遗迹", "一座被时间遗忘的古老文明遗迹，散发着神秘的能量。"),
            ("被诅咒的神殿", "曾经神圣的神殿，如今被黑暗力量腐蚀。"),
            ("英雄墓地", "传说中英雄的最后安息之地。"),
            ("魔法泉", "涌动着纯净魔力的泉水。"),
            ("龙巢", "远古巨龙的巢穴，财宝不计其数。"),
            ("远古战场", "千年前大战的遗址，插满生锈武器。"),
            ("精灵遗迹", "精灵族留下的神秘建筑。"),
            ("矮人要塞", "古老的矮人要塞，深入地下。"),
        ]
        
        for region in self.regions:
            if self._rng.random() < 0.4:
                lm_name, lm_desc = self._rng.choice(landmark_templates)
                landmark = {
                    "landmark_id": f"lm_{region['region_id']}_{self._rng.randint(100, 999)}",
                    "name": f"{region['name']}的{lm_name}",
                    "type": lm_name,
                    "description": lm_desc,
                    "discovered": self._rng.random() < 0.3,
                    "region_id": region["region_id"],
                }
                region["landmarks"].append(landmark)
                self._landmarks.append(landmark)
    
    def _generate_history(self):
        """生成世界历史"""
        history_pool = [
            "矮人氏族在黑岩山脉建立了第一座要塞。",
            "精灵与兽人之间的战争持续了百年。",
            "大瘟疫席卷了白银平原，半数人口丧生。",
            "一位无名英雄在巨龙巢穴中夺回了圣剑。",
            "魔法泉突然干涸，法师们陷入恐慌。",
            "北方部落南侵，烈焰沙漠的游牧民奋起抵抗。",
            "遗忘沙漠中发现了远古遗迹。",
            "霜冻山谷的冰霜巨人苏醒。",
            "翡翠森林中出现了一颗世界树幼苗。",
            "月光林地中的暗影生物开始活跃。",
        ]
        self._rng.shuffle(history_pool)
        self.history_events = history_pool[:6]
        for region in self.regions:
            region["history"] = self._rng.sample(history_pool, k=self._rng.randint(1, 3))
    
    def get_all_regions(self) -> List[dict]:
        """获取所有区域"""
        return self.regions
    
    def get_region_by_id(self, region_id: str) -> Optional[dict]:
        """根据ID获取区域"""
        for r in self.regions:
            if r["region_id"] == region_id:
                return r
        return None
    
    def describe_history(self) -> str:
        """描述世界历史"""
        lines = [f"═══ 世界历史（种子: {self.seed}） ═══"]
        for i, event in enumerate(self.history_events, 1):
            lines.append(f"  第{i}纪元: {event}")
        return "\n".join(lines)
    
    def get_settlements(self) -> List[dict]:
        """获取所有定居点"""
        return self._settlements
    
    def get_landmarks(self) -> List[dict]:
        """获取所有地标"""
        return self._landmarks
    
    def discover_landmark(self, landmark_id: str) -> bool:
        """发现地标"""
        for lm in self._landmarks:
            if lm["landmark_id"] == landmark_id and not lm["discovered"]:
                lm["discovered"] = True
                return True
        return False
    
    def get_region_description(self, region_id: str) -> str:
        """获取区域详细描述"""
        region = self.get_region_by_id(region_id)
        if not region:
            return "未知区域"
        
        lines = [
            f"=== {region['name']} ===",
            f"地形: {region['terrain']}  气候: {region['biome']}",
            f"危险等级: {'*' * region['danger_level']}{'.' * (10 - region['danger_level'])}",
        ]
        if region["settlements"]:
            lines.append(f"定居点: {', '.join(s['name'] for s in region['settlements'])}")
        if region["landmarks"]:
            discovered = [lm["name"] for lm in region["landmarks"] if lm["discovered"]]
            if discovered:
                lines.append(f"已发现地标: {', '.join(discovered)}")
            hidden = len([lm for lm in region["landmarks"] if not lm["discovered"]])
            if hidden:
                lines.append(f"未发现地标: {hidden}个")
        if region["resources"]:
            lines.append(f"资源: {', '.join(region['resources'][:5])}")
        return "\n".join(lines)
