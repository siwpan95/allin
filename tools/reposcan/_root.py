#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reposcan 工具链的路径定位器（发布区根 + 中间物/产物落点）。

为什么单独成文件：`reposcan/` 下多个脚本都要用到同一组路径，各自写一份就会
各自漂移 —— 此前发布区根五份都写成了同一台机器的盘符路径，中间物与产物的落点
则跟着**调用者的当前目录**走（从仓根跑流水线会把文件散落到仓根）。

铁律 5 禁止硬编码盘符，因此这里统一按**本文件位置**推导，源码里不出现任何盘符：

1. 发布区根（``repos_root``）：环境变量优先，其次推本仓同级的 repos 目录；
2. 中间物与产物（``data_path`` / ``out_path``）：一律锚在本工具链目录下，
   从哪个目录调用都落到同一处。
"""
import json
import os
from pathlib import Path


def repos_root():
    """返回工作区 repos 目录；命中即用，按序：

    1. 环境变量 ``ALLIN_REPOS`` 已设且确实是目录 → 用之（换机/异机最省事）；
    2. 本仓仓根（``tools/reposcan/_root.py`` 的上两级）的**同级** ``repos`` 目录存在 → 用之；
    3. 都没有 → 抛错退出（fails loud：宁可不跑，也不要静默扫错目录）。
    """
    env = os.environ.get("ALLIN_REPOS", "").strip()
    if env and os.path.isdir(env):
        return env
    here = Path(__file__).resolve()
    # parents[0]=reposcan, parents[1]=tools, parents[2]=仓根；仓根同级即工作区 repos
    sibling = here.parents[2].parent / "repos"
    if sibling.is_dir():
        return str(sibling)
    raise SystemExit("ENV ERROR: 定位不到 repos 目录；请设置 ALLIN_REPOS=<工作区 repos 路径>")


#: 本工具链所在目录（tools/reposcan/）。
HERE = Path(__file__).resolve().parent
#: 渲染产物目录（脚本产出，不入版本控制）。
OUT_DIR = HERE / "output"
#: 流水线顺序（缺中间物时的报错指路用）。
PIPELINE = "先跑 python tools/reposcan/scan_repos.py 与 python tools/reposcan/detect_techstack.py"


def data_path(name):
    """扫描中间物（``repos_meta.json`` / ``tech_meta.json``）的落点。

    锚在本工具链目录下，不随调用者的当前目录漂移 —— 从仓根跑流水线也不会
    把中间物散落到仓根（散落后的副本还不在 .gitignore 覆盖范围内）。
    """
    return str(HERE / name)


def out_path(name):
    """渲染产物的落点；目录不存在则创建。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(OUT_DIR / name)


def read_json(name):
    """读取扫描中间物；缺失时大声失败并指路流水线顺序。"""
    path = HERE / name
    if not path.is_file():
        raise SystemExit(f"reposcan: 缺少扫描中间物 {name} —— {PIPELINE}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)
