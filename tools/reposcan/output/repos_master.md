# D:\projects\repos 仓库总表（领域 × 技术栈 · 交叉索引）

> 扫描日期：2026-10-28 ｜ 仓库总数：**133**（已同步删除远端/本地均移除的 `sin-virtue-game`）
> 依据：README + 语言/框架信号 + 10 个边界仓深层源码核实。技术栈列格式：`语言 | 界面/形态 | 架构 | 依赖引擎 | 关键依赖`

## 分类概览

| 大类 | 数量 |
|------|------|
| 游戏引擎/框架 | 12 |
| 游戏作品 | 42 |
| 音乐/音频 | 13 |
| 视频/图像/特效 | 17 |
| 播放器 | 6 |
| 小说/网文 | 7 |
| 跑团/TRPG | 3 |
| AI/大模型 | 3 |
| 爬虫/采集 | 8 |
| 开发者/系统工具 | 17 |
| 多语言引擎移植验证 | 2 |
| 原型/学习/杂项 | 3 |
| **合计** | **133** |

## 主总表（每仓一行，领域 + 技术栈全字段）

| # | 仓库 | 领域 | 子类 | 语言 | 界面/形态 | 架构 | 依赖引擎 | 关键依赖 | 证据（README） |
|---|------|------|------|------|-----------|------|----------|----------|----------------|
| 1 | `3dworld` | 游戏引擎/框架 | 3D 引擎库 | Python | Pyglet | Cordis | 3dworld/procgen | numpy, pyglet | pyglet 三维世界引擎库 (world3d) |
| 2 | `3dworld-demos` | 游戏引擎/框架 | 引擎演示集 | Python | Pyglet·输入模拟 | Cordis | 3dworld | ffmpeg, numpy, pyglet, scipy | 3dworld 引擎 43 个单文件演示 + 演出入口 |
| 3 | `3dworld-globe` | 游戏引擎/框架 | 引擎应用/演示 | Python | CLI/headless | - | 3dworld | ffmpeg, pyglet | 基于 3dworld 的交互地球仪 |
| 4 | `an-engine` | 游戏引擎/框架 | 统一游戏引擎 | Node/JS/Python/TypeScript | Pygame(-ce)·Web服务 | Cordis/ECS | allin_engine | asteval, numpy, ollama, pygame, pygame-ce, react, requests, scipy | 从 100+ 项目提炼的 Python 通用引擎 (ECS/事件总线/TRPG 内核) |
| 5 | `cordis-py` | 游戏引擎/框架 | 场景引擎内核 | Python | Web服务 | Cordis | dse-core | - | dse-core 字典场景引擎 Python 版 |
| 6 | `cordis-snake` | 游戏引擎/框架 | 架构样例 | Node/JS | 输入模拟 | Cordis | - | - | Cordis 『一切皆插件』贪吃蛇样例 |
| 7 | `cordis-table-app` | 游戏引擎/框架 | 应用内核 | Node/JS/TypeScript | Web服务 | Cordis | - | openpyxl, vite | Cordis 内核 + OpenPyXL 表格应用 (JSON-RPC 桥) |
| 8 | `cordis-text-game` | 游戏引擎/框架 | 架构样例 | Node/JS/TypeScript | Web服务 | Cordis | - | - | Cordis 文字冒险引擎示例 |
| 9 | `dict-scene-engine` | 游戏引擎/框架 | 场景引擎 | Node/JS | CLI/headless | Cordis | dse-core | - | Cordis 4.0 文字冒险引擎 (场景即字典/能力即插件) |
| 10 | `dse-core` | 游戏引擎/框架 | 场景引擎内核 | Node/JS | CLI/headless | Cordis | dse-core | - | 字典场景引擎内核 (Node) |
| 11 | `superengine` | 游戏引擎/框架 | 组合引擎仓 | Python | CLI/headless | Cordis | 3dworld/procgen | numpy | cordis 三仓组合流水线 |
| 12 | `worldbuilder` | 游戏引擎/框架 | 程序化生成库 | Python | Pillow | - | procgen | Pillow, numpy | 供游戏 import 复用的 procgen 工具包 |
| 13 | `adventurelog` | 游戏作品 | 挂机 RPG | Python | Pillow·Tkinter | - | - | Pillow, numpy, openpyxl, pystray | tkinter 数据驱动挂机放置 RPG |
| 14 | `arcade` | 游戏作品 | 街机合集 | Python | Tkinter | - | - | - | 街机小游戏合集 (俄罗斯方块等) |
| 15 | `ashen-beacon` | 游戏作品 | 文字冒险 | Python | CLI/headless | Cordis/ECS | allin_engine/dse-core | Pillow, numpy | 终端废土文字冒险 (dse-core + allin-engine) |
| 16 | `backroom` | 游戏作品 | 3D 漫游 | Python | Pyglet | - | 3dworld | pygame, pyglet | Backrooms 伪无限第一人称漫游 (3dworld PBR) |
| 17 | `bee` | 游戏作品 | 挂机 RPG | Python | CLI/headless | - | - | Pillow, numpy, openpyxl, pystray, sounddevice | 蜜蜂挂机 RPG (系统托盘 + 实时音频) |
| 18 | `darksouls` | 游戏作品 | 卡牌 Roguelike | Python | Pygame(-ce)·输入模拟 | - | - | pygame, pygame-ce | 黑暗之魂题材 Roguelike 卡牌 |
| 19 | `diablo` | 游戏作品 | 图形 RPG | Python | Tkinter | Cordis | - | - | 暗黑破坏神风格图形 RPG |
| 20 | `dungeon` | 游戏作品 | 地牢 Roguelike | Python | Pygame(-ce) | - | - | numpy, pygame, pygame-ce, scipy, sounddevice | pygame-ce 地牢 Roguelike (Savage Worlds 骰系) |
| 21 | `dwarf-scrolls` | 游戏作品 | 模拟/冒险 | Python | Pillow·Pygame(-ce)·Tkinter | ECS | allin_engine | asteval, numpy, ollama, pygame, pygame-ce, requests, scipy | 矮人要塞画风 × 上古卷轴世界 |
| 22 | `fish` | 游戏作品 | 桌宠 | Python | Pygame(-ce)·Tkinter | ECS | allin_engine | Pillow, asteval, ffmpeg, numpy, ollama, pygame, pygame-ce, pystray | 桌面养鱼桌宠模拟器 |
| 23 | `god-hand-` | 游戏作品 | 文字冒险/roguelite | Python | Pygame(-ce)·Tkinter | - | - | openpyxl, pygame, pygame-ce | 希腊十二试炼文字冒险 (Tkinter/pygame/控制台) |
| 24 | `happy-childrens-day` | 游戏作品 | 休闲 | Python | Tkinter | ECS | - | numpy, pandas, scipy, sounddevice | 六一零食大闯关无尽模式 |
| 25 | `hell-below` | 游戏作品 | 游戏启动平台 | Python | Tkinter | - | - | - | tkinter 小游戏聚合启动器 |
| 26 | `Idle` | 游戏作品 | 放置/挂机 | Python | Tkinter | Cordis | - | - | tkinter 放置点击 RPG (科技树/装备/转生) |
| 27 | `jotunnslayer` | 游戏作品 | 动作 Roguelite | Python | Pygame(-ce) | - | allin_engine | numpy, pygame, pygame-ce, scipy | JOTUNNSLAYER 复刻原型 (pygame-ce) |
| 28 | `kard` | 游戏作品 | 卡牌动作 | Python | Pygame(-ce)·输入模拟 | ECS | - | openpyxl, pygame, pygame-ce | 类吸血鬼幸存者+杀戮尖塔关键字卡牌 |
| 29 | `legend` | 游戏作品 | 点怪打怪 | Python | Tkinter | ECS | - | openpyxl | 文字传奇点怪就打 (MVP+ECS+MVVM) |
| 30 | `life-reset-simulator` | 游戏作品 | 人生模拟 | Python | Tkinter | - | - | - | 人生重开模拟器 (MBTI+决策树) |
| 31 | `loly` | 游戏作品 | 伪 3D FPS | Python | Pygame(-ce) | - | - | numpy, pygame, pygame-ce, sounddevice | DOOM 风格光线投射游戏 (pygame-ce) |
| 32 | `lonely-desert-road` | 游戏作品 | 驾驶/无尽 | Python | Pyglet·输入模拟 | ECS | 3dworld | ffmpeg, numpy, pygame, pyglet, scipy, sounddevice | ECS 无尽沙漠公路驾驶 (3D 透视) |
| 33 | `maga` | 游戏作品 | 废土 RPG | Python | Pygame(-ce)·Tkinter | - | - | openpyxl, pandas, pygame, pygame-ce | 重装机兵同人赏金猎人 RPG |
| 34 | `magic-tower` | 游戏作品 | 爬塔 Roguelike | Python | Tkinter | Cordis/ECS | procgen | Pillow, openpyxl, pandas, pystray | Tkinter 魔塔 (ECS + 自动挂机 + exe) |
| 35 | `mahjong` | 游戏作品 | 解谜 | Python | Pillow·Pygame(-ce)·Tkinter | ECS | allin_engine | asteval, numpy, ollama, pygame, pygame-ce, requests, scipy | 麻将连连看 (144 张多层堆叠) |
| 36 | `mc-clone` | 游戏作品 | 沙盒合集 | Python | Pygame(-ce)·Tkinter | ECS | allin_engine | asteval, numpy, ollama, pygame, pygame-ce, requests, scipy | MC 风格复刻合集 (文字+2D 侧视) |
| 37 | `mcclone3d` | 游戏作品 | 体素沙盒 | Python | CLI/headless | Cordis/ECS | 3dworld | Pillow, pyglet, torch | MC 风格 3D 体素沙盒 (3dworld) |
| 38 | `mirsolo` | 游戏作品 | ARPG 单机 | Python | Pyglet | ECS | 3dworld/allin_engine/dse-core | ffmpeg, numpy, pyglet, scipy, sounddevice | 热血传奇单机复刻 (三职业 + AI 对手) |
| 39 | `moba_battle_platform` | 游戏作品 | 对战平台 | Python | Tkinter | - | allin_engine | requests | MOBA 1v1 对战平台 |
| 40 | `niulai` | 游戏作品 | 动画复刻 | Python | CLI/headless | ECS | 3dworld/allin_engine | ffmpeg, numpy, pyglet, scipy | 《牛来》双引擎复刻工程 |
| 41 | `pq-multiverse` | 游戏作品 | 自动 RPG | Python | Tkinter | - | - | - | Progress Quest 多元宇宙自动 RPG |
| 42 | `project-root` | 游戏作品 | 模拟器 | Python | Tkinter | - | - | - | 诡秘之主序列途径模拟系统 |
| 43 | `random-dungeon-` | 游戏作品 | 终端地牢 | Python | CLI/headless | Cordis | procgen | numpy | 终端文字地牢探险 (可接超级引擎) |
| 44 | `russia` | 游戏作品 | 轮盘赌 | Python | Pygame(-ce) | ECS | - | pygame, pygame-ce | 俄罗斯轮盘赌 (pygame-ce, ECS) |
| 45 | `sandbox` | 游戏作品 | 地牢冒险 | Python | Tkinter | ECS | allin_engine/procgen | Pillow, numpy, pygame | procgen + alloy 熔接的地牢冒险者 |
| 46 | `sign-in-simulator` | 游戏作品 | 签到/斯金纳箱 | Python | Tkinter | - | - | pandas | tkinter 签到奖励强化演示 |
| 47 | `smile` | 游戏作品 | 签到抽卡 | Python | Pygame(-ce)·Web服务 | - | - | pygame, pygame-ce | pygame 签到抽卡式游戏 |
| 48 | `stay` | 游戏作品 | 进度放置 | Python | CLI/headless | - | - | numpy, react | Progress Quest 2 Python/Tkinter 移植 |
| 49 | `table-hanging-machine` | 游戏作品 | 挂机桌游 | Python | CLI/headless | - | - | openpyxl | Progress Quest v2 风格挂机桌游 |
| 50 | `tavern-rogue` | 游戏作品 | 自走棋 Roguelike | Python | Pygame(-ce) | - | allin_engine | numpy, pygame, pygame-ce, scipy | D&D SRD 酒馆异闻录自走棋 |
| 51 | `text-adventure` | 游戏作品 | 文字解谜 | Node/JS/Python | Pygame(-ce)·Web服务·输入模拟 | Cordis | - | cryptography, playwright, pygame, pygame-ce | 文字冒险解谜 (pygame + 浏览器 + Cordis 宿主) |
| 52 | `text-fps` | 游戏作品 | 战术 FPS | Python | Pygame(-ce) | - | - | pygame, pygame-ce | 文字 FPS 战术战斗 (pygame-ce) |
| 53 | `under-withered-limbs` | 游戏作品 | 卡牌 | Python | Pygame(-ce) | ECS | - | numpy, pygame, pygame-ce, scipy | pygame-ce 卡牌游戏 + 程序化音频 |
| 54 | `yuanbao` | 游戏作品 | 细胞模拟 | Python | CLI/headless | - | - | - | 细胞工厂 (生命游戏 + CNN 卷积核) |
| 55 | `audio-pipeline` | 音乐/音频 | 制作流水线 | Python | CLI/headless | - | - | demucs, mido, numpy, pydub, torch | 纯音乐制作流水线 (拆歌→分轨→混音→重分离) |
| 56 | `audio-separator` | 音乐/音频 | 人声分离 | Python | Tkinter·Web服务 | - | - | demucs, flask, numpy, soundfile, torch | Demucs/BS-RoFormer 人声伴奏分离桌面应用 |
| 57 | `audiotool` | 音乐/音频 | 加工工具 | Python | Tkinter | - | - | ffmpeg, pydub | Tkinter 批量音频/视频加工 |
| 58 | `bloodmusic` | 音乐/音频 | 程序化合成引擎 | Node/JS/Python | Matplotlib·Tkinter | Cordis | allin_engine | demucs, ffmpeg, midi, mido, numpy, pydub, pygame, scipy | 程序化游戏音频合成引擎 |
| 59 | `csmusic` | 音乐/音频 | 资源库 | Python | CLI/headless | - | - | requests | CS 音乐盒 MP3 成品库 + 下载脚本 |
| 60 | `midi` | 音乐/音频 | DAW/MIDI | Python | Pygame(-ce) | - | - | librosa, midi, numpy, pygame-ce, scipy, soundfile | MusicStudio 音乐制作/DAW 项目 |
| 61 | `mp` | 音乐/音频 | 生成+可视化 | Python | Tkinter | - | - | - | 随机音乐生成器 + WMP 风格可视化 |
| 62 | `musickit` | 音乐/音频 | 混音项目 | Python | Tkinter·Web服务 | - | - | fastapi, ffmpeg, flask, midi, numpy, pydub, scipy, soundfile | phonk 混音项目 (真实采样 + 本地混音) |
| 63 | `ncmturnmp3` | 音乐/音频 | 格式转换 | Python | Tkinter | - | - | ffmpeg, numpy, pycryptodome | 加密音乐多格式转换器 (本地离线) |
| 64 | `private-radio-stations` | 音乐/音频 | 转播/电台 | Node/JS | Web服务 | Cordis | - | ffmpeg | 视频转播 + 音频电台 monorepo (npm workspaces) |
| 65 | `radio_special_instruments` | 音乐/音频 | 采样库 | Python | CLI/headless | - | - | - | 特殊乐器采样包库 + 下载脚本 |
| 66 | `remix` | 音乐/音频 | 混音/合成 | Python | Tkinter | - | - | ffmpeg, numpy, pydub | pydub 音频混音 & 视频音频合成 |
| 67 | `wav_music_gen` | 音乐/音频 | 生成器 | Python | Tkinter | - | - | midi, numpy, scipy, torch | 零依赖随机 WAV 音乐生成器 |
| 68 | `art_video_gen` | 视频/图像/特效 | 艺术视频生成 | Python | OpenCV·Tkinter | - | - | Pillow, asteval, cv2, ffmpeg, librosa, numpy, opencv-python, pygame | 元胞自动机 + 粒子系统生成艺术视频 + ffmpeg 合成 |
| 69 | `cellular_automaton` | 视频/图像/特效 | 动态壁纸 | Python | Pygame(-ce)·输入模拟 | - | - | ffmpeg, numpy, pygame, pygame-ce, scipy | 2D 元胞自动机桌面壁纸 (pygame+numpy) |
| 70 | `ddd2` | 视频/图像/特效 | CA 视频 | Python | Pillow·Tkinter | - | - | Pillow, numpy, scipy | 元胞自动机视频生成器 (tkinter) |
| 71 | `drawpic` | 视频/图像/特效 | 故障艺术 | Python | Pillow·Tkinter | - | - | Pillow, ffmpeg, numpy | 21 个故障艺术生成器 (PNG/MP4) |
| 72 | `gan` | 视频/图像/特效 | 视频生成 | Python | OpenCV | - | - | cv2, numpy, opencv-python | 马尔可夫/CA/CNN-RNN-GNN 随机视频生成 |
| 73 | `imgproc` | 视频/图像/特效 | 图像批处理工具 | Python | Pillow·Tkinter | - | - | Pillow | Tkinter 批量图像加工 (缩放/水印/格式转换) |
| 74 | `ling-train` | 视频/图像/特效 | 短视频流水线 | Python | Pillow | - | - | Pillow, ffmpeg | 《火车进站》短视频自动化制作流水线 (三代) |
| 75 | `math` | 视频/图像/特效 | CA 公式实验 | Python | Pygame(-ce)·Tkinter | - | - | numpy, pygame, pygame-ce | Cellular Automata Formula Lab |
| 76 | `mathematical-formula-renderer` | 视频/图像/特效 | CA 渲染引擎 | Python | Pygame(-ce)·Web服务 | - | - | asteval, numpy, pygame, scipy | CA Render Engine (pygame) |
| 77 | `media-tools` | 视频/图像/特效 | 媒体工具集 | Python | Pillow·Tkinter | - | - | numpy, pystray | 5 个视觉/图像/壁纸工具 (光栅化/PNG/风扇仿真/壁纸) |
| 78 | `particlefx` | 视频/图像/特效 | 粒子系统 | Python | Pillow·Pygame(-ce) | - | - | Pillow, ffmpeg, numpy, pydub, pygame, pygame-ce | 独立粒子系统库 (NumPy/pygame) |
| 79 | `photovideo` | 视频/图像/特效 | 图转视频 | Python | OpenCV·Pillow·Tkinter | - | - | Pillow, cv2, ffmpeg, numpy, opencv-python | 图片转视频生成器 (6 种动效) |
| 80 | `procedural-video` | 视频/图像/特效 | 过程生成视频 | Python | Pygame(-ce)·Tkinter | - | - | pygame, pygame-ce | kkrieger 风格过程生成视频 |
| 81 | `pywallpaper` | 视频/图像/特效 | 动态壁纸 | Python | Pillow·Pygame(-ce)·Tkinter·Web服务 | Cordis/ECS | allin_engine | Pillow, asteval, numpy, pygame, pygame-ce, pystray | 数学公式 + CA 驱动动态壁纸引擎 (ECS) |
| 82 | `shikonghuaban` | 视频/图像/特效 | 音频可视化 | Python | Pygame(-ce) | - | - | numpy, pygame, pygame-ce, sounddevice | 黑洞/Penrose 全屏音频可视化引擎 |
| 83 | `video-generator` | 视频/图像/特效 | 随机视频 | Python | Pillow·Tkinter | Cordis | - | asteval, demucs, ffmpeg, librosa, midi, numpy, playwright, pydub | 整合 9685 个效果预设的随机视频生成器 |
| 84 | `wave4` | 视频/图像/特效 | 噪声/分析 | Python | Matplotlib | - | - | numpy, scipy | 布朗噪声/fBm 生成与 Hurst/PSD 分析工具包 |
| 85 | `daily_player` | 播放器 | 视频播放器 | Python | Pillow·Tkinter·VLC | - | - | Pillow, pystray, vlc | 基于 VLC 的日常视频播放器 (字幕/播放列表) |
| 86 | `localplayer` | 播放器 | 浏览器扩展 | Python | MV3扩展·Web服务 | ECS | - | flask | 本地媒体轻量播放器 (Chrome/Edge MV3) |
| 87 | `music-player` | 播放器 | 音乐播放器 | Node/JS/Python | Tkinter·VLC | Cordis | - | Pillow, librosa, numpy, python-vlc, scipy, vlc | Python + VLC 音乐播放器 |
| 88 | `player` | 播放器 | 音频可视化 | Python | Tkinter | - | - | - | 模拟 WMP 音频可视化效果程序 |
| 89 | `players-unified` | 播放器 | 整合仓 | Node/JS/Python | MV3扩展·Tkinter·VLC·Web服务 | Cordis | - | flask, pystray, python-vlc, vlc | 三端本地播放器整合 (Python+VLC / MV3 / Cordis Web) |
| 90 | `pluginplayer` | 播放器 | 插件播放器 | Node/JS | CLI/headless | Cordis | - | ffmpeg | FFmpeg 9 + SDL3 内核 + 一切皆插件 (C ABI + Cordis JS) |
| 91 | `novel` | 小说/网文 | 小说生成器 | Python | Web服务 | - | - | flask | 《万界归墟》双引擎程序化中文小说生成 |
| 92 | `novel-down` | 小说/网文 | 离线阅读/爬虫 | Python | 输入模拟 | - | - | beautifulsoup4, bs4, cryptography, lxml, numpy, playwright, pygame, requests | 规则驱动网络小说离线阅读 (免费章节) |
| 93 | `novel-generator` | 小说/网文 | 小说生成器 | Python | CLI/headless | - | - | - | novel_generator 通用小说生成库 |
| 94 | `novel-reader` | 小说/网文 | 视觉小说 | Python | CLI/headless | - | - | - | 基于同名小说改编 Tkinter 视觉小说游戏 (3.2 万页) |
| 95 | `novel-run` | 小说/网文 | 集成验证 | Node/JS | CLI/headless | - | dse-core | - | novel 结构化输出 + DSE 运行时的独立验证 |
| 96 | `weor` | 小说/网文 | AI 小说系统 | Python | Tkinter | - | - | numpy, ollama, requests | 整合多开源范式的 AI 小说生成系统 |
| 97 | `write` | 小说/网文 | 创作工作区 | Node/JS | CLI/headless | Cordis | - | - | 网文正文/设定/素材工作区 (多为文本，无构建) |
| 98 | `d20-table-link` | 跑团/TRPG | 联动适配器 | Node/JS | CLI/headless | Cordis | allin_engine | openpyxl | allin_engine TRPG × cordis-table-app 适配器 |
| 99 | `roleplayer` | 跑团/TRPG | 跑团模拟器 | Node/JS/Python | Tkinter·Web服务 | Cordis | - | react, vite | D&D/GURPS/CoC 融合跑团模拟器 (v3) |
| 100 | `running-group-simulator` | 跑团/TRPG | TRPG 中间件 | Python | CLI/headless | - | allin_engine | openpyxl | Mirror of the Lost 终端驱动 TRPG 中间件引擎 |
| 101 | `music-prompt-generator` | AI/大模型 | AI 音乐提示词 | Python | Tkinter | - | - | - | 纯音乐风格提示词生成器 (Suno/Udio，无模型调用) |
| 102 | `ollama_generator` | AI/大模型 | 文本生成库 | Python | CLI/headless | - | - | ollama, requests | 基于 Ollama 的通用 AI 文本生成库 |
| 103 | `peasy-ai` | AI/大模型 | AI 框架 | Python | CLI/headless | - | - | numpy | 零硬编码配置驱动通用 AI 对话框架 + 叙事引擎 |
| 104 | `bilibili-helper-py` | 爬虫/采集 | 视频下载 | Python | Tkinter | - | - | playwright, requests | B站视频下载桌面版 (Playwright) |
| 105 | `crawl-hub` | 爬虫/采集 | 爬虫启动器 | Python | CLI/headless | Cordis | - | playwright, requests | webcopier/sfx/font/bilibili/image 统一启动器 |
| 106 | `hushi_twrj` | 爬虫/采集 | 文档存档 | Python | CLI/headless | - | - | - | 胡适日记本地存档爬虫 (虚阁网) |
| 107 | `image-scraper` | 爬虫/采集 | 图片爬虫 | Python | CLI/headless | Cordis | 3dworld | playwright | 多源图片爬虫 (30 源, 断点续传) |
| 108 | `midjourney_video` | 爬虫/采集 | 视频下载 | Python | Tkinter | - | - | ffmpeg, playwright | Midjourney Explore 视频下载 (Playwright) |
| 109 | `photo` | 爬虫/采集 | 图片爬虫 | Python | Pillow·Tkinter | - | - | Pillow, beautifulsoup4, bs4, requests | Tkinter 网页图片解析下载工具 |
| 110 | `sfx-download` | 爬虫/采集 | 音频爬取 | Python | Pygame(-ce)·Tkinter | Cordis | - | Pillow, playwright, pydub, pygame, pygame-ce, pystray, requests | 通用免费公版音频爬取程序 |
| 111 | `webcopier` | 爬虫/采集 | 网页抓取 | Python | Tkinter | Cordis | - | Pillow, beautifulsoup4, bs4, lxml, playwright, requests | 网页正文抓取 v5.3 (反爬系统) |
| 112 | `auto_clicker` | 开发者/系统工具 | 鼠标连点器 | Python | Tkinter | - | - | pyautogui | Python GUI 鼠标连点器 (模块化) |
| 113 | `board-replay` | 开发者/系统工具 | 棋谱复盘工具 | Node/JS | CLI/headless | Cordis | - | Pillow, ffmpeg | Cordis 围棋SGF+国象UCI 本地复盘器 (Web UI+PNG出图) |
| 114 | `calculator` | 开发者/系统工具 | 计算器 | Python | Tkinter | - | - | - | Calculator ∞ Alchemia 解密终端 (tkinter) |
| 115 | `captcha-demo` | 开发者/系统工具 | 验证码演示 | Python | Tkinter | - | - | - | 6 类验证码识别交互 (MVVM) |
| 116 | `fonts` | 开发者/系统工具 | 字体工具 | Python | Tkinter | - | - | beautifulsoup4, requests | 中文字体资源库 + 浏览/复制工具 |
| 117 | `foolproof-operation` | 开发者/系统工具 | 依赖安装器 | Python | Tkinter | Cordis | - | - | 图形化 Python 依赖库管理 (761 库) |
| 118 | `markdown` | 开发者/系统工具 | MD 查看器 | Node/JS/Python/TypeScript | Web服务 | Cordis | - | Pillow, requests, vite | Cordis 驱动的本地 Markdown 查看器 |
| 119 | `pdf` | 开发者/系统工具 | PDF 阅读器 | Python | Pillow·Tkinter | - | - | Pillow, fitz, pymupdf | PyMuPDF + Pillow Tkinter PDF 阅读器 |
| 120 | `pomodmer` | 开发者/系统工具 | 番茄钟 | Node/JS/TypeScript | Web服务 | Cordis | - | electron, openpyxl, vite | Cordis + 本地 Web UI 番茄钟 |
| 121 | `print` | 开发者/系统工具 | 输入法 | Python | Tkinter | - | - | beautifulsoup4, pandas, requests | 中文拼音输入法 (tkinter + 全局键盘监听) |
| 122 | `py_test_runner` | 开发者/系统工具 | 测试框架 | Python | Pygame(-ce)·Tkinter | ECS | - | numpy, pygame, pygame-ce | Python 项目全覆盖测试框架 |
| 123 | `pyinstaller` | 开发者/系统工具 | 打包工具 | Python | Tkinter | - | - | Pillow | PyInstaller 批量打包工具箱 |
| 124 | `renamer` | 开发者/系统工具 | 批量重命名 | Python | Tkinter | - | - | - | 正则批量重命名工具 (Tkinter) |
| 125 | `santi-teleprompter` | 开发者/系统工具 | 提词器 | Node/JS | Web服务 | Cordis | - | electron | 三题故事提词器 |
| 126 | `subtitle` | 开发者/系统工具 | 字幕工具 | Python | Tkinter | - | - | Pillow, ffmpeg, numpy | Tkinter + ffmpeg 字幕提取/编辑/烧录 |
| 127 | `yasuo` | 开发者/系统工具 | 加密/压缩 | Python | Tkinter | - | - | - | 文件加密与无损压缩工具 (pycryptodome) |
| 128 | `zhuangtaiji` | 开发者/系统工具 | 决策引擎 | Python | Tkinter | Cordis | - | react | 多范式决策引擎 + Tkinter/React 工作台 |
| 129 | `lab` | 多语言引擎移植验证 | 国际象棋 | Node/JS/TypeScript | Web服务 | Cordis | - | requests, vite | 10 语言国际象棋引擎功能对等实现 + perft 验证 |
| 130 | `weiqi_lab` | 多语言引擎移植验证 | 围棋 | Python | CLI/headless | - | - | numpy, tensorflow, torch | 6 语言围棋引擎功能对等实现 (MCTS-UCT+RAVE) |
| 131 | `haha` | 原型/学习/杂项 | MVC/多语言演示 | Node/JS/Python | Tkinter | Cordis | - | - | tkinter MVC 演示 + 76 语言 HelloWorld + Cordis 热插拔 |
| 132 | `sin-virtue-cordis-host` | 原型/学习/杂项 | 架构验证 | Node/JS | Web服务 | Cordis | - | - | 七宗罪×七美德 Cordis 宿主验证原型 |
| 133 | `test` | 原型/学习/杂项 | 人格测试 | Node/JS | CLI/headless | - | - | - | 荣格八功能 + 45 原型每日人格测试网页 |

