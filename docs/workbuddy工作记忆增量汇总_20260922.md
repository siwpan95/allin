# WorkBuddy / CodeBuddy 工作记忆 · 增量汇总（2026-09-11 ~ 2026-09-22）

> **本文件是新增文件，不覆盖任何既有备份。**
> 来源：`/Users/13122/WorkBuddy/**/.workbuddy/memory/*` + `/Users/13122/CodeBuddy/**/.codebuddy/memory/*`，共 **165 份 memory md**；本汇总覆盖 **2026-09-11 ~ 2026-09-22** 区间（此区间此前未进 G 盘备份，本轮已同步 31 个文件）。
> 既有旧备份（**未改动**）：`/allin/docs/workbuddy工作记忆备份.txt`（2026-09-16 快照）、`/workbuddy/CONSOLIDATED_MEMORY.md`（2026-08-21，跨 77 工作区）。
> 写法：按**项目线归并**，只收录 memory 中真实记载的内容；数字（提交号/测试数/字节数/版本号）原样保留。

---

## 一、项目线总表

| 项目线 | 本地/Gitee | 区间内做了什么 | 状态 | 见证工作区 |
|---|---|---|---|---|
| **PluginPlayer** | `/repos/pluginplayer`（siwpan/pluginplayer，main） | 插件版播放器（C++ 内核 + JS host）；上线前全检 44 项修 42；播放增强 P0-1~P0-4/P0-4b'/B5；字幕(libass)/HDR 色彩空间/画质插件；radio 集成 + `radio_bridge` 插件 | 门禁 18/18、自检 15/15；v1.0.0；**远端领先本地 2 提交** | 09-11-17-50-40、09-12 各档、09-13、09-14-21-53-08 |
| **players-unified** | `/repos/players-unified`（siwpan） | 三端**物理合并 monorepo**（复制非移动，原三仓未删）；Phase1-4（MediaItem schema / PlayerEngine / launcher / 内核评估 S0-S4）；Phase5 S5 Cordis 统一宿主 `host/` | v0.1.0→v0.8.0；S5 双跑等价 **116/116**；tag v0.8.0 | MEMORY.md、09-14、09-15-21-53-08 |
| **localplayer** | `/repos/localplayer`（siwpan） | v1.3.0~v1.3.4：侧边栏/全页应用、WebRTC 网页投送、投送健壮性、GitFlow、修 Werkzeug 依赖 | v1.3.4；master=1bc0310、develop=f3801ae | CodeBuddy 09-14 |
| **daily_player** | `/repos/daily_player` | 方向探明 = Python3.14 + tkinter + python-vlc 桌面播放器（PyInstaller） | v1.0.0 已发 Gitee | CodeBuddy 09-14 |
| **12test / cordis-host** | `/local/12test` | 按 5 份 docx 重做为 Cordis「一切皆插件」；再按《原始设计》重写为计数器模型 | playthrough 穷举 4096 局、12/12 结局可达；Web `localhost:3210` | CodeBuddy 09-12 |
| **an-engine（引擎）** | `/repos/an-engine`（siwpan/an-engine） | **alloy → allin_engine 彻底改名**（173 文件 / 753 处）；字体拆出发布包；双写副本分叉治理 + media 5021 文件补齐；**5 个内联副本迁移**（371 文件 / 1586 处引用） | 提交 `72c1d63`、`bd70af2`；**`allin-engine 1.0.0` 上正式 PyPI**（3.38MB） | 09-17~09-19（WorkBuddy + CodeBuddy） |
| **bloodmusic** | `/repos/audio-generation` | 命名空间包改造 + 字体可选化 + TestPyPI→正式发布 | **`bloodmusic 2.0.0` 上正式 PyPI**（0.47MB） | 09-19 |
| **audio-generation** | `/repos/audio-generation` | Cordis 重构 Phase A（host-js 10/10 绿）+ Phase B（pytest 583→0、players-unified 收编、interactive/service B-lite 20 绿）；内容/QA 自动化（content_pipeline 232 WAV、qa_pipeline 543+16 passed） | 提交 67 文件 6679 行；master → `2a76a82` | 09-17~09-19 |
| **musickit remix** | `/repos/musickit` | 每小时随机风格混音自动化三轮迭代：v1 内置随机 → v2 提示词驱动（跑偏被纠）→ v3 回归 `--remix`，叠加 `--mixer-style` / `--fusion` / 发布安全默认关 | ACTIVE，FREQ=HOURLY，id `08a8fee6-…`；实测 120.03s | 09-16-19-58-06 |
| **foolproof-operation** | `/repos/foolproof-operation` | 「🔍 自动发现」601 包归类：15→25 分类、764→760 条目；修 httpx/aiohttp 同名覆盖、CLI 忽略 value、路径型 value；`shlex.split` 自适应；接入自研包 alloy/bloodmusic | 25 分类/761 条目 | 09-19-21-14-30 |
| **novel-down** | `/repos/novel-down`（siwpan，**main**，公开 MIT） | 从 v0.1.0 建成 → 建仓推送 → 迁入 G:\repos；接入正版/免费镜像站约 20 个；字体反爬破解；镜像站批量铺开（族规则流水线）；出版读物线（虚阁网/国图古籍 OCR）；Tkinter GUI；发行版 + 审计整改 | **v0.8.40**；测试 85→**353**；规则 161（启用 146）；门禁 11 PASS + 自检 11/11；release id 1158890/1158945/1159011 | 09-20-10-38-43 全档、09-22-08-41-13 |
| **综网废柴逆命**（小说） | `/local/write/综网废柴逆命`（起点中文网） | 37 轮：设定提取 → 三大框架重构 → 第一卷 21 章完成**冻结** → 第二卷《第 9 个》开工（楔子+01/02/03 章）；行业趋势/外部点评对照；竞品调研 | 第一卷 **51,691 字**冻结；第二卷连载中 | 09-20-07-08-27 全档 |
| **webcopier** | `/repos/webcopier` | 诊断 `F:\Python314` 环境大规模损坏并修复（**非项目代码问题**） | 5 种提取方式 + GUI/全模块导入 + tkinter 全通过 | CodeBuddy 09-20 |
| **DSH 本地部署** | `/notpython/deepseek-harness-master` | 修复 npm arborist 空版本 bug；重打 WinError 448 补丁；`start-dsh.bat` 改直调 bin | `npm install --legacy-peer-deps` 装 428 包(35s)；3080 HTTP 200；PID 14120 | 09-22-10-54-28 |
| **环境/系统（CodeBuddy）** | 本机 | wuauserv 无限重试（DACL 被锁）修复；Windows Terminal 报错弹窗定位；「反复弹窗」排查（迅雷插件/QQPCTray/explorer） | 修复验证通过 | CodeBuddy 09-18/09-19 |
| **环境（WorkBuddy）** | 本机 | Bash 工具 `command not found` 根因（非 login PATH 缺 /usr/bin）→ shim 补丁 + 计划任务自愈；批量文件删除源排查（9/17-9/18 三次删 .git refs/32 个 .py/site-packages） | 已修复；唯一嫌疑=腾讯电脑管家 18.2.30823.301 | 09-16-21-52-29、09-19 |

