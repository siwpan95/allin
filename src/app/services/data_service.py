# -*- coding: utf-8 -*-
"""数据服务 - 优先从 Excel 加载游戏数据，Excel 不存在则回退到 JSON"""
import json
import os
import sys
from typing import Dict, List, Optional


class DataService:
    """统一的数据服务，Excel 优先 → JSON 回退"""

    def __init__(self, data_dir: str = None, use_excel: bool = True):
        if data_dir is None:
            if getattr(sys, 'frozen', False):
                # 打包后：优先用 exe 旁边的外部 data 目录，其次用包内数据
                base_dir = os.path.dirname(sys.executable)
                external_data = os.path.join(base_dir, "resources", "data")
                if os.path.isdir(external_data):
                    data_dir = external_data
                else:
                    # 回退到包内数据（PyInstaller  bundled）
                    data_dir = os.path.join(sys._MEIPASS, "resources", "data")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                src_dir = os.path.dirname(os.path.dirname(current_dir))
                data_dir = os.path.join(src_dir, "resources", "data")
        self.data_dir = data_dir
        self._cache = {}
        self._excel_service = None
        self._use_excel = use_excel

    def _get_excel_service(self):
        """延迟加载 Excel 服务"""
        if self._excel_service is None and self._use_excel:
            try:
                from .excel_service import ExcelService
                if getattr(sys, 'frozen', False):
                    # 打包为 exe 后，Excel 在 exe 同目录外部
                    base_dir = os.path.dirname(sys.executable)
                    excel_path = os.path.join(base_dir, "resources", "config", "game_config.xlsx")
                else:
                    config_dir = os.path.join(
                        os.path.dirname(self.data_dir), "config"
                    )
                    excel_path = os.path.join(config_dir, "game_config.xlsx")
                self._excel_service = ExcelService(excel_path)
            except ImportError:
                print("[DataService] openpyxl 未安装，使用 JSON 模式")
                self._use_excel = False
        return self._excel_service

    def reload_from_excel(self):
        """强制从 Excel 重新加载（清除所有缓存）"""
        self._cache.clear()
        if self._excel_service:
            self._excel_service.clear_cache()
        self._use_excel = True

    def _load_json(self, filename: str) -> dict:
        """加载 JSON 文件（带缓存）"""
        if filename in self._cache:
            return self._cache[filename]

        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache[filename] = data
                return data
        except FileNotFoundError:
            print(f"警告: 数据文件不存在 {filepath}")
            return {}
        except json.JSONDecodeError as e:
            print(f"错误: JSON 解析失败 {filepath}: {e}")
            return {}

    def get_item_templates(self) -> dict:
        """获取物品模板数据（Excel 优先）"""
        es = self._get_excel_service()
        if es and es.file_exists():
            return es.get_item_templates()
        return self._load_json("item_templates.json")

    def get_enemy_templates(self) -> List[dict]:
        """获取敌人模板数据（Excel 优先）"""
        es = self._get_excel_service()
        if es and es.file_exists():
            return es.get_enemy_templates()
        data = self._load_json("enemy_templates.json")
        return data.get("enemy_templates", [])

    def get_quest_templates(self) -> List[dict]:
        """获取任务模板数据（Excel 优先）"""
        es = self._get_excel_service()
        if es and es.file_exists():
            return es.get_quest_templates()
        data = self._load_json("quest_templates.json")
        return data.get("quest_templates", [])

    def get_potion_config(self) -> List[dict]:
        """获取药水配置（Excel 优先 → 返回空则调用方使用硬编码默认）"""
        es = self._get_excel_service()
        if es and es.file_exists():
            result = es.get_potion_config()
            if result:
                return result
        return []

    def get_artifact_config(self) -> List[dict]:
        """获取神器配置（Excel 优先 → 返回空则使用硬编码默认）"""
        es = self._get_excel_service()
        if es and es.file_exists():
            result = es.get_artifact_config()
            if result:
                return result
        return []

    def get_achievement_config(self) -> List[dict]:
        """获取成就配置（Excel 优先 → 返回空则使用硬编码默认）"""
        es = self._get_excel_service()
        if es and es.file_exists():
            result = es.get_achievement_config()
            if result:
                return result
        return []

    def get_enemy_by_name(self, name: str) -> Optional[dict]:
        """根据名称获取敌人模板"""
        enemies = self.get_enemy_templates()
        for enemy in enemies:
            if enemy["name"] == name:
                return enemy
        return None
    
    def get_enemies_by_level(self, level: int, level_range: int = 3) -> List[dict]:
        """根据等级获取合适的敌人模板"""
        enemies = self.get_enemy_templates()
        suitable = []
        for enemy in enemies:
            if abs(enemy["level"] - level) <= level_range:
                suitable.append(enemy)
        return suitable if suitable else enemies
