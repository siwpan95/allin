#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reposcan 工具链共用的路径解析与中间物读取。

三条约定，全部与本仓既有写法一致：

1. **发布区根**（``repos_root``）：``ALLIN_REPOS_ROOT`` 环境变量优先，否则
   ``<仓根>/../repos`` —— 与 ``tools/license_matrix.py``、门禁 ``g17_registry.py``
   同一口径。
2. **不写死盘符**（SPEC-001 §铁律 5）：源码里不出现机器相关绝对路径；
   报告标题用去符盘形式（``/projects/repos``）指代约定目录。
3. **路径相对脚本自身**：所有中间物与产物的读写都锚在本目录，
   不依赖调用者的当前工作目录 —— 流水线从仓根跑也不会把文件散落到别处。
"""
import json
import os
from pathlib import Path

#: 本工具链所在目录（tools/reposcan/）。
HERE = Path(__file__).resolve().parent
#: 仓根（= 本目录上溯两级：tools/reposcan/ -> 仓根）。
REPO_ROOT = HERE.parents[1]
#: 渲染产物目录（本机生成物，不入库）。
OUT_DIR = HERE / "output"

#: 流水线顺序（缺中间物时的报错指路用）。
PIPELINE = "先跑 python tools/reposcan/scan_repos.py 与 python tools/reposcan/detect_techstack.py"


def repos_root() -> Path:
    """发布区根目录：``ALLIN_REPOS_ROOT`` 优先，否则 ``<仓根>/../repos``。"""
    override = os.environ.get("ALLIN_REPOS_ROOT")
    return Path(override) if override else REPO_ROOT.parent / "repos"


def repos_label() -> str:
    """发布区的去符盘标签（如 ``/projects/repos``），供报告标题使用。

    去符盘形式是本仓对「仓根 / 约定父目录」的既定写法（SPEC-001 §铁律 5），
    明确表示它是约定位置，而非某台机器上的真实路径。
    """
    root = repos_root().resolve()
    parent = root.parent.name
    return f"/{parent}/{root.name}" if parent else f"/{root.name}"


def data_path(name: str) -> Path:
    """扫描中间物（``repos_meta.json`` / ``tech_meta.json``）的落点。"""
    return HERE / name


def out_path(name: str) -> Path:
    """渲染产物的落点；目录不存在则创建。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR / name


def read_data(name: str):
    """读取扫描中间物；缺失时大声失败并指路流水线顺序。"""
    path = data_path(name)
    if not path.is_file():
        raise SystemExit(f"reposcan: 缺少扫描中间物 {path.name} —— {PIPELINE}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)
