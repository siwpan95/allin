#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成单份带交叉索引的总表 repos_master.md：主总表(领域+技术栈全字段) + 领域分组 + 技术栈分组(标签后附领域)。"""
import json

with open("repos_meta.json", encoding="utf-8") as fh:
    meta = json.load(fh)
with open("tech_meta.json", encoding="utf-8") as fh:
    tech = json.load(fh)
TECH = {t["name"]: t for t in tech}
META = {m["name"]: m for m in meta}

# 修正后的 CAT（已剔除已删除的 sin-virtue-game）
CAT = {
    "3dworld": ("游戏引擎/框架","3D 引擎库","pyglet 三维世界引擎库 (world3d)"),
    "3dworld-demos": ("游戏引擎/框架","引擎演示集","3dworld 引擎 43 个单文件演示 + 演出入口"),
    "3dworld-globe": ("游戏引擎/框架","引擎应用/演示","基于 3dworld 的交互地球仪"),
    "an-engine": ("游戏引擎/框架","统一游戏引擎","从 100+ 项目提炼的 Python 通用引擎 (ECS/事件总线/TRPG 内核)"),
    "cordis-py": ("游戏引擎/框架","场景引擎内核","dse-core 字典场景引擎 Python 版"),
    "cordis-snake": ("游戏引擎/框架","架构样例","Cordis 『一切皆插件』贪吃蛇样例"),
    "cordis-table-app": ("游戏引擎/框架","应用内核","Cordis 内核 + OpenPyXL 表格应用 (JSON-RPC 桥)"),
    "cordis-text-game": ("游戏引擎/框架","架构样例","Cordis 文字冒险引擎示例"),
    "dict-scene-engine": ("游戏引擎/框架","场景引擎","Cordis 4.0 文字冒险引擎 (场景即字典/能力即插件)"),
    "dse-core": ("游戏引擎/框架","场景引擎内核","字典场景引擎内核 (Node)"),
    "superengine": ("游戏引擎/框架","组合引擎仓","cordis 三仓组合流水线"),
    "worldbuilder": ("游戏引擎/框架","程序化生成库","供游戏 import 复用的 procgen 工具包"),

    "Idle": ("游戏作品","放置/挂机","tkinter 放置点击 RPG (科技树/装备/转生)"),
    "adventurelog": ("游戏作品","挂机 RPG","tkinter 数据驱动挂机放置 RPG"),
    "arcade": ("游戏作品","街机合集","街机小游戏合集 (俄罗斯方块等)"),
    "ashen-beacon": ("游戏作品","文字冒险","终端废土文字冒险 (dse-core + allin-engine)"),
    "backroom": ("游戏作品","3D 漫游","Backrooms 伪无限第一人称漫游 (3dworld PBR)"),
    "bee": ("游戏作品","挂机 RPG","蜜蜂挂机 RPG (系统托盘 + 实时音频)"),
    "darksouls": ("游戏作品","卡牌 Roguelike","黑暗之魂题材 Roguelike 卡牌"),
    "diablo": ("游戏作品","图形 RPG","暗黑破坏神风格图形 RPG"),
    "dungeon": ("游戏作品","地牢 Roguelike","pygame-ce 地牢 Roguelike (Savage Worlds 骰系)"),
    "dwarf-scrolls": ("游戏作品","模拟/冒险","矮人要塞画风 × 上古卷轴世界"),
    "fish": ("游戏作品","桌宠","桌面养鱼桌宠模拟器"),
    "god-hand-": ("游戏作品","文字冒险/roguelite","希腊十二试炼文字冒险 (Tkinter/pygame/控制台)"),
    "happy-childrens-day": ("游戏作品","休闲","六一零食大闯关无尽模式"),
    "hell-below": ("游戏作品","游戏启动平台","tkinter 小游戏聚合启动器"),
    "jotunnslayer": ("游戏作品","动作 Roguelite","JOTUNNSLAYER 复刻原型 (pygame-ce)"),
    "kard": ("游戏作品","卡牌动作","类吸血鬼幸存者+杀戮尖塔关键字卡牌"),
    "legend": ("游戏作品","点怪打怪","文字传奇点怪就打 (MVP+ECS+MVVM)"),
    "life-reset-simulator": ("游戏作品","人生模拟","人生重开模拟器 (MBTI+决策树)"),
    "loly": ("游戏作品","伪 3D FPS","DOOM 风格光线投射游戏 (pygame-ce)"),
    "lonely-desert-road": ("游戏作品","驾驶/无尽","ECS 无尽沙漠公路驾驶 (3D 透视)"),
    "maga": ("游戏作品","废土 RPG","重装机兵同人赏金猎人 RPG"),
    "magic-tower": ("游戏作品","爬塔 Roguelike","Tkinter 魔塔 (ECS + 自动挂机 + exe)"),
    "mahjong": ("游戏作品","解谜","麻将连连看 (144 张多层堆叠)"),
    "mc-clone": ("游戏作品","沙盒合集","MC 风格复刻合集 (文字+2D 侧视)"),
    "mcclone3d": ("游戏作品","体素沙盒","MC 风格 3D 体素沙盒 (3dworld)"),
    "mirsolo": ("游戏作品","ARPG 单机","热血传奇单机复刻 (三职业 + AI 对手)"),
    "moba_battle_platform": ("游戏作品","对战平台","MOBA 1v1 对战平台"),
    "niulai": ("游戏作品","动画复刻","《牛来》双引擎复刻工程"),
    "pq-multiverse": ("游戏作品","自动 RPG","Progress Quest 多元宇宙自动 RPG"),
    "project-root": ("游戏作品","模拟器","诡秘之主序列途径模拟系统"),
    "random-dungeon-": ("游戏作品","终端地牢","终端文字地牢探险 (可接超级引擎)"),
    "russia": ("游戏作品","轮盘赌","俄罗斯轮盘赌 (pygame-ce, ECS)"),
    "sandbox": ("游戏作品","地牢冒险","procgen + alloy 熔接的地牢冒险者"),
    "sign-in-simulator": ("游戏作品","签到/斯金纳箱","tkinter 签到奖励强化演示"),
    "smile": ("游戏作品","签到抽卡","pygame 签到抽卡式游戏"),
    "stay": ("游戏作品","进度放置","Progress Quest 2 Python/Tkinter 移植"),
    "table-hanging-machine": ("游戏作品","挂机桌游","Progress Quest v2 风格挂机桌游"),
    "tavern-rogue": ("游戏作品","自走棋 Roguelike","D&D SRD 酒馆异闻录自走棋"),
    "text-adventure": ("游戏作品","文字解谜","文字冒险解谜 (pygame + 浏览器 + Cordis 宿主)"),
    "text-fps": ("游戏作品","战术 FPS","文字 FPS 战术战斗 (pygame-ce)"),
    "under-withered-limbs": ("游戏作品","卡牌","pygame-ce 卡牌游戏 + 程序化音频"),
    "yuanbao": ("游戏作品","细胞模拟","细胞工厂 (生命游戏 + CNN 卷积核)"),

    "audio-pipeline": ("音乐/音频","制作流水线","纯音乐制作流水线 (拆歌→分轨→混音→重分离)"),
    "audio-separator": ("音乐/音频","人声分离","Demucs/BS-RoFormer 人声伴奏分离桌面应用"),
    "audiotool": ("音乐/音频","加工工具","Tkinter 批量音频/视频加工"),
    "bloodmusic": ("音乐/音频","程序化合成引擎","程序化游戏音频合成引擎"),
    "csmusic": ("音乐/音频","资源库","CS 音乐盒 MP3 成品库 + 下载脚本"),
    "midi": ("音乐/音频","DAW/MIDI","MusicStudio 音乐制作/DAW 项目"),
    "mp": ("音乐/音频","生成+可视化","随机音乐生成器 + WMP 风格可视化"),
    "music-prompt-generator": ("AI/大模型","AI 音乐提示词","纯音乐风格提示词生成器 (Suno/Udio，无模型调用)"),
    "musickit": ("音乐/音频","混音项目","phonk 混音项目 (真实采样 + 本地混音)"),
    "ncmturnmp3": ("音乐/音频","格式转换","加密音乐多格式转换器 (本地离线)"),
    "private-radio-stations": ("音乐/音频","转播/电台","视频转播 + 音频电台 monorepo (npm workspaces)"),
    "radio_special_instruments": ("音乐/音频","采样库","特殊乐器采样包库 + 下载脚本"),
    "remix": ("音乐/音频","混音/合成","pydub 音频混音 & 视频音频合成"),
    "wav_music_gen": ("音乐/音频","生成器","零依赖随机 WAV 音乐生成器"),

    "art_video_gen": ("视频/图像/特效","艺术视频生成","元胞自动机 + 粒子系统生成艺术视频 + ffmpeg 合成"),
    "cellular_automaton": ("视频/图像/特效","动态壁纸","2D 元胞自动机桌面壁纸 (pygame+numpy)"),
    "ddd2": ("视频/图像/特效","CA 视频","元胞自动机视频生成器 (tkinter)"),
    "drawpic": ("视频/图像/特效","故障艺术","21 个故障艺术生成器 (PNG/MP4)"),
    "gan": ("视频/图像/特效","视频生成","马尔可夫/CA/CNN-RNN-GNN 随机视频生成"),
    "imgproc": ("视频/图像/特效","图像批处理工具","Tkinter 批量图像加工 (缩放/水印/格式转换)"),
    "ling-train": ("视频/图像/特效","短视频流水线","《火车进站》短视频自动化制作流水线 (三代)"),
    "math": ("视频/图像/特效","CA 公式实验","Cellular Automata Formula Lab"),
    "mathematical-formula-renderer": ("视频/图像/特效","CA 渲染引擎","CA Render Engine (pygame)"),
    "media-tools": ("视频/图像/特效","媒体工具集","5 个视觉/图像/壁纸工具 (光栅化/PNG/风扇仿真/壁纸)"),
    "particlefx": ("视频/图像/特效","粒子系统","独立粒子系统库 (NumPy/pygame)"),
    "photovideo": ("视频/图像/特效","图转视频","图片转视频生成器 (6 种动效)"),
    "procedural-video": ("视频/图像/特效","过程生成视频","kkrieger 风格过程生成视频"),
    "pywallpaper": ("视频/图像/特效","动态壁纸","数学公式 + CA 驱动动态壁纸引擎 (ECS)"),
    "shikonghuaban": ("视频/图像/特效","音频可视化","黑洞/Penrose 全屏音频可视化引擎"),
    "video-generator": ("视频/图像/特效","随机视频","整合 9685 个效果预设的随机视频生成器"),
    "wave4": ("视频/图像/特效","噪声/分析","布朗噪声/fBm 生成与 Hurst/PSD 分析工具包"),

    "daily_player": ("播放器","视频播放器","基于 VLC 的日常视频播放器 (字幕/播放列表)"),
    "localplayer": ("播放器","浏览器扩展","本地媒体轻量播放器 (Chrome/Edge MV3)"),
    "music-player": ("播放器","音乐播放器","Python + VLC 音乐播放器"),
    "player": ("播放器","音频可视化","模拟 WMP 音频可视化效果程序"),
    "players-unified": ("播放器","整合仓","三端本地播放器整合 (Python+VLC / MV3 / Cordis Web)"),
    "pluginplayer": ("播放器","插件播放器","FFmpeg 9 + SDL3 内核 + 一切皆插件 (C ABI + Cordis JS)"),

    "novel": ("小说/网文","小说生成器","《万界归墟》双引擎程序化中文小说生成"),
    "novel-down": ("小说/网文","离线阅读/爬虫","规则驱动网络小说离线阅读 (免费章节)"),
    "novel-generator": ("小说/网文","小说生成器","novel_generator 通用小说生成库"),
    "novel-reader": ("小说/网文","视觉小说","基于同名小说改编 Tkinter 视觉小说游戏 (3.2 万页)"),
    "novel-run": ("小说/网文","集成验证","novel 结构化输出 + DSE 运行时的独立验证"),
    "weor": ("小说/网文","AI 小说系统","整合多开源范式的 AI 小说生成系统"),
    "write": ("小说/网文","创作工作区","网文正文/设定/素材工作区 (多为文本，无构建)"),

    "d20-table-link": ("跑团/TRPG","联动适配器","allin_engine TRPG × cordis-table-app 适配器"),
    "roleplayer": ("跑团/TRPG","跑团模拟器","D&D/GURPS/CoC 融合跑团模拟器 (v3)"),
    "running-group-simulator": ("跑团/TRPG","TRPG 中间件","Mirror of the Lost 终端驱动 TRPG 中间件引擎"),

    "ollama_generator": ("AI/大模型","文本生成库","基于 Ollama 的通用 AI 文本生成库"),
    "peasy-ai": ("AI/大模型","AI 框架","零硬编码配置驱动通用 AI 对话框架 + 叙事引擎"),

    "bilibili-helper-py": ("爬虫/采集","视频下载","B站视频下载桌面版 (Playwright)"),
    "crawl-hub": ("爬虫/采集","爬虫启动器","webcopier/sfx/font/bilibili/image 统一启动器"),
    "hushi_twrj": ("爬虫/采集","文档存档","胡适日记本地存档爬虫 (虚阁网)"),
    "image-scraper": ("爬虫/采集","图片爬虫","多源图片爬虫 (30 源, 断点续传)"),
    "midjourney_video": ("爬虫/采集","视频下载","Midjourney Explore 视频下载 (Playwright)"),
    "photo": ("爬虫/采集","图片爬虫","Tkinter 网页图片解析下载工具"),
    "sfx-download": ("爬虫/采集","音频爬取","通用免费公版音频爬取程序"),
    "webcopier": ("爬虫/采集","网页抓取","网页正文抓取 v5.3 (反爬系统)"),

    "auto_clicker": ("开发者/系统工具","鼠标连点器","Python GUI 鼠标连点器 (模块化)"),
    "board-replay": ("开发者/系统工具","棋谱复盘工具","Cordis 围棋SGF+国象UCI 本地复盘器 (Web UI+PNG出图)"),
    "calculator": ("开发者/系统工具","计算器","Calculator ∞ Alchemia 解密终端 (tkinter)"),
    "captcha-demo": ("开发者/系统工具","验证码演示","6 类验证码识别交互 (MVVM)"),
    "fonts": ("开发者/系统工具","字体工具","中文字体资源库 + 浏览/复制工具"),
    "foolproof-operation": ("开发者/系统工具","依赖安装器","图形化 Python 依赖库管理 (761 库)"),
    "markdown": ("开发者/系统工具","MD 查看器","Cordis 驱动的本地 Markdown 查看器"),
    "pdf": ("开发者/系统工具","PDF 阅读器","PyMuPDF + Pillow Tkinter PDF 阅读器"),
    "pomodmer": ("开发者/系统工具","番茄钟","Cordis + 本地 Web UI 番茄钟"),
    "print": ("开发者/系统工具","输入法","中文拼音输入法 (tkinter + 全局键盘监听)"),
    "py_test_runner": ("开发者/系统工具","测试框架","Python 项目全覆盖测试框架"),
    "pyinstaller": ("开发者/系统工具","打包工具","PyInstaller 批量打包工具箱"),
    "renamer": ("开发者/系统工具","批量重命名","正则批量重命名工具 (Tkinter)"),
    "santi-teleprompter": ("开发者/系统工具","提词器","三题故事提词器"),
    "subtitle": ("开发者/系统工具","字幕工具","Tkinter + ffmpeg 字幕提取/编辑/烧录"),
    "yasuo": ("开发者/系统工具","加密/压缩","文件加密与无损压缩工具 (pycryptodome)"),
    "zhuangtaiji": ("开发者/系统工具","决策引擎","多范式决策引擎 + Tkinter/React 工作台"),

    "lab": ("多语言引擎移植验证","国际象棋","10 语言国际象棋引擎功能对等实现 + perft 验证"),
    "weiqi_lab": ("多语言引擎移植验证","围棋","6 语言围棋引擎功能对等实现 (MCTS-UCT+RAVE)"),

    "haha": ("原型/学习/杂项","MVC/多语言演示","tkinter MVC 演示 + 76 语言 HelloWorld + Cordis 热插拔"),
    "sin-virtue-cordis-host": ("原型/学习/杂项","架构验证","七宗罪×七美德 Cordis 宿主验证原型"),
    "test": ("原型/学习/杂项","人格测试","荣格八功能 + 45 原型每日人格测试网页"),
}