## 领域维度分组

### 游戏引擎/框架（12）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `3dworld` | 3D 引擎库 | Python | Pyglet | +Cordis | ▸3dworld/procgen |
| `3dworld-demos` | 引擎演示集 | Python | Pyglet·输入模拟 | +Cordis | ▸3dworld |
| `3dworld-globe` | 引擎应用/演示 | Python | CLI/headless | ▸3dworld |
| `an-engine` | 统一游戏引擎 | Node/JS/Python/TypeScript | Pygame(-ce)·Web服务 | +Cordis/ECS | ▸allin_engine |
| `cordis-py` | 场景引擎内核 | Python | Web服务 | +Cordis | ▸dse-core |
| `cordis-snake` | 架构样例 | Node/JS | 输入模拟 | +Cordis |
| `cordis-table-app` | 应用内核 | Node/JS/TypeScript | Web服务 | +Cordis |
| `cordis-text-game` | 架构样例 | Node/JS/TypeScript | Web服务 | +Cordis |
| `dict-scene-engine` | 场景引擎 | Node/JS | CLI/headless | +Cordis | ▸dse-core |
| `dse-core` | 场景引擎内核 | Node/JS | CLI/headless | +Cordis | ▸dse-core |
| `superengine` | 组合引擎仓 | Python | CLI/headless | +Cordis | ▸3dworld/procgen |
| `worldbuilder` | 程序化生成库 | Python | Pillow | ▸procgen |

