# -*- coding: utf-8 -*-
"""
游戏 I/O 模块 - 存档 / 读档 / 暂停 / 速度控制

以 Mixin 方式注入 GameController。
"""

import json
import os
import sys

from src.app.models.character import Character, Party


class GameIOMixin:
    """I/O Mixin — 提供 save_game / _load_game / _toggle_pause / _set_speed"""

    def _toggle_pause(self):
        """切换暂停/继续"""
        self.paused = not self.paused
        status = "\u5df2\u6682\u505c" if self.paused else "\u7ee7\u7eed"
        self._add_log(f"[\u7cfb\u7edf] {status}")

    def _set_speed(self, mult: int):
        """设置游戏速度"""
        self.paused = False
        self.speed_mult = mult
        self._add_log(f"[\u7cfb\u7edf] \u901f\u5ea6\u8bbe\u7f6e\u4e3a {mult}x")

    def save_game(self):
        """保存游戏"""
        if not self.character:
            return
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                save_dir = os.path.join(base_dir, "data")
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                save_dir = os.path.join(base_dir, "..", "data")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "save.json")

            # 保存队伍
            party_data = []
            for m in self.party.members:
                party_data.append(m.to_dict())

            data = {
                "character": self.character.to_dict(),
                "party": party_data,
                "game_time": self.game_time,
                "world_seed": self.world_seed,
                "quest_service": self.quest_service.to_dict(),
                "potion_service": self.potion_service.to_dict(),
                "castle_service": self.castle_service.to_dict(),
                "achievement_service": self.achievement_service.to_dict(),
                "artifact_service": self.artifact_service.to_dict(),
                # 地牢进度
                "current_region_id": self.current_region["region_id"] if self.current_region else None,
                "current_dungeon_idx": self.current_dungeon_idx,
            }
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._add_log("[\u7cfb\u7edf] \u6e38\u620f\u5df2\u4fdd\u5b58")
            self.audio.sfx_ui_save()
        except Exception as e:
            self._add_log(f"[\u7cfb\u7edf] \u4fdd\u5b58\u5931\u8d25: {e}")

    def _load_game(self):
        """读取存档"""
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                save_path = os.path.join(base_dir, "data", "save.json")
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                save_path = os.path.join(base_dir, "..", "data", "save.json")
            with open(save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.character = Character.from_dict(data.get("character", {}))
            self.game_time = data.get("game_time", 0)
            self.world_seed = data.get("world_seed", 0)

            # 恢复队伍
            self.party = Party(self.character)
            party_data = data.get("party", [])
            # 跳过 hero（index 0）
            for i, member_data in enumerate(party_data):
                if i == 0:
                    continue
                companion = Character.from_dict(member_data)
                self.party.add_member(companion)

            # 恢复世界
            self.world_service = WorldService(seed=self.world_seed)
            self.world = self.world_service
            self.world_history_lines = self.world_service.history_events

            # 初始化地牢服务
            self.dungeon_service = DungeonService(self.data_service, self.world_service)
            self.potion_service = PotionService(self.data_service)
            self.castle_service = CastleService(self.dungeon_service)
            self.achievement_service = AchievementService(self.data_service)
            self.artifact_service = ArtifactService(self.data_service)

            # 恢复区域与地牢
            regions = self.world_service.get_all_regions()
            saved_region_id = data.get("current_region_id")
            if regions:
                if saved_region_id:
                    region = self.world_service.get_region_by_id(saved_region_id)
                    self.current_region = region if region else regions[0]
                else:
                    self.current_region = regions[0]
                # 生成当前区域地牢
                self.dungeon_service.generate_dungeons_for_region(self.current_region)
                d_idx = data.get("current_dungeon_idx", 0)
                self.current_dungeon_idx = d_idx
                self.current_dungeon = self.dungeon_service.get_current_dungeon(
                    self.current_region["region_id"], d_idx
                )

            # 恢复任务状态
            if "quest_service" in data:
                self.quest_service.from_dict(data["quest_service"], self.data_service.get_quest_templates())
            if "potion_service" in data:
                self.potion_service.from_dict(data["potion_service"])
            if "castle_service" in data:
                self.castle_service.from_dict(data["castle_service"])
            if "achievement_service" in data:
                self.achievement_service.from_dict(data["achievement_service"])
            if "artifact_service" in data:
                self.artifact_service.from_dict(data["artifact_service"])
            self._add_log("[\u7cfb\u7edf] \u5b58\u6863\u5df2\u8bfb\u53d6")
            return True
        except FileNotFoundError:
            return False
        except Exception as _e:
            import sys
            print(f"[IO] 读档异常：{_e}", file=sys.stderr)
            return False
