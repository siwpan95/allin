# gitee.com/siwpan ↔ G:\ 本地副本 全量映射与同步核对

审计时间：本次会话。只读远程（git ls-remote over https），本地仓库零写操作。
令牌掩码规则：`user:<32hex>@` → `***@`。

---

## 1. 远程仓库枚举结果

候选名共 **85 个（去重后）全部存在**，另有 3 个补充探测名：
- `media-collection` → **存在**（第 4 个集合型仓库，见 §2）
- `snake-game` → **不存在**
- `tools-music-git-backup` → **不存在**

### 集合型（多分支）仓库
| 仓库 | 分支数 | 默认分支(HEAD) | 说明 |
|---|---|---|---|
| game-collection | 8 | master `ce47a96c` | MCclone, arcade, cordis_snake, dwarf_scrolls, fish, mahjong, sandbox, master |
| tools-collection | 26 | **imgproc** `ac2c219c`（非 master） | art_video_gen/audiotool/auto_clicker/bilibili-helper-py/daily_player/drawpic/easy-ai/image-scraper/imgproc/midjourney_video/ncmturnmp3/ollama_generator/pdf/photovideo/print/procgen/py_test_runner/pyinstaller/renamer/repocheck/requirements/subtitle/wav_music_gen/webcopier/yasuo + master |
| media-collection | 7 | **photo** `b00b0595`（非 master） | cellular_automaton, midi, mp, photo, shikonghuaban, yuanbao + master |
| music | 3 | master `c838fbc2` | musickit, radio + master |
| private-radio-stations | 5 | master `14d7f088` | 2.0, 3.0, archived, archived-video + master（注意：**无 video 分支**） |

### 单项目仓库（其余 ~81 个）
全部为 `master` 单分支 + `v*` 标签结构。HEAD 短 hash 见 §4 对照表。

---

## 2. 集合型仓库分支 ↔ 本地项目映射

### game-collection（G:\repos\cordis-snake、G:\_job\_arcade2）
| 分支 | 远程 hash | 本地副本 | 本地 HEAD | 状态 |
|---|---|---|---|---|
| cordis_snake | `018533c5` | G:\repos\cordis-snake | `018533c5` | ✅ 同步 |
| arcade | `1940b60a` | G:\_job\_arcade2 | `db98b22c` | ❌ 不同步（本地 ahead/分叉） |
| master | `ce47a96c` | — | — | 无本地 |
| MCclone/dwarf_scrolls/fish/mahjong/sandbox | — | — | — | 无本地（各对应独立仓库） |

> `_arcade2` 本地仅 2 个提交（`b701819`→`db98b22c`），远程 arcade `1940b60a` **不在本地对象库**（浅/分叉）。本地 arcade 内容（2048/calculator/rider/sixone 等 10 游戏）未推送到远程 arcade 分支。

### tools-collection（G:\Temp\tc3_fhj79sp6\drawpic、G:\Temp\lic_km1787td\tools-collection）
| 分支 | 远程 hash | 本地副本 | 本地 HEAD | 状态 |
|---|---|---|---|---|
| master | `6567d87a` | G:\Temp\lic_km1787td\tools-collection | `6567d87a` | ✅ 同步（origin URL 已移除） |
| drawpic | `c213396d` | G:\Temp\tc3_fhj79sp6\drawpic | `a9152ebf` | ❌ 不同步（本地 master `a9152ebf` 既不等于 drawpic 分支也不等于 master） |
| requirements | `7e666c49` | G:\repos\requirements | `7e666c49` | ✅ 内容匹配（但该副本 origin 指向独立 requirements.git，见 §4） |
| 其余 23 分支 | — | — | — | 无本地 |

### media-collection（G:\Temp\lic_km1787td\media-collection）
- 本地 `master` = `3a516646` == 远程 `master` `3a516646` → ✅ 同步（origin URL 已移除）。
- 分支 photo/midi/mp/shikonghuaban/yuanbao/cellular_automaton 均无本地独立副本。

---

## 3. 本地 .git 全量枚举（46 处标记）

来源目录：G:\repos、G:\platform、G:\allin、G:\local、G:\Temp\lic_km1787td、G:\Temp\tc3_fhj79sp6、G:\_job

完整清单（type|路径|remote|分支|HEAD 前 8 位）已存 `G:\archive\docs-nondoc-20260924\audit-fragments\_local_repos.txt`。
关键点：
- G:\repos\particle\.venv312\...\taichi\assets\.git 为 **FILE 型**（vendored 产物，无 remote/HEAD），非真实仓库。
- G:\repos\musickit 下嵌套 5 个无 remote 的备份/实验仓库（见 §6 悬空清单）。