### 游戏作品（42）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `adventurelog` | 挂机 RPG | Python | Pillow·Tkinter |
| `arcade` | 街机合集 | Python | Tkinter |
| `ashen-beacon` | 文字冒险 | Python | CLI/headless | +Cordis/ECS | ▸allin_engine/dse-core |
| `backroom` | 3D 漫游 | Python | Pyglet | ▸3dworld |
| `bee` | 挂机 RPG | Python | CLI/headless |
| `darksouls` | 卡牌 Roguelike | Python | Pygame(-ce)·输入模拟 |
| `diablo` | 图形 RPG | Python | Tkinter | +Cordis |
| `dungeon` | 地牢 Roguelike | Python | Pygame(-ce) |
| `dwarf-scrolls` | 模拟/冒险 | Python | Pillow·Pygame(-ce)·Tkinter | +ECS | ▸allin_engine |
| `fish` | 桌宠 | Python | Pygame(-ce)·Tkinter | +ECS | ▸allin_engine |
| `god-hand-` | 文字冒险/roguelite | Python | Pygame(-ce)·Tkinter |
| `happy-childrens-day` | 休闲 | Python | Tkinter | +ECS |
| `hell-below` | 游戏启动平台 | Python | Tkinter |
| `Idle` | 放置/挂机 | Python | Tkinter | +Cordis |
| `jotunnslayer` | 动作 Roguelite | Python | Pygame(-ce) | ▸allin_engine |
| `kard` | 卡牌动作 | Python | Pygame(-ce)·输入模拟 | +ECS |
| `legend` | 点怪打怪 | Python | Tkinter | +ECS |
| `life-reset-simulator` | 人生模拟 | Python | Tkinter |
| `loly` | 伪 3D FPS | Python | Pygame(-ce) |
| `lonely-desert-road` | 驾驶/无尽 | Python | Pyglet·输入模拟 | +ECS | ▸3dworld |
| `maga` | 废土 RPG | Python | Pygame(-ce)·Tkinter |
| `magic-tower` | 爬塔 Roguelike | Python | Tkinter | +Cordis/ECS | ▸procgen |
| `mahjong` | 解谜 | Python | Pillow·Pygame(-ce)·Tkinter | +ECS | ▸allin_engine |
| `mc-clone` | 沙盒合集 | Python | Pygame(-ce)·Tkinter | +ECS | ▸allin_engine |
| `mcclone3d` | 体素沙盒 | Python | CLI/headless | +Cordis/ECS | ▸3dworld |
| `mirsolo` | ARPG 单机 | Python | Pyglet | +ECS | ▸3dworld/allin_engine/dse-core |
| `moba_battle_platform` | 对战平台 | Python | Tkinter | ▸allin_engine |
| `niulai` | 动画复刻 | Python | CLI/headless | +ECS | ▸3dworld/allin_engine |
| `pq-multiverse` | 自动 RPG | Python | Tkinter |
| `project-root` | 模拟器 | Python | Tkinter |
| `random-dungeon-` | 终端地牢 | Python | CLI/headless | +Cordis | ▸procgen |
| `russia` | 轮盘赌 | Python | Pygame(-ce) | +ECS |
| `sandbox` | 地牢冒险 | Python | Tkinter | +ECS | ▸allin_engine/procgen |
| `sign-in-simulator` | 签到/斯金纳箱 | Python | Tkinter |
| `smile` | 签到抽卡 | Python | Pygame(-ce)·Web服务 |
| `stay` | 进度放置 | Python | CLI/headless |
| `table-hanging-machine` | 挂机桌游 | Python | CLI/headless |
| `tavern-rogue` | 自走棋 Roguelike | Python | Pygame(-ce) | ▸allin_engine |
| `text-adventure` | 文字解谜 | Node/JS/Python | Pygame(-ce)·Web服务·输入模拟 | +Cordis |
| `text-fps` | 战术 FPS | Python | Pygame(-ce) |
| `under-withered-limbs` | 卡牌 | Python | Pygame(-ce) | +ECS |
| `yuanbao` | 细胞模拟 | Python | CLI/headless |

