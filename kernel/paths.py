# -*- coding: utf-8 -*-
"""allin 仓库根与常用路径常量（kernel 包内共用）。"""
from __future__ import annotations

import os

#: allin 仓库根（本文件在 allin/kernel/ 下，上溯两层）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOOLS_DIR = os.path.join(ROOT, 'tools')
PLATFORM_DIR = os.path.join(ROOT, 'platform')
PRESET_DIR = os.path.join(ROOT, 'preset')
DOCS_DIR = os.path.join(ROOT, 'docs')
VENV_PY = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