---

## 4. 同步核对表（本地 HEAD vs 远程 HEAD）

短 hash 取前 8 位。`→` 前为本地，`→` 后为远程。

### G:\repos（主副本）
| 本地 | 远程目标 | 本地 HEAD | 远程 HEAD | 状态 |
|---|---|---|---|---|
| adventurelog | adventurelog | `8150d173` | `bf59fea5` | ❌ 落后 |
| audio-generation | audio-generation | `b0a2231c` | `b42fbbff` | ❌ 落后 |
| bee | bee | `1078c2d2` | `1078c2d2` | ✅ |
| calculator | calculator | `0437621b` | `0437621b` | ✅ |
| cordis-snake | game-collection/cordis_snake | `018533c5` | `018533c5` | ✅ |
| crawl-hub | crawl-hub | `5ff79720` | `5ff79720` | ✅ |
| happy-childrens-day | happy-childrens-day | `463915d3` | `25dde3da` | ❌ 落后 |
| jotunnslayer | jotunnslayer | `9e942f33` | `2d72fb32` | ❌ 落后 |
| literary-legend | literary-legend | `ee66a25a` | `ee66a25a` | ✅ |
| mathematical-formula-renderer | mathematical-formula-renderer | `cb991d08` | `cb991d08` | ✅ |
| music-prompt-generator | music-prompt-generator | `c838fbc2` | `e2545c08` | ❌ 落后（本地值 == music.git master，见 §7 交叉引用） |
| musickit | musickit | `95a58ed0` | `ca2ccb3e` | ❌ 落后 |
| novel-reader | novel-reader | `9934a466` | `866e4516` | ❌ 落后 |
| particle | particle（本地分支 `5.0`） | `f5278398` | `7edb690a`(master) | ❌ 落后；`5.0` 为本地分支，远程无此分支 |
| private-radio-stations | private-radio-stations | `14d7f088` | `14d7f088` | ✅ |
| random-dungeon- | random-dungeon- | `ab2e5727` | `55a361bd` | ❌ 落后 |
| requirements | requirements | `7e666c49` | `900512e3` | ❌ 落后（本地值 == tools-collection/requirements 分支） |
| running-group-simulator | running-group-simulator | `4ed1a834` | `b478b1ff` | ❌ 落后 |
| table-hanging-machine | table-hanging-machine | `ed0564fc` | `8863ae56` | ❌ 落后 |

### G:\platform / G:\allin
| 本地 | 远程目标 | 本地 HEAD | 远程 HEAD | 状态 |
|---|---|---|---|---|
| G:\platform | allin-platform | `f0ee5120` | `f0ee5120` | ✅ |
| G:\allin | allin | `90ca2dfd` | `90ca2dfd` | ✅ |

### G:\local
| 本地 | 远程目标 | 本地 HEAD | 远程 HEAD | 状态 |
|---|---|---|---|---|
| snake-game | （无 remote） | `8de66017` | — | 悬空 |
| tools-backup\radio-20260823 | private-radio-stations/3.0 | `eaabce9a` | `8cfa5454` | ❌ 落后 |
| tools-backup\radio-pre-merge | private-radio-stations/3.0 | `eaabce9a` | `8cfa5454` | ❌ 落后 |
| tools-backup\video-20260823 | private-radio-stations/video | `b1ef7f7c` | 分支已删 | ❌ 跟踪分支已改名 archived-video `a426067b` |
| tools-backup\video-pre-merge | private-radio-stations/video | `b1ef7f7c` | 分支已删 | ❌ 同上 |

### G:\Temp\lic_km1787td（一次性 clone）
| 本地 | 远程目标 | 本地 HEAD | 远程 HEAD | 状态 |
|---|---|---|---|---|
| audio-pipeline | audio-pipeline | `b77492da` | `7d32d76a` | ❌ 落后 |
| audio-separator | audio-separator | `9ccb22d6` | `8bf05b5c` | ❌ 落后 |
| bee | bee | `5ee1e1df` | `1078c2d2` | ❌ 落后 |
| crawl-hub | crawl-hub | `ffb36f38` | `5ff79720` | ❌ 落后 |
| media-collection | media-collection | `3a516646` | `3a516646`(master) | ✅（origin 已移除） |
| novel | novel | `1b7e6855` | `714f9f29` | ❌ 落后 |
| particle | particle | `6ddd4baa` | `7edb690a` | ❌ 落后 |
| pywallpaper | pywallpaper | `b92b88ea` | `b570c7a0` | ❌ 落后 |
| remix | remix | `b2250e93` | `d009bdf7` | ❌ 落后 |
| station | station | `9a832f8c` | `fab5cf6b` | ❌ 落后 |
| tools-collection | tools-collection | `6567d87a` | `6567d87a`(master) | ✅（origin 已移除） |
| video-generator | video-generator | `fbf3fb8b` | `3f46e16b` | ❌ 落后 |

