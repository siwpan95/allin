# -*- coding: utf-8 -*-
"""地牢数据模型"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class RoomContent(Enum):
    """房间内容类型"""
    ENEMY = "enemy"          # 普通怪物
    CHEST = "chest"          # 宝箱
    POTION_RACK = "potion"   # 药水架
    ELITE = "elite"          # 精英房(怪物翻倍)


@dataclass
class Room:
    """地牢房间"""
    room_index: int                                    # 房间序号
    content: RoomContent                               # 内容类型
    enemies: List[dict] = field(default_factory=list)   # 当前房间的敌人列表
    cleared: bool = False                              # 是否清空
    chest_opened: bool = False                         # 宝箱是否已开启

    def has_enemies(self) -> bool:
        return any(e.get("alive", True) for e in self.enemies)

    def enemy_count(self) -> int:
        return sum(1 for e in self.enemies if e.get("alive", True))


@dataclass
class Dungeon:
    """地牢"""
    dungeon_id: str                                    # 唯一ID
    name: str                                          # 地牢名称
    region_id: str                                     # 所属区域ID
    danger_level: int                                  # 危险等级
    rooms: List[Room] = field(default_factory=list)    # 房间列表
    current_room_idx: int = 0                          # 当前所在房间
    cleared: bool = False                              # 整个地牢是否清空
    is_farm: bool = False                              # 是否已转为农场
    secured: bool = False                              # 是否有城堡守护（不再滋生）

    @property
    def current_room(self) -> Optional[Room]:
        if 0 <= self.current_room_idx < len(self.rooms):
            return self.rooms[self.current_room_idx]
        return None

    @property
    def total_rooms(self) -> int:
        return len(self.rooms)

    @property
    def cleared_rooms(self) -> int:
        return sum(1 for r in self.rooms if r.cleared)

    def is_complete(self) -> bool:
        return all(r.cleared for r in self.rooms)