---

## 二、关键事实（可复用）

**播放器簇**
- PluginPlayer：FFmpeg **9.0.1** + SDL3 **3.4.16**；`g++`=`/mingw64/mingw64/bin/g++.exe`（GCC 16.1.0，不在 PATH）；控制通道 TCP `127.0.0.1:7911`（换行分隔 JSON-RPC，auth 必须是第一条消息，token ≥16 字符）；Web 控制页 7912（默认关）；`--write-dir` 白名单；`--hidden` 无人值守；默认不推事件，须 `topic.subscribe`。
- 控制通道每帧抽干一次 → RPC 往返 **p50≈16.6ms（≈1 帧@60fps）**，逐帧驱动不可行，UI 按 ≥100ms 节流。
- FFmpeg 9.0.1 ABI：avutil 61.1.101 / avcodec 63.1.101 / avformat 63.1.101 / swscale 10.1.101 / swresample 7.1.101 / avfilter 12.1.101。
- SDL3 3.4.16 无 `SDL_SetTextureColorSpace`（只能建纹理时给），NV12 纹理默认 `SDL_COLORSPACE_JPEG`（全范围 BT.601）。
- players-unified 端口：launcher **7920** / host web **5000** / pluginplayer HTTP **7913**、控制 RPC **7911**。
- 形态澄清（用户更正）：`localplayer` = Chrome MV3 扩展；`PluginPlayer` = 「cordis 独立应用」，**不是**网页插件版；`daily_player` = libVLC 桌面端。
- 打包口径：`build.py --release` 由 17 文件/127MB → 54 文件/146MB（加 libass 32 DLL）→ **55 文件/145.6MB**；payload 由 `gen_third_party_notices.dist_payload()` 决定，改依赖须重跑并同步 README；`dist/build/vendor` 均 `.gitignore`。