### 音乐/音频（13）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `audio-pipeline` | 制作流水线 | Python | CLI/headless |
| `audio-separator` | 人声分离 | Python | Tkinter·Web服务 |
| `audiotool` | 加工工具 | Python | Tkinter |
| `bloodmusic` | 程序化合成引擎 | Node/JS/Python | Matplotlib·Tkinter | +Cordis | ▸allin_engine |
| `csmusic` | 资源库 | Python | CLI/headless |
| `midi` | DAW/MIDI | Python | Pygame(-ce) |
| `mp` | 生成+可视化 | Python | Tkinter |
| `musickit` | 混音项目 | Python | Tkinter·Web服务 |
| `ncmturnmp3` | 格式转换 | Python | Tkinter |
| `private-radio-stations` | 转播/电台 | Node/JS | Web服务 | +Cordis |
| `radio_special_instruments` | 采样库 | Python | CLI/headless |
| `remix` | 混音/合成 | Python | Tkinter |
| `wav_music_gen` | 生成器 | Python | Tkinter |

### 视频/图像/特效（17）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `art_video_gen` | 艺术视频生成 | Python | OpenCV·Tkinter |
| `cellular_automaton` | 动态壁纸 | Python | Pygame(-ce)·输入模拟 |
| `ddd2` | CA 视频 | Python | Pillow·Tkinter |
| `drawpic` | 故障艺术 | Python | Pillow·Tkinter |
| `gan` | 视频生成 | Python | OpenCV |
| `imgproc` | 图像批处理工具 | Python | Pillow·Tkinter |
| `ling-train` | 短视频流水线 | Python | Pillow |
| `math` | CA 公式实验 | Python | Pygame(-ce)·Tkinter |
| `mathematical-formula-renderer` | CA 渲染引擎 | Python | Pygame(-ce)·Web服务 |
| `media-tools` | 媒体工具集 | Python | Pillow·Tkinter |
| `particlefx` | 粒子系统 | Python | Pillow·Pygame(-ce) |
| `photovideo` | 图转视频 | Python | OpenCV·Pillow·Tkinter |
| `procedural-video` | 过程生成视频 | Python | Pygame(-ce)·Tkinter |
| `pywallpaper` | 动态壁纸 | Python | Pillow·Pygame(-ce)·Tkinter·Web服务 | +Cordis/ECS | ▸allin_engine |
| `shikonghuaban` | 音频可视化 | Python | Pygame(-ce) |
| `video-generator` | 随机视频 | Python | Pillow·Tkinter | +Cordis |
| `wave4` | 噪声/分析 | Python | Matplotlib |

