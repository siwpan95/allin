# -*- coding: utf-8 -*-
"""
游戏控制器 - 核心协调层（精简版）

原来的 825 行巨型控制器已拆分为专用 Mixin：
  GameInitMixin         → game_init.py         初始化 / 角色创建 / 队友招募
  GameCombatMixin       → game_combat.py        战斗循环 / 击杀处理
  GameExplorationMixin  → game_exploration.py   地牢推进 / 探索 / 区域移动
  GameAchievementMixin  → game_achievements.py  日志 / 成就 / 奖励

  GameRenderer          → game_render.py        Canvas 绘制（已有）
  SystemTrayMixin       → game_tray.py          系统托盘（已有）
  GameIOMixin           → game_io.py            存档/读档/暂停/速度（已有）

本文件仅保留：__init__、UI 构建、主循环调度、窗口事件。
"""

import random
import time
import tkinter as tk
from tkinter import messagebox

from src.app.models.character import Character, Race, CharClass, Party
from src.app.models.dungeon import Dungeon, RoomContent
from src.app.services.data_service import DataService
from src.app.services.item_service import ItemService
from src.app.services.combat_service import CombatService
from src.app.services.quest_service import QuestService
from src.app.services.world_service import WorldService
from src.config.settings import (
    GAME_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    LOOT_INTERVAL, REGION_CHANGE_INTERVAL, ENEMY_RESPAWN_DELAY,
    MAX_LOG_ENTRIES,
)

# ── 渲染 / 托盘 / I/O Mixin（已有） ────────────────────────
from src.app.controllers.game_render import GameRenderer
from src.app.controllers.game_tray import SystemTrayMixin
from src.app.controllers.game_io import GameIOMixin

# ── 新拆分的模块化 Mixin ──────────────────────────────────
from src.app.controllers.game_init import GameInitMixin
from src.app.controllers.game_combat import GameCombatMixin
from src.app.controllers.game_exploration import GameExplorationMixin
from src.app.controllers.game_achievements import GameAchievementMixin


