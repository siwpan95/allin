# C_misc_audit — G:\notpython / G:\local / G:\web 深度画像

> 只读审查，未修改任何被审文件。规模统计口径：文件数/大小均**排除** `node_modules`、`__pycache__`、`.git`（.venv 未排除，因本地项目普遍含 .venv，已在备注中体现）。
> 时间戳观测：多数 GitHub 解压包整包文件 mtime 落在 2026-08-04/05（deepseek-harness 为 08-16），因此"本地改动"按**晚于该目录主体解压时间、且为孤立新增文件**判定（多为 08-17~08-25 的 .bat/.py/.md/requirements.txt）。

---

## 一、G:\notpython（43 个一级子目录，多为 GitHub/Gitee 下载解压包）

### 1.1 逐目录画像

| 目录 | 来源仓库 | LICENSE | 文件数/大小(MB) | 分类 | 本地改动 |
|---|---|---|---|---|---|
| AI-NovelsGenerator-main | github.com/YILING0013/AI_NovelGenerator | AGPL-3.0 | 3851 / 51.43 | ai | +requirements.txt、+_来源说明.md |
| AzuraCast-main | github.com/AzuraCast/AzuraCast | README 标注 AGPL-3.0-or-later，**但目录内无 LICENSE 文件** | 1786 / 23.13 | audio | — |
| bilibili-helper | 自研（浏览器扩展，无上游） | 无 | 10 / 30.28 | other | 自建 README.md（08-20） |
| cheatcard | 自研（德州扑克+俄罗斯轮盘） | 无 | 1299 / 31.23 | game | +requirements.txt |
| ChineseAiDungeon-main | github.com/bupticybee/ChineseAiDungeon | GPL-2.0 | 28109 / 926.87 | ai | +requirements.txt |
| cocostudio-mahjong-master | gitee（COCOS2D-X 单机麻将，作者未注明） | 无 | 2211 / 84.09 | game | — |
| ComfyUI-master | github.com/comfyanonymous/ComfyUI | GPL-3.0 | 41180 / 1848.25 | ai | +requirements.txt |
| cordis-snake-example | 本地归档快照（E:\docs\snake-game，2026-08-24） | 无 | 40 / 0.13 | game | +_来源说明.md |
| darksouls_cli | 自研（Dark Souls roguelike） | 无 | 4467 / 971.77 | game | 自建 README.md、+requirements.txt |
| deepseek-harness-master | DeepSeek Harness（github deepseek-ai） | MIT（Copyright 2026 DeepSeek） | 7417 / 45.49 | engine | **部署补丁（见 1.3）** |
| diabloworld-master | 9miao.com（firefly 框架 Diablo 演示，作者 hg/lan/sean_lan） | 无 | 3062 / 304.63 | game | — |
| DouZero-main | github.com/kwai/DouZero | Apache-2.0 | 16289 / 530.54 | ai | +requirements.txt、+_来源说明.md |
| DrissionPage-master | github.com/g1879/DrissionPage | 自定义（个人学习/非商业） | 3553 / 189.16 | crawler | +requirements.txt |
| ECommerceCrawlers-master | github.com/DropsDevopsOrg/ECommerceCrawlers | MIT | 14164 / 529.15 | crawler | +requirements.txt、+_来源说明.md |
| Fictionist-master | 未注明（AI 小说生成器，README 无 URL） | 无 | 2717 / 26.82 | ai | +requirements.txt、+_来源说明.md |
| firefly-master | github.com/9miao/firefly | MIT（2013 9miao.com） | 1260 / 12.3 | engine | +requirements.txt |
| html | 自研（全哥游戏工坊网页合集） | 无 | 139 / 1.8 | game | 自建 README.md、+open-allin-python-platform.bat |
| kard_CN | 自研（KARD 卡牌动作游戏） | 无 | 2284 / 89.19 | game | 自建 README.md、+requirements.txt |
| KKRIEGER | 自研（.kkrieger 96KB 演示二进制） | 无 | 3 / 0.19 | game | 自建 README.md |
| kontakt_transcode | 自研（Kontakt NKX/NCW 转码工具链） | 无 | 449 / 332.52 | audio | 自建 README.md、大量 .log/.txt 工作产物 |
| krieger-clone | 自研（Backrooms 光线投射） | 无 | 2350 / 166.15 | game | 自建 README.md、+requirements.txt |
| manual_dota-master | github.com/beyonehu/manual_dota（推断自 LICENSE 版权） | MIT（2015 beyonehu） | 5733 / 293.83 | game | — |
| merged_gui | 自研（tkinter 迷你程序合集） | 无 | 21829 / 722.23 | other | 自建 README.md、+requirements.txt |
| mindspore-master | gitee.com/mindspore / github.com/mindspore-ai/mindspore | Apache-2.0 | 71328 / 2182.2 | ai | — |
| MusicStudioPro | 自研（音乐制作系统，无 README） | 无 | 12211 / 1884.73 | audio | 自建 main.py/setup.py/bat |
| NKGMobaBasedOnET-master | gitee.com/NKG_admin/NKGMobaBasedOnET | MIT（2021 烟雨迷离半世殇） | 6905 / 297.9 | game | — |
| obEspoir-master | github.com/obespoir/echecs（gitee jamon/echecs） | AFL-3.0 | 1545 / 17.63 | engine | +requirements.txt |
| PlantsVsZombies-master | gitee.com/GITLZ/PlantsVsZombies | Apache-2.0 | 6216 / 431.88 | game | — |
| pq6-4-4 | 自研（Progress Quest 合集） | 无 | 716 / 16.62 | game | 自建 README.md |
| pro2 | 自研（music-production-system v1.0.0，无 README） | 无 | 15432 / 514.95 | audio | 自建脚本（1.py~8.py、setup.py） |
| pyaudio-simpleaudio | 自研（仅一个 requirements.txt 空壳） | 无 | 1 / 0 | audio | 仅 requirements.txt |
| Python-master | gitee.com/52itstyle（从零学Python） | GPL-3.0 | 11138 / 494.33 | other | +requirements.txt |
| ratel-master | github.com/ainilili/ratel | Apache-2.0 | 133 / 0.82 | game | — |
| search_word | 自研（搜索词爬虫，无 README） | 无 | 1737 / 22.53 | crawler | — |
| SerpentAI-dev | github.com/SerpentAI/SerpentAI | MIT（2017-2020 Serpent.AI） | 21173 / 861.36 | ai | +requirements.txt |
| ShicimingjuCrawleAndDisplay | 诗词名句网爬虫（ECommerceCrawlers 系） | Apache-2.0 | 1980 / 27.27 | crawler | — |
| SohuNewCrawler | 搜狐新闻爬虫（作者 Hatcat123） | 无 | 6459 / 80.62 | crawler | — |
| TaobaoCrawler | 淘宝爬虫（ECommerceCrawlers 系） | 无 | 3334 / 52.05 | crawler | — |
| TownGeneratorOS-master | github.com/watabou/TownGeneratorOS | GPL-3.0 | 64 / 0.16 | game | — |
| unityRpg-unity54 | gitee.com/liyonghelpme（unityRpg/Moba） | 无 | 20057 / 1094.72 | game | — |
| XianyuCrawler | github.com/Hatcat123/XianyuSdd | 无 | 6450 / 80.51 | crawler | — |
| youjian | 自研（解除复制限制 Tampermonkey 脚本+扩展） | 无 | 11 / 0.48 | other | 自建 README.md |
| ZhaopinCrawler | 招聘爬虫 FindJob（ECommerceCrawlers 系） | 无 | 649 / 7.85 | crawler | — |

