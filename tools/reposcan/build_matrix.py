#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成：① 领域×技术栈矩阵热力表(HTML) ② CSV + Excel 导出（总表 + 矩阵双 sheet）。"""
import json, csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import repos_root

ROOT = repos_root()

with open("repos_meta.json", encoding="utf-8") as fh:
    meta = json.load(fh)
with open("tech_meta.json", encoding="utf-8") as fh:
    tech = json.load(fh)
TECH = {t["name"]: t for t in tech}

# 与 build_master.py 保持一致的 133 仓分类（已剔除 sin-virtue-game）
CAT = {
    "3dworld": ("游戏引擎/框架","3D 引擎库"),"3dworld-demos": ("游戏引擎/框架","引擎演示集"),"3dworld-globe": ("游戏引擎/框架","引擎应用/演示"),
    "an-engine": ("游戏引擎/框架","统一游戏引擎"),"cordis-py": ("游戏引擎/框架","场景引擎内核"),"cordis-snake": ("游戏引擎/框架","架构样例"),
    "cordis-table-app": ("游戏引擎/框架","应用内核"),"cordis-text-game": ("游戏引擎/框架","架构样例"),"dict-scene-engine": ("游戏引擎/框架","场景引擎"),
    "dse-core": ("游戏引擎/框架","场景引擎内核"),"superengine": ("游戏引擎/框架","组合引擎仓"),"worldbuilder": ("游戏引擎/框架","程序化生成库"),
    "Idle": ("游戏作品","放置/挂机"),"adventurelog": ("游戏作品","挂机 RPG"),"arcade": ("游戏作品","街机合集"),"ashen-beacon": ("游戏作品","文字冒险"),
    "backroom": ("游戏作品","3D 漫游"),"bee": ("游戏作品","挂机 RPG"),"darksouls": ("游戏作品","卡牌 Roguelike"),"diablo": ("游戏作品","图形 RPG"),
    "dungeon": ("游戏作品","地牢 Roguelike"),"dwarf-scrolls": ("游戏作品","模拟/冒险"),"fish": ("游戏作品","桌宠"),"god-hand-": ("游戏作品","文字冒险/roguelite"),
    "happy-childrens-day": ("游戏作品","休闲"),"hell-below": ("游戏作品","游戏启动平台"),"jotunnslayer": ("游戏作品","动作 Roguelite"),"kard": ("游戏作品","卡牌动作"),
    "legend": ("游戏作品","点怪打怪"),"life-reset-simulator": ("游戏作品","人生模拟"),"loly": ("游戏作品","伪 3D FPS"),"lonely-desert-road": ("游戏作品","驾驶/无尽"),
    "maga": ("游戏作品","废土 RPG"),"magic-tower": ("游戏作品","爬塔 Roguelike"),"mahjong": ("游戏作品","解谜"),"mc-clone": ("游戏作品","沙盒合集"),
    "mcclone3d": ("游戏作品","体素沙盒"),"mirsolo": ("游戏作品","ARPG 单机"),"moba_battle_platform": ("游戏作品","对战平台"),"niulai": ("游戏作品","动画复刻"),
    "pq-multiverse": ("游戏作品","自动 RPG"),"project-root": ("游戏作品","模拟器"),"random-dungeon-": ("游戏作品","终端地牢"),"russia": ("游戏作品","轮盘赌"),
    "sandbox": ("游戏作品","地牢冒险"),"sign-in-simulator": ("游戏作品","签到/斯金纳箱"),"smile": ("游戏作品","签到抽卡"),"stay": ("游戏作品","进度放置"),
    "table-hanging-machine": ("游戏作品","挂机桌游"),"tavern-rogue": ("游戏作品","自走棋 Roguelike"),"text-adventure": ("游戏作品","文字解谜"),"text-fps": ("游戏作品","战术 FPS"),
    "under-withered-limbs": ("游戏作品","卡牌"),"yuanbao": ("游戏作品","细胞模拟"),
    "audio-pipeline": ("音乐/音频","制作流水线"),"audio-separator": ("音乐/音频","人声分离"),"audiotool": ("音乐/音频","加工工具"),"bloodmusic": ("音乐/音频","程序化合成引擎"),
    "csmusic": ("音乐/音频","资源库"),"midi": ("音乐/音频","DAW/MIDI"),"mp": ("音乐/音频","生成+可视化"),"music-prompt-generator": ("AI/大模型","AI 音乐提示词"),
    "musickit": ("音乐/音频","混音项目"),"ncmturnmp3": ("音乐/音频","格式转换"),"private-radio-stations": ("音乐/音频","转播/电台"),"radio_special_instruments": ("音乐/音频","采样库"),
    "remix": ("音乐/音频","混音/合成"),"wav_music_gen": ("音乐/音频","生成器"),
    "art_video_gen": ("视频/图像/特效","艺术视频生成"),"cellular_automaton": ("视频/图像/特效","动态壁纸"),"ddd2": ("视频/图像/特效","CA 视频"),"drawpic": ("视频/图像/特效","故障艺术"),
    "gan": ("视频/图像/特效","视频生成"),"imgproc": ("视频/图像/特效","图像批处理工具"),"ling-train": ("视频/图像/特效","短视频流水线"),"math": ("视频/图像/特效","CA 公式实验"),
    "mathematical-formula-renderer": ("视频/图像/特效","CA 渲染引擎"),"media-tools": ("视频/图像/特效","媒体工具集"),"particlefx": ("视频/图像/特效","粒子系统"),"photovideo": ("视频/图像/特效","图转视频"),
    "procedural-video": ("视频/图像/特效","过程生成视频"),"pywallpaper": ("视频/图像/特效","动态壁纸"),"shikonghuaban": ("视频/图像/特效","音频可视化"),"video-generator": ("视频/图像/特效","随机视频"),
    "wave4": ("视频/图像/特效","噪声/分析"),
    "daily_player": ("播放器","视频播放器"),"localplayer": ("播放器","浏览器扩展"),"music-player": ("播放器","音乐播放器"),"player": ("播放器","音频可视化"),
    "players-unified": ("播放器","整合仓"),"pluginplayer": ("播放器","插件播放器"),
    "novel": ("小说/网文","小说生成器"),"novel-down": ("小说/网文","离线阅读/爬虫"),"novel-generator": ("小说/网文","小说生成器"),"novel-reader": ("小说/网文","视觉小说"),
    "novel-run": ("小说/网文","集成验证"),"weor": ("小说/网文","AI 小说系统"),"write": ("小说/网文","创作工作区"),
    "d20-table-link": ("跑团/TRPG","联动适配器"),"roleplayer": ("跑团/TRPG","跑团模拟器"),"running-group-simulator": ("跑团/TRPG","TRPG 中间件"),
    "ollama_generator": ("AI/大模型","文本生成库"),"peasy-ai": ("AI/大模型","AI 框架"),
    "bilibili-helper-py": ("爬虫/采集","视频下载"),"crawl-hub": ("爬虫/采集","爬虫启动器"),"hushi_twrj": ("爬虫/采集","文档存档"),"image-scraper": ("爬虫/采集","图片爬虫"),
    "midjourney_video": ("爬虫/采集","视频下载"),"photo": ("爬虫/采集","图片爬虫"),"sfx-download": ("爬虫/采集","音频爬取"),"webcopier": ("爬虫/采集","网页抓取"),
    "auto_clicker": ("开发者/系统工具","鼠标连点器"),"board-replay": ("开发者/系统工具","棋谱复盘工具"),"calculator": ("开发者/系统工具","计算器"),"captcha-demo": ("开发者/系统工具","验证码演示"),
    "fonts": ("开发者/系统工具","字体工具"),"foolproof-operation": ("开发者/系统工具","依赖安装器"),"markdown": ("开发者/系统工具","MD 查看器"),"pdf": ("开发者/系统工具","PDF 阅读器"),
    "pomodmer": ("开发者/系统工具","番茄钟"),"print": ("开发者/系统工具","输入法"),"py_test_runner": ("开发者/系统工具","测试框架"),"pyinstaller": ("开发者/系统工具","打包工具"),
    "renamer": ("开发者/系统工具","批量重命名"),"santi-teleprompter": ("开发者/系统工具","提词器"),"subtitle": ("开发者/系统工具","字幕工具"),"yasuo": ("开发者/系统工具","加密/压缩"),
    "zhuangtaiji": ("开发者/系统工具","决策引擎"),
    "lab": ("多语言引擎移植验证","国际象棋"),"weiqi_lab": ("多语言引擎移植验证","围棋"),
    "haha": ("原型/学习/杂项","MVC/多语言演示"),"sin-virtue-cordis-host": ("原型/学习/杂项","架构验证"),"test": ("原型/学习/杂项","人格测试"),
}

