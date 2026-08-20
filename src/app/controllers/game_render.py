# -*- coding: utf-8 -*-
"""
游戏渲染模块 - Canvas 绘制逻辑

以 Mixin 方式注入 GameController，负责所有视觉渲染。
"""

import tkinter as tk

from src.config.settings import WINDOW_WIDTH, WINDOW_HEIGHT


class GameRenderer:
    """渲染 Mixin — 提供 _redraw / _draw_log_area / _draw_right_panel"""

    def _redraw(self):
        """重绘 UI"""
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 背景
        self.canvas.create_rectangle(0, 0, w, h, fill="#0d1117", outline="")

        if not self.character:
            self.canvas.create_text(w // 2, h // 2, text="加载中...", fill="#c9d1d9")
            return

        FONT_SM = ("Consolas", 9)
        FONT = ("Consolas", 10)
        FONT_TITLE = ("Consolas", 11, "bold")

        # 顶栏 - 角色信息 + 地牢进度
        top_y = 8
        char = self.character
        if self.current_region:
            region_info = f"{self.current_region['name']}[{self.current_region['danger_level']}]"
        else:
            region_info = "???"

        # 地牢名称与房间进度
        dungeon_part = ""
        if self.current_dungeon:
            d = self.current_dungeon
            room_num = (d.current_room_idx + 1) if d.current_room_idx < d.total_rooms else d.total_rooms
            dungeon_part = f" | {d.name} [{room_num}/{d.total_rooms}]"

        title = (
            f"{char.name} | Lv.{char.level} "
            f"HP:{char.hp}/{char.max_hp} "
            f"金币:{char.gold} | {region_info}{dungeon_part}"
        )
        self.canvas.create_rectangle(0, 0, w, 28, fill="#161b22", outline="#21262d")
        self.canvas.create_text(8, top_y + 6, text=title, fill="#c9d1d9", font=FONT_SM, anchor="w")

        # 右侧控制按钮
        btn_x = w - 8
        speed_label = {0: "\u23f8 暂停", 1: "\25b6 1x", 2: "\u23e9 2x"}
        current_speed = speed_label.get(self.speed_mult, f"\25b6 {self.speed_mult}x")
        if self.paused:
            pace_text = "\u23f8 已暂停"
            pace_color = "#e94560"
        else:
            pace_text = current_speed
            pace_color = "#1eff00" if self.speed_mult >= 2 else "#58a6ff"
        self.canvas.create_text(btn_x, top_y + 6, text=pace_text, fill=pace_color, font=FONT_TITLE, anchor="e")

        # 底部控制栏
        ctrl_y = h - 20
        ctrl_texts = ["[空格]暂停", "[1]1x速度", "[2]2x速度", "[S]保存"]
        ctrl_colors = ["#8b949e", "#58a6ff", "#1eff00", "#facc15"]
        ctrl_x = 8
        for text, color in zip(ctrl_texts, ctrl_colors):
            self.canvas.create_text(ctrl_x, ctrl_y, text=text, fill=color, font=("Consolas", 8), anchor="w")
            ctrl_x += 100

        # 主日志区
        self._draw_log_area(w, h, FONT, FONT_SM, FONT_TITLE)

        # 右侧面板
        self._draw_right_panel(w, h, FONT, FONT_SM, FONT_TITLE)

    def _draw_log_area(self, w, h, FONT, FONT_SM, FONT_TITLE):
        """绘制主日志区"""
        log_x, log_y = 4, 36
        log_w = w - 240
        log_h = h - 42

        self.canvas.create_rectangle(log_x, log_y, log_x + log_w, log_y + log_h,
                                       fill="#0d1117", outline="")

        if self.combat_service.in_combat:
            enemy = self.combat_service.current_enemy
            if enemy:
                d_info = ""
                if self.current_dungeon:
                    d = self.current_dungeon
                    d_info = f" [{d.name} {d.cleared_rooms}/{d.total_rooms}]"
                line = f">> 战斗: 对决 {enemy['name']} [HP:{enemy['hp']}/{enemy['max_hp']}]{d_info}"
                self.canvas.create_text(log_x + 8, log_y + 4, text=line,
                                          fill="#e94560", font=FONT_TITLE, anchor="w")
            else:
                self.canvas.create_text(log_x + 8, log_y + 4, text="... 探索中 ...",
                                          fill="#30363d", font=FONT_SM, anchor="w")
        else:
            if self.current_dungeon:
                d = self.current_dungeon
                d_detail = f"... 探索 {d.name} [{d.cleared_rooms}/{d.total_rooms}] ..."
                self.canvas.create_text(log_x + 8, log_y + 4, text=d_detail,
                                          fill="#30363d", font=FONT_SM, anchor="w")
            else:
                self.canvas.create_text(log_x + 8, log_y + 4, text="... 探索中 ...",
                                          fill="#30363d", font=FONT_SM, anchor="w")

        self.canvas.create_line(log_x + 4, log_y + 22, log_x + log_w - 4, log_y + 22,
                                 fill="#21262d")
        log_start_y = log_y + 28

        # 绘制最近30条日志
        visible = self.log_messages[-30:]
        for i, msg in enumerate(reversed(visible)):
            yy = log_start_y + i * 16
            if yy > log_y + log_h - 4:
                break

            # 关键词着色
            color = "#8b949e"
            if "[战利品]" in msg or "[宝箱]" in msg:
                color = "#1eff00"
            elif "[战斗]" in msg:
                color = "#e94560"
            elif "[暴击]" in msg:
                color = "#ff8000"
            elif "[击杀]" in msg:
                color = "#ff4040"
            elif "[升级]" in msg:
                color = "#a335ee"
            elif "[旅行]" in msg:
                color = "#facc15"
            elif "[地牢]" in msg or "[房间]" in msg or "[探索]" in msg:
                color = "#58a6ff"
            elif "[地标]" in msg:
                color = "#e6cc80"
            elif "[历史]" in msg:
                color = "#58a6ff"
            elif "[任务]" in msg or "[队伍]" in msg:
                color = "#facc15"
            elif "[装备]" in msg:
                color = "#1eff00"
            elif "[城堡]" in msg or "[入侵]" in msg or "[奖励]" in msg:
                color = "#ff8000"

            # 裁剪文本避免溢出到右侧面板
            max_chars = (log_w - 20) // 9
            display = msg[:max(max_chars, 20)]
            self.canvas.create_text(log_x + 8, yy, text=display,
                                      fill=color, font=FONT_SM, anchor="w")

    def _draw_right_panel(self, w, h, FONT, FONT_SM, FONT_TITLE):
        """绘制右侧面板：属性 + 技能 + 装备 + 任务 + 地标"""
        c = self.canvas
        char = self.character
        rx = w - 236
        ry = 30
        rw = 232
        rh = h - 34
        panel_bottom = ry + rh

        def _check_space(needed=16):
            nonlocal py
            return py + needed <= panel_bottom - 6

        c.create_rectangle(rx, ry, rx + rw, ry + rh, fill="#161b22", outline="#21262d")
        px = rx + 6
        py = ry + 6

        # -- 队伍 --
        if _check_space(24):
            c.create_text(px, py, text="-- 队伍 --", fill="#58a6ff", font=FONT_TITLE, anchor="w")
            py += 18
            if self.party:
                for member in self.party.members:
                    if not _check_space(14):
                        break
                    is_hero = member == self.party.hero
                    hp_pct = member.hp / max(member.max_hp, 1)
                    hp_color = "#1eff00" if hp_pct > 0.5 else ("#facc15" if hp_pct > 0.2 else "#e94560")
                    star = "\u2605" if is_hero else "  "
                    name_tag = f"{star} {member.char_class.value[0]}\u00b7{member.name}"
                    hp_tag = f"HP:{member.hp}/{member.max_hp} Lv.{member.level}"
                    c.create_text(px, py, text=name_tag[:16], fill="#c9d1d9", font=FONT_SM, anchor="w")
                    c.create_text(rx + rw - 10, py, text=hp_tag,
                                  fill=hp_color, font=("Consolas", 8), anchor="e")
                    py += 14
            py += 4

        # -- 药水 --
        active_potions = self.potion_service.get_active_list()
        if active_potions and _check_space(24):
            c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
            py += 6
            c.create_text(px, py, text="-- 药水 --", fill="#e6cc80", font=FONT_TITLE, anchor="w")
            py += 18
            for potion in active_potions[:3]:
                if not _check_space(14):
                    break
                time_left = f"{int(potion.remaining_time)}s"
                c.create_text(px, py, text=f" {potion.name}", fill="#1eff00", font=FONT_SM, anchor="w")
                c.create_text(rx + rw - 10, py, text=time_left,
                              fill="#8b949e", font=("Consolas", 8), anchor="e")
                py += 14
            py += 2

        # -- 属性 --
        if not _check_space(18):
            return
        c.create_text(px, py, text="-- 属性 --", fill="#e6cc80", font=FONT_TITLE, anchor="w")
        py += 18
        s = char.stats
        for label, val in [("力量", s.strength), ("敏捷", s.dexterity),
                           ("体质", s.constitution), ("智力", s.intelligence),
                           ("感知", s.wisdom), ("魅力", s.charisma)]:
            if not _check_space():
                return
            c.create_text(px, py, text=f" {label}:{val:>3d}", fill="#8b949e", font=FONT_SM, anchor="w")
            py += 16

        # -- 统计 --
        if not _check_space(24):
            return
        py += 2
        c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
        py += 6
        c.create_text(px, py, text="-- 统计 --", fill="#e6cc80", font=FONT_TITLE, anchor="w")
        py += 18
        for label, val in [("击杀", char.kills), ("死亡", char.deaths),
                           ("金币", f"{char.gold}G"), ("任务", char.quests_completed)]:
            if not _check_space():
                return
            c.create_text(px, py, text=f" {label}: {val}", fill="#8b949e", font=FONT_SM, anchor="w")
            py += 16

        # -- 技能 --
        if not _check_space(24):
            return
        py += 2
        c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
        py += 6
        c.create_text(px, py, text=f"-- 技能 ({char.char_class.value[0]}) --",
                      fill="#e6cc80", font=FONT_TITLE, anchor="w")
        py += 18
        if char.skills:
            for skill in char.skills:
                if not _check_space(14):
                    return
                cd_text = "\u5c31\u7eea" if skill.is_ready() else f"CD:{skill.current_cooldown:.0f}s"
                c.create_text(px, py, text=f" {skill.name}", fill="#58a6ff", font=FONT_SM, anchor="w")
                c.create_text(rx + rw - 12, py, text=cd_text, fill="#8b949e",
                              font=("Consolas", 8), anchor="e")
                py += 14
        else:
            if not _check_space(14):
                return
            c.create_text(px, py, text=" \u65e0\u6280\u80fd", fill="#484f58", font=FONT_SM, anchor="w")
            py += 14

        # -- 装备 --
        if not _check_space(24):
            return
        py += 2
        c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
        py += 6
        c.create_text(px, py, text="-- 装备 --", fill="#e6cc80", font=FONT_TITLE, anchor="w")
        py += 18
        slot_names = {"WEAPON": "\u6b66\u5668", "HEAD": "\u5934\u90e8", "CHEST": "\u80f8\u7532", "HANDS": "\u624b\u90e8", "LEGS": "\u817f\u90e8", "FEET": "\u811a\u90e8",
                      "NECKLACE": "\u9879\u94fe", "RING1": "\u6212\u6307", "RING2": "\u6212\u6307"}
        equipped_any = False
        for slot_key, slot_label in slot_names.items():
            if not _check_space(14):
                return
            item = char.equipment.get(slot_key)
            if item and hasattr(item, "get_display_name"):
                name = item.get_display_name()[:18]
                c.create_text(px, py, text=f" {slot_label}: {name}", fill="#1eff00", font=FONT_SM, anchor="w")
                equipped_any = True
            else:
                c.create_text(px, py, text=f" {slot_label}: ---", fill="#484f58", font=FONT_SM, anchor="w")
            py += 14
        if not equipped_any:
            py -= len(slot_names) * 14
            c.create_text(px, py, text=" \u5c1a\u672a\u88c5\u5907", fill="#484f58", font=FONT_SM, anchor="w")
        py += 4

        # -- 神器 --
        artifacts = self.artifact_service.get_owned_list()
        if artifacts and _check_space(24):
            c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
            py += 6
            c.create_text(px, py, text="-- \u795e\u5668 --", fill="#ff8000", font=FONT_TITLE, anchor="w")
            py += 18
            for art in artifacts[:5]:
                if not _check_space(14):
                    break
                c.create_text(px, py, text=f" {art.name}",
                              fill="#ff8000", font=FONT_SM, anchor="w")
                py += 13
            py += 2

        # -- 任务 --
        if not _check_space(24):
            return
        c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
        py += 6
        c.create_text(px, py, text="-- \u4efb\u52a1 --", fill="#e6cc80", font=FONT_TITLE, anchor="w")
        py += 18
        active = self.quest_service.get_active_quests()
        if active:
            for quest in active[:4]:
                if not _check_space(25):
                    return
                pct = int(quest.progress_pct() * 100)
                bar = "|" * (pct // 10) + "." * (10 - pct // 10)
                c.create_text(px, py, text=f" {quest.name[:16]}", fill="#facc15", font=FONT_SM, anchor="w")
                py += 13
                c.create_text(px + 4, py, text=f"  [{bar}] {pct}%", fill="#8b949e",
                              font=("Consolas", 8), anchor="w")
                py += 12
        else:
            if not _check_space(14):
                return
            c.create_text(px, py, text=" \u6682\u65e0\u4efb\u52a1", fill="#484f58", font=FONT_SM, anchor="w")
            py += 14

        # -- 地标 --
        if not _check_space(24):
            return
        py += 2
        c.create_line(px, py, rx + rw - 6, py, fill="#21262d")
        py += 6
        c.create_text(px, py, text="-- \u5730\u6807 --", fill="#e6cc80", font=FONT_TITLE, anchor="w")
        py += 18
        discovered = [lm for lm in self.world_service.get_landmarks() if lm["discovered"]]
        if discovered:
            for lm in discovered[:3]:
                if not _check_space(14):
                    return
                c.create_text(px, py, text=f" {lm['name'][:20]}",
                              fill="#facc15", font=FONT_SM, anchor="w")
                py += 14
        else:
            if not _check_space(14):
                return
            c.create_text(px, py, text=" \u6682\u65e0\u53d1\u73b0", fill="#484f58", font=FONT_SM, anchor="w")