### 1.2 汇总统计

- 一级子目录数：**43**
- 分类统计：game 16 · crawler 8 · ai 7 · audio 5 · engine 3 · other 4
- 有 LICENSE：**18**（含 AzuraCast 的"README 标注但缺文件"计入则 19）；许可证分布：MIT 6 · Apache-2.0 6 · GPL（2.0/3.0）4 · AGPL 1 · AFL-3.0 1 · 自定义（DrissionPage）1 · CC（见 web 节）
- 自研/本地项目（非上游下载）：约 17 个（bilibili-helper、cheatcard、cordis-snake-example、darksouls_cli、html、kard_CN、KKRIEGER、kontakt_transcode、krieger-clone、merged_gui、MusicStudioPro、pq6-4-4、pro2、pyaudio-simpleaudio、search_word、youjian，及部分为归档/合集）
- 总规模（粗略）：约 60 万文件、约 18 GB（未排除 .venv，实际源码远小于此）

### 1.3 deepseek-harness-master 的"部署补丁"（重点）

该目录是 DeepSeek Harness 的 GitHub 下载副本，用户在根目录**自行新增了 6 项部署文件**（解包主体时间 08-16 22:34，这些文件均为 08-17~08-20）：

1. `DEPLOY.md`（08-20）— 部署说明，记录三层故障根因与修复：① 本地 npm 镜像代理未就绪导致 npx 静默挂起；② **腾讯电脑管家 QQSysMonX64_EV.sys 过滤驱动全局禁止目录联接(junction)遍历（WinError 448 / ERROR_UNTRUSTED_MOUNT_POINT）**，导致 dsh 把 profiles/node_modules 维护成 junction 时所有插件导入失败、`dsh web` 启动即崩；③ 物化拷贝后 optionalDependencies（@img/sharp-win32-x64、@koromix/koffi-win32-x64）无法解析。
2. `fix_dsh_fallback_patch.py`（08-20）— **补丁重放脚本（幂等）**，给 npx 缓存里的 `dsh-app-boot/lib/index.js` 打补丁。行为概括：把 `ensureSymlink` 改为"仅当现有 junction 可实际遍历才保留，否则用 `cpSync` 物化成真实目录拷贝"；并把 `healProfilesModuleFallback` 的依赖闭包遍历从 `dependencies+peerDependencies` 扩展为**同时纳入 optionalDependencies**，从而解决 sharp/koffi 原生模块加载失败。已打补丁则跳过，代码结构变化时报 SHAPE MISMATCH 并退出非零。
3. `gen_start_bat.py`（08-20）— 生成 `start-dsh.bat`（CRLF/纯 ASCII），内含"先拉起 8899 本地镜像代理并等待其真正监听（最多 30s）再执行 npx"的逻辑，避免 npx 与死端口竞态挂起。
4. `start-dsh.bat`（08-20）— 由上述脚本生成的实际启动器，执行 `npx -y @deepseek-ai/dsh@0.1.0-rc.6 web --port 3080`。
5. `npm_local_mirror.py`（08-17）— 本地 npm 缓存镜像代理（流式版，监听 8899，上游 npmmirror），分块流式转发大 tarball 边下边缓存，规避 pnpm 因无字节到达而 body timeout 的问题。
6. `__pycache__/` — Python 运行生成的字节码缓存。

