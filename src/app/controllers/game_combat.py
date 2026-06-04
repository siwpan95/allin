# -*- coding: utf-8 -*-
"""
战斗系统 Mixin — 战斗循环 / 击杀处理

以 Mixin 方式注入 GameController，负责：战斗计时更新、队伍攻击/防御、敌人击杀奖励。
"""

import random


class GameCombatMixin:
    """战斗 Mixin — _update_combat / _handle_enemy_defeated"""

    # ── 战斗循环 ──────────────────────────────────────────

    def _update_combat(self, dt):
        """更新战斗 — 组队版"""
        self._combat_time += dt
        enemy = self.combat_service.current_enemy

        # 检查敌人是否还活着
        if not enemy or not enemy.get("alive", True):
            self._handle_enemy_defeated(enemy)
            return

        # 队伍攻击（约每1.5秒一次）
        if self._combat_time >= 1.5:
            self._combat_time = 0.0
            msgs = self.combat_service.party_attack_cycle(self.party, enemy)
            for msg in msgs:
                self._add_log(msg)
                # 音效：每次攻击播放打击音
                if "暴击" in msg:
                    self.audio.sfx_combat_critical()
                else:
                    self.audio.sfx_combat_attack()
            if not enemy.get("alive", True):
                self._handle_enemy_defeated(enemy)
                return

        # 敌人反击
        if random.random() < 0.3 * dt:
            msgs = self.combat_service.party_defend_cycle(self.party, enemy, dt)
            for msg in msgs:
                self._add_log(msg)
                # 音效：受伤/闪避
                if "躲开" in msg:
                    self.audio.sfx_combat_dodge()
                elif "伤害" in msg:
                    self.audio.sfx_combat_hurt()
                elif "阵亡" in msg:
                    self.audio.sfx_system_fallen()

    # ── 击杀处理 ──────────────────────────────────────────

    def _handle_enemy_defeated(self, enemy):
        """处理敌人被击败：经验、金币、战利品、药水、成就"""
        char = self.character

        # 任务：击杀敌人（传递 party 以便任务奖励分发给全队）
        for event in self.quest_service.on_kill(enemy.get("name", "?"), char, self.party):
            self._add_log(event)

        # 全队获得经验与金币（存活队员每人获得相同经验）
        exp_gained = enemy.get("exp_reward", 10)
        gold_gained = enemy.get("gold_reward", 5)
        leveled_up = []
        for member in self.party.get_alive():
            member.kills += 1
            old_level = member.level
            member.gain_exp(exp_gained)
            member.gold += gold_gained
            if member.level > old_level:
                leveled_up.append(member)

        self._add_log(f"[击杀] {enemy.get('name', '?')}! 队伍 +{exp_gained}EXP")
        self.audio.sfx_combat_enemy_death()
        for member in leveled_up:
            self._add_log(f"[升级] {member.name} 升到了 Lv.{member.level}")
            self.audio.sfx_system_levelup()

        # 战利品掉落（50% 概率），尝试为全队自动装备
        if random.random() < 0.5:
            loot = self.item_service.generate_loot(char.level)
            if loot:
                self._add_log(f"[战利品] 获得: {loot.get_display_name()}")
                self.audio.sfx_explore_loot()
                equipped = False
                for member in self.party.members:
                    if member.try_auto_equip(loot):
                        self._add_log(f"[装备] {member.name} 已装备: {loot.get_display_name()}")
                        self.audio.sfx_explore_equip()
                        equipped = True
                        break

        # 药水掉落（5% 概率）
        if random.random() < 0.05:
            pt = self.potion_service.random_potion_type()
            msg = self.potion_service.pickup_potion(pt)
            self._add_log(msg)
            self.audio.sfx_explore_potion()

        # 成就检查
        self._check_achievements()

        # 检查房间是否清空
        dungeon = self.current_dungeon
        if dungeon and dungeon.current_room:
            room = dungeon.current_room
            # 从房间敌人列表中移除
            room.enemies = [e for e in room.enemies if e is not enemy]
            if not room.has_enemies():
                room.cleared = True
                cleared = dungeon.cleared_rooms
                total = dungeon.total_rooms
                self._add_log(f"[房间] 房间已清空!({cleared}/{total})")
                self.audio.sfx_explore_room_clear()
                # 缩短推进等待时间
                from src.config.settings import REGION_CHANGE_INTERVAL
                self._region_change_timer = REGION_CHANGE_INTERVAL - 2.0

        self.combat_service.in_combat = False
        self.combat_service.current_enemy = None
