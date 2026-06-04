# -*- coding: utf-8 -*-
"""
探索系统 Mixin — 地牢推进 / 房间探索 / 区域移动

以 Mixin 方式注入 GameController，负责：地牢房间推进、房间内容交互、
战利品掉落、区域切换、地标发现、入侵检测。
"""

import random

from src.app.models.dungeon import RoomContent
from src.config.settings import LOOT_INTERVAL, ENEMY_RESPAWN_DELAY, REGION_CHANGE_INTERVAL


class GameExplorationMixin:
    """探索 Mixin — 地牢推进、探索、区域移动"""

    # ── 探索调度 ──────────────────────────────────────────

    def _handle_exploration(self, dt):
        """非战斗状态：探索（敌人重生 + 战利品掉落）"""
        # 敌人重生（从当前房间获取敌人）
        self._enemy_respawn_timer += dt
        if self._enemy_respawn_timer >= ENEMY_RESPAWN_DELAY:
            self._enemy_respawn_timer = 0.0
            self._start_combat_from_room()

        # 战利品掉落
        self._loot_timer += dt
        if self._loot_timer >= LOOT_INTERVAL:
            self._loot_timer = 0.0
            self._random_loot()

    # ── 地牢房间推进 ──────────────────────────────────────

    def _advance_dungeon_room(self):
        """推进到下一个地牢房间"""
        dungeon = self.current_dungeon
        if not dungeon:
            return

        # 当前房间已清空 → 推进
        if dungeon.current_room and dungeon.current_room.cleared:
            new_room = self.dungeon_service.advance_room(dungeon)
            if new_room is None:
                # 地牢清空！
                self._add_log(f"[地牢] {dungeon.name} 已清空！")
                self._on_dungeon_cleared()
            else:
                self._add_log(
                    f"[探索] {dungeon.name} — 进入第{new_room.room_index + 1}间房 "
                    f"[{dungeon.cleared_rooms}/{dungeon.total_rooms}]"
                )
                if new_room.content == RoomContent.CHEST:
                    self._add_log("[探索] 房间里有宝箱...")
                elif new_room.content == RoomContent.ELITE:
                    self._add_log("[探索] ⚡ 精英房！怪物成群出现！")
                    self.audio.sfx_explore_elite()

    def _on_dungeon_cleared(self):
        """地牢清空后的处理：金币奖励 + 神器掉落 + 下一个地牢"""
        dungeon = self.current_dungeon
        self.audio.sfx_explore_dungeon_cleared()

        # 奖励：金币（全队获得）
        gold_bonus = dungeon.danger_level * 50
        for member in self.party.members:
            member.gold += gold_bonus
        self._add_log(f"[奖励] 地牢清空，队伍获得 {gold_bonus} 金币")
        self.audio.sfx_system_gold()

        # 神器掉落（5% 概率）
        artifact = self.artifact_service.try_get_artifact("dungeon_clear")
        if artifact:
            self._add_log(
                f"🏶 获得神器：{artifact.name} — {artifact.get_effect_desc()}"
            )
            self.audio.sfx_system_artifact()

        # 检查区域状态并自动切换到下一个地牢
        self._auto_next_dungeon()

    def _auto_next_dungeon(self):
        """自动进入下一个地牢或触发区域清空"""
        region_id = self.current_region["region_id"]

        if self.dungeon_service.check_region_cleared(region_id):
            self._on_region_cleared()
            return

        # 尝试找下一个未清空地牢
        next_d = self.dungeon_service.get_first_uncleared_dungeon(region_id)
        if next_d:
            self.current_dungeon = next_d
            dungeons = self.dungeon_service.get_region_dungeons(region_id)
            # 找到序号
            for i, d in enumerate(dungeons):
                if d.dungeon_id == next_d.dungeon_id:
                    self.current_dungeon_idx = i
                    break
            self._add_log(
                f"[地牢] 进入: {next_d.name} [{next_d.total_rooms}间房]"
            )

    # ── 区域清空 ──────────────────────────────────────────

    def _on_region_cleared(self):
        """区域所有地牢清空后的处理：城堡购买 + 农场 + 切换区域"""
        region_id = self.current_region["region_id"]

        # 使用 castle_service 处理城堡购买
        gold_ref = [self.character.gold]  # 可变引用，允许服务层修改
        msg = self.castle_service.try_buy_castle(self.current_region, gold_ref)
        self.character.gold = gold_ref[0]
        self._add_log(msg)
        if "购买" in msg or "建造" in msg:
            self.audio.sfx_system_castle()

        # 无论是否购买城堡，都设为农场
        self.castle_service.setup_farm(
            region_id, self.current_region.get("danger_level", 1)
        )

        # 如果没买城堡，提示入侵可能
        if region_id not in self.castle_service.secured_regions:
            self._add_log(
                "[入侵] 未守护区域的地牢即将被怪物重新侵占..."
            )

        # 切换到相邻区域
        self._move_to_neighbor_region()

    # ── 房间交互 ──────────────────────────────────────────

    def _start_combat_from_room(self):
        """从当前房间获取敌人开始战斗"""
        dungeon = self.current_dungeon
        if not dungeon or not dungeon.current_room:
            return

        room = dungeon.current_room

        # 宝箱房：首次打开触发战利品
        if room.content == RoomContent.CHEST and not room.chest_opened:
            room.chest_opened = True
            self._add_log("[宝箱] 打开了宝箱！")
            self.audio.sfx_explore_chest()
            for _ in range(2):
                self._random_loot()
            room.cleared = True
            return

        # 药水架：首次触发获得药水
        if room.content == RoomContent.POTION_RACK and not room.chest_opened:
            room.chest_opened = True
            pt = self.potion_service.random_potion_type()
            msg = self.potion_service.pickup_potion(pt)
            self._add_log(f"[药水] 发现药水架 — {msg}")
            self.audio.sfx_explore_potion()
            room.cleared = True
            return

        # 如果房间有敌人且未清空
        if room.enemies and room.has_enemies():
            enemy = next(e for e in room.enemies if e.get("alive", True))
            self.combat_service.current_enemy = enemy
            self.combat_service.in_combat = True
            self._combat_time = 0.0
            self._add_log(f"[战斗] 遭遇: {enemy['name']}")
            self.audio.sfx_combat_attack()
        else:
            # 房间没有敌人（已全部击杀），标记清空
            room.cleared = True

    # ── 战利品 ────────────────────────────────────────────

    def _random_loot(self):
        """随机发现战利品（20% 概率），尝试为全队装备"""
        if random.random() < 0.2 and self.character:
            loot = self.item_service.generate_loot(self.character.level)
            if loot:
                self._add_log(f"[战利品] 发现: {loot.get_display_name()}")
                equipped = False
                for member in self.party.members:
                    if member.try_auto_equip(loot):
                        self._add_log(f"[装备] {member.name} 已装备: {loot.get_display_name()}")
                        equipped = True
                        break

    # ── 区域移动 ──────────────────────────────────────────

    def _move_to_neighbor_region(self):
        """移动到相邻区域"""
        regions = self.world_service.get_all_regions()
        neighbors = self.current_region.get("neighbors", [])

        # 优先邻居，否则随机选一个
        candidate_ids = neighbors if neighbors else [r["region_id"] for r in regions]
        if not candidate_ids:
            return

        new_id = random.choice(candidate_ids)
        new_region = self.world_service.get_region_by_id(new_id)
        if not new_region or new_region == self.current_region:
            return

        old_name = self.current_region["name"]
        self.current_region = new_region
        self._add_log(
            f"[旅行] {old_name} → {new_region['name']} "
            f"(危险:{new_region['danger_level']})"
        )
        self.audio.sfx_explore_travel()

        # 检查入侵：旧区域未守护地牢可能被滋生
        self._check_reinfestation(old_name)

        # 生成新区域地牢
        self.dungeon_service.generate_dungeons_for_region(new_region)
        dungeons = self.dungeon_service.get_region_dungeons(new_region["region_id"])
        if dungeons:
            self.current_dungeon = dungeons[0]
            self.current_dungeon_idx = 0
            self._add_log(
                f"[地牢] 进入: {self.current_dungeon.name} "
                f"[{self.current_dungeon.total_rooms}间房]"
            )

        # 描述新区域
        desc = self.world_service.get_region_description(new_region["region_id"])
        for line in desc.split("\n")[1:3]:
            self._add_log(f"        {line}")

    def _check_reinfestation(self, region_name: str):
        """检查旧区域是否有地牢被入侵滋生"""
        for rid, _dungeons in list(self.dungeon_service.dungeons.items()):
            region = self.world_service.get_region_by_id(rid)
            if not region:
                continue
            infested = self.dungeon_service.check_infest(rid)
            if infested:
                self._add_log(
                    f"[入侵] {region['name']}的{infested.name}被怪物重新侵占!"
                    f" 须要折返清理..."
                )
                self.audio.sfx_explore_infestation()
                # TODO Phase 2: 自动折返或提示

    # ── 地标发现 ──────────────────────────────────────────

    def _try_discover_landmark(self):
        """尝试发现地标"""
        if not self.current_region:
            return

        landmarks = [
            lm for lm in self.world_service.get_landmarks()
            if lm["region_id"] == self.current_region["region_id"]
            and not lm["discovered"]
        ]

        if landmarks and random.random() < 0.2:
            lm = random.choice(landmarks)
            self.world_service.discover_landmark(lm["landmark_id"])
            self._add_log(f"[地标] 发现: {lm['name']}!")
            self._add_log(f"        {lm['description']}")
            self.audio.sfx_explore_landmark()