ORDER = ["游戏引擎/框架","游戏作品","音乐/音频","视频/图像/特效","播放器",
    "小说/网文","跑团/TRPG","AI/大模型","爬虫/采集","开发者/系统工具",
    "多语言引擎移植验证","原型/学习/杂项"]

DOM_SHORT = {"游戏引擎/框架":"引擎","游戏作品":"游戏","音乐/音频":"音乐","视频/图像/特效":"视效",
    "播放器":"播放","小说/网文":"小说","跑团/TRPG":"跑团","AI/大模型":"AI","爬虫/采集":"爬虫",
    "开发者/系统工具":"工具","多语言引擎移植验证":"验证","原型/学习/杂项":"原型"}

REMOVE = {"sin-virtue-game"}  # 远端+本地已删除，总表同步剔除

GUI_MAP = {"tkinter":"Tkinter","pygame":"Pygame(-ce)","pyglet":"Pyglet",
    "Pillow/PIL":"Pillow","VLC":"VLC","OpenCV":"OpenCV","Matplotlib":"Matplotlib",
    "浏览器扩展(MV3)":"MV3扩展","Web服务/HTTP":"Web服务","系统级输入模拟":"输入模拟"}
NOTABLE_DEPS = {"torch","tensorflow","transformers","ollama","demucs","pydub","vlc","python-vlc",
    "soundfile","sounddevice","librosa","mido","midi","cv2","opencv-python","ffmpeg","Pillow",
    "pygame","pygame-ce","pyglet","numpy","scipy","playwright","requests","beautifulsoup4","bs4",
    "lxml","openpyxl","pycryptodome","pyautogui","electron","react","vite","fastapi","flask",
    "asteval","pandas","cryptography","pymupdf","fitz","pystray"}