ORDER = ["游戏引擎/框架","游戏作品","音乐/音频","视频/图像/特效","播放器",
    "小说/网文","跑团/TRPG","AI/大模型","爬虫/采集","开发者/系统工具",
    "多语言引擎移植验证","原型/学习/杂项"]

REMOVE = {"sin-virtue-game"}

EVID = {
 "3dworld":"pyglet 三维世界引擎库 (world3d)","3dworld-demos":"3dworld 引擎 43 个单文件演示 + 演出入口","3dworld-globe":"基于 3dworld 的交互地球仪",
 "an-engine":"从 100+ 项目提炼的 Python 通用引擎 (ECS/事件总线/TRPG 内核)","cordis-py":"dse-core 字典场景引擎 Python 版","cordis-snake":"Cordis 『一切皆插件』贪吃蛇样例",
 "cordis-table-app":"Cordis 内核 + OpenPyXL 表格应用 (JSON-RPC 桥)","cordis-text-game":"Cordis 文字冒险引擎示例","dict-scene-engine":"Cordis 4.0 文字冒险引擎 (场景即字典/能力即插件)",
 "dse-core":"字典场景引擎内核 (Node)","superengine":"cordis 三仓组合流水线","worldbuilder":"供游戏 import 复用的 procgen 工具包",
 "Idle":"tkinter 放置点击 RPG (科技树/装备/转生)","adventurelog":"tkinter 数据驱动挂机放置 RPG","arcade":"街机小游戏合集 (俄罗斯方块等)","ashen-beacon":"终端废土文字冒险 (dse-core + allin-engine)",
 "backroom":"Backrooms 伪无限第一人称漫游 (3dworld PBR)","bee":"蜜蜂挂机 RPG (系统托盘 + 实时音频)","darksouls":"黑暗之魂题材 Roguelike 卡牌","diablo":"暗黑破坏神风格图形 RPG",
 "dungeon":"pygame-ce 地牢 Roguelike (Savage Worlds 骰系)","dwarf-scrolls":"矮人要塞画风 × 上古卷轴世界","fish":"桌面养鱼桌宠模拟器","god-hand-":"希腊十二试炼文字冒险 (Tkinter/pygame/控制台)",
 "happy-childrens-day":"六一零食大闯关无尽模式","hell-below":"tkinter 小游戏聚合启动器","jotunnslayer":"JOTUNNSLAYER 复刻原型 (pygame-ce)","kard":"类吸血鬼幸存者+杀戮尖塔关键字卡牌",
 "legend":"文字传奇点怪就打 (MVP+ECS+MVVM)","life-reset-simulator":"人生重开模拟器 (MBTI+决策树)","loly":"DOOM 风格光线投射游戏 (pygame-ce)","lonely-desert-road":"ECS 无尽沙漠公路驾驶 (3D 透视)",
 "maga":"重装机兵同人赏金猎人 RPG","magic-tower":"Tkinter 魔塔 (ECS + 自动挂机 + exe)","mahjong":"麻将连连看 (144 张多层堆叠)","mc-clone":"MC 风格复刻合集 (文字+2D 侧视)",
 "mcclone3d":"MC 风格 3D 体素沙盒 (3dworld)","mirsolo":"热血传奇单机复刻 (三职业 + AI 对手)","moba_battle_platform":"MOBA 1v1 对战平台","niulai":"《牛来》双引擎复刻工程",
 "pq-multiverse":"Progress Quest 多元宇宙自动 RPG","project-root":"诡秘之主序列途径模拟系统","random-dungeon-":"终端文字地牢探险 (可接超级引擎)","russia":"俄罗斯轮盘赌 (pygame-ce, ECS)",
 "sandbox":"procgen + alloy 熔接的地牢冒险者","sign-in-simulator":"tkinter 签到奖励强化演示","smile":"pygame 签到抽卡式游戏","stay":"Progress Quest 2 Python/Tkinter 移植",
 "table-hanging-machine":"Progress Quest v2 风格挂机桌游","tavern-rogue":"D&D SRD 酒馆异闻录自走棋","text-adventure":"文字冒险解谜 (pygame + 浏览器 + Cordis 宿主)","text-fps":"文字 FPS 战术战斗 (pygame-ce)",
 "under-withered-limbs":"pygame-ce 卡牌游戏 + 程序化音频","yuanbao":"细胞工厂 (生命游戏 + CNN 卷积核)",
 "audio-pipeline":"纯音乐制作流水线 (拆歌→分轨→混音→重分离)","audio-separator":"Demucs/BS-RoFormer 人声伴奏分离桌面应用","audiotool":"Tkinter 批量音频/视频加工","bloodmusic":"程序化游戏音频合成引擎",
 "csmusic":"CS 音乐盒 MP3 成品库 + 下载脚本","midi":"MusicStudio 音乐制作/DAW 项目","mp":"随机音乐生成器 + WMP 风格可视化","music-prompt-generator":"纯音乐风格提示词生成器 (Suno/Udio，无模型调用)",
 "musickit":"phonk 混音项目 (真实采样 + 本地混音)","ncmturnmp3":"加密音乐多格式转换器 (本地离线)","private-radio-stations":"视频转播 + 音频电台 monorepo (npm workspaces)","radio_special_instruments":"特殊乐器采样包库 + 下载脚本",
 "remix":"pydub 音频混音 & 视频音频合成","wav_music_gen":"零依赖随机 WAV 音乐生成器",
 "art_video_gen":"元胞自动机 + 粒子系统生成艺术视频 + ffmpeg 合成","cellular_automaton":"2D 元胞自动机桌面壁纸 (pygame+numpy)","ddd2":"元胞自动机视频生成器 (tkinter)","drawpic":"21 个故障艺术生成器 (PNG/MP4)",
 "gan":"马尔可夫/CA/CNN-RNN-GNN 随机视频生成","imgproc":"Tkinter 批量图像加工 (缩放/水印/格式转换)","ling-train":"《火车进站》短视频自动化制作流水线 (三代)","math":"Cellular Automata Formula Lab",
 "mathematical-formula-renderer":"CA Render Engine (pygame)","media-tools":"5 个视觉/图像/壁纸工具 (光栅化/PNG/风扇仿真/壁纸)","particlefx":"独立粒子系统库 (NumPy/pygame)","photovideo":"图片转视频生成器 (6 种动效)",
 "procedural-video":"kkrieger 风格过程生成视频","pywallpaper":"数学公式 + CA 驱动动态壁纸引擎 (ECS)","shikonghuaban":"黑洞/Penrose 全屏音频可视化引擎","video-generator":"整合 9685 个效果预设的随机视频生成器",
 "wave4":"布朗噪声/fBm 生成与 Hurst/PSD 分析工具包",
 "daily_player":"基于 VLC 的日常视频播放器 (字幕/播放列表)","localplayer":"本地媒体轻量播放器 (Chrome/Edge MV3)","music-player":"Python + VLC 音乐播放器","player":"模拟 WMP 音频可视化效果程序",
 "players-unified":"三端本地播放器整合 (Python+VLC / MV3 / Cordis Web)","pluginplayer":"FFmpeg 9 + SDL3 内核 + 一切皆插件 (C ABI + Cordis JS)",
 "novel":"《万界归墟》双引擎程序化中文小说生成","novel-down":"规则驱动网络小说离线阅读 (免费章节)","novel-generator":"novel_generator 通用小说生成库","novel-reader":"基于同名小说改编 Tkinter 视觉小说游戏 (3.2 万页)",
 "novel-run":"novel 结构化输出 + DSE 运行时的独立验证","weor":"整合多开源范式的 AI 小说生成系统","write":"网文正文/设定/素材工作区 (多为文本，无构建)",
 "d20-table-link":"allin_engine TRPG × cordis-table-app 适配器","roleplayer":"D&D/GURPS/CoC 融合跑团模拟器 (v3)","running-group-simulator":"Mirror of the Lost 终端驱动 TRPG 中间件引擎",
 "ollama_generator":"基于 Ollama 的通用 AI 文本生成库","peasy-ai":"零硬编码配置驱动通用 AI 对话框架 + 叙事引擎",
 "bilibili-helper-py":"B站视频下载桌面版 (Playwright)","crawl-hub":"webcopier/sfx/font/bilibili/image 统一启动器","hushi_twrj":"胡适日记本地存档爬虫 (虚阁网)","image-scraper":"多源图片爬虫 (30 源, 断点续传)",
 "midjourney_video":"Midjourney Explore 视频下载 (Playwright)","photo":"Tkinter 网页图片解析下载工具","sfx-download":"通用免费公版音频爬取程序","webcopier":"网页正文抓取 v5.3 (反爬系统)",
 "auto_clicker":"Python GUI 鼠标连点器 (模块化)","board-replay":"Cordis 围棋SGF+国象UCI 本地复盘器 (Web UI+PNG出图)","calculator":"Calculator ∞ Alchemia 解密终端 (tkinter)","captcha-demo":"6 类验证码识别交互 (MVVM)",
 "fonts":"中文字体资源库 + 浏览/复制工具","foolproof-operation":"图形化 Python 依赖库管理 (761 库)","markdown":"Cordis 驱动的本地 Markdown 查看器","pdf":"PyMuPDF + Pillow Tkinter PDF 阅读器",
 "pomodmer":"Cordis + 本地 Web UI 番茄钟","print":"中文拼音输入法 (tkinter + 全局键盘监听)","py_test_runner":"Python 项目全覆盖测试框架","pyinstaller":"PyInstaller 批量打包工具箱",
 "renamer":"正则批量重命名工具 (Tkinter)","santi-teleprompter":"三题故事提词器","subtitle":"Tkinter + ffmpeg 字幕提取/编辑/烧录","yasuo":"文件加密与无损压缩工具 (pycryptodome)",
 "zhuangtaiji":"多范式决策引擎 + Tkinter/React 工作台",
 "lab":"10 语言国际象棋引擎功能对等实现 + perft 验证","weiqi_lab":"6 语言围棋引擎功能对等实现 (MCTS-UCT+RAVE)",
 "haha":"tkinter MVC 演示 + 76 语言 HelloWorld + Cordis 热插拔","sin-virtue-cordis-host":"七宗罪×七美德 Cordis 宿主验证原型","test":"荣格八功能 + 45 原型每日人格测试网页",
}

