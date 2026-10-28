#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作区 repos 目录的定位器。

为什么单独成文件：`reposcan/` 下五个脚本都要用到同一个「仓库根目录」，
各自写一份就会各自漂移（而且此前五份都写成了同一台机器的盘符路径）。
铁律 5 禁止硬编码盘符，所以这里只做两件事：环境变量优先，其次按**本文件位置**
推导出本仓（allin）同级的 repos 目录 —— 源码里不出现任何盘符。
"""
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