def tech_cols(name):
    t = TECH.get(name, {})
    lang = "/".join(t.get("lang",["-"]))
    gui = [GUI_MAP.get(g,g) for g in t.get("gui",["CLI/headless"])]
    gui = sorted(set(gui))
    arch = t.get("arch",["-"])
    fw = [a for a in arch if a in ("Cordis","ECS")]
    eng = [a.split("/")[0].replace("3dworld/world3d","3dworld").replace("procgen/worldbuilder","procgen")
           for a in arch if a in ("allin_engine","3dworld/world3d","dse-core","procgen/worldbuilder")]
    deps = [d for d in t.get("deps",[]) if d in NOTABLE_DEPS]
    return lang, "·".join(gui), ("/".join(fw) if fw else "-"), ("/".join(sorted(set(eng))) if eng else "-"), ", ".join(deps[:8]) or "-"

# ── 主总表 ──
L = []
L.append("# D:\\projects\\repos 仓库总表（领域 × 技术栈 · 交叉索引）")
L.append("")
L.append("> 扫描日期：2026-10-28 ｜ 仓库总数：**133**（已同步删除远端/本地均移除的 `sin-virtue-game`）")
L.append("> 依据：README + 语言/框架信号 + 10 个边界仓深层源码核实。技术栈列格式：`语言 | 界面/形态 | 架构 | 依赖引擎 | 关键依赖`")
L.append("")
L.append("## 分类概览")
L.append("")
L.append("| 大类 | 数量 |")
L.append("|------|------|")
for c in ORDER:
    L.append(f"| {c} | {sum(1 for v in CAT.values() if v[0]==c)} |")