> 结论：这 6 项是**部署/故障修复补丁**，不是上游仓库内容。

### 1.4 无 LICENSE 清单（25 个）

AzuraCast-main（标注 AGPL 但缺文件）、bilibili-helper、cheatcard、cocostudio-mahjong-master、cordis-snake-example、darksouls_cli、diabloworld-master、Fictionist-master、html、kard_CN、KKRIEGER、kontakt_transcode、krieger-clone、merged_gui、MusicStudioPro、pq6-4-4、pro2、pyaudio-simpleaudio、search_word、SohuNewCrawler、TaobaoCrawler、unityRpg-unity54、XianyuCrawler、youjian、ZhaopinCrawler。

（注：其中多数为自研/本地项目，本就不带许可证；纯上游下载却缺 LICENSE 的是 AzuraCast、cocostudio-mahjong、diabloworld、Fictionist、SohuNewCrawler、TaobaoCrawler、unityRpg-unity54、XianyuCrawler、ZhaopinCrawler 等。）

### 1.5 被本地改动的上游项目清单

- **deepseek-harness-master**：部署补丁（6 项，见 1.3）——改动最大。
- **AI-NovelsGenerator-main / DouZero-main / ECommerceCrawlers-master / Fictionist-master**：各新增 `_来源说明.md`（08-24，标注"外部源码转储、不改动不整合"）。
- 约 30 个目录统一新增 `requirements.txt`（08-21，用户批量 pip 依赖固化）。
- 多个自研目录的 `README.md` 为 08-20 用户自建（非上游原始 README）。

---

## 二、G:\local（26 个小项目，多为 2026-07~08 会话产物，全部为自研）

> 结论前置：**全部 26 个均为"自研草稿/会话产物"，无 LICENSE，绝大多数有自建 README.md**。除 snake-game 与 G:\repos\cordis-snake 同源外，其余与 G:\repos 无同名对应（diff 抽查见 2.2）。