**引擎与包**
- Cordis 成套版本：仓库钉 `cordis ^4.0.0-rc.9` + `plugin-loader ^1.0.0-rc.6`；npm 最新 rc.10 要求 plugin-loader ≥1.0.0-rc.7；Cordis 核心平台中立（依赖仅 cosmokit + @standard-schema/spec）。
- pytest（audio-generation）须从 `/Python314/Lib/site-packages`（junction）跑；禁 `--basetemp`（Windows 假 11 errors）；关 `hydra_pytest`/`langsmith_plugin`/`pytest_aiohttp` 三插件；ruff 用 `pip download` + `zipfile.extractall` 取 ruff.exe。
- pytest 收集错误 **583→0** 根因 = flat 包根（连字符非法包名）× Package 收集器；修法 = 根/album_maker `__init__.py` 加 `__package__` 守卫（`c2e9464`）。
- PyPI 名称永久占用：`alloy` 已被 Elide 占用 → 改名 `allin-engine`；`bloodmusic` 404 可注册。
- foolproof-operation `_pypi_exists()` 会跳过 PyPI 404 的包 → 纯自研包（bloodmusic）天然不被全盘收录；`alloy` 混入因 PyPI 有同名他项目。

**混音/音频**
- 混音时长公式 `bars = round(target_sec*bpm/240)`；BPM 取偶数 → bars=bpm/2，精确 120s；实测 1.83MB/22.3s。
- `F:\Python314`（3.14.7）是**唯一带 tkinter** 的环境；其 pip 写盘/解包/卸载会卡死 → 脚本只做导入检测不装包；bloodmusic 可导入靠 junction + `.pth`。

**novel-down**
- 版本链 v0.1.0(`4340f79`) → **v0.8.40(`caa5acc`)**；番茄字体反爬：54% 汉字换 PUA，字形轮廓匹配 **362/362 码位 100% 覆盖**，随仓索引 `sourcehan-sc-2.002.bin` **470171 字节**（须严格 2.002R）。
- 发行版实测：CLI onedir **35MB/启动 1.4s**、onefile **18.6MB/启动 47s**（非冷启动）、GUI onedir 41MB、zip 18MB。
- 镜像漏斗：书源 31526 → 唯一域 10574 → 覆盖 **392 域**；「未确认域」重扫救回率 8.1%~41%。
- 出版读物：虚阁网《红楼梦》**121 章/850,277 字/188s**；国图古籍库《繡像西遊記》API 链 129 页/3224×3009；OCR 最优 = 切半页 + 逆时针 90°（隐含字准 41%/43%），GOT-OCR2_0 VLM 持平（44%）。
- `identities.json`（674KB / 1373 条）为**合成 UA 指纹、无 PII**，可随公开仓分发。

**小说**
- 第一卷 21 章 **51,691 字**（签约门槛 2 万）；去 AI 味：破折号 328→14（密度 17.2→0.7/千字）；第二卷楔子 3254 字、01 章 2654、02 章 2878、03 章 3516。