L.append(f"| **合计** | **{len(CAT)}** |")
L.append("")

L.append("## 主总表（每仓一行，领域 + 技术栈全字段）")
L.append("")
L.append("| # | 仓库 | 领域 | 子类 | 语言 | 界面/形态 | 架构 | 依赖引擎 | 关键依赖 | 证据（README） |")
L.append("|---|------|------|------|------|-----------|------|----------|----------|----------------|")
idx = 0
for c in ORDER:
    for name in sorted([n for n,v in CAT.items() if v[0]==c], key=str.lower):
        if name in REMOVE: continue
        idx += 1
        sub, ev = CAT[name][1], CAT[name][2]
        lang, gui, fw, eng, deps = tech_cols(name)
        L.append(f"| {idx} | `{name}` | {c} | {sub} | {lang} | {gui} | {fw} | {eng} | {deps} | {ev} |")
L.append("")

# ── 领域维度分组 ──
L.append("## 领域维度分组")
L.append("")
by_cat = {c: [] for c in ORDER}
for n in CAT:
    if n in REMOVE: continue
    by_cat[CAT[n][0]].append(n)
for c in ORDER:
    items = sorted(by_cat[c], key=str.lower)
    if not items: continue
    L.append(f"### {c}（{len(items)}）")
    L.append("")
    L.append("| 仓库 | 子类 | 技术栈 |")
    L.append("|------|------|--------|")
    for name in items:
        lang, gui, fw, eng, deps = tech_cols(name)
        ts = f"{lang} | {gui}"
        if fw!="-": ts += f" | +{fw}"
        if eng!="-": ts += f" | ▸{eng}"
        L.append(f"| `{name}` | {CAT[name][1]} | {ts} |")
    L.append("")