| 目录 | README | 规模(文件/ MB) | 入口 | 一句话功能 |
|---|---|---|---|---|
| captcha-demo | 有 | 506 / 6.57 | main.py | tkinter 人机验证码演示系统（MVVM，6 类验证码） |
| D20 | 有 | 1046 / 13.05 | cli.py / mvp_gui.py | D&D-GURPS 角色构建器 v2.0 |
| ddd2 | 有 | 4225 / 376.34 | ddd (2).py | 元胞自动机视频生成器 |
| haha | 有 | 574 / 6.29 | main.py | tkinter MVC 演示应用 |
| hell-below | 有 | 1141 / 14.73 | launcher/ | 游戏启动器平台（聚合多款本地化小游戏） |
| Idle | 有 | 1045 / 43.86 | main.py | Idle Clicker 放置挂机（纪元/科技树/英雄/转生） |
| life-reset-simulator | 有 | 548 / 7.66 | main.py | 人生重开模拟器（MBTI 出身 + 决策树） |
| loly | 有 | 2601 / 77.87 | main.py | DOOM 风格伪 3D 光线投射游戏（pygame-ce） |
| maga | 有 | 3701 / 81.62 | main.py | 重装机兵同人游戏 |
| math | 有 | 3295 / 302.52 | main.py | 元胞自动机 Formula Lab（可插拔公式） |
| media-archive | 无 | 23995 / 766.89 | — | 媒体特效归档（art/wallpaper/media_engine 等） |
| player | 有 | 493 / 6.27 | player.py | 模拟 WMP 可视化效果程序 |
| pq-multiverse | 有 | 611 / 7.03 | main.py | Progress Quest 多元宇宙自动 RPG |
| project-root | 有 | 572 / 23.14 | main.py / gui_app.py | 《诡秘之主》序列途径模拟系统 |
| russia | 有 | 1055 / 179.34 | main.py | 俄罗斯轮盘赌（ECS 版） |
| snake-game | 有 | 49 / 0.26 | src/index.js（npm） | Cordis「一切皆插件」贪吃蛇（与 repos\cordis-snake 同源） |
| stay | 有 | 2012 / 65.34 | main.py | Progress Quest 2 移植版（Python/Tkinter） |
| tavern-rogue | 有 | 1055 / 78.53 | run_gui.py | 酒馆异闻录 Roguelike 自走棋（D&D SRD） |
| text-adventure | 有 | 1058 / 27.92 | text_adventure/ | 文字冒险解谜（中英双版） |
| text-fps | 有 | 3658 / 91.11 | text_fps/ | 文字 FPS 战术战斗（中英双版） |
| tools-archive | 无 | 3136 / 221.13 | — | 工具归档（faatt_archived、清理目录） |
| tools-backup | 有(README.txt) | 737 / 473.48 | — | radio/video 合并前后备份 |
| tools-category-readmes | 无 | 7 / 0 | — | 分类说明文档（ai/audio/crawler/game/…） |
| tools-migration | 无 | 9 / 0.01 | fix_paths.ps1 / rebuild_*.ps1 | 迁移与重建脚本 |
| wave4 | 有 | 3186 / 101.99 | wave4/ | 布朗噪声/fBm 生成与分析工具包 |
| zhuangtaiji | 有 | 2427 / 23.13 | main.py | 多范式决策引擎可视化工作台 |

### 2.1 汇总

- 项目数：26；README 有 21 / 无 5（media-archive、tools-archive、tools-category-readmes、tools-migration，及 tools-backup 用 README.txt）；**LICENSE：全部无**。
- 判定：**26 个全部为自研草稿/会话产物**，非从 G:\repos 复制。
- 创建时间集中在 2026-07-24 ~ 08-25（requirements.txt 批量添加于 08-21，自建 README 多为 08-20）。

### 2.2 diff -q 抽查（对照 G:\repos，按文件清单比对，排除 .venv/node_modules/__pycache__/.git/build/dist）

| 本地目录 | 对照 repos 目录 | 相同文件 | 结论 |
|---|---|---|---|
| snake-game | cordis-snake | 47（几乎全同） | **同源**：Cordis 贪吃蛇在本地/repos/notpython 多处副本 |
| math | mathematical-formula-renderer | 3 | 无关，自研 |
| player | daily_player | 2 | 无关，自研 |
| stay | adventurelog | 3 | 无关，自研 |
| text-adventure | dungeon | 2 | 无关，自研 |

> 说明：G:\repos 下**不存在**与 math/player/stay/text-adventure 同名的目录，比对对象为最相近的候选，结果一致表明本地这些项目并非 repos 副本。

---

## 三、G:\web（仅 counterdisinfo-master）

| 项 | 内容 |
|---|---|
| 目录 | counterdisinfo-master |
| 来源 | gitee.com/furyphoenix/counterdisinfo |
| 功能 | "CounterDisInfo：对抗虚假信息兵棋" —— 2-4 人策略卡牌兵棋，模拟虚假信息对抗（8 类资产、20 种攻击技战术、20 种防御技战术、8 类场景），西北工业大学认知安全团队（李晓宇、王震、高超等）设计 |
| LICENSE | **CC BY-SA 4.0**（Attribution-ShareAlike 4.0 International） |
| 规模 | 13 文件 / 106.06 MB（含 61.5MB apk、31.7MB mp4、6.2MB pdf 及多张 png/牌面 md） |
| 分类 | game（策略兵棋/桌游） |

---

## 四、三目录总体结论

1. **G:\notpython**：43 个目录，主体为 GitHub/Gitee 下载的上游解压包（约 26 个），另有约 17 个为自研/本地归档；18 个带 LICENSE、25 个无 LICENSE；`deepseek-harness-master` 是唯一被实质本地改造的上游项目（6 项部署补丁）。
2. **G:\local**：26 个自研会话产物，无 LICENSE，功能以 tkinter/pygame 小游戏与工具为主，与 G:\repos 基本无同名副本关系。
3. **G:\web**：1 个目录，gitee 上游反虚假信息兵棋（CC BY-SA 4.0）。