# ── 技术属性抽取 ──
def get_attrs(name):
    t = TECH.get(name, {})
    langs = t.get("lang", ["-"]); gui = t.get("gui", ["CLI/headless"])
    arch = t.get("arch", ["-"]); deps = set(t.get("deps", []))
    a = set()
    if "Node/JS" in langs and "Python" in langs: a.add("多语言(Py+Node)")
    elif "TypeScript" in langs: a.add("TypeScript")
    elif "Node/JS" in langs: a.add("Node/JS")
    elif "Python" in langs: a.add("Python")
    gui_match = False
    if "tkinter" in gui: a.add("Tkinter"); gui_match = True
    if "pygame" in gui: a.add("Pygame"); gui_match = True
    if "pyglet" in gui: a.add("Pyglet"); gui_match = True
    if "Web服务/HTTP" in gui: a.add("Web服务"); gui_match = True
    if "浏览器扩展(MV3)" in gui: a.add("MV3扩展"); gui_match = True
    if "VLC" in gui: a.add("VLC"); gui_match = True
    if "Pillow/PIL" in gui: a.add("Pillow")
    if "系统级输入模拟" in gui: a.add("输入模拟"); gui_match = True
    if not gui_match: a.add("CLI/无界面")
    if "Cordis" in arch: a.add("Cordis")
    if "ECS" in arch: a.add("ECS")
    for e, lab in (("allin_engine","allin_engine"),("3dworld/world3d","3dworld"),("dse-core","dse-core"),("procgen/worldbuilder","procgen")):
        if e in arch: a.add(lab)
    if deps & {"torch","tensorflow","transformers","ollama"}: a.add("AI/ML")
    if deps & {"demucs","pydub","vlc","python-vlc","soundfile","sounddevice","librosa","mido","midi"}: a.add("音频栈")
    if deps & {"cv2","opencv-python","ffmpeg","Pillow"}: a.add("图像/视频栈")
    if deps & {"playwright","requests","beautifulsoup4","bs4","lxml"}: a.add("爬虫/网络栈")
    if deps & {"openpyxl"}: a.add("表格(OpenPyXL)")
    return a