### 播放器（6）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `daily_player` | 视频播放器 | Python | Pillow·Tkinter·VLC |
| `localplayer` | 浏览器扩展 | Python | MV3扩展·Web服务 | +ECS |
| `music-player` | 音乐播放器 | Node/JS/Python | Tkinter·VLC | +Cordis |
| `player` | 音频可视化 | Python | Tkinter |
| `players-unified` | 整合仓 | Node/JS/Python | MV3扩展·Tkinter·VLC·Web服务 | +Cordis |
| `pluginplayer` | 插件播放器 | Node/JS | CLI/headless | +Cordis |

### 小说/网文（7）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `novel` | 小说生成器 | Python | Web服务 |
| `novel-down` | 离线阅读/爬虫 | Python | 输入模拟 |
| `novel-generator` | 小说生成器 | Python | CLI/headless |
| `novel-reader` | 视觉小说 | Python | CLI/headless |
| `novel-run` | 集成验证 | Node/JS | CLI/headless | ▸dse-core |
| `weor` | AI 小说系统 | Python | Tkinter |
| `write` | 创作工作区 | Node/JS | CLI/headless | +Cordis |

### 跑团/TRPG（3）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `d20-table-link` | 联动适配器 | Node/JS | CLI/headless | +Cordis | ▸allin_engine |
| `roleplayer` | 跑团模拟器 | Node/JS/Python | Tkinter·Web服务 | +Cordis |
| `running-group-simulator` | TRPG 中间件 | Python | CLI/headless | ▸allin_engine |