# ── 技术栈维度分组（标签后附领域，交叉索引）──
def group(fn):
    d = {}
    for name, t in TECH.items():
        if name in REMOVE or name not in CAT: continue
        dom = DOM_SHORT[CAT[name][0]]
        for k in fn(t):
            d.setdefault(k, []).append(f"`{name}`({dom})")
    return d

def lang_keys(t):
    langs=t.get("lang",["-"])
    if "Node/JS" in langs and "Python" in langs: return ["多语言(Python+Node)"]
    if "TypeScript" in langs: return ["TypeScript 为主"]
    if "Node/JS" in langs: return ["Node/JS"]
    if "Python" in langs: return ["Python"]
    if any(x in langs for x in ("Rust","Go","Java")): return ["其他编译型"]
    return ["未检出代码(资源/文档)"]
def gui_keys(t):
    ks=[GUI_MAP.get(g,g) for g in t.get("gui",["CLI/headless"])]
    return ks if ks else ["CLI / 无界面"]
def arch_keys(t):
    arch=t.get("arch",["-"]); ks=[]
    if "Cordis" in arch: ks.append("Cordis 驱动")
    if "ECS" in arch: ks.append("ECS 架构")
    for e in ("allin_engine","3dworld/world3d","dse-core","procgen/worldbuilder"):
        if e in arch: ks.append("依赖引擎:"+e.split("/")[0].replace("3dworld/world3d","3dworld").replace("procgen/worldbuilder","procgen"))
    return ks if ks else ["普通/无特定框架"]