COLS = ["Python","Node/JS","TypeScript","多语言(Py+Node)","Tkinter","Pygame","Pyglet","Web服务","MV3扩展","VLC","Pillow","输入模拟","CLI/无界面",
        "Cordis","ECS","allin_engine","3dworld","dse-core","procgen","AI/ML","音频栈","图像/视频栈","爬虫/网络栈","表格(OpenPyXL)"]
SECTIONS = [("语言",4),("GUI形态",9),("架构",6),("依赖库",5)]
FLAT_FLAGS = ["Cordis","ECS","allin_engine","3dworld","dse-core","procgen","Tkinter","Pygame","Pyglet","Web服务","AI/ML","音频栈","图像/视频栈","爬虫/网络栈","表格(OpenPyXL)"]

# 计算矩阵
repos = [(n, CAT[n][0], CAT[n][1], get_attrs(n)) for n in CAT if n not in REMOVE]
mat = {c: {col: 0 for col in COLS} for c in ORDER}
for n, dom, sub, attrs in repos:
    for col in COLS:
        if col in attrs: mat[dom][col] += 1
colmax = {col: max(mat[c][col] for c in ORDER) for col in COLS}
domtot = {c: sum(mat[c][col] for col in COLS) for c in ORDER}

# ── ① HTML 热力表 ──
def lerp(a,b,t): return int(a+(b-a)*t)
def cell_style(cnt, mx):
    if cnt == 0: return "background:#f1f3f5;color:#ced4da;"
    t = cnt/mx if mx else 0
    r=lerp(231,29,t); g=lerp(240,78,t); b=lerp(255,216,t)
    col = "color:#fff;" if t>0.5 else "color:#13203a;"
    return f"background:rgb({r},{g},{b});{col}"