### AI/大模型（3）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `music-prompt-generator` | AI 音乐提示词 | Python | Tkinter |
| `ollama_generator` | 文本生成库 | Python | CLI/headless |
| `peasy-ai` | AI 框架 | Python | CLI/headless |

### 爬虫/采集（8）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `bilibili-helper-py` | 视频下载 | Python | Tkinter |
| `crawl-hub` | 爬虫启动器 | Python | CLI/headless | +Cordis |
| `hushi_twrj` | 文档存档 | Python | CLI/headless |
| `image-scraper` | 图片爬虫 | Python | CLI/headless | +Cordis | ▸3dworld |
| `midjourney_video` | 视频下载 | Python | Tkinter |
| `photo` | 图片爬虫 | Python | Pillow·Tkinter |
| `sfx-download` | 音频爬取 | Python | Pygame(-ce)·Tkinter | +Cordis |
| `webcopier` | 网页抓取 | Python | Tkinter | +Cordis |

### 开发者/系统工具（17）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `auto_clicker` | 鼠标连点器 | Python | Tkinter |
| `board-replay` | 棋谱复盘工具 | Node/JS | CLI/headless | +Cordis |
| `calculator` | 计算器 | Python | Tkinter |
| `captcha-demo` | 验证码演示 | Python | Tkinter |
| `fonts` | 字体工具 | Python | Tkinter |
| `foolproof-operation` | 依赖安装器 | Python | Tkinter | +Cordis |
| `markdown` | MD 查看器 | Node/JS/Python/TypeScript | Web服务 | +Cordis |
| `pdf` | PDF 阅读器 | Python | Pillow·Tkinter |
| `pomodmer` | 番茄钟 | Node/JS/TypeScript | Web服务 | +Cordis |
| `print` | 输入法 | Python | Tkinter |
| `py_test_runner` | 测试框架 | Python | Pygame(-ce)·Tkinter | +ECS |
| `pyinstaller` | 打包工具 | Python | Tkinter |
| `renamer` | 批量重命名 | Python | Tkinter |
| `santi-teleprompter` | 提词器 | Node/JS | Web服务 | +Cordis |
| `subtitle` | 字幕工具 | Python | Tkinter |
| `yasuo` | 加密/压缩 | Python | Tkinter |
| `zhuangtaiji` | 决策引擎 | Python | Tkinter | +Cordis |

### 多语言引擎移植验证（2）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `lab` | 国际象棋 | Node/JS/TypeScript | Web服务 | +Cordis |
| `weiqi_lab` | 围棋 | Python | CLI/headless |

### 原型/学习/杂项（3）

| 仓库 | 子类 | 技术栈 |
|------|------|--------|
| `haha` | MVC/多语言演示 | Node/JS/Python | Tkinter | +Cordis |
| `sin-virtue-cordis-host` | 架构验证 | Node/JS | Web服务 | +Cordis |
| `test` | 人格测试 | Node/JS | CLI/headless |

## 技术栈维度分组（标签后附领域，实现交叉索引）

### 2a. 按语言

**Node/JS（12）**：`board-replay`(工具)、`cordis-snake`(引擎)、`d20-table-link`(跑团)、`dict-scene-engine`(引擎)、`dse-core`(引擎)、`novel-run`(小说)、`pluginplayer`(播放)、`private-radio-stations`(音乐)、`santi-teleprompter`(工具)、`sin-virtue-cordis-host`(原型)、`test`(原型)、`write`(小说)
**Python（109）**：`3dworld-demos`(引擎)、`3dworld-globe`(引擎)、`3dworld`(引擎)、`Idle`(游戏)、`adventurelog`(游戏)、`arcade`(游戏)、`art_video_gen`(视效)、`ashen-beacon`(游戏)、`audio-pipeline`(音乐)、`audio-separator`(音乐)、`audiotool`(音乐)、`auto_clicker`(工具)、`backroom`(游戏)、`bee`(游戏)、`bilibili-helper-py`(爬虫)、`calculator`(工具)、`captcha-demo`(工具)、`cellular_automaton`(视效)、`cordis-py`(引擎)、`crawl-hub`(爬虫)、`csmusic`(音乐)、`daily_player`(播放)、`darksouls`(游戏)、`ddd2`(视效)、`diablo`(游戏)、`drawpic`(视效)、`dungeon`(游戏)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`fonts`(工具)、`foolproof-operation`(工具)、`gan`(视效)、`god-hand-`(游戏)、`happy-childrens-day`(游戏)、`hell-below`(游戏)、`hushi_twrj`(爬虫)、`image-scraper`(爬虫)、`imgproc`(视效)、`jotunnslayer`(游戏)、`kard`(游戏)、`legend`(游戏)、`life-reset-simulator`(游戏)、`ling-train`(视效)、`localplayer`(播放)、`loly`(游戏)、`lonely-desert-road`(游戏)、`maga`(游戏)、`magic-tower`(游戏)、`mahjong`(游戏)、`math`(视效)、`mathematical-formula-renderer`(视效)、`mc-clone`(游戏)、`mcclone3d`(游戏)、`media-tools`(视效)、`midi`(音乐)、`midjourney_video`(爬虫)、`mirsolo`(游戏)、`moba_battle_platform`(游戏)、`mp`(音乐)、`music-prompt-generator`(AI)、`musickit`(音乐)、`ncmturnmp3`(音乐)、`niulai`(游戏)、`novel-down`(小说)、`novel-generator`(小说)、`novel-reader`(小说)、`novel`(小说)、`ollama_generator`(AI)、`particlefx`(视效)、`pdf`(工具)、`peasy-ai`(AI)、`photo`(爬虫)、`photovideo`(视效)、`player`(播放)、`pq-multiverse`(游戏)、`print`(工具)、`procedural-video`(视效)、`project-root`(游戏)、`py_test_runner`(工具)、`pyinstaller`(工具)、`pywallpaper`(视效)、`radio_special_instruments`(音乐)、`random-dungeon-`(游戏)、`remix`(音乐)、`renamer`(工具)、`running-group-simulator`(跑团)、`russia`(游戏)、`sandbox`(游戏)、`sfx-download`(爬虫)、`shikonghuaban`(视效)、`sign-in-simulator`(游戏)、`smile`(游戏)、`stay`(游戏)、`subtitle`(工具)、`superengine`(引擎)、`table-hanging-machine`(游戏)、`tavern-rogue`(游戏)、`text-fps`(游戏)、`under-withered-limbs`(游戏)、`video-generator`(视效)、`wav_music_gen`(音乐)、`wave4`(视效)、`webcopier`(爬虫)、`weiqi_lab`(验证)、`weor`(小说)、`worldbuilder`(引擎)、`yasuo`(工具)、`yuanbao`(游戏)、`zhuangtaiji`(工具)
**TypeScript 为主（4）**：`cordis-table-app`(引擎)、`cordis-text-game`(引擎)、`lab`(验证)、`pomodmer`(工具)
**多语言(Python+Node)（8）**：`an-engine`(引擎)、`bloodmusic`(音乐)、`haha`(原型)、`markdown`(工具)、`music-player`(播放)、`players-unified`(播放)、`roleplayer`(跑团)、`text-adventure`(游戏)

### 2b. 按 GUI / 运行时形态