### G:\Temp\tc3_fhj79sp6
| 本地 | 远程目标 | 本地 HEAD | 远程 HEAD | 状态 |
|---|---|---|---|---|
| drawpic | tools-collection | `a9152ebf`(master) | `6567d87a`(master) / `c213396d`(drawpic) | ❌ 落后且分支错位 |

### G:\_job
| 本地 | 远程目标 | 本地 HEAD | 远程 HEAD | 状态 |
|---|---|---|---|---|
| _arcade2 | game-collection/arcade | `db98b22c` | `1940b60a` | ❌ 本地 ahead/分叉 |

---

## 5. 不同步清单汇总

**G:\repos 落后（14 个）**：adventurelog、audio-generation、happy-childrens-day、jotunnslayer、music-prompt-generator、musickit、novel-reader、particle、random-dungeon-、requirements、running-group-simulator、table-hanging-machine、（+ particle 独立项）。

**G:\local 落后/分支删除（4 个）**：radio-20260823、radio-pre-merge、video-20260823、video-pre-merge。

**G:\Temp 落后（10 个）**：audio-pipeline、audio-separator、bee、crawl-hub、novel、particle、pywallpaper、remix、station、video-generator。

**G:\_job 分叉（1 个）**：_arcade2。

**G:\Temp\tc3 drawpic（1 个）**：分支错位。

**G:\repos 同步（7 个）**：bee、calculator、cordis-snake、crawl-hub、literary-legend、mathematical-formula-renderer、private-radio-stations。
**同步（其他）**：G:\platform、G:\allin、lic\media-collection、lic\tools-collection。

---

## 6. 孤儿与悬空清单

### 远程有、本地无 .git 副本（孤儿，共 56 个单项目仓库）
music, mc-clone, backroom, photo, subtitle, renamer, audiotool, auto_clicker, pdf, ncmturnmp3, webcopier, print, midi, procgen, ling-train, gan, foolproof-operation, pyinstaller, py_test_runner, sfx-download, ollama_generator, mp, weor, art_video_gen, daily_player, darksouls, drawpic, dungeon, dwarf-scrolls, easy-ai, fish, god-hand-, image-scraper, kard, legend, lonely-desert-road, magic-tower, mahjong, midjourney_video, photovideo, sandbox, sign-in-simulator, smile, under-withered-limbs, an-engine, cordis-snake, arcade, cellular_automaton, imgproc, shikonghuaban, yuanbao, repocheck, test, novel-generator, wav_music_gen, procedural-video

> 其中多数内容已合并进 4 个集合仓库对应分支：
> - game-collection：mc-clone(MCclone)、arcade、cordis-snake(cordis_snake)、dwarf-scrolls(dwarf_scrolls)、fish、mahjong、sandbox
> - tools-collection：art_video_gen/audiotool/auto_clicker/daily_player/drawpic/easy-ai/image-scraper/imgproc/midjourney_video/ncmturnmp3/ollama_generator/pdf/photovideo/print/procgen/py_test_runner/pyinstaller/renamer/repocheck/requirements/subtitle/wav_music_gen/webcopier
> - media-collection：cellular_automaton/midi/mp/photo/shikonghuaban/yuanbao
> - music：musickit/radio

### 本地有 .git、远程找不到（悬空，共 8 处）
| 路径 | 分支 | HEAD | 说明 |
|---|---|---|---|
| G:\local\snake-game | master | `8de66017` | 无 origin；远程 `snake-game` 不存在 |
| G:\repos\musickit\archived\tools-music-git-backup | main | `cdbcac4a` | 无 origin；远程 `tools-music-git-backup` 不存在 |
| G:\repos\musickit\musickit-fix-20260817\sim\music | master | `359961af` | 无 origin |
| G:\repos\musickit\musickit-fix-20260817\sim\musickit | master | `a13ab3a5` | 无 origin |
| G:\repos\musickit\musickit-fix-20260817\sim2\musickit | master | `8329087a` | 无 origin |
| G:\repos\musickit\musickit-fix-20260817\sim2\musickit\archived\tools-music-git-backup | master | `a5acd8fd` | 无 origin |
| G:\Temp\lic_km1787td\tools-collection | master | `6567d87a` | origin URL 已移除（内容仍 == 远程 master） |
| G:\Temp\lic_km1787td\media-collection | master | `3a516646` | origin URL 已移除（内容仍 == 远程 master） |
| （particle\.venv312 taichi\assets\.git FILE） | — | — | vendored 伪仓库 |