html=[]
html.append("<!doctype html><html lang='zh'><head><meta charset='utf-8'>")
html.append(f"<title>{ROOT} · 领域×技术栈矩阵热力表</title>")
html.append("<style>body{font-family:-apple-system,Segoe UI,Roboto,'Microsoft YaHei',sans-serif;margin:24px;color:#1a1a2e;}")
html.append("h1{font-size:20px;} .sub{color:#666;font-size:13px;margin-bottom:16px;}")
html.append("table{border-collapse:collapse;font-size:12px;} th,td{border:1px solid #e3e6ea;padding:5px 7px;text-align:center;}")
html.append("th.dom{text-align:left;background:#21304a;color:#fff;position:sticky;left:0;}")
html.append("th.col{background:#21304a;color:#fff;writing-mode:vertical-rl;transform:rotate(180deg);height:96px;white-space:nowrap;}")
html.append("td.dom{text-align:left;font-weight:600;background:#f8f9fb;position:sticky;left:0;white-space:nowrap;}")
html.append("td.tot{font-weight:700;background:#eef1f5;}")
thr=("").join(f"<th class='col'>{c}</th>" for c in COLS)
html.append("</style></head><body>")
html.append(f"<h1>{ROOT} · 领域 × 技术栈 矩阵热力表</h1>")
html.append(f"<div class='sub'>共 {len(repos)} 仓（已剔除 sin-virtue-game）。单元格数字=该领域下命中所列技术属性的仓库数；颜色越深=数量越多（按列归一化）。</div>")
html.append("<table><tr><th class='dom'>领域 \\ 技术属性</th>"+thr+"<th class='col'>合计</th></tr>")
for c in ORDER:
    cells="".join(f"<td style='{cell_style(mat[c][col],colmax[col])}'>{mat[c][col]}</td>" for col in COLS)
    html.append(f"<tr><td class='dom'>{c}</td>{cells}<td class='tot'>{domtot[c]}</td></tr>")