def lib_keys(t):
    deps=set(t.get("deps",[])); ks=[]
    if deps&{"torch","tensorflow","transformers","ollama"}: ks.append("AI/ML 栈")
    if deps&{"demucs","pydub","vlc","python-vlc","soundfile","sounddevice","librosa","mido","midi"}: ks.append("音频栈")
    if deps&{"cv2","opencv-python","ffmpeg","Pillow"}: ks.append("图像/视频栈")
    if deps&{"playwright","requests","beautifulsoup4","bs4","lxml"}: ks.append("爬虫/网络栈")
    if deps&{"openpyxl"}: ks.append("表格(OpenPyXL)")
    return ks if ks else ["标准库/轻依赖"]

sections=[("### 2a. 按语言",lang_keys),("### 2b. 按 GUI / 运行时形态",gui_keys),
          ("### 2c. 按架构 / 框架",arch_keys),("### 2d. 按关键依赖库集群",lib_keys)]
L.append("## 技术栈维度分组（标签后附领域，实现交叉索引）")
L.append("")
for title, fn in sections:
    L.append(title); L.append("")
    grp=group(fn)
    for k in sorted(grp.keys(), key=str.lower):
        names=sorted(grp[k])
        L.append(f"**{k}（{len(names)}）**：" + "、".join(names))
    L.append("")

out="\n".join(L)
with open("repos_master.md","w",encoding="utf-8") as fh:
    fh.write(out)
print("repos_master.md 生成，总行数:", out.count("\n"), "| 主总表行数(含表头):", idx+2, "| 总数:", len(CAT))