### G:\Temp 临时 clone 状态
- `G:\Temp\lic_km1787td`（13 子仓库）：最后修改 2026-08-26 22:23，为一次性作业 clone，**全部落后远程**（除 media-collection/tools-collection 与 master 同步但 origin 已移除）。
- `G:\Temp\tc3_fhj79sp6`（drawpic）：最后修改 2026-08-26 22:37，落后且分支错位。
- 结论：**两处均视为已废弃的一次性 clone**（token 型 origin URL 仍在，内容陈旧）。

---

## 7. G:\allin 详情

- **git status**：工作树干净；仅 3 个未跟踪文件：`归类清单.csv`、`归类清单.md`、`归类移动.ps1`。
- **跟踪文件（ls-files，4 个）**：`.gitignore`、`LICENSE`、`README.md`、`目录索引.txt`。
- **远程 HEAD 对比**：本地 `90ca2dfd` == 远程 `90ca2dfd` → ✅ **master 同步**。
- **远程 tracked 文件（ls-tree origin/master）**：`.gitignore`、`LICENSE`、`README.md`、`目录索引.txt`（与本地 4 文件完全一致）。
- **远程 refs**：`refs/heads/master`=`90ca2dfd`；`refs/tags/nothing`（annotated `3911bfe5`→`64087928`）。
- **本地 refs 差异**：
  - 本地 tag `游戏`=`47d3557b` —— **远程无此 tag**（本地专属，未推送）。
  - 本地遗留远程跟踪 `origin/nothing`=`64087928` —— 对应已删除的远程分支（现仅为远程 tag `nothing` 的解引用值），属陈旧 ref。
- 最近提交：`90ca2dfd docs: 目录重构后的顶层结构说明 + 目录索引重生成（2026-08-27）`。

---

## 8. 交叉引用 / 结构性发现

1. **music-prompt-generator 本地值错位**：G:\repos\music-prompt-generator 的 HEAD `c838fbc2` 实为 `music.git` 的 master，而非 `music-prompt-generator.git` 的 master `e2545c08`（疑似仓库改名/重组前 clone）。
2. **requirements 本地值错位**：G:\repos\requirements 的 HEAD `7e666c49` 实为 `tools-collection` 的 `requirements` 分支，而非独立 `requirements.git` 的 master `900512e3`。
3. **arcade 双处**：独立 `arcade.git` master == `game-collection` 的 `arcade` 分支 == `1940b60a`；但本地 `_arcade2` 的 2 个提交（`b701819`→`db98b22c`）尚未进入二者。
4. **共享 tag**：`musickit.git` 与 `music.git` 共享 tag `v1.0.0`=`a5a28069`。
5. **默认分支异常**：tools-collection 默认分支指向 `imgproc`、media-collection 默认分支指向 `photo`（均非 master）。
6. **private-radio-stations**：本地 video 备份跟踪的 `video` 分支在远程已消失（现为 `archived-video` `a426067b`）。

---

# 附：全量 91 仓清单修正（重建仓后）

依据《重建仓执行报告_2026-08-27.md》+《发行版规划_2026-08-27.md》+《会话交接_2026-08-27.md》，远程实际结构为 **91 仓 = 86 活跃 + 5 legacy**：
- **46 新仓**（集合仓拆出）：media 6（cellular_automaton/shikonghuaban/photo/yuanbao/midi/mp）+ tools 25（art_video_gen/audiotool/auto_clicker/**bilibili-helper-py**/daily_player/drawpic/easy-ai/image-scraper/imgproc/midjourney_video/ncmturnmp3/ollama_generator/pdf/photovideo/print/procgen/py_test_runner/pyinstaller/renamer/repocheck/requirements/subtitle/wav_music_gen/webcopier/**yasuo**）+ games 7（mc-clone/arcade/cordis-snake/dwarf-scrolls/fish/mahjong/sandbox）+ ai 5（gan/ling-train/novel-generator/procedural-video/weor）+ music 2（music-prompt-generator/musickit）+ smile 1。
- **40 老仓**（重建前即独立）：allin/allin-platform/an-engine/particle/bee/audio-pipeline/audio-separator/crawl-hub/novel/station/video-generator/pywallpaper/remix/novel-reader/backroom/jotunnslayer/private-radio-stations/foolproof-operation/sfx-download/adventurelog/darksouls/dungeon/god-hand-/happy-childrens-day/kard/legend/literary-legend/lonely-desert-road/magic-tower/random-dungeon-/running-group-simulator/sign-in-simulator/table-hanging-machine/under-withered-limbs/audio-generation/calculator/test/mathematical-formula-renderer/**moba_battle_platform**/**diablo**。
- **5 legacy**（集合仓改名，旧链接重定向到同名 legacy）：game-collection-legacy/tools-collection-legacy/media-collection-legacy/ai-collection-legacy/music-legacy。
- ⚠️ 我原始枚举漏了 4 个活跃仓：`bilibili-helper-py`、`yasuo`、`diablo`、`moba_battle_platform`（默认分支 main，其余 master）——已补入下述 D1/D2 核验。