# 合计行
totcells="".join(f"<td class='tot'>{colmax[col]}</td>" for col in COLS)
html.append(f"<tr><td class='dom'>合计</td>{totcells}<td class='tot'>{len(repos)}</td></tr>")
html.append("</table>")
# 图例 + 小节
html.append("<div class='sub' style='margin-top:18px;'><b>读图示例：</b>Cordis 列中「游戏作品」格最深 → 多数游戏作品基于 Cordis；「音频栈」集中在音乐/音频与部分视频/特效；「CLI/无界面」多见于爬虫/引擎验证。</div>")
html.append("</body></html>")
open("repos_master_matrix.html","w",encoding="utf-8").write("\n".join(html))

# ── ② CSV ──
def tech_flat(name):
    t = TECH.get(name, {})
    lang="/".join(t.get("lang",["-"]))
    gui=[{"tkinter":"Tkinter","pygame":"Pygame(-ce)","pyglet":"Pyglet","Pillow/PIL":"Pillow","VLC":"VLC","OpenCV":"OpenCV","Matplotlib":"Matplotlib","浏览器扩展(MV3)":"MV3扩展","Web服务/HTTP":"Web服务","系统级输入模拟":"输入模拟"}.get(g,g) for g in t.get("gui",["CLI/headless"])]
    gui="·".join(sorted(set(gui)))
    arch=t.get("arch",["-"]); fw="/".join([x for x in arch if x in ("Cordis","ECS")]) or "-"
    eng="/".join(sorted({x.split("/")[0].replace("3dworld/world3d","3dworld").replace("procgen/worldbuilder","procgen") for x in arch if x in ("allin_engine","3dworld/world3d","dse-core","procgen/worldbuilder")})) or "-"
    return lang, gui, fw, eng
