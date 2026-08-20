# -*- coding: utf-8 -*-
"""任务管理服务 — 自动接取/进度更新/完成奖励"""
import random
from typing import List, Dict, Optional
from ..models.quest import Quest, QuestReward, QuestType, QuestStatus
from ..models.character import Character


class QuestService:
    """任务管理服务：管理角色的任务生命周期"""

    MAX_ACTIVE_QUESTS = 5  # 最多同时进行中的任务
    AUTO_ACCEPT_INTERVAL = 15.0  # 自动接取间隔（秒）

    def __init__(self, data_service):
        self.data_service = data_service
        self.active_quests: Dict[str, Quest] = {}  # quest_id -> Quest
        self.completed_quests: List[str] = []  # 已完成的任务 ID 列表
        self._accept_timer = 0.0
        self._templates = data_service.get_quest_templates()

    def tick(self, dt: float, character: Character) -> List[str]:
        """每帧更新，返回新事件日志列表"""
        events = []
        self._accept_timer += dt

        # 自动接取新任务
        if self._accept_timer >= self.AUTO_ACCEPT_INTERVAL:
            self._accept_timer = 0.0
            event = self._auto_accept_quest(character)
            if event:
                events.append(event)

        return events

    def _auto_accept_quest(self, character: Character) -> Optional[str]:
        """自动接取一个合适的任务，返回日志文本"""
        if len(self.active_quests) >= self.MAX_ACTIVE_QUESTS:
            return None

        available = []
        for tpl in self._templates:
            qid = tpl.get("quest_id", "")
            if qid in self.active_quests or qid in self.completed_quests:
                continue
            if character.level < tpl.get("level_req", 1):
                continue
            prev = tpl.get("previous_quest")
            if prev and prev not in self.completed_quests:
                continue
            available.append(tpl)

        if not available:
            return None

        tpl = random.choice(available)
        quest = Quest(
            quest_id=tpl.get("quest_id", f"q{len(self.completed_quests)}"),
            name=tpl.get("name", "未知任务"),
            quest_type=QuestType.from_name(tpl.get("type", "KILL")),
            description=tpl.get("description", ""),
            target=tpl.get("target", ""),
            target_count=tpl.get("target_count", 5),
            level_req=tpl.get("level_req", 1),
            previous_quest=tpl.get("previous_quest"),
            next_quest=tpl.get("next_quest"),
            reward=QuestReward(
                exp=tpl.get("reward_exp", 0),
                gold=tpl.get("reward_gold", 0),
            ),
            is_epic=tpl.get("is_epic", False),
            story_text=tpl.get("story_text", ""),
            completion_text=tpl.get("completion_text", ""),
        )
        quest.status = QuestStatus.ACTIVE
        self.active_quests[quest.quest_id] = quest
        epic_tag = "[史诗] " if quest.is_epic else ""
        return f"[任务] {epic_tag}接取: {quest.name} — {quest.description}"

    def on_kill(self, enemy_name: str, character, party=None) -> list:
        """击杀敌人时更新击杀类任务进度"""
        return self._update_quests_by_type(QuestType.KILL, 1, character, party, enemy_name)

    def on_collect(self, item_name: str, character, party=None) -> list:
        """获得物品时更新收集类任务进度"""
        return self._update_quests_by_type(QuestType.COLLECT, 1, character, party, item_name)

    def on_explore(self, region_name: str, character, party=None) -> list:
        """探索新区域时更新探索类任务进度"""
        events = self._update_quests_by_type(QuestType.EXPLORE, 1, character, party, region_name)
        # BOSS 任务也在探索时触发（到达特定区域）
        events += self._update_quests_by_type(QuestType.BOSS, 1, character, party, region_name)
        return events

    def on_delivery(self, character: Character) -> List[str]:
        """递送任务自动完成（挂机递送）"""
        return self._update_quests_by_type(QuestType.DELIVERY, 1, character, "")

    def on_escort(self, character: Character) -> List[str]:
        """护送任务自动完成"""
        return self._update_quests_by_type(QuestType.ESCORT, 1, character, "")

    def _update_quests_by_type(self, quest_type: QuestType, amount: int,
                                character, party=None, context: str = "") -> list:
        """按任务类型更新进度"""
        events = []
        for quest in list(self.active_quests.values()):
            if quest.quest_type != quest_type:
                continue
            if quest.status != QuestStatus.ACTIVE:
                continue

            if quest.update_progress(amount):
                events.append(self._complete_quest(quest, character, party))
        return events

    def _complete_quest(self, quest: Quest, character, party=None) -> str:
        """完成任务，发放奖励（若有队伍则全队分享）"""
        quest.status = QuestStatus.COMPLETED
        del self.active_quests[quest.quest_id]
        self.completed_quests.append(quest.quest_id)

        # 发放奖励：若传入队伍则全队获得，否则仅角色获得
        recipients = party.get_alive() if party else [character]
        for member in recipients:
            member.gold += quest.reward.gold
            member.gain_exp(quest.reward.exp)
            member.quests_completed += 1

        text = quest.completion_text or f"{quest.name} 完成！"
        reward_parts = []
        if quest.reward.exp:
            reward_parts.append(f"+{quest.reward.exp}EXP")
        if quest.reward.gold:
            reward_parts.append(f"+{quest.reward.gold}G")
        reward_str = " · ".join(reward_parts) if reward_parts else ""

        epic_tag = "[史诗] " if quest.is_epic else ""
        if reward_str:
            return f"[任务] {epic_tag}完成: {text} ({reward_str})"
        return f"[任务] {epic_tag}完成: {text}"

    def get_active_quests(self) -> List[Quest]:
        """获取当前进行中的任务列表"""
        return list(self.active_quests.values())

    def to_dict(self) -> dict:
        """序列化任务状态"""
        return {
            "active_quests": {
                qid: {
                    "quest_id": q.quest_id,
                    "name": q.name,
                    "quest_type": q.quest_type.name,
                    "target_count": q.target_count,
                    "current_count": q.current_count,
                    "status": q.status.name,
                }
                for qid, q in self.active_quests.items()
            },
            "completed_quests": self.completed_quests,
        }

    def from_dict(self, data: dict, templates: list):
        """从存档恢复任务状态"""
        self.completed_quests = data.get("completed_quests", [])
        for qid, q_data in data.get("active_quests", {}).items():
            tpl = next((t for t in templates if t.get("quest_id") == qid), None)
            if not tpl:
                continue
            quest = Quest(
                quest_id=qid,
                name=tpl.get("name", "未知"),
                quest_type=QuestType.from_name(q_data.get("quest_type", "KILL")),
                description=tpl.get("description", ""),
                target=tpl.get("target", ""),
                target_count=q_data["target_count"],
                current_count=q_data["current_count"],
                level_req=tpl.get("level_req", 1),
                reward=QuestReward(
                    exp=tpl.get("reward_exp", 0),
                    gold=tpl.get("reward_gold", 0),
                ),
                is_epic=tpl.get("is_epic", False),
            )
            quest.status = QuestStatus[q_data["status"]]
            self.active_quests[qid] = quest