**CLI/headless（30）**：`3dworld-globe`(引擎)、`ashen-beacon`(游戏)、`audio-pipeline`(音乐)、`bee`(游戏)、`board-replay`(工具)、`crawl-hub`(爬虫)、`csmusic`(音乐)、`d20-table-link`(跑团)、`dict-scene-engine`(引擎)、`dse-core`(引擎)、`hushi_twrj`(爬虫)、`image-scraper`(爬虫)、`mcclone3d`(游戏)、`niulai`(游戏)、`novel-generator`(小说)、`novel-reader`(小说)、`novel-run`(小说)、`ollama_generator`(AI)、`peasy-ai`(AI)、`pluginplayer`(播放)、`radio_special_instruments`(音乐)、`random-dungeon-`(游戏)、`running-group-simulator`(跑团)、`stay`(游戏)、`superengine`(引擎)、`table-hanging-machine`(游戏)、`test`(原型)、`weiqi_lab`(验证)、`write`(小说)、`yuanbao`(游戏)
**Matplotlib（2）**：`bloodmusic`(音乐)、`wave4`(视效)
**MV3扩展（2）**：`localplayer`(播放)、`players-unified`(播放)
**OpenCV（3）**：`art_video_gen`(视效)、`gan`(视效)、`photovideo`(视效)
**Pillow（16）**：`adventurelog`(游戏)、`daily_player`(播放)、`ddd2`(视效)、`drawpic`(视效)、`dwarf-scrolls`(游戏)、`imgproc`(视效)、`ling-train`(视效)、`mahjong`(游戏)、`media-tools`(视效)、`particlefx`(视效)、`pdf`(工具)、`photo`(爬虫)、`photovideo`(视效)、`pywallpaper`(视效)、`video-generator`(视效)、`worldbuilder`(引擎)
**Pygame(-ce)（28）**：`an-engine`(引擎)、`cellular_automaton`(视效)、`darksouls`(游戏)、`dungeon`(游戏)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`god-hand-`(游戏)、`jotunnslayer`(游戏)、`kard`(游戏)、`loly`(游戏)、`maga`(游戏)、`mahjong`(游戏)、`math`(视效)、`mathematical-formula-renderer`(视效)、`mc-clone`(游戏)、`midi`(音乐)、`particlefx`(视效)、`procedural-video`(视效)、`py_test_runner`(工具)、`pywallpaper`(视效)、`russia`(游戏)、`sfx-download`(爬虫)、`shikonghuaban`(视效)、`smile`(游戏)、`tavern-rogue`(游戏)、`text-adventure`(游戏)、`text-fps`(游戏)、`under-withered-limbs`(游戏)
**Pyglet（5）**：`3dworld-demos`(引擎)、`3dworld`(引擎)、`backroom`(游戏)、`lonely-desert-road`(游戏)、`mirsolo`(游戏)
**Tkinter（64）**：`Idle`(游戏)、`adventurelog`(游戏)、`arcade`(游戏)、`art_video_gen`(视效)、`audio-separator`(音乐)、`audiotool`(音乐)、`auto_clicker`(工具)、`bilibili-helper-py`(爬虫)、`bloodmusic`(音乐)、`calculator`(工具)、`captcha-demo`(工具)、`daily_player`(播放)、`ddd2`(视效)、`diablo`(游戏)、`drawpic`(视效)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`fonts`(工具)、`foolproof-operation`(工具)、`god-hand-`(游戏)、`haha`(原型)、`happy-childrens-day`(游戏)、`hell-below`(游戏)、`imgproc`(视效)、`legend`(游戏)、`life-reset-simulator`(游戏)、`maga`(游戏)、`magic-tower`(游戏)、`mahjong`(游戏)、`math`(视效)、`mc-clone`(游戏)、`media-tools`(视效)、`midjourney_video`(爬虫)、`moba_battle_platform`(游戏)、`mp`(音乐)、`music-player`(播放)、`music-prompt-generator`(AI)、`musickit`(音乐)、`ncmturnmp3`(音乐)、`pdf`(工具)、`photo`(爬虫)、`photovideo`(视效)、`player`(播放)、`players-unified`(播放)、`pq-multiverse`(游戏)、`print`(工具)、`procedural-video`(视效)、`project-root`(游戏)、`py_test_runner`(工具)、`pyinstaller`(工具)、`pywallpaper`(视效)、`remix`(音乐)、`renamer`(工具)、`roleplayer`(跑团)、`sandbox`(游戏)、`sfx-download`(爬虫)、`sign-in-simulator`(游戏)、`subtitle`(工具)、`video-generator`(视效)、`wav_music_gen`(音乐)、`webcopier`(爬虫)、`weor`(小说)、`yasuo`(工具)、`zhuangtaiji`(工具)
**VLC（3）**：`daily_player`(播放)、`music-player`(播放)、`players-unified`(播放)
**Web服务（20）**：`an-engine`(引擎)、`audio-separator`(音乐)、`cordis-py`(引擎)、`cordis-table-app`(引擎)、`cordis-text-game`(引擎)、`lab`(验证)、`localplayer`(播放)、`markdown`(工具)、`mathematical-formula-renderer`(视效)、`musickit`(音乐)、`novel`(小说)、`players-unified`(播放)、`pomodmer`(工具)、`private-radio-stations`(音乐)、`pywallpaper`(视效)、`roleplayer`(跑团)、`santi-teleprompter`(工具)、`sin-virtue-cordis-host`(原型)、`smile`(游戏)、`text-adventure`(游戏)
**输入模拟（8）**：`3dworld-demos`(引擎)、`cellular_automaton`(视效)、`cordis-snake`(引擎)、`darksouls`(游戏)、`kard`(游戏)、`lonely-desert-road`(游戏)、`novel-down`(小说)、`text-adventure`(游戏)

### 2c. 按架构 / 框架

**Cordis 驱动（40）**：`3dworld-demos`(引擎)、`3dworld`(引擎)、`Idle`(游戏)、`an-engine`(引擎)、`ashen-beacon`(游戏)、`bloodmusic`(音乐)、`board-replay`(工具)、`cordis-py`(引擎)、`cordis-snake`(引擎)、`cordis-table-app`(引擎)、`cordis-text-game`(引擎)、`crawl-hub`(爬虫)、`d20-table-link`(跑团)、`diablo`(游戏)、`dict-scene-engine`(引擎)、`dse-core`(引擎)、`foolproof-operation`(工具)、`haha`(原型)、`image-scraper`(爬虫)、`lab`(验证)、`magic-tower`(游戏)、`markdown`(工具)、`mcclone3d`(游戏)、`music-player`(播放)、`players-unified`(播放)、`pluginplayer`(播放)、`pomodmer`(工具)、`private-radio-stations`(音乐)、`pywallpaper`(视效)、`random-dungeon-`(游戏)、`roleplayer`(跑团)、`santi-teleprompter`(工具)、`sfx-download`(爬虫)、`sin-virtue-cordis-host`(原型)、`superengine`(引擎)、`text-adventure`(游戏)、`video-generator`(视效)、`webcopier`(爬虫)、`write`(小说)、`zhuangtaiji`(工具)
**ECS 架构（20）**：`an-engine`(引擎)、`ashen-beacon`(游戏)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`happy-childrens-day`(游戏)、`kard`(游戏)、`legend`(游戏)、`localplayer`(播放)、`lonely-desert-road`(游戏)、`magic-tower`(游戏)、`mahjong`(游戏)、`mc-clone`(游戏)、`mcclone3d`(游戏)、`mirsolo`(游戏)、`niulai`(游戏)、`py_test_runner`(工具)、`pywallpaper`(视效)、`russia`(游戏)、`sandbox`(游戏)、`under-withered-limbs`(游戏)
**依赖引擎:3dworld（10）**：`3dworld-demos`(引擎)、`3dworld-globe`(引擎)、`3dworld`(引擎)、`backroom`(游戏)、`image-scraper`(爬虫)、`lonely-desert-road`(游戏)、`mcclone3d`(游戏)、`mirsolo`(游戏)、`niulai`(游戏)、`superengine`(引擎)
**依赖引擎:allin_engine（16）**：`an-engine`(引擎)、`ashen-beacon`(游戏)、`bloodmusic`(音乐)、`d20-table-link`(跑团)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`jotunnslayer`(游戏)、`mahjong`(游戏)、`mc-clone`(游戏)、`mirsolo`(游戏)、`moba_battle_platform`(游戏)、`niulai`(游戏)、`pywallpaper`(视效)、`running-group-simulator`(跑团)、`sandbox`(游戏)、`tavern-rogue`(游戏)
**依赖引擎:dse-core（6）**：`ashen-beacon`(游戏)、`cordis-py`(引擎)、`dict-scene-engine`(引擎)、`dse-core`(引擎)、`mirsolo`(游戏)、`novel-run`(小说)
**依赖引擎:procgen（6）**：`3dworld`(引擎)、`magic-tower`(游戏)、`random-dungeon-`(游戏)、`sandbox`(游戏)、`superengine`(引擎)、`worldbuilder`(引擎)
**普通/无特定框架（70）**：`adventurelog`(游戏)、`arcade`(游戏)、`art_video_gen`(视效)、`audio-pipeline`(音乐)、`audio-separator`(音乐)、`audiotool`(音乐)、`auto_clicker`(工具)、`bee`(游戏)、`bilibili-helper-py`(爬虫)、`calculator`(工具)、`captcha-demo`(工具)、`cellular_automaton`(视效)、`csmusic`(音乐)、`daily_player`(播放)、`darksouls`(游戏)、`ddd2`(视效)、`drawpic`(视效)、`dungeon`(游戏)、`fonts`(工具)、`gan`(视效)、`god-hand-`(游戏)、`hell-below`(游戏)、`hushi_twrj`(爬虫)、`imgproc`(视效)、`life-reset-simulator`(游戏)、`ling-train`(视效)、`loly`(游戏)、`maga`(游戏)、`math`(视效)、`mathematical-formula-renderer`(视效)、`media-tools`(视效)、`midi`(音乐)、`midjourney_video`(爬虫)、`mp`(音乐)、`music-prompt-generator`(AI)、`musickit`(音乐)、`ncmturnmp3`(音乐)、`novel-down`(小说)、`novel-generator`(小说)、`novel-reader`(小说)、`novel`(小说)、`ollama_generator`(AI)、`particlefx`(视效)、`pdf`(工具)、`peasy-ai`(AI)、`photo`(爬虫)、`photovideo`(视效)、`player`(播放)、`pq-multiverse`(游戏)、`print`(工具)、`procedural-video`(视效)、`project-root`(游戏)、`pyinstaller`(工具)、`radio_special_instruments`(音乐)、`remix`(音乐)、`renamer`(工具)、`shikonghuaban`(视效)、`sign-in-simulator`(游戏)、`smile`(游戏)、`stay`(游戏)、`subtitle`(工具)、`table-hanging-machine`(游戏)、`test`(原型)、`text-fps`(游戏)、`wav_music_gen`(音乐)、`wave4`(视效)、`weiqi_lab`(验证)、`weor`(小说)、`yasuo`(工具)、`yuanbao`(游戏)

