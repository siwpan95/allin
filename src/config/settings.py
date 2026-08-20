# -*- coding: utf-8 -*-
"""游戏配置"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录
DATA_DIR = os.path.join(BASE_DIR, "resources", "data")
SAVE_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

# 游戏设置
GAME_TITLE = "蜂蜜挂机 RPG"
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 700
FPS = 20

# 游戏平衡性配置
HP_REGEN_RATE = 0.02          # 每秒回血比例
MP_REGEN_RATE = 0.03          # 每秒回蓝比例
LOOT_INTERVAL = 8.0           # 战利品掉落间隔（秒）
REGION_CHANGE_INTERVAL = 30.0 # 区域切换间隔（秒）
ENEMY_RESPAWN_DELAY = 2.0     # 敌人重生延迟（秒）
MAX_LOG_ENTRIES = 500         # 最大日志条数

# 经验公式
def exp_to_next_level(level):
    return int(level ** 2 * 50 + 50)

# 区域匹配公式
def is_region_suitable(region_danger, player_level):
    return abs(region_danger - (player_level // 2)) <= 3