**系统/环境**
- 「黑框一闪 + 报错」真身 = Windows Terminal 报错弹窗（`defaultProfile` 指向已搬走的 pwsh + 手写项带 `source`）；Fragment 须 UTF-8 **带 BOM** 且放子目录。
- 诊断弹窗利器：空闲关联法（`GetLastInputInfo`，<1.5s=USER / >5s=AUTO）+ `SetWinEventHook` 事件驱动钩子（无采样盲区）。
- wuauserv 7023 + DCOM 10010 同节拍 = 服务启动失败重试环；`tracerpt *.etl -o out.xml` 可读 `*FAILED*[code]`。
- 端口记录（CodeBuddy MEMORY）：DSH Web `127.0.0.1:3080`、npm 镜像 `127.0.0.1:8899`、12test Web `localhost:3210`、PluginPlayer 控制 `7911`。

---

## 三、教训与坑（可复用）

**工程/工具类**
1. **`.git` 对象库事故**：删 `.git/index` + 只 `add` 部分路径 + commit = 一次批量删除；重建索引用 `git reset --mixed <commit>`；PowerShell 写 refs 带 CRLF → 用 `git update-ref`；`expire reflog` 再 `gc` 才清 blob。
2. **子进程 stdout 不能用 PIPE**（>4KB 阻塞起不来）→ 重定向文件；冷启动（11 插件 + 字体）可达 10s+，等端口给 40s。
3. PowerShell：子进程非零退出被当终止错误（`$PSNativeCommandUseErrorActionPreference` 固定置 `$false`）；中文乱码加 `[Console]::OutputEncoding=UTF8`；`$LASTEXITCODE` 会被管道覆盖；`.ps1` 正文**绝不含中文**（PS 5.1 按 GBK 解析）；内联 `$var` 被外层 shell 吃掉 → 写脚本 `-File` 跑。
4. **判断「是否分叉」先归一化换行符/BOM**；`1,470c1,470` 全行不同 = 换行符差异特征。
5. `git rm -r` 只删被跟踪文件，`__pycache__` 残留会让 `git mv` 移成子目录；`git mv` 前用 `os.path.isdir` 确认目标不存在。
6. `git add -A` 前先看 `??` 数量（构建残留会一并入库）；`mv` 绕过删除限制须同步 `.gitignore`。
7. 仅删 package-data 无效（pyproject 下 `include-package-data` 默认 True）；`*.egg-info/SOURCES.txt` 缓存致三次构建字节数一模一样，须 `rm -rf *.egg-info build` + `--no-cache-dir`。
8. 全局替换后**先看被替换的函数体**（`applyState` 递归→挂死 180s）；判据读的变量须与赋值同序（NV12 纹理每帧重建）。
9. 判断 CVE 是否影响依赖要看**该 CVE 自己的 affected range / fixed version**；发行版公告的 CVE 列表 ≠ 受影响集合；能拿源码就直读确认修复。
10. libass 0.17.5 **严禁** `ass_add_font` 内存字体（0xC0000005），用 `ass_set_fonts_dir` + `ASS_FONTPROVIDER_AUTODETECT`；字体真实 family 名以 name 表为准。
11. 生成的报告提交前问「**能否重跑复现**」，不能就默认不写盘（闸门 `PU_REPORT=1`）。
12. Bash 工具基本不可用（缺 dirname/head/tail/wc/ls）时，跑 git 一律不加管道，推送后用 `git ls-remote` 核验。

**平台/接口类**
13. **Gitee 建 release 不带 `target_commitish` → 400**；**附件上传路径漏 `/api/v5` → 返回 404 HTML、静默失败**（本次靠手工调一次接口才定位）；`assets` 无 `id` 字段，**重传同名会并存** → 正确做法是删整个 release 再重建。
14. Gitee 平台坑：单附件 100MB / 总 1GB；`PATCH /repos` 必须带 `name`；`GET /releases/tags/{tag}` 不存在返 200+null；建仓 `auto_init:false`；发布页源码包链接非直链。
15. 令牌用法：`https://<账号>:<令牌>@gitee.com`（令牌放密码位；`<令牌>@` 会被当用户名而失败）；`credential-store store` 会崩（exit 128）→ 用 `-c credential.helper=`，用完 `git remote set-url` 还原无令牌。
16. 端口治理：8000 曾被本机策略禁（bind 10013）→ 用 `PORT=8760` 绕过（`cordis.yml` 支持 PORT 覆盖，不改文件）。