class GameController(
    GameInitMixin,
    GameCombatMixin,
    GameExplorationMixin,
    GameAchievementMixin,
    GameRenderer,
    SystemTrayMixin,
    GameIOMixin,
):
    """游戏主控制器 — 核心调度层

    所有具体逻辑已下沉到对应的 Mixin 类中。
    本类只负责：状态初始化、UI 搭建、主循环调度、窗口生命周期。
    """

    def __init__(self, root):
        self.root = root
        self.root.title(GAME_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg="#0d1117")

        # ── 服务层初始化 ──────────────────────────────────
        self.data_service = DataService()
        self.item_service = ItemService(data_service=self.data_service)
        self.combat_service = CombatService(self.data_service)
        self.quest_service = QuestService(self.data_service)

        # ── 游戏运行时状态 ────────────────────────────────
        self.character = None          # 兼容旧代码，指向 party.hero
        self.party = None              # Party 实例
        self.world = None
        self.current_region = None
        self.current_dungeon = None    # 当前所在地牢
        self.current_dungeon_idx = 0   # 当前区域的地牢序号
        self.game_time = 0.0
        self.world_seed = 0
        self.running = True
        self.paused = False
        self.speed_mult = 1.0
        self.log_messages = []
        self.max_logs = MAX_LOG_ENTRIES

        # ── 计时器状态 ────────────────────────────────────
        self._loot_timer = 0.0
        self._enemy_respawn_timer = 0.0
        self._region_change_timer = 0.0
        self._landmark_discover_timer = 0.0
        self._history_display_timer = 0.0
        self._combat_time = 0.0
        self._resurrect_timer = 0.0    # 队友复活计时器
        self._farm_report_timer = 0.0  # 农场收益报告计时器

        # ── 系统托盘 ──────────────────────────────────────
        self.tray_icon = None
        self._tray_running = False
        self._tray_minimizing = False

        # ── 世界信息 ──────────────────────────────────────
        self.world_history_lines = []
        self.show_world_panel = False
        self._discovered_landmarks = []

        # ── 启动流程 ──────────────────────────────────────
        self._build_ui()
        self._init_game()                          # → GameInitMixin
        self._last_frame = time.time()
        self._game_loop()

    # ======================== UI 构建 ========================

    def _build_ui(self):
        """构建 UI 骨架（Canvas + 快捷键绑定）"""
        self.canvas = tk.Canvas(self.root, bg="#0d1117", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_minimize)

        # 快捷键
        self.root.bind("<space>", lambda e: self._toggle_pause())
        self.root.bind("<Key-1>", lambda e: self._set_speed(1))
        self.root.bind("<Key-2>", lambda e: self._set_speed(2))
        self.root.bind("<Key-s>", lambda e: self.save_game())
        self.canvas.focus_set()

    # ==================== 窗口事件 ====================

    def _on_resize(self, event):
        self._redraw()  # → GameRenderer

    def _on_close(self):
        """关闭确认 → 自动保存 → 退出"""
        if messagebox.askyesno("退出确认", "确定退出游戏?\n退出前自动保存。"):
            self.running = False
            self.audio.stop_all()
            self.save_game()           # → GameIOMixin
            self._tray_minimizing = True
            self.root.destroy()

    def _on_minimize(self, event=None):
        """窗口最小化 → 缩入系统托盘"""
        if self._tray_minimizing:
            return
        if event and event.widget == self.root and self.root.state() == "iconic":
            if self.tray_available:
                self._tray_minimizing = True
                self._minimize_to_tray()  # → SystemTrayMixin
                self._tray_minimizing = False

    # ==================== 主循环调度 ====================

    def _game_loop(self):
        """游戏主循环：每 50ms 一帧"""
        if not self.running:
            return

        now = time.time()
        dt = min(0.1, now - self._last_frame)
        self._last_frame = now

        self._update_game(dt)
        self._redraw()  # → GameRenderer

        self.root.after(50, self._game_loop)

    def _update_game(self, dt):
        """每帧更新：调度各子系统（纯编排逻辑）"""
        if not self.party or not self.current_region:
            return
        if self.paused:
            return

        dt = dt * self.speed_mult
        char = self.character
        self.game_time += dt

        # ── 队友复活 ──────────────────────────────────────
        self._resurrect_timer += dt
        if self._resurrect_timer >= 3.0:
            self._resurrect_timer = 0.0
        msgs = self.combat_service.resurrect_fallen(self.party)
        for msg in msgs:
            self._add_log(msg)                     # → GameAchievementMixin
            self.audio.sfx_system_resurrect()

        # ── 药水时效 ──────────────────────────────────────
        potion_expired = self.potion_service.tick(dt)
        for msg in potion_expired:
            self._add_log(msg)

        # ── 农场产出 ──────────────────────────────────────
        farm_coins = self.castle_service.tick_farm(dt)
        if farm_coins > 0:
            for member in self.party.members:
                member.gold += farm_coins
        self._farm_report_timer += dt
        if self._farm_report_timer >= 60.0:
            self._farm_report_timer = 0.0
            if self.castle_service.get_farm_count() > 0:
                self._add_log(
                    f"🏰 农场产出中...({self.castle_service.get_farm_count()}个农场)"
                )

        # ── 任务系统 ──────────────────────────────────────
        quest_events = self.quest_service.tick(dt, char)
        for event in quest_events:
            self._add_log(event)
            if "完成" in event:
                self.audio.sfx_system_quest()

        # ── 自然回血（所有队员，非战斗时） ────────────────
        if not self.combat_service.in_combat:
            for member in self.party.members:
                regen = max(1, int(member.max_hp * 0.02))
                if int(self.game_time) != int(self.game_time - dt):
                    member.heal(regen)

        # ── 战斗 vs 探索 ──────────────────────────────────
        if self.combat_service.in_combat:
            self._update_combat(dt)                # → GameCombatMixin
        else:
            self._handle_exploration(dt)           # → GameExplorationMixin

        # ── 地牢房间推进 ──────────────────────────────────
        self._region_change_timer += dt
        if self._region_change_timer >= REGION_CHANGE_INTERVAL:
            self._region_change_timer = 0.0
            if not self.combat_service.in_combat:
                self._advance_dungeon_room()       # → GameExplorationMixin

        # ── 地标发现 ──────────────────────────────────────
        self._landmark_discover_timer += dt
        if self._landmark_discover_timer >= 30.0:
            self._landmark_discover_timer = 0.0
            self._try_discover_landmark()          # → GameExplorationMixin

        # ── 世界历史展示 ─────────────────────────────────
        self._history_display_timer += dt
        if self._history_display_timer >= 60.0:
            self._history_display_timer = 0.0
            if self.world_history_lines:
                event = random.choice(self.world_history_lines)
                self._add_log(f"[历史] {event}")
