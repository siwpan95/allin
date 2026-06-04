# -*- coding: utf-8 -*-
"""
游戏初始化 Mixin — 角色创建 / 世界生成 / 队友招募

以 Mixin 方式注入 GameController，负责：角色创建界面、游戏初始化、队友生成。
"""

import random
import tkinter as tk

from src.app.models.character import Character, Race, CharClass, Party, CharacterStats
from src.app.services.world_service import WorldService
from src.app.services.dungeon_service import DungeonService
from src.app.services.potion_service import PotionService
from src.app.services.castle_service import CastleService
from src.app.services.achievement_service import AchievementService
from src.app.services.artifact_service import ArtifactService
from src.app.services.audio_service import AudioService


class GameInitMixin:
    """初始化 Mixin — 角色创建、世界生成、队友招募"""

    # ── 角色创建 ──────────────────────────────────────────

    def _show_character_creation(self):
        """角色创建界面"""
        win = tk.Toplevel(self.root)
        win.title("创建角色")
        win.geometry("400x420")
        win.configure(bg="#161b22")
        win.transient(self.root)
        win.grab_set()
        win.focus_set()

        result = [None, None, ""]

        frame = tk.Frame(win, bg="#161b22")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        tk.Label(frame, text="创建你的冒险者", font=("Consolas", 14, "bold"),
                 fg="#c9d1d9", bg="#161b22").pack(pady=(0, 10))

        # 名字输入
        tk.Label(frame, text="名字:", fg="#8b949e", bg="#161b22",
                 anchor="w").pack(fill=tk.X)
        name_entry = tk.Entry(frame, bg="#0d1117", fg="#c9d1d9",
                              insertbackground="#c9d1d9", relief=tk.FLAT)
        name_entry.pack(fill=tk.X, pady=(0, 10))
        name_entry.insert(0, "冒险者")

        # 种族选择
        tk.Label(frame, text="种族:", fg="#8b949e", bg="#161b22",
                 anchor="w").pack(fill=tk.X)
        race_var = tk.StringVar(value=list(Race)[0].value[0])
        race_frame = tk.Frame(frame, bg="#161b22")
        race_frame.pack(fill=tk.X, pady=(0, 10))
        for r in Race:
            rb = tk.Radiobutton(race_frame, text=r.value[0], variable=race_var,
                                value=r.value[0], fg="#c9d1d9", bg="#161b22",
                                selectcolor="#21262d", activebackground="#161b22",
                                activeforeground="#c9d1d9")
            rb.pack(side=tk.LEFT, padx=4)

        # 职业选择
        tk.Label(frame, text="职业:", fg="#8b949e", bg="#161b22",
                 anchor="w").pack(fill=tk.X)
        class_var = tk.StringVar(value=list(CharClass)[0].value[0])
        class_frame = tk.Frame(frame, bg="#161b22")
        class_frame.pack(fill=tk.X, pady=(0, 10))
        for c in CharClass:
            rb = tk.Radiobutton(class_frame, text=c.value[0], variable=class_var,
                                value=c.value[0], fg="#c9d1d9", bg="#161b22",
                                selectcolor="#21262d", activebackground="#161b22",
                                activeforeground="#c9d1d9")
            rb.pack(side=tk.LEFT, padx=4)

        # 属性预览
        preview_label = tk.Label(frame, text="", fg="#58a6ff", bg="#161b22",
                                  justify=tk.LEFT, anchor="nw")
        preview_label.pack(fill=tk.BOTH, expand=True)

        def _find_race(name):
            return next(r for r in Race if r.value[0] == name)

        def _find_class(name):
            return next(c for c in CharClass if c.value[0] == name)

        def update_preview():
            try:
                race_obj = _find_race(race_var.get())
                cls_obj = _find_class(class_var.get())
                name = name_entry.get().strip() or "冒险者"
                stats = CharacterStats.generate_for_class_race(cls_obj, race_obj)
                preview_label.config(text=(
                    f"预览: {name} ({race_obj.value[0]} {cls_obj.value[0]})\n\n"
                    f"  力量: {stats.strength}  敏捷: {stats.dexterity}\n"
                    f"  体质: {stats.constitution}  智力: {stats.intelligence}\n"
                    f"  感知: {stats.wisdom}  魅力: {stats.charisma}\n\n"
                    f"  HP: {Character.calc_max_hp(stats.constitution)}\n"
                    f"  基础攻击力: {cls_obj.base_attack}"
                ))
            except Exception:
                pass

        def on_confirm():
            try:
                race_obj = _find_race(race_var.get())
                cls_obj = _find_class(class_var.get())
                name = name_entry.get().strip() or "冒险者"
                result[0] = race_obj
                result[1] = cls_obj
                result[2] = name
                win.destroy()
            except StopIteration:
                return

        def random_create():
            race_obj = random.choice(list(Race))
            cls_obj = random.choice(list(CharClass))
            race_var.set(race_obj.value[0])
            class_var.set(cls_obj.value[0])
            update_preview()

        # 绑定事件
        name_entry.bind("<KeyRelease>", lambda e: update_preview())
        race_var.trace_add("write", lambda *a: update_preview())
        class_var.trace_add("write", lambda *a: update_preview())

        # 按钮
        btn_frame = tk.Frame(frame, bg="#161b22")
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="随机", command=random_create,
                  bg="#21262d", fg="#c9d1d9", relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="确定", command=on_confirm,
                  bg="#238636", fg="white", relief=tk.FLAT).pack(side=tk.RIGHT, padx=2)

        update_preview()
        win.wait_window()
        return tuple(result)

    # ── 游戏初始化 ────────────────────────────────────────

    def _init_game(self):
        """初始化游戏：读档或新建世界"""
        # 尝试读取存档
        if not self._load_game():
            # 自动创建角色
            races = list(Race)
            classes = list(CharClass)
            race = random.choice(races)
            char_class = random.choice(classes)
            name = random.choice([
                "艾德里安", "赛巴斯蒂安", "奥利维亚", "亚瑟兰",
                "卡斯帕", "克劳斯", "赛林特", "凯尔斯",
            ])

            # 生成世界和角色
            world_seed = random.randint(1, 999999)
            self.world_seed = world_seed
            hero = Character.create(
                name=name, race=race, char_class=char_class, seed=world_seed,
            )
            self.character = hero
            self.party = Party(hero)

            # 自动招募队友（2-3人）
            self._auto_recruit_companions()

            # 生成新世界
            self.world_service = WorldService(seed=world_seed)
            self.world = self.world_service
            self.world_history_lines = self.world_service.history_events

            # 初始化地牢服务
            self.dungeon_service = DungeonService(self.data_service, self.world_service)
            self.potion_service = PotionService(self.data_service)

        # 始终初始化这些服务（存档也需要的运行时服务）
        self.castle_service = CastleService(self.dungeon_service)
        self.achievement_service = AchievementService(self.data_service)
        self.artifact_service = ArtifactService(self.data_service)

        # 音频服务
        self.audio = AudioService()

        # 设置初始区域并生成地牢
        regions = self.world_service.get_all_regions()
        if regions:
            self.current_region = regions[0]
            self.dungeon_service.generate_dungeons_for_region(self.current_region)
            self.current_dungeon = self.dungeon_service.get_current_dungeon(
                self.current_region["region_id"], 0
            )
            self.current_dungeon_idx = 0
            self._add_log(f"[旅行] 出生点: {self.current_region['name']}")
            if self.current_dungeon:
                self._add_log(
                    f"[地牢] 进入: {self.current_dungeon.name} "
                    f"[{self.current_dungeon.total_rooms}间房]"
                )

        self._add_log("[系统] 冒险开始！")
        self._add_log(self.world_service.describe_history())
        # 显示队伍信息
        names = self.party.get_member_names()
        self._add_log(f"[队伍] {', '.join(names)} 集结完毕！")

    # ── 队友招募 ──────────────────────────────────────────

    def _auto_recruit_companions(self):
        """自动招募队友（2-3人，随机种族职业）"""
        races = list(Race)
        classes = list(CharClass)

        count = random.randint(2, 3)
        names_pool = [
            "艾琳", "卡尔", "雷恩", "索菲", "达芙", "艾莎", "柯林", "蒂娜",
            "哈罗德", "莱娅", "贝恩", "娜塔", "泽诺", "米拉", "卡特", "安雅",
            "莉娜", "亚瑟", "梅林", "摩根", "伊莉丝", "罗兰", "赛拉", "凯恩",
        ]
        existing_names = {self.party.hero.name}
        for _ in range(count):
            available = [n for n in names_pool if n not in existing_names]
            name = random.choice(available) if available else f"佣兵{random.randint(100, 999)}"
            existing_names.add(name)
            race = random.choice(races)
            cls = random.choice(classes)
            companion = Character.create(
                name=name, race=race, char_class=cls,
                seed=self.world_seed + len(self.party.members),
            )
            self.party.add_member(companion)
