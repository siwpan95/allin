# -*- coding: utf-8 -*-
"""物品生成服务 - 逻辑与数据解耦，优先从 Excel 加载"""
import json
import os
import random
from typing import Dict, List, Optional
from ..models.item import (
    ItemQuality, EquipmentSlot, WeaponType, ArmorType,
    Weapon, Armor, Accessory
)


class ItemService:
    """物品生成服务 - Excel 优先 → JSON 回退"""

    def __init__(self, data_dir: str = None, data_service=None):
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(src_dir, "resources", "data")
        self.data_dir = data_dir
        self._cache = {}
        self._data_service = data_service  # 可注入 DataService 实现 Excel 加载

    def _load_config(self) -> dict:
        """加载物品配置（Excel 优先，JSON 回退）"""
        if "item_templates" in self._cache:
            return self._cache["item_templates"]

        # 优先从 DataService (Excel) 加载
        if self._data_service is not None:
            data = self._data_service.get_item_templates()
            self._cache["item_templates"] = data
            return data

        # 回退到直接加载 JSON
        filepath = os.path.join(self.data_dir, "item_templates.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache["item_templates"] = data
                return data
        except FileNotFoundError:
            print(f"警告: 数据文件不存在 {filepath}")
            return {}
        except json.JSONDecodeError as e:
            print(f"错误: JSON 解析失败 {filepath}: {e}")
            return {}
    
    def _get_quality_mult(self, quality: ItemQuality, mult_type: str) -> float:
        """获取品质倍率"""
        data = self._load_config()
        if mult_type == "damage":
            mult_dict = data.get("quality_settings", {}).get("QUALITY_DAMAGE_MULT", {})
        elif mult_type == "defense":
            mult_dict = data.get("quality_settings", {}).get("QUALITY_DEFENSE_MULT", {})
        else:
            return 1.0
        
        return mult_dict.get(quality.name, 1.0)
    
    def _roll_quality(self, player_level: int) -> ItemQuality:
        """根据玩家等级 roll 物品品质"""
        # 权重配置（可以从 JSON 加载，这里简化）
        weights = [50, 30, 15, 8, 4, 2, 0.8, 0.2]
        
        if player_level >= 20:
            weights = [10, 20, 30, 20, 12, 5, 2, 1]
        elif player_level >= 10:
            weights = [30, 35, 20, 10, 4, 1, 0, 0]
        
        idx = random.choices(range(len(weights)), weights=weights)[0]
        return list(ItemQuality)[idx]
    
    def _random_bonuses(self, quality: ItemQuality, level: int) -> Dict[str, int]:
        """生成随机属性加成"""
        bonuses = {}
        num_bonus = quality.value[1]
        if num_bonus <= 0:
            return bonuses

        data = self._load_config()
        stat_pool = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma",
                      "crit_chance", "attack_speed", "hp_bonus", "mp_bonus"]
        
        chosen = random.sample(stat_pool, k=min(num_bonus, len(stat_pool)))
        for stat in chosen:
            if stat in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
                bonuses[stat] = random.randint(1, max(2, level // 3 + 1))
            elif stat == "crit_chance":
                bonuses[stat] = random.randint(1, 8)
            elif stat == "attack_speed":
                bonuses[stat] = random.randint(1, 15)
            else:
                bonuses[stat] = random.randint(5, 10 + level * 2)
        return bonuses
    
    def generate_weapon(self, player_level: int, weapon_type: Optional[WeaponType] = None) -> Weapon:
        """生成一把程序化武器"""
        quality = self._roll_quality(player_level)
        if weapon_type is None:
            weapon_type = random.choice(list(WeaponType))
        if weapon_type == WeaponType.SHIELD:
            weapon_type = WeaponType.SWORD
        
        # 从配置加载武器模板
        data = self._load_config()
        templates = data.get("weapon_templates", {})
        type_key = weapon_type.name
        if type_key in templates:
            name = random.choice(templates[type_key])
        else:
            name = "未知武器"
        
        # 高品质添加前缀
        if quality.value[1] >= 3:
            prefixes = data.get("prefixes", {}).get("weapon", ["锋利的"])
            name = random.choice(prefixes) + name
        
        base_damage = 5 + player_level * 2
        damage = int(base_damage * self._get_quality_mult(quality, "damage") + random.randint(-3, 5))
        damage = max(1, damage)
        
        speed = round(random.uniform(1.2, 3.5), 1)
        crit = round(0.05 + quality.value[1] * 0.01 + random.uniform(-0.01, 0.03), 3)
        
        bonuses = self._random_bonuses(quality, player_level)
        
        return Weapon(
            name=name,
            item_type="weapon",
            quality=quality,
            level_req=max(1, player_level - 3),
            value=damage * 5 + quality.value[1] * 20,
            weapon_type=weapon_type,
            damage=damage,
            speed=speed,
            crit_chance=max(0.01, min(0.5, crit)),
            bonuses=bonuses,
        )
    
    def generate_armor(self, player_level: int, slot: EquipmentSlot) -> Armor:
        """生成一件程序化护甲"""
        quality = self._roll_quality(player_level)
        
        # 根据 slot 选择护甲类型
        if slot in (EquipmentSlot.HEAD, EquipmentSlot.HANDS, EquipmentSlot.FEET):
            armor_type = random.choice([ArmorType.LIGHT, ArmorType.MEDIUM])
        elif slot == EquipmentSlot.CHEST:
            armor_type = random.choice(list(ArmorType))
        elif slot == EquipmentSlot.LEGS:
            armor_type = random.choice([ArmorType.MEDIUM, ArmorType.HEAVY, ArmorType.ROBE])
        else:
            armor_type = random.choice(list(ArmorType))
        
        # 从配置加载护甲模板
        data = self._load_config()
        templates = data.get("armor_templates", {})
        type_key = armor_type.name
        if type_key in templates:
            base_name = random.choice(templates[type_key])
        else:
            base_name = "未知护甲"
        
        slot_suffix = {
            EquipmentSlot.HEAD: "头盔",
            EquipmentSlot.CHEST: "胸甲",
            EquipmentSlot.HANDS: "手套",
            EquipmentSlot.LEGS: "护腿",
            EquipmentSlot.FEET: "靴子",
        }
        name = base_name + slot_suffix.get(slot, "")
        
        # 高品质添加前缀
        if quality.value[1] >= 3:
            prefixes = data.get("prefixes", {}).get("armor", ["坚固的"])
            name = random.choice(prefixes) + name
        
        base_defense = 3 + player_level * 1.5
        defense = int(base_defense * self._get_quality_mult(quality, "defense") + random.randint(-2, 4))
        defense = max(1, defense)
        
        bonuses = self._random_bonuses(quality, player_level)
        
        return Armor(
            name=name,
            item_type="armor",
            quality=quality,
            level_req=max(1, player_level - 3),
            value=defense * 4 + quality.value[1] * 15,
            armor_type=armor_type,
            defense=defense,
            slot=slot,
            bonuses=bonuses,
        )
    
    def generate_loot(self, player_level: int, loot_table: str = "normal"):
        """生成战利品 - 统一入口"""
        roll = random.random()
        if roll < 0.15:
            # 饰品
            slot = random.choice([EquipmentSlot.NECK, EquipmentSlot.RING])
            return self.generate_accessory(player_level, slot)
        elif roll < 0.55:
            # 武器
            return self.generate_weapon(player_level)
        else:
            # 护甲
            slot = random.choice([
                EquipmentSlot.HEAD, EquipmentSlot.CHEST,
                EquipmentSlot.HANDS, EquipmentSlot.LEGS, EquipmentSlot.FEET
            ])
            return self.generate_armor(player_level, slot)
    
    def generate_accessory(self, player_level: int, slot: EquipmentSlot) -> Accessory:
        """生成一个饰品"""
        quality = self._roll_quality(player_level)
        if quality.value[1] < ItemQuality.FINE.value[1]:
            quality = ItemQuality.FINE
        
        data = self._load_config()

        if slot == EquipmentSlot.RING:
            name = random.choice(data.get("jewelry_names", {}).get("RING", ["铁戒指"]))
        else:
            slot = EquipmentSlot.NECK
            name = random.choice(data.get("jewelry_names", {}).get("NECK", ["铁项链"]))
        
        if quality.value[1] >= 3:
            prefixes = data.get("prefixes", {}).get("accessory", ["魔力"])
            name = random.choice(prefixes) + name
        
        effect_pool = data.get("effect_pool", ["生命恢复", "法力恢复", "暴击提升", "速度提升", "经验加成"])
        effect = random.choice(effect_pool)
        
        bonuses = self._random_bonuses(quality, player_level)
        
        return Accessory(
            name=name,
            item_type="accessory",
            quality=quality,
            level_req=max(1, player_level - 5),
            value=quality.value[1] * 30 + player_level * 5,
            slot=slot,
            effect=effect,
            bonuses=bonuses,
        )
