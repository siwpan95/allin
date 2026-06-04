# -*- coding: utf-8 -*-
"""战斗服务 - 处理战斗逻辑"""
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from ..models.item import Weapon, EquipmentSlot


class CombatService:
    """战斗服务 - 解耦战斗逻辑与数据"""
    
    def __init__(self, data_service):
        self.data_service = data_service
        self.HIT_LOCATIONS = ["头部", "胸部", "手臂", "腿部", "手部", "脚部"]
        self.HIT_WEIGHTS = [0.1, 0.35, 0.2, 0.2, 0.1, 0.05]
        self.in_combat = False
        self.current_enemy = None
    
    def create_enemy_from_template(self, template: dict) -> dict:
        """从模板创建敌人数据（返回字典，不直接依赖 Enemy 类）"""
        return {
            "name": f"{template['name']} Lv.{template.get('level', 1)}",
            "level": template.get("level", 1),
            "max_hp": template.get("hp", 30),
            "hp": template.get("hp", 30),
            "damage": template.get("damage", 5),
            "defense": template.get("defense", 0),
            "exp_reward": template.get("exp", 10),
            "gold_reward": template.get("gold", 5),
            "loot_table": template.get("loot_table", "normal"),
            "race": template.get("race", "未知"),
            "description": template.get("description", ""),
            "alive": True,
            "body_parts": {
                "头部": 0.15, "躯干": 0.40, "手臂": 0.20,
                "腿部": 0.20, "要害": 0.05,
            },
            "buffs": {},
            "buff_durations": {},
        }
    
    def calculate_player_damage(self, character, weapon, is_crit=False):
        """计算玩家伤害"""
        base_dmg = character.get_attack_power()
        
        if is_crit:
            damage = int(base_dmg * (1.5 + random.random() * 0.5))
        else:
            damage = int(base_dmg * (0.85 + random.random() * 0.3))
        
        return max(1, damage)
    
    def calculate_enemy_damage(self, enemy_data: dict) -> int:
        """计算敌人伤害"""
        return max(1, enemy_data["damage"] + random.randint(-2, 3))
    
    def apply_damage_to_enemy(self, enemy_data: dict, damage: int, location: str = "躯干") -> int:
        """对敌人造成伤害，返回实际伤害"""
        location_mult = enemy_data["body_parts"].get(location, 1.0)
        actual = max(0, int(damage * location_mult) - enemy_data["defense"] // 3)
        if actual <= 0:
            actual = random.randint(1, max(1, damage // 4))
        
        enemy_data["hp"] = max(0, enemy_data["hp"] - actual)
        if enemy_data["hp"] <= 0:
            enemy_data["alive"] = False
        
        return actual
    
    def apply_damage_to_character(self, character, raw_damage: int) -> int:
        """对角色造成伤害，返回实际伤害"""
        actual = character.take_damage(raw_damage)
        return actual
    
    def check_dodge(self, character) -> bool:
        """检查是否闪避"""
        dodge_chance = character.stats.dexterity * 0.01
        return random.random() < dodge_chance
    
    def check_block(self, character) -> bool:
        """检查是否格挡"""
        block_chance = 0.05 + character.stats.constitution * 0.003
        return random.random() < block_chance
    
    def get_hit_location(self) -> str:
        """获取命中部位"""
        return random.choices(self.HIT_LOCATIONS, weights=self.HIT_WEIGHTS)[0]
    
    def get_enemy_template(self, region_data: dict) -> Optional[dict]:
        """根据区域获取敌人模板"""
        enemies = self.data_service.get_enemies_by_level(region_data.get("danger_level", 1))
        if enemies:
            return random.choice(enemies)
        return None

    # ======== 组队战斗方法 ========

    def party_attack_cycle(self, party, enemy_data: dict) -> List[str]:
        """
        队伍攻击循环：所有存活队员各自攻击当前敌人。
        返回战斗日志列表。
        """
        messages = []
        if not enemy_data or not enemy_data.get("alive", True):
            return messages

        for member in party.get_alive():
            is_crit = random.random() < 0.1
            damage = self.calculate_player_damage(member, None, is_crit)
            location = self.get_hit_location()
            actual = self.apply_damage_to_enemy(enemy_data, damage, location)

            name_tag = f"[{member.char_class.value[0]}·{member.name}]"
            crit_text = "【暴击！】" if is_crit else ""
            messages.append(
                f"[战斗] {name_tag} 攻击{enemy_data['name']}的{location}，造成{actual}伤害 {crit_text}"
            )
            if not enemy_data.get("alive", True):
                break

        return messages

    def party_defend_cycle(self, party, enemy_data: dict, dt: float) -> List[str]:
        """
        敌人攻击队伍：随机选择一个存活队员攻击。
        返回战斗日志列表。
        """
        messages = []
        if not enemy_data or not enemy_data.get("alive", True):
            return messages

        alive = party.get_alive()
        if not alive:
            return messages

        target = random.choice(alive)
        if not self.check_dodge(target):
            dmg = self.calculate_enemy_damage(enemy_data)
            actual = self.apply_damage_to_character(target, dmg)
            name_tag = f"[{target.char_class.value[0]}·{target.name}]"
            messages.append(
                f"[战斗] {enemy_data['name']} 攻击 {name_tag}，造成 {actual} 伤害"
            )
            if target.hp <= 0:
                messages.append(f"[系统] {name_tag} 阵亡！")
        else:
            name_tag = f"[{target.char_class.value[0]}·{target.name}]"
            messages.append(f"[战斗] {name_tag} 躲开了攻击！")

        return messages

    def resurrect_fallen(self, party) -> List[str]:
        """自动复活阵亡队员（50% HP，3秒后复活）"""
        messages = []
        for member in party.get_defeated():
            member.hp = int(member.max_hp * 0.5)
            name_tag = f"[{member.char_class.value[0]}·{member.name}]"
            messages.append(f"[系统] {name_tag} 已复活（HP:{member.hp}）")
        return messages