**审计/测试/流程类**
17. **「测试全绿」≠「这条路能跑」**：加代码漏 import，pytest 全绿没发现（因为没用例走该路径）；新增测试时要问「这条路径之前有人走过吗」。
18. **同一个坑（漏 import）连踩三次**（engine 漏 `RuleError`、cli 漏 `BrowserUnavailable`、http_client 漏 `import re`）→ 补 `tests/test_imports.py` 烟雾测试（逐个 import + 断言异常类可见）。
19. **不采纳审计建议的正当情形**：删 `freeguard.startswith(denied)` 会让「相似域名绕过」拦不住——**政策名单 fail-closed ≠ 规则匹配必须严格**，两处语义不同是有意的（测试比审计更懂既有意图）。
20. 门禁过度声称：`HARDCODED_PATH_RE` 的 `\b` 对 `F:/Python314` 一直失效（`\b` 前后都是 word 字符）→ 改用负向先行断言。
21. 自检用例写错比门禁坏掉更难发现 → 教训写进代码注释。
22. **批量删除须先定位唯一分类再删**，删完用「对比备份找丢失包」断言兜底（httpx/aiohttp 曾整组误删 4 条）；判定用取证（联网核验），不按「名字眼熟 / PyPI 可查」。
23. pip 名是全局命名空间：自研包与公开包重名会装错，须区分「本机装什么」vs「这名字解析到谁」。
24. **报数前先核对口径**：deep 结果「通过 0 个」等结论必须先分离「工具缺陷」与「真实结果」。
25. 文件放错位置会让外部评审得出错误结论（小说楔子误摆成全书开篇即一例）。

**创作类**
26. 「随机风格」≠ 提示词驱动——用户指的是 `--remix` 内置随机；跑偏两次后回归主路径。
27. curl 返回 000 ≠ 死站（requests 与 curl TLS 栈不同；已踩三次）；回收站在 C 盘，「删到回收站」不释放空间。

---

## 四、未闭环待办汇总

**仓库/技术**
- `pluginplayer`：#35 保留完整路径（按设计）、#27 补文档收口不重构 ABI；`host-js/package.json` 死依赖 `@cordisjs/plugin-loader` 有意不删（npm install 会重解析到 rc.10）。
- `players-unified`（非阻塞未做）：S2 单窗口嵌入（需 C++ `SDL_CreateWindowFrom`）、播放列表 UI 侧自建、分发带预编译 exe；`localplayer` 引 Cordis/MediaMTX 判定不成立已搁置。
- `localplayer` 浏览器实测量子：侧栏/全页打开、WebRTC 投送、`/remote` 双音频、offscreen 直连 WS 是否被拦（多数已迭代，最新状态见 v1.3.4）。
- `image-scraper`：`pixabay_video` 沙箱代理不通得 0（真机直连可用）；midjourney 需代理 + 已登录 cookies。
- **inline 副本字体问题**：`allin-engine` 字体需用户自备（`%APPDATA%\allin_engine\fonts`）；5 个内联副本项目字体同样未随包分发；**字体仍在 git 历史里**，彻底消除需重写历史（破坏性，未做）。
- `foolproof-operation`：`requirements.py` 已删改 `.pyw`，`D requirements.py / ?? requirements.pyw` 当时未提交。
- `novel-down`：镜像线残留（`gen_family_rule` 的 `_reject_reason` 对英文域名/路径无效）；出版读物 OCR VLM 路线搁置（重开须指定书目 + 逆向 guji.nlc.cn + 重写分篇规则）。
- 三播放器整合：CodeBuddy 侧 `/local/players-unified` 当时仍「仅规划不执行」，与 WorkBuddy 侧 `/repos/players-unified` 已实施为**两条线、路径不同**（需合并口径）。

**创作**
- 综网废柴逆命：第二卷 04 章起继续连载；第一卷 4 处悬空伏笔留第二卷回收。

**系统**
- Windows 更新（09-19）安装失败 `0x80073D02/0x80240016/0x800706BE` + AppXSvc/TiWorker 各崩一次 → 未处理。
- QQPCTray SideBySide ID=78 兼容性 bug（升级/删 Run 项/卸载三选一未拍板）。
- 迅雷浏览器接管插件 `xl_ext_chrome` 每分钟自起进程（是否禁用/卸载未决定）。
- Intel 核显驱动 31.0.101.2125（2023-05-24）偏旧，TDR（LiveKernelEvent 141）备查未处理。
- Windows Terminal 修复需用户亲验（修复前曾有一次复现未弹，间歇性）。