---

# D1 LICENSE 核验（治理声明「91/91 全绿」vs 实测）

方法：HTTP GET 跟随 302 重定向 `https://gitee.com/siwpan/<repo>/raw/<branch>/LICENSE`；branch = `main` 仅 moba_battle_platform，其余 `master`；500/429 重试一次。（用 curl.exe 等价 Invoke-WebRequest 取最终状态码。）

**结果：90/91 返回 200，1/91 返回 404。声明「91/91 全绿」未完全核实 —— 实为 90/91。**

| 状态 | 数量 | 说明 |
|---|---|---|
| 200（有 LICENSE） | 90 | 全部活跃 86 仓 + 4 legacy（game/tools/media/music-legacy） |
| 404（缺 LICENSE） | 1 | **ai-collection-legacy**（无 master 分支；见下） |

**唯一缺口 `ai-collection-legacy` 详查**：该仓无 `master` 分支，默认分支 HEAD = `novel_generator`；5 个分支逐一探测：`novel_generator`=200，`gan`/`ling-train`/`procedural_video`/`weor` 均 404。即 legacy 仓内 4 个分支始终未补 LICENSE（对应文档「ai-collection 用户先行处理未补的 4 仓」——用户是拆成独立仓补的 LICENSE，legacy 分支本身仍缺）。

**文档声明补漏的 9 仓实测**：fish/gan/ling-train/mahjong/mc-clone/musickit/procedural-video/sandbox/weor（独立活跃仓）现全部 200 ✅（此部分补漏已核实）。

---

# D2 tag / 发行版核验（治理声明「81/86 已发布 v1.0.0」vs 实测）

方法：`git ls-remote --tags`，按「含 v1.0.0 类 tag（v1.0.0 / <项目>-v1.0.0 / v1.0.0-*）」判定。

**活跃 86 仓实测分组：**

| 分组 | 数量 | 成员 |
|---|---|---|
| v1.0.0 类 tag | **79** | 74 个纯 `v1.0.0` + 5 个特殊格式：cellular_automaton=`cellular-v1.0.0`、shikonghuaban=`shikonghuaban-v1.0.0`、photo=`photo-v1.0.0`、yuanbao=`yuanbao-v1.0.0`、arcade=`v1.0.0-arcade` |
| 非 v1.0.0 发行 tag | **2** | station=`v3.0.0`、private-radio-stations=`v4.0.0` |
| 无 v1.0.0 tag（未发布 5） | **5** | literary-legend（无任何 tag）、allin（`nothing`）、test（无任何 tag）、calculator（`mvvm`）、mathematical-formula-renderer（`2.0`,`3.0`） |

**「无任何 tag」组（含 legacy，共 4 仓）**：literary-legend、test、tools-collection-legacy、ai-collection-legacy。

**legacy 5 仓 tag**：game-collection-legacy=`v1.0.0-arcade`；media-collection-legacy=4 个 `<项目>-v1.0.0`；music-legacy=`v1.0.0`；tools-collection-legacy=无 tag；ai-collection-legacy=无 tag。

**与「81」对比结论**：
- 79（v1.0.0 类）+ 2（v3.0.0/v4.0.0）= **81「已发布」**，与声明一致 ✅。
- 但严格按「v1.0.0 类 tag」口径计 = **79**，与「81」差 2 —— 差在 station（v3.0.0）与 private-radio-stations（v4.0.0）两仓用了非 v1.0.0 版本号。
- 未发布 5 仓（literary-legend/allin/test/calculator/mathematical-formula-renderer）与文档「剩余 5 个」完全吻合 ✅。

（核验原始数据见 `G:\archive\docs-nondoc-20260924\audit-fragments\_verify_license_tags.txt`。）