### 2d. 按关键依赖库集群

**AI/ML 栈（15）**：`an-engine`(引擎)、`art_video_gen`(视效)、`audio-pipeline`(音乐)、`audio-separator`(音乐)、`bloodmusic`(音乐)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`mahjong`(游戏)、`mc-clone`(游戏)、`mcclone3d`(游戏)、`ollama_generator`(AI)、`video-generator`(视效)、`wav_music_gen`(音乐)、`weiqi_lab`(验证)、`weor`(小说)
**图像/视频栈（42）**：`3dworld-demos`(引擎)、`3dworld-globe`(引擎)、`adventurelog`(游戏)、`art_video_gen`(视效)、`ashen-beacon`(游戏)、`audiotool`(音乐)、`bee`(游戏)、`bloodmusic`(音乐)、`board-replay`(工具)、`cellular_automaton`(视效)、`daily_player`(播放)、`ddd2`(视效)、`drawpic`(视效)、`fish`(游戏)、`gan`(视效)、`imgproc`(视效)、`ling-train`(视效)、`lonely-desert-road`(游戏)、`magic-tower`(游戏)、`markdown`(工具)、`mcclone3d`(游戏)、`midjourney_video`(爬虫)、`mirsolo`(游戏)、`music-player`(播放)、`musickit`(音乐)、`ncmturnmp3`(音乐)、`niulai`(游戏)、`particlefx`(视效)、`pdf`(工具)、`photo`(爬虫)、`photovideo`(视效)、`pluginplayer`(播放)、`private-radio-stations`(音乐)、`pyinstaller`(工具)、`pywallpaper`(视效)、`remix`(音乐)、`sandbox`(游戏)、`sfx-download`(爬虫)、`subtitle`(工具)、`video-generator`(视效)、`webcopier`(爬虫)、`worldbuilder`(引擎)
**标准库/轻依赖（56）**：`3dworld`(引擎)、`Idle`(游戏)、`arcade`(游戏)、`auto_clicker`(工具)、`backroom`(游戏)、`calculator`(工具)、`captcha-demo`(工具)、`cordis-py`(引擎)、`cordis-snake`(引擎)、`cordis-text-game`(引擎)、`darksouls`(游戏)、`diablo`(游戏)、`dict-scene-engine`(引擎)、`dse-core`(引擎)、`foolproof-operation`(工具)、`haha`(原型)、`hell-below`(游戏)、`hushi_twrj`(爬虫)、`jotunnslayer`(游戏)、`life-reset-simulator`(游戏)、`localplayer`(播放)、`math`(视效)、`mathematical-formula-renderer`(视效)、`media-tools`(视效)、`mp`(音乐)、`music-prompt-generator`(AI)、`novel-generator`(小说)、`novel-reader`(小说)、`novel-run`(小说)、`novel`(小说)、`peasy-ai`(AI)、`player`(播放)、`pq-multiverse`(游戏)、`procedural-video`(视效)、`project-root`(游戏)、`py_test_runner`(工具)、`radio_special_instruments`(音乐)、`random-dungeon-`(游戏)、`renamer`(工具)、`roleplayer`(跑团)、`russia`(游戏)、`santi-teleprompter`(工具)、`sign-in-simulator`(游戏)、`sin-virtue-cordis-host`(原型)、`smile`(游戏)、`stay`(游戏)、`superengine`(引擎)、`tavern-rogue`(游戏)、`test`(原型)、`text-fps`(游戏)、`under-withered-limbs`(游戏)、`wave4`(视效)、`write`(小说)、`yasuo`(工具)、`yuanbao`(游戏)、`zhuangtaiji`(工具)
**爬虫/网络栈（23）**：`an-engine`(引擎)、`bilibili-helper-py`(爬虫)、`crawl-hub`(爬虫)、`csmusic`(音乐)、`dwarf-scrolls`(游戏)、`fish`(游戏)、`fonts`(工具)、`image-scraper`(爬虫)、`lab`(验证)、`mahjong`(游戏)、`markdown`(工具)、`mc-clone`(游戏)、`midjourney_video`(爬虫)、`moba_battle_platform`(游戏)、`novel-down`(小说)、`ollama_generator`(AI)、`photo`(爬虫)、`print`(工具)、`sfx-download`(爬虫)、`text-adventure`(游戏)、`video-generator`(视效)、`webcopier`(爬虫)、`weor`(小说)
**表格(OpenPyXL)（12）**：`adventurelog`(游戏)、`bee`(游戏)、`cordis-table-app`(引擎)、`d20-table-link`(跑团)、`god-hand-`(游戏)、`kard`(游戏)、`legend`(游戏)、`maga`(游戏)、`magic-tower`(游戏)、`pomodmer`(工具)、`running-group-simulator`(跑团)、`table-hanging-machine`(游戏)
**音频栈（22）**：`art_video_gen`(视效)、`audio-pipeline`(音乐)、`audio-separator`(音乐)、`audiotool`(音乐)、`bee`(游戏)、`bloodmusic`(音乐)、`daily_player`(播放)、`dungeon`(游戏)、`happy-childrens-day`(游戏)、`loly`(游戏)、`lonely-desert-road`(游戏)、`midi`(音乐)、`mirsolo`(游戏)、`music-player`(播放)、`musickit`(音乐)、`particlefx`(视效)、`players-unified`(播放)、`remix`(音乐)、`sfx-download`(爬虫)、`shikonghuaban`(视效)、`video-generator`(视效)、`wav_music_gen`(音乐)
