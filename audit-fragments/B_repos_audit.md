# G:\repos 全量画像审计汇总

扫描时间: 2026-08-27 20:16:30   |   一级子目录总数: 84（任务预估约 95，实际 84）

## 1. 分类统计

| 分类 | 数量 |
|---|---|
| game | 34 |
| tool | 17 |
| ai-gen | 9 |
| crawler | 7 |
| audio | 11 |
| media | 4 |
| platform | 1 |
| other | 1 |

## 2. Git 与来源

- 有 .git 的仓库：19 个
- 上游克隆（remote 非 siwpan / github 等）：0 个
- 自推仓库（gitee.com/siwpan）：19 个（全部 git 仓库均指向 gitee.com/siwpan）
- 本地项目（无 remote 或非 git）：65 个

## 3. 缺 LICENSE 清单（54 个）

art_video_gen, audio-pipeline, audio-separator, audiotool, auto_clicker, backroom, bilibili-helper-py, cellular_automaton, daily_player, darksouls, diablo, drawpic, dungeon, easy-ai, foolproof-operation, god-hand-, image-scraper, imgproc, kard, legend, lonely-desert-road, magic-tower, midi, midjourney_video, moba_battle_platform, mp, ncmturnmp3, novel-generator, ollama_generator, particle, pdf, photo, photovideo, print, procgen, py_test_runner, pyinstaller, pywallpaper, remix, renamer, repocheck, sfx-download, shikonghuaban, sign-in-simulator, smile, station, subtitle, test, under-withered-limbs, video-generator, wav_music_gen, webcopier, yasuo, yuanbao

## 4. 工作区 dirty 清单（13 个 git 仓库）

| 仓库 | dirty 文件数 |
|---|---|
| adventurelog | 5 |
| audio-generation | 3 |
| cordis-snake | 2 |
| happy-childrens-day | 5 |
| jotunnslayer | 34 |
| musickit | 1 |
| music-prompt-generator | 2 |
| novel-reader | 5 |
| particle | 2 |
| random-dungeon- | 5 |
| requirements | 5 |
| running-group-simulator | 5 |
| table-hanging-machine | 6 |

## 5. 异常项清单（令牌/密钥/超大文件/坏味道）

### 令牌 / 密钥 / Cookie 风险

- `moba_battle_platform` — 根目录 `私人令牌.txt`（私有令牌明文文件）⚠️
- `novel` — `novel_generator/tools/wordbank_expand/tavily.key`（Tavily API Key）⚠️
- `bilibili-helper-py` — `cookie_utils.py` + `config.json`（登录 Cookie 处理）⚠️
- `ollama_generator` — `deepseek_config.json`（DeepSeek API 配置）
- `image-scraper` / `midjourney_video` / `webcopier` — 根目录 `config.json`（爬虫代理/令牌配置）
- `private-radio-stations` — `apps/video/mediamtx/auto.key`

> 全仓库未发现 `.env*` 文件（env_files 全空）。上述为文件名层面暴露的凭证/令牌风险，未读取其内容。

### 超大文件（>100MB，排除 venv/node_modules）

| 目录 | 说明 |
|---|---|
| musickit | 总 120.5GB；archived 下含 ffmpeg/ngrok/cloudflared、海量音频样本 |
| image-scraper | 总 13.8GB；images/ 爬取的图片与 midjourney 视频 |
| bilibili-helper-py | 总 5.6GB；output/ 下载的 mp4（最大 793MB） |
| print | 2.96GB；dictionary/ 重复词典副本；dist 385MB exe |
| art_video_gen | 3.03GB；.venv 含 torch（torch_cpu.dll 291MB） |
| audio-generation | 2.64GB；.venv + 大量输出 wav/log |
| arcade | 1.92GB；build/dist 多游戏 exe |
| fish | 2.43GB；dist LazyFishTank exe 127MB |
| video-generator | 1.89GB；ffmpeg 二进制 + 输出 mp4 |
| webcopier | 1.80GB；dist + onnxruntime |
| photovideo | 2.00GB；output2.mp4 1271MB |
| drawpic | 1.76GB；dist 133MB exe |
| bee | 1.20GB；dist/BeeIdleRPG.exe 428MB |
| mc-clone | MC2/dist/mc_clone_gui.exe 608MB |

### 常见坏味道

- **虚拟环境目录存在（.venv / venv）**：多数 PyInstaller 项目工作区均携带 .venv（adventurelog, an-engine, arcade, art_video_gen, audio-*, bee, diablo, drawpic, dungeon, dwarf-scrolls, easy-ai, fish, god-hand-, jotunnslayer, legend, lonely-desert-road, magic-tower, mahjong, mc-clone, midi, midjourney_video, moba_battle_platform, novel, particle(.venv312), pywallpaper, sandbox, shikonghuaban, sign-in-simulator, under-withered-limbs, video-generator, wav_music_gen, weor, yasuo, yuanbao 等）。
- **日志入库**：audio-generation（23 个 .log）、py_test_runner（大量 test_errors_*.log）、novel、musickit、bilibili-helper-py(download.log)、crawl-hub、image-scraper、moba_battle_platform、ling-train、bee、midjourney_video、sfx-download(.workbuddy log)。
- **__pycache__ 误留**：audio-separator(1776)、video-generator(1641)、midi(1277)、art_video_gen(1043)、arcade(885)、musickit(849)、wav_music_gen(710) 等数量巨大。
- **dist/build exe 入库**：几乎所有项目都提交了 PyInstaller 的 build/dist 产物（exe + 大量 DLL）。
- **调试/临时文件入库**：audio-pipeline(_debug*.txt, _smoke*.txt)、cellular_automaton(_t.txt)、legend(err.txt, demo.py.bak)、mahjong(_refactor_backup)、audio-separator(*.bak)、moba_battle_platform(add_err.log)。
- **无任何文档（README/LICENSE/requirements 全缺）**：backroom。

## 6. 明细 CSV

完整明细见同目录 `B_repos_audit.csv`（84 行数据 + 表头）。