csv_cols=["仓库","领域","子类","语言","界面/形态","架构","依赖引擎","关键依赖","证据"]+FLAT_FLAGS
with open("repos_master.csv","w",encoding="utf-8-sig",newline="") as fh:
    w=csv.writer(fh); w.writerow(csv_cols)
    for n,dom,sub,attrs in sorted(repos,key=lambda x:(ORDER.index(x[1]),x[0].lower())):
        lang,gui,fw,eng=tech_flat(n)
        depset={"torch","tensorflow","transformers","ollama","demucs","pydub","vlc","python-vlc","soundfile","sounddevice","librosa","mido","midi","cv2","opencv-python","ffmpeg","Pillow","pygame","pygame-ce","pyglet","numpy","scipy","playwright","requests","beautifulsoup4","bs4","lxml","openpyxl","pycryptodome","pyautogui","electron","react","vite","fastapi","flask","asteval","pandas","cryptography","pymupdf","fitz","pystray"}
        deps=", ".join(d for d in TECH.get(n,{}).get("deps",[]) if d in depset) or "-"
        row=[n,dom,sub,lang,gui,fw,eng,deps,EVID.get(n,"")]
        row+=["是" if f in attrs else "否" for f in FLAT_FLAGS]
        w.writerow(row)

# ── ② XLSX ──
# tools/ 约定零三方依赖的唯一例外：XLSX 导出需要 openpyxl（HTML/CSV 部分不受影响）
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    raise SystemExit("build_matrix.py 的 XLSX 导出需要 openpyxl：pip install openpyxl（HTML/CSV 已在其之前生成，不受影响）")
wb=openpyxl.Workbook()
# Sheet1 总表
ws=wb.active; ws.title="总表"
hdrfill=PatternFill("solid",fgColor="21304A"); hdrfont=Font(color="FFFFFF",bold=True)
thin=Side(style="thin",color="D0D5DD"); border=Border(left=thin,right=thin,top=thin,bottom=thin)
ws.append(csv_cols)
for c in range(1,len(csv_cols)+1):
    cell=ws.cell(1,c); cell.fill=hdrfill; cell.font=hdrfont; cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True); cell.border=border
