# -*- coding: utf-8 -*-
"""成就服务 — 纯被动追踪，自动播报 + 奖励"""
from typing import Dict, List, Callable, Optional


class Achievement:
    """成就定义"""
    def __init__(self, ach_id: str, name: str, description: str, target: int,
                 reward_type: str, reward_value: float, hidden: bool = False):
        self.ach_id = ach_id
        self.name = name
        self.description = description
        self.target = target      # 达成目标值
        self.reward_type = reward_type  # gold / xp / hp_bonus / xp_bonus / title
        self.reward_value = reward_value
        self.hidden = hidden
        self.progress: int = 0     # 当前进度
        self.completed: bool = False


# 成就定义列表
ACHIEVEMENT_DEFS = [
    # (id, name, desc, target, reward_type, reward_value, hidden)
    ("ACH_KILL_10", "初出茅庐", "击杀10只怪物", 10, "gold", 50, False),
    ("ACH_KILL_100", "百人斩", "击杀100只怪物", 100, "gold", 200, False),
    ("ACH_KILL_1000", "千人屠", "击杀1000只怪物", 1000, "gold", 1000, False),
    ("ACH_KILL_10000", "万人敌", "击杀10000只怪物", 10000, "gold", 5000, False),
    ("ACH_FINE_ITEM", "寻宝猎人", "获得精良品质装备", 1, "gold", 100, False),
    ("ACH_LEGENDARY", "欧皇时刻", "获得传说品质装备", 1, "gold", 500, False),
    ("ACH_LANDMARK_5", "探险家", "发现5个地标", 5, "xp", 200, False),
    ("ACH_REGION_3", "征服者", "清空3个区域", 3, "gold", 300, False),
    ("ACH_CASTLE_5", "领主", "守护5座城堡", 5, "gold", 1000, False),
    ("ACH_QUEST_10", "任务达人", "完成10个任务", 10, "gold", 300, False),
    ("ACH_POTION_20", "药水爱好者", "使用20瓶药水", 20, "gold", 200, False),
    ("ACH_LV10", "老兵", "角色达到10级", 10, "xp_bonus", 0.10, False),
    ("ACH_LV25", "传奇", "角色达到25级", 25, "gold", 1000, False),
    ("ACH_DEATH_5", "不死之身", "死亡后复活5次", 5, "hp_bonus", 0.10, False),
    ("ACH_ARTIFACT_5", "收集狂", "拥有5件神器", 5, "gold", 800, False),
    ("ACH_SOLO", "寂寞之旅", "单角色守护5座城堡", 5, "title", "孤勇者", True),
    ("ACH_ALLSTAR", "全明星", "4队友每人不同职业", 4, "gold", 500, False),
    ("ACH_CASTLE_10", "城堡大师", "守护10座城堡", 10, "gold", 2000, False),
    ("ACH_INFEST_50", "救火队员", "清除50次入侵滋生", 50, "gold", 500, False),
    ("ACH_REGION_30", "世界探索者", "到达30级区域", 30, "gold", 1500, False),
]


class AchievementService:
    """成就服务"""

    def __init__(self, data_service=None):
        self.achievements: Dict[str, Achievement] = {}
        self._pending_rewards: List[dict] = []

        # 尝试从 Excel 加载成就配置
        if data_service:
            config = data_service.get_achievement_config()
            if config:
                self._init_from_excel(config)
            else:
                self._init_achievements()
        else:
            self._init_achievements()

    def _init_from_excel(self, config: list):
        """从 Excel 配置初始化成就"""
        global ACHIEVEMENT_DEFS
        new_defs = []
        for item in config:
            aid = item.get("ach_id", "")
            name = item.get("name", "")
            desc = item.get("description", "")
            target = int(item.get("target", 0))
            rtype = item.get("reward_type", "")
            rval = float(item.get("reward_value", 0))
            hidden = item.get("hidden", False)
            if aid and name:
                new_defs.append((aid, name, desc, target, rtype, rval, hidden))
                self.achievements[aid] = Achievement(
                    ach_id=aid, name=name, description=desc,
                    target=target, reward_type=rtype, reward_value=rval, hidden=hidden,
                )
        if new_defs:
            ACHIEVEMENT_DEFS = new_defs

    def _init_achievements(self):
        for ach_id, name, desc, target, rtype, rval, hidden in ACHIEVEMENT_DEFS:
            self.achievements[ach_id] = Achievement(
                ach_id=ach_id, name=name, description=desc,
                target=target, reward_type=rtype, reward_value=rval,
                hidden=hidden,
            )

    def update_progress(self, ach_id: str, increment: int = 1) -> Optional[str]:
        """
        更新成就进度。如果成就完成，返回播报消息（None表示未完成）。
        """
        ach = self.achievements.get(ach_id)
        if not ach or ach.completed:
            return None

        ach.progress += increment
        if ach.progress >= ach.target:
            ach.completed = True
            ach.progress = ach.target
            self._pending_rewards.append({
                "name": ach.name,
                "reward_type": ach.reward_type,
                "reward_value": ach.reward_value,
            })
            return f"🏆 成就解锁：{ach.name} — {ach.description}"
        return None

    def get_pending_rewards(self) -> List[dict]:
        """获取并清空待发放奖励"""
        rewards = self._pending_rewards[:]
        self._pending_rewards.clear()
        return rewards

    def get_completed(self) -> List[Achievement]:
        return [a for a in self.achievements.values() if a.completed]

    def get_uncompleted(self) -> List[Achievement]:
        return [a for a in self.achievements.values() if not a.completed and not a.hidden]

    def get_completed_count(self) -> int:
        return len(self.get_completed())

    def to_dict(self) -> dict:
        return {
            ach_id: {"progress": a.progress, "completed": a.completed}
            for ach_id, a in self.achievements.items()
        }

    def from_dict(self, data: dict):
        for ach_id, state in data.items():
            if ach_id in self.achievements:
                self.achievements[ach_id].progress = state.get("progress", 0)
                self.achievements[ach_id].completed = state.get("completed", False)
