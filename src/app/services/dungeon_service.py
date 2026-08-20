# -*- coding: utf-8 -*-
"""地牢服务 - 地牢生成、房间推进"""
import random
from typing import List, Dict, Optional
from ..models.dungeon import Dungeon, Room, RoomContent


# 地牢名称词库
DUNGEON_PREFIXES = [
    "暗影", "遗忘", "诅咒", "深渊", "血染", "黑暗", "幽暗", "混沌",
    "烈焰", "冰霜", "雷霆", "毒雾", "死寂", "破碎", "荒芜", "腐化",
]
DUNGEON_TYPES = [
    "洞穴", "神殿", "矿坑", "堡垒", "地牢", "陵墓", "高塔", "深渊",
    "墓穴", "石窟", "要塞", "地窖", "迷宫", "废墟", "巢穴", "回廊",
]


class DungeonService:
    """地牢生成与管理服务"""

    def __init__(self, data_service, world_service):
        self.data_service = data_service
        self.world_service = world_service
        self.dungeons: Dict[str, List[Dungeon]] = {}  # region_id → [Dungeon, ...]

    def generate_dungeons_for_region(self, region: dict) -> List[Dungeon]:
        """为指定区域生成地牢（2-4个）"""
        region_id = region["region_id"]
        danger = region.get("danger_level", 1)
        num_dungeons = random.randint(2, 4)

        dungeons = []
        for i in range(num_dungeons):
            prefix = random.choice(DUNGEON_PREFIXES)
            dtype = random.choice(DUNGEON_TYPES)
            name = f"{prefix}{dtype}"

            # 房间数: 5 + 危险等级 * 2
            num_rooms = 5 + danger * 2
            rooms = self._generate_rooms(num_rooms, danger)

            dungeon = Dungeon(
                dungeon_id=f"{region_id}_d{i:02d}",
                name=name,
                region_id=region_id,
                danger_level=danger,
                rooms=rooms,
            )
            dungeons.append(dungeon)

        self.dungeons[region_id] = dungeons
        return dungeons

    def _generate_rooms(self, num_rooms: int, danger: int) -> List[Room]:
        """生成地牢房间"""
        rooms = []
        for idx in range(num_rooms):
            # 房间内容随机
            roll = random.random()
            if roll < 0.25:
                content = RoomContent.CHEST
            elif roll < 0.40:
                content = RoomContent.POTION_RACK
            elif roll < 0.50 and idx > 0:  # 第一个房间不生成精英房
                content = RoomContent.ELITE
            else:
                content = RoomContent.ENEMY

            # 生成房间敌人（ENEMY/ELITE 才生成，CHEST/POTION 为空）
            enemies = []
            if content == RoomContent.ENEMY:
                enemies = self._spawn_enemies(danger, 1, 3)
            elif content == RoomContent.ELITE:
                enemies = self._spawn_enemies(danger, 3, 6)

            rooms.append(Room(room_index=idx, content=content, enemies=enemies))

        return rooms

    def _spawn_enemies(self, danger: int, min_count: int, max_count: int) -> List[dict]:
        """生成房间怪物"""
        from ..services.combat_service import CombatService
        cs = CombatService(self.data_service)
        templates = self.data_service.get_enemies_by_level(danger, level_range=2)
        if not templates:
            templates = self.data_service.get_enemies_by_level(1, level_range=5)

        count = random.randint(min_count, max_count)
        enemies = []
        for _ in range(count):
            tpl = random.choice(templates)
            enemy = cs.create_enemy_from_template(tpl)
            enemies.append(enemy)
        return enemies

    def get_region_dungeons(self, region_id: str) -> List[Dungeon]:
        """获取区域的地牢列表（不存在则生成）"""
        if region_id not in self.dungeons:
            region = self.world_service.get_region_by_id(region_id)
            if region:
                self.generate_dungeons_for_region(region)
        return self.dungeons.get(region_id, [])

    def get_current_dungeon(self, region_id: str, dungeon_idx: int = 0) -> Optional[Dungeon]:
        """获取当前区域当前地牢"""
        dungeons = self.get_region_dungeons(region_id)
        if dungeons and 0 <= dungeon_idx < len(dungeons):
            return dungeons[dungeon_idx]
        return None

    def advance_room(self, dungeon: Dungeon) -> Optional[Room]:
        """推进到下一个房间，返回新房间"""
        if dungeon.current_room:
            dungeon.current_room.cleared = True

        dungeon.current_room_idx += 1
        if dungeon.current_room_idx >= dungeon.total_rooms:
            dungeon.cleared = True
            return None

        return dungeon.current_room

    def check_region_cleared(self, region_id: str) -> bool:
        """检查区域所有地牢是否清空"""
        dungeons = self.get_region_dungeons(region_id)
        if not dungeons:
            return False
        return all(d.cleared for d in dungeons)

    def check_infest(self, region_id: str) -> Optional[Dungeon]:
        """
        入侵/滋生检查：
        如果区域没有可探索的地牢（全清空或无未清空房间），
        随机选一个已清空但未守护的地牢重新滋生怪物。
        返回被入侵的地牢，或 None 表示无需入侵。
        """
        dungeons = self.get_region_dungeons(region_id)
        if not dungeons:
            return None

        # 检查是否有未完成的地牢
        has_uncleared = any(not d.cleared for d in dungeons)
        if has_uncleared:
            return None

        # 所有地牢都已清空：找一个未守护的进行入侵
        unsecured = [d for d in dungeons if not d.secured and not d.is_farm]
        if not unsecured:
            return None

        target = random.choice(unsecured)
        # 随机重新滋生：保留原有房间数，重新生成怪物
        for room in target.rooms:
            content = room.content
            if content in (RoomContent.ENEMY, RoomContent.ELITE):
                danger = target.danger_level
                if content == RoomContent.ENEMY:
                    room.enemies = self._spawn_enemies(danger, 1, 3)
                else:
                    room.enemies = self._spawn_enemies(danger, 3, 6)
            room.cleared = False
            room.chest_opened = False
        target.cleared = False
        target.current_room_idx = 0
        return target

    def check_region_has_uncleared(self, region_id: str) -> bool:
        """检查区域是否有未清空地牢"""
        dungeons = self.get_region_dungeons(region_id)
        if not dungeons:
            return False
        return any(not d.cleared for d in dungeons)

    def get_first_uncleared_dungeon(self, region_id: str) -> Optional[Dungeon]:
        """获取区域第一个未清空地牢"""
        dungeons = self.get_region_dungeons(region_id)
        for d in dungeons:
            if not d.cleared:
                return d
        return None
