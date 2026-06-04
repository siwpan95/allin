# -*- coding: utf-8 -*-
"""任务数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class QuestType(Enum):
    """任务类型"""
    KILL = "击杀"
    COLLECT = "收集"
    EXPLORE = "探索"
    BOSS = "首领"
    ESCORT = "护送"
    DELIVERY = "递送"
    EPIC = "史诗"

    @classmethod
    def from_name(cls, name: str) -> "QuestType":
        """从名称字符串或枚举名获取 QuestType"""
        name_upper = name.upper()
        for member in cls:
            if member.name == name_upper or member.value == name:
                return member
        return cls.KILL


class QuestStatus(Enum):
    """任务状态"""
    AVAILABLE = "可接取"
    ACTIVE = "进行中"
    COMPLETED = "已完成"
    FAILED = "失败"


@dataclass
class QuestReward:
    """任务奖励"""
    exp: int = 0
    gold: int = 0
    items: List = field(default_factory=list)
    reputation: int = 0

    def describe(self) -> str:
        parts = []
        if self.exp:
            parts.append(f"+{self.exp}EXP")
        if self.gold:
            parts.append(f"+{self.gold}G")
        if self.items:
            parts.append(f"物品: {len(self.items)}件")
        return ", ".join(parts) if parts else "无"


@dataclass
class Quest:
    """任务数据模型"""
    quest_id: str
    name: str
    quest_type: QuestType
    description: str
    target: str
    target_count: int
    current_count: int = 0
    status: QuestStatus = QuestStatus.AVAILABLE
    level_req: int = 1
    previous_quest: Optional[str] = None
    next_quest: Optional[str] = None
    reward: QuestReward = field(default_factory=QuestReward)
    is_epic: bool = False
    story_text: str = ""
    completion_text: str = ""

    def update_progress(self, amount: int = 1) -> bool:
        """更新进度，返回是否完成"""
        self.current_count = min(self.target_count, self.current_count + amount)
        if self.current_count >= self.target_count:
            self.status = QuestStatus.COMPLETED
            return True
        return False

    def progress_pct(self) -> float:
        """进度百分比"""
        if self.target_count <= 0:
            return 1.0
        return self.current_count / self.target_count

    def progress_bar(self, width: int = 20) -> str:
        """进度条"""
        filled = int(self.progress_pct() * width)
        bar = "#" * filled + "." * (width - filled)
        return f"[{bar}] {self.current_count}/{self.target_count}"

    def get_status_icon(self) -> str:
        """状态图标"""
        if self.status == QuestStatus.COMPLETED:
            return "[*]"
        elif self.status == QuestStatus.ACTIVE:
            return "[>]"
        elif self.status == QuestStatus.FAILED:
            return "[x]"
        return "[-]"
