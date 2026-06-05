# -*- coding: utf-8 -*-
"""
日志 & 成就系统 Mixin

以 Mixin 方式注入 GameController，负责：日志写入/截断、成就进度检查、奖励发放。

变更说明：
  - 城堡成就统计使用 get_secured_count()，该接口现返回已维护城堡数（由 CastleService 兼容）。
"""


class GameAchievementMixin:
    """日志 & 成就 Mixin — _add_log / _check_achievements / _apply_achievement_reward"""

    # ── 日志 ──────────────────────────────────────────────

    def _add_log(self, msg: str):
        """添加带时间戳的日志条目，自动截断超过上限的旧条目"""
        t = int(self.game_time)
        hh, mm, ss = t // 3600, (t % 3600) // 60, t % 60
        ts = f"{hh:02d}:{mm:02d}:{ss:02d}"
        self.log_messages.append(f"[{ts}] {msg}")
        if len(self.log_messages) > self.max_logs:
            self.log_messages = self.log_messages[-self.max_logs:]

    # ── 成就检查 ──────────────────────────────────────────

    def _check_achievements(self):
        """检查并触发成就，发放奖励（数据以全队汇总为准）"""
        char = self.character
        # 汇总全队数据
        total_kills = sum(m.kills for m in self.party.members) if self.party else char.kills
        max_level = max((m.level for m in self.party.members), default=char.level) if self.party else char.level
        total_deaths = sum(m.deaths for m in self.party.members) if self.party else char.deaths
        total_quests = sum(m.quests_completed for m in self.party.members) if self.party else char.quests_completed
        checks = [
            ("ACH_KILL_10",    total_kills, None),
            ("ACH_KILL_100",   total_kills, None),
            ("ACH_KILL_1000",  total_kills, None),
            ("ACH_KILL_10000", total_kills, None),
            ("ACH_LV10",       max_level, None),
            ("ACH_LV25",       max_level, None),
            ("ACH_DEATH_5",    total_deaths, None),
            ("ACH_QUEST_10",   total_quests, None),
            ("ACH_CASTLE_5",
             self.castle_service.get_secured_count(), None),  # 现统计已维护城堡数
            ("ACH_CASTLE_10",
             self.castle_service.get_secured_count(), None),  # 现统计已维护城堡数
            ("ACH_ARTIFACT_5",
             len(self.artifact_service.get_owned_list()), None),
        ]

        for ach_id, progress, _ in checks:
            ach = self.achievement_service.achievements.get(ach_id)
            if not ach or ach.completed:
                continue
            old_progress = ach.progress
            ach.progress = min(progress, ach.target)
            if ach.progress >= ach.target and old_progress < ach.target:
                ach.completed = True
                self.achievement_service._pending_rewards.append({
                    "name": ach.name,
                    "reward_type": ach.reward_type,
                    "reward_value": ach.reward_value,
                })

        # 发放奖励
        rewards = self.achievement_service.get_pending_rewards()
        for reward in rewards:
            self._add_log(f"🏆 成就解锁：{reward['name']}!")
            self.audio.sfx_system_achievement()
            self._apply_achievement_reward(reward)

    # ── 奖励发放 ──────────────────────────────────────────

    def _apply_achievement_reward(self, reward: dict):
        """根据奖励类型应用成就奖励（分发给全队）"""
        rtype = reward["reward_type"]
        rval = reward["reward_value"]

        if rtype == "gold":
            for member in self.party.members:
                member.gold += int(rval)
        elif rtype == "xp":
            for member in self.party.get_alive():
                member.gain_exp(int(rval))
        elif rtype == "hp_bonus":
            for member in self.party.members:
                member.max_hp = int(member.max_hp * (1 + rval))
                member.hp = min(member.hp, member.max_hp)
        elif rtype == "xp_bonus":
            pass  # 经验加成在计算时生效，此处无需额外处理
        elif rtype == "drug_capacity":
            cls = type(self)
            current_max = getattr(cls, 'MAX_ACTIVE', 3)
            cls.MAX_ACTIVE = current_max + 1