for n,dom,sub,attrs in sorted(repos,key=lambda x:(ORDER.index(x[1]),x[0].lower())):
    lang,gui,fw,eng=tech_flat(n)
    depset={"torch","tensorflow","transformers","ollama","demucs","pydub","vlc","python-vlc","soundfile","sounddevice","librosa","mido","midi","cv2","opencv-python","ffmpeg","Pillow","pygame","pygame-ce","pyglet","numpy","scipy","playwright","requests","beautifulsoup4","bs4","lxml","openpyxl","pycryptodome","pyautogui","electron","react","vite","fastapi","flask","asteval","pandas","cryptography","pymupdf","fitz","pystray"}
    deps=", ".join(d for d in TECH.get(n,{}).get("deps",[]) if d in depset) or "-"
    row=[n,dom,sub,lang,gui,fw,eng,deps,EVID.get(n,"")]+["是" if f in attrs else "否" for f in FLAT_FLAGS]
    ws.append(row)
widths=[22,16,16,16,18,10,14,30,40]+[9]*len(FLAT_FLAGS)
for i,wd in enumerate(widths,1): ws.column_dimensions[get_column_letter(i)].width=wd
ws.freeze_panes="A2"
ws.auto_filter.ref=f"A1:{get_column_letter(len(csv_cols))}{len(repos)+1}"
# Sheet2 矩阵
ws2=wb.create_sheet("矩阵")
ws2.append(["领域 \\ 技术属性"]+COLS+["合计"])
for c in range(1,len(COLS)+3):
    cell=ws2.cell(1,c); cell.fill=hdrfill; cell.font=hdrfont; cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True); cell.border=border
for c in ORDER:
    ws2.append([c]+[mat[c][col] for col in COLS]+[domtot[c]])
ws2.append(["合计"]+[colmax[col] for col in COLS]+[len(repos)])
# 热力上色（每列归一化）
for ci,col in enumerate(COLS,2):
    mx=colmax[col]
    for ri,c in enumerate(ORDER,2):
        v=mat[c][col]
        if v==0: fill=PatternFill("solid",fgColor="F1F3F5")
        else:
            t=v/mx; r=lerp(231,29,t); g=lerp(240,78,t); b=lerp(255,216,t)
            fill=PatternFill("solid",fgColor=f"{r:02X}{g:02X}{b:02X}")
        ws2.cell(ri,ci).fill=fill
        ws2.cell(ri,ci).alignment=Alignment(horizontal="center")
        if v>0 and t>0.5: ws2.cell(ri,ci).font=Font(color="FFFFFF")
ws2.column_dimensions["A"].width=16
for i in range(2,len(COLS)+2): ws2.column_dimensions[get_column_letter(i)].width=11
ws2.column_dimensions[get_column_letter(len(COLS)+2)].width=8
ws2.freeze_panes="B2"
wb.save("repos_master.xlsx")
print("OK -> repos_master_matrix.html / repos_master.csv / repos_master.xlsx | 仓数:",len(repos))