---

## 五、与 G 盘治理相关的事实

- **Gitee 公开仓（新增/活跃）**：`pluginplayer`(main, v1.0.0)、`players-unified`(master, v0.1.0~v0.8.0)、`localplayer`(master+develop, v1.3.1~v1.3.4)、`novel-down`(main, v0.8.40)、`daily_player`(v1.0.0)、`santi-teleprompter`(v1.1.0)；`private-radio-stations` 推出 apps/video 特性（master=b6de97a）。
- **PyPI 正式发布（不可逆公开）**：`allin-engine 1.0.0`（3.38MB）、`bloodmusic 2.0.0`（0.47MB），`twine check` PASSED。
- **许可证口径**：`pluginplayer` dist 为 **GPLv3 衍生作品**（FFmpeg gyan.dev full_build 标 GPLv3，LICENSE SHA-256 与源码 `COPYING.GPLv3` 一致）；SDL3=zlib、cordis/plugin-loader=MIT；当时决定「本机自用暂不加 LICENSE，一旦对外分发须先补 GPL 兼容许可」——**注意：本轮实测其远端仓 LICENSE 存在（HTTP 200）**，实际许可文本需另行核对。
- **仓库结构**：`players-unified` 为三端物理合并 **monorepo**（复制非移动，原三仓未删）；`.githooks/pre-commit` 可选钩子对齐 DSH lefthook。
- **令牌**：gitee 令牌从 `G:\私人令牌.txt` 读入环境变量，不入命令行历史/remote URL；该文件另存正式 PyPI 令牌与 TestPyPI 令牌；**PyPI 恢复码**落盘于 `G:\PyPI-Recovery-Codes-siwpan-*.txt`、`G:\TestPyPI-Recovery-Codes-siwpan-*.txt`。
- **第三方源码不入仓**：novel-down 侧记录 `backupqidian` 无 LICENSE（按「保留全部权利」）、`novel-spider` GPL-3.0 不入仓、`stealth.min.js` 评估后未分发；书旗正文加密 = 红线；bilibili-helper 复用登录态 = 红线不借鉴。
- **环境**：`F:\Python314` 唯一带 tkinter；`G:\local`（本地项目区）与 `G:\repos`（Gitee 推送区）分区约定；DSH `start-dsh.bat` 直调 `bin.js`，3080。

---

## 六、与 2026-09-22 三线核对的交叉印证

| 本汇总条目 | 本轮核对结果 |
|---|---|
| `private-radio-stations` 推 master=`b6de97a`（09-14 记录） | ✅ 本地 HEAD 确为 `b6de97a`，但**远端已领先 16 提交**（09-14~09-22，含卫星影像特性），本地记忆**无对应记录** → 归属待确认 |
| `pluginplayer` v1.0.0 推 main | ⚠ 本地落后远端 2 提交（09-14 tonemap Phase 2 等） |
| `santi-teleprompter` v1.1.0（09-21 远端） | ⚠ 本地 `/repos/santi-teleprompter` **无 `.git`**，含 2 处未推送依赖改动（详见《gitee本地核对报告_2026-09-22》§四） |
| 记忆中的端口（3080/8899/7911/3210） | ✅ 3080、8899 实测 LISTEN（PID 14120 / 22684 与记录一致）；7911、3210 当前 FREE（按需启动） |
| `dict-scene-engine`（G:\repos，09-06~09-08 线） | ✅ 目录存在，且有 8 项未提交改动（README/package.json/tests + 3 个 scripts） |
| registry 与仓覆盖 | ⚠ `musickit`/`players-unified`/`localplayer`/`pluginplayer`/`novel-down`/`dict-scene-engine`/`santi-teleprompter` 均**未登记** platform registry |

---

*汇总生成：2026-09-22 ｜ 逐条可回溯到具体 memory 文件与行；本文件为新增，不改动任何既有备份。*
