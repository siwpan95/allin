# SPEC-004 · 调试铁律（1–62）

> **编号** SPEC-004 ｜ **效力** 纪律（事故驱动沉淀，代价可量化） ｜ **状态** 生效
> **生效** 2026-08-24 ｜ **最后修订** 2026-09-27 ｜ **适用面** 本工作区全部工程操作（PowerShell / Python / git / 门禁 / 盘与文件系统）
> **承载体** 逐条见 `规范/README.md` §4.1–4.2 的「规则 → 门禁映射」；未机械化者在表中标注为流程纪律
> **引用格式** SPEC-004 §调试铁律 19

---

## 调试铁律（2026-08-24 自 Cordis 贪吃蛇实验沉淀）
1. **inject 守卫**：Cordis Service/plugin 在事件回调里访问 `ctx.xxx`（哪怕是别的 service）必须在 `static inject` 声明，否则运行时抛 "without inject"。
2. **同帧抢占**：手动 set 状态但运行时无效，先查是否有同事件的其他监听器在同帧抢占（如 AI 驱动在 tick 时覆盖手动方向），不要直觉甩锅给输入校验。
3. **HMR 正确姿势**：Fiber.dispose/update + provider 级联重载 + fs.watch；core rc.8 不自带文件监听器（@cordis/loader 才带）。
4. **重开叠加泄漏**：reset 类路径重应用前必须先回收上一轮监听器/定时器（时间可组合逆操作）。
5. **工具可靠性铁律（agent 协作层）**：命令工具通道持续报错时，立即停止重试同一招；改用 Write/Read/Edit 完成能离线做的事，并诚实告知用户"请本地验收"，不假装再试。
6. **大文件文本处理（2026-08-28 沉淀）**：PowerShell 5.1 对 50 万行级文件用数组 `+=` 逐行过滤是 O(n²)（120s 超时被杀）——一律 [IO.File]::ReadAllText + [regex]::Replace；git 的 stderr 信息输出在 `2>&1` 下会被 `$ErrorActionPreference='Stop'` 误判为异常，逐条 git 调用要包 Continue。
7. **未跟踪文件审计口径（2026-08-28 沉淀）**：git status 里的未跟踪文件不全是构建产物——G:\ 曾发现 18 个「从未入过任何仓库」的真源码（README 已描述它们为入口/主程序）。.gitignore 治理前必须先分类核验：非产物未跟踪 = 潜在资产，逐件判「入库 / 忽略 / 归档」后再动手，判据看 README 与代码引用。gitignore 无前导斜杠的 `build/` 可全深度匹配嵌套产物；git status 对非 ASCII 目录输出 core.quotepath 转义（`?? "\346\234\254\345\234\260/"`），匹配前先去引号/反转义。
8. **PowerShell 变量大小写不敏感（2026-08-28 沉淀）**：`$R` 与 `$r` 是同一个变量——`$R='G:\repos'` 后 foreach 用 `$r` 会静默覆盖它（整批 git 路径错乱成「仓名\仓名」）。变量命名必须超大小写区分；批处理脚本先跑 1 个样本验证路径再全量。
9. **隐藏目录搜不到 ≠ 没有（2026-09-22 沉淀）**：ripgrep 系搜索默认跳过隐藏目录——`.workbuddy` / `.codebuddy` / `.git` 里的内容搜不到，「No matches」是**假阴性**。搜 memory、隐藏工作区、`.git` 配置必须用 PowerShell 显式遍历（`Get-ChildItem -Force -Recurse`）。
10. **PowerShell 条件表达式不能直接塞进参数位（2026-09-22 沉淀）**：`("... {0}" -f (if($x){'A'}else{'B'}))` 会让**整条语句失效**；叠加 `$ErrorActionPreference='SilentlyContinue'` 时连报错都被吞，只表现为「那一行没输出」。必须先赋值到变量，或用 `$(...)` 子表达式。
11. **TrimEnd 字符陷阱 + 全树扫描超时（2026-09-22 沉淀）**：① `'\\'` 在单引号里是**两个字符**，`.TrimEnd('\\')` 抛 `String must be exactly one character long` —— 用 `[char[]]@('\')`；② 递归 `Select-String` 扫 `G:\repos` 全树（11 万+ 文件）会超 120s 被杀，定向搜索一律用 ripgrep（grep 工具），别用 Select-String 全树。
12. **跨副本比对必须先归一化换行符（2026-09-22 第二次踩到，与 09-19 同源，已固化为动作）**：`santi-teleprompter` 本地副本初判「25 个文件内容不同」，归一化 CRLF/LF 后**真差异仅 2 个**（package.json / package-lock.json）。动作固化：**字节哈希只用于「发现候选」，下结论前必须做 EOL/BOM 归一化文本比对**。
13. **对比脚本的主键必须是 origin 仓名，不是目录名（2026-09-22 沉淀）**：本地目录名可与远端仓名不同（`G:\platform` ↔ 远端 `allin-platform`），以目录名为主键会漏配、导致总账不平（本次曾复现「116 ≠ 117」）。凡做「本地 ↔ 远端」对账，先由 `git config remote.origin.url` 解析出仓名再匹配。
14. **DSH 会话内验证 Electron 会被 `ELECTRON_RUN_AS_NODE` 污染（2026-09-22 沉淀）**：本 harness 给子进程注入 `ELECTRON_RUN_AS_NODE=1`（**仅 Process 作用域，User/Machine 未设**），此时 `electron.exe --version` 打印的是内嵌 **Node** 版本（Electron 30 → `v20.16.0`）而非 Electron 版本，极易误判「装错版本」。验证 electron 必须 `Remove-Item Env:ELECTRON_RUN_AS_NODE` 或直接读 `dist/version`；同理，**在 DSH 会话里启动任何 Electron 应用前都要清掉该变量**，否则应用会以 Node 模式运行。
15. **npm 重装大依赖会挂起（2026-09-22 复现）**：`npm uninstall electron` 在本机跑 13 分钟零输出（同「Node undici 大 tarball 不可靠」根因）。**外科式替代**：保留 `node_modules/<pkg>` 与声明，直接跑该包的 `install.js`（electron 从其 `%LOCALAPPDATA%\electron\Cache` 解包），10s 完成且不用动依赖树。
16. **仓内 pre-commit/pre-push 门禁在 DSH 沙箱里会「假红」（2026-09-22 沉淀并已实证，private-radio-stations）**：钩子形如 `#!/bin/sh` → `node scripts/check.mjs --fast`，而 check 内部对每个文件再 `spawn('node')` 做语法检查——**沙箱禁止管道 stdio 的子进程**，于是逐文件报 `x syntax: …（node 无法执行：node；EBUSY）`、整体 `check FAILED: 60`，**极像「代码全坏」**（该仓 pre-commit 与 pre-push 各拦一次）。处置动作：① 用 PowerShell 逐文件 `node --check` 独立复核（本次 78/78 全绿）；② 据实以 `git commit --no-verify` / `git push --no-verify` 完成，并在**提交信息与交接文档里写明理由与证据**；③ 请用户在正常终端复跑门禁。**实证**：用户复跑 `npm run check` → **`check PASSED`**（syntax/cordis.yml/package.json/whitespace/unit tests 全绿），确认是环境边界而非代码缺陷。**结论：不要把沙箱边界当成代码缺陷去改代码。**
17. **PowerShell 变量名含 `?` 的静默 URL 陷阱（2026-09-22 沉淀，gitee API 实测）**：`"$repo?access_token=$tok"` 里 `?` 是**合法变量名字符**，PowerShell 会把 `repo?access_token` 当成**一个变量名**（未定义→空串），URL 静默变成 `…/repos/siwpan/<token>`，接口返回 **403 Forbidden**——报错完全指不到真因（看着像 token 失效或接口被封）。**规则：字符串里变量后紧跟 `?` `-` `:` `=` `.` 等字符时一律写 `${var}`**。本次 85 仓社区指标采集因此 100% 失败，加 `${}` 后同一端点立即正常。附带：**别用 `powershell`(5.1) 去跑 pwsh 写的无 BOM UTF-8 脚本**（中文路径会烤成乱码、报「Cannot find path」）——用 UTF-8 存脚本、并统一用 pwsh 执行。
18. **批量正则改文档必须先 dry-run（2026-09-23 沉淀，85 仓 README 去本地化实测）**：把 `X:\…` 批量替换成占位符时，字符类的**排除集漏一个字符就吞掉正文**——本次两处实证：① 未排除全角 `（` → `/allin/docs/x.md（2026-08-25 用户拍板…` 被吃成 `<PATH> 用户拍板…`；② 未排除反引号 → `` `/allin/docs/x/ports.yaml` `` 的**收尾反引号被一并吃掉**，行内代码块破掉。另：尾部加 `(?<![\\/])` 防尾随斜杠反而让单独的 `G:\` 漏替换 → 改为替换后再清理 `<PATH>\`。**铁律：批量文本改写一律先 `-DryRun` 打印 before→after 样本，且排除集必须含 `（）「」《》【】、，。；：？！—=*` 与反引号/引号/尖括号/竖线**；改完必须回扫残留数 = 0 才算过。
19. **改多仓时只 `git add <指定文件>`，绝不用 `git add -A`（2026-09-23 实证价值）**：批量改 85 仓 README 时，`foolproof-operation` 当时正有另一路会话在做 Cordis 架构重构（工作区里 `core/ plugins/ index/ tests/ docs/` 均为未提交在建内容）。因为脚本只 `git add README.md`，84 个提交**逐一核验均只含 README.md**，零卷入他人在建工作。**凡在多仓并发环境下操作，逐文件 add 是硬纪律**；提交后再用 `git show --name-only HEAD` 回扫确认提交面。
    - **状态订正（2026-09-23 晚，避免后期会话误判）**：上条括注描述的是**当时那一刻的工作区状态，不是长期并行常态**。该 Cordis 重构按阶段推进，**阶段 0~5 已于 2026-09-23 当日完成**（阶段 6 文档/推送待做）；工作树**仍未提交、未推送**。后期会话读此条时**不要假设还有另一路会话在改该仓**——如需接手，先 `git status` 看实际工作区，再按 `/allin/docs/md/allin主工作区/USN索引与Cordis内核规划_2026-09-23.md` 的阶段表核对真实进度（该规划文档的阶段勾选即事实源）。

20. **PowerShell 函数禁用 `$args` 当参数名（2026-09-23 沉淀，代价一次 600s 超时 + 一次误判）**：`function Run($label, $args)` 里 `$args` 是**自动变量**（未绑定参数数组），声明为形参后 `& python script.py @args` 会 splat **空数组** → 实际执行 `python script.py`（无参数）→ **启动了 tkinter GUI**，进程永不退出，批处理被 600s 杀掉且**零输出**。当时误判为「`cli envs --backend walk` 全盘遍历挂死」，实测证明 walk 与该超时无关（无根时 0.00s 返回空），**结论已回头更正**。**纪律**：① 形参禁用 `$args`/`$input`/`$PSBoundParameters`，改 `$cmdArgs`；② 批处理每条命令都要有超时与回声，出现「零输出 + 超时」先怀疑脚手架本身；③ 误判必须回头纠正结论，不得让错因留在文档里。
21. **SQLite 的 `IN (…) COLLATE X` 用不上 `COLLATE X` 索引（2026-09-23 沉淀，foolproof-operation）**：批量等值查询写成 `WHERE name IN (?,?,?) COLLATE NOCASE` 会退化为**全表扫描**（实测 251 万行 **355ms**），改成逐项 `name = ? COLLATE NOCASE OR …` 才命中索引（**2.0ms，快 177 倍**）。**纪律**：有索引 ≠ 用了索引——关键查询必须实测 `EXPLAIN QUERY PLAN`，并把「不出现 `SCAN <表>`」**锁进测试**，防止日后被「简化」回去而性能静默劣化。
22. **把 `PYTHONWARNINGS=error::ResourceWarning` 当作黄金值跑一次（2026-09-23 沉淀，foolproof-operation）**：它能抓出「功能正确但资源泄漏」的静默缺陷——本次抓到 ① `IndexStore.open()` 自建连接却按「外部传入」判所有权，导致 `close()` **从未真正关闭连接**（被 WAL + 每批 commit 掩盖，长跑持续泄漏句柄）；② 测试代码里 `open(...).write(...)` 的句柄泄漏；③ 打开失败路径不回收连接。**纪律**：资源所有权必须显式声明；泄漏类缺陷靠「告警升级为错误」暴露，不要指望读代码看出来。
23. **PowerShell 做批量文本改写有两个会「写坏文件」的陷阱（2026-09-23 沉淀，各踩一次）**：① **单元素嵌套数组会被展平**——`@{ pairs = @( @('A','B') ) }` 取到的是 `@('A','B')` 两个**字符串**，于是 `$pair[0]` 变成字符串首字符、`$pair[1]` 变成第二个字符：本次把 `'plugin="plugins.installer:…"'` 的 `$pair[0]/[1]` 取成 `'p'/'l'`，**全文件 p→l**（"pip" 变 "lil"，410 处），文件损坏；**多元素数组不会展平**，所以同样的写法在另一处正常——这种「时对时错」最容易骗过人。② **`[IO.File]::ReadAllText/WriteAllText` 用的是 `Environment.CurrentDirectory`，不随 PowerShell `Set-Location`/`cd` 变**——相对路径会落到启动目录（本次落到工作区 `G:\job`，报「找不到路径」而替换计数显示 0，看着像「没匹配」实为「读的不是那个文件」）。**纪律**：批量改写一律 **Python 脚本 + 绝对路径**（Python 无展平、无 CWD 歧义），并坚持 dry-run 报计数 + 改后立即 `py_compile`/跑测试（本次正是靠 `py_compile` 与测试数量从 271 掉到 241 才发现）；**改文件前后用 `git checkout -- <file>` 兜底恢复**。
24. **`.Replace` 计数放大的信号**（2026-09-23 同上）：批量替换后若「处数」远超文件里该字符串的合理出现次数（本次 410 处），**立刻停下看现场**，不要继续往后续文件跑——这是类型/展平错误的典型指纹。

> 理论面见同目录《Cordis 理论笔记.md》；最小可运行样例见 /notpython/cordis-snake-example（selftest 41/41）。

25. **PowerShell splat 单个字符串会按「字符」展开（2026-09-23 沉淀，代价 5 仓提交静默失败）**：`[string]$files = (git status --porcelain ...)` 在**只有一行**输出时是标量字符串，`& git add @files` 会把它按字符拆成 `s` `c` `r` `i` `p` `t` `s` `/` … 逐个当参数（git 报 `fatal: /: '/' is outside repository`）；`$files[0]` 同样只取到首**字符** `'s'`。多行输出时是数组，所以「时对时错」。**纪律**：一律写 `[string[]]$files = @(...)`；取元素前先看 `$files.GetType().FullName`。**同一族的第二个坑（本轮同时踩到）**：循环里 `& git commit ... | Out-String` 会把 exit code 与失败输出一起吞掉，只打印「On branch master」——**判定提交/推送成功不能看有没有报错，必须核对 `git log -1` 或 `@{u}..HEAD` 是否真的变化**。
26. **判「路径是否已失效」的扫描器有三个必须堵的漏（2026-09-23 沉淀，硬编码去本地化实测）**：① **只对 MUST_FIX 行判死会漏掉赋值型行**（`MUSIC_ROOT = Path(r"/radio/music")` 被判 LIKELY_FIX，从未进 T1 清单，audio-separator 一仓就漏 25 处）；② **转义双反斜杠写法判活**——源码里 `"//allin//not//OK"` 取「前两段」得到 `D:\`，而 `D:\` 存在，于是**死路径被判成活的**（py_test_runner/fish 共 19 处）；③ 死根清单若取自①的产物，则清单外的死根（`G:\csmusic*`）永远查不出。**固化口径**：对**全量命中**判死 + 分隔符容错 `[\\/]{1,2}` + 系统路径白名单 + 命中按「CODE 有效行 / CODE 注释行 / DOC·CFG」三分，只有 CODE 有效行算阻断项。
27. **多行字面量替换必须先归一化 EOL，且 here-string 的闭合符不能与其他 token 同行书写（2026-09-23 沉淀）**：CRLF 文件里用 LF 拼的搜索串 `.Contains()` 恒假（静默「未命中」）；`@'...'@.TrimEnd()` 这种「闭合符 + 方法调用同行」写法会让解析器把后续行吞进字符串。**纪律**：批量替换统一走「先测文件 EOL → 把搜索/替换串的 `\n` 换成该 EOL」，here-string 一律先赋值给变量再使用；替换后**必须** `py_compile` / 跑测试，且核对「替换处数」是否与预期一致（计数异常 = 有东西被吃掉）。

28. **发布链路三个坑（2026-09-23 沉淀，foolproof-operation 首发 PyPI 实测）**：① **第三方 CLI 的富文本进度条在 GBK 控制台直接崩** —— `twine upload` 的 rich 进度条输出 `•`（U+2022），默认 936 代码页抛 `UnicodeEncodeError` 且**上传中断**（与本地 CLI 的 emoji 崩溃同源）。动作：跑 twine/pip 等带富文本输出的工具一律 `PYTHONIOENCODING=utf-8` 并加 `--disable-progress-bar`。② **验证「安装后的包」必须在源码目录之外运行** —— 在仓库根执行 `python -c "import foolproof_operation"` 命中的是**本地源码树**而非刚装进 venv 的副本，读出正确版本是**假绿**（当时安装其实失败了）。动作：先 `cd` 到源码目录之外，并打印 `模块.__file__` 作为证据。③ **刚上传后索引有 CDN 滞后**：TestPyPI/PyPI 的 `/simple/` 页面可能仍列旧版本（本次 2 分钟内 pip 只看到 1.1.0，而 JSON API 已列出 1.1.1）。动作：以 `https://<index>/pypi/<pkg>/json` 判断上传成功，并**按上传产物的直链 URL 安装验证**；**索引未刷新时绝不重复上传同一版本**（同名版本不可重传）。
29. **PowerShell 通配符不展开给原生命令（2026-09-23 第二次踩到）**：`python -m py_compile core/*.py` 把**字面量** `core/*.py` 传给 Python → `py_compile exit 1`，看起来像「代码编译失败」。动作：用 `Get-ChildItem ... -Recurse | ForEach-Object { $_.FullName }` 收集绝对路径再 splat（与第 11、23 条同族：PowerShell 的参数传递语义必须按「它实际传了什么」验证，而不是按意图推断）。

> **本轮事实补充（2026-09-23，硬编码去本地化第 1 批）**：
> - **MIDI 素材库**：原 `G:\midi` 已不存在；4 个 `*_130406` 现存 `/notpython/MusicStudioPro/Data/MIDI`，2026-09-23 已**复制**回 `/repos/midi/pro4/MusicStudioPro/Data/MIDI`（`pro4/` 在 `.gitignore`，不进库）。合并后 `scan_midi_assets(/repos/midi)` = 6 素材齐，audio-generation 的 bridge 测试由「永远跳过」变为 **55 passed / 0 skipped**。
> - **`bloodmusic` 是 junction**：`/Python314/Lib/site-packages/bloodmusic` → `/repos/audio-generation`，仓内改动对全局解释器立即生效（无需 pip 重装），改坏即污染所有调用方。
> - **素材归位地在 `/assets/`**（2026-09-23 实测）：`radio_music_stems`、`csmusic_stems`、`csmusic`、`yasuobao`、`musicdown`、`fonts`、`musickit_transcode`、`radio_special_instruments`、`transcode_work`。原 `/music/*`（radio_music_stems / csmusic_stems / yasuobao）、`G:\midi` 等顶层分类目录均已不存在；musickit 与 audio-separator 的 stem/归档默认值现指向这里（可被 `STEMS_ROOT` / `CSMUSIC_STEMS_ROOT` / `YASUOBAO_SRC` 覆盖）。
> - **编译工具链其实在盘上（补正旧记录）**：`g++/clang++` 虽不在 PATH，但存在 `/VS2022/VC/Tools/Llvm/x64/bin/clang++.exe`（另有 Android NDK 与 `.workbuddy\binaries\llvm` 下的副本），`cl.exe` 在 `/VS2022/VC/Tools/MSVC/*/bin/HostX64/x64/cl.exe`。**C/C++ 改动可以真编译验证**（本次 fish `golden_runner.cpp` 即用 clang++ 编译并实跑通过）。
> - **`G:\notpython` 是资产/项目再分布区**：`merged_gui`、`kontakt_transcode`、`MusicStudioPro` 等原 `/allin/*`、`/tools/*` 的内容落到这里，跨盘引用时先 `es.exe` 全盘定位再写死。
> - **明文凭据 remote 已清理（2026-09-23）**：`bee`、`particle` 的 origin URL 原有内嵌令牌（形如 `https://siwpan:<TOKEN>@gitee.com/...`），已 `remote set-url` 改为无令牌 URL 并验证推送正常（系统级 `credential.helper=manager` 供凭据）；令牌真值只在 `G:\私人令牌.txt`。**`G:\` 旧目录侧另 2 处待盘点**。

30. **门禁必须「现在就能绿」，否则等于没有门禁（2026-09-23 沉淀，硬编码路径门禁 /tools/gate/scan_hardcoded.ps1）**：一次普查扫出 323 条存量阻断项（45 仓）——若门禁直接 `有命中即 exit 1`，任何仓都无法提交，团队第一反应是绕过它。**正确形态 = 基线棘轮**：`-WriteBaseline` 固化存量，日常只对**基线之外的新增命中**返回 1（存量清理后用 `-WriteBaseline` 刷新）。同时**门禁自身必须有测试**：`-SelfTest` 要同时验证「能抓」（临时仓放死路径 → 检出）与「不误报」（系统路径 / URL / 测试夹具 / `e:\n` 转义伪影 / 占位符），并验证「写入基线后新增 = 0」；再加一条端到端负例（新增死路径 → 只报那 1 条 → exit 1）。**只验证「能抓」的门禁会退化成噪声，只验证「不误报」的门禁会退化成摆设。**
31. **「拼接式替换对」已第三次丢行，必须改用 here-string 变量（2026-09-23 第三次复发，教训升级）**：在 `@( , @($old, '注释' + "`n" + '代码') )` 这种「参数位拼接」写法里，PowerShell 会**静默丢掉拼接出来的那一行**——只留下注释，代码行消失。三次实证：① musickit `_dedupe_all_pools.py` 丢了 `with open(...)`（触发 IndentationError，被编译抓到）；② musickit `ingest_csmusic.py` 丢了 `CS = ...`、`make_archive_manifest.py` 丢了 `YASUOBAO = ...`（**编译查不出**，是运行时探针才抓到 NameError）；③ musickit `build_framework.py` 丢了一整行 `r = subprocess.run(...)`（SyntaxError）。**纪律**：替换对一律**先赋值给变量**（here-string 或 `$new = "a`nb"` 单独一行），绝不在 `@(...)` 里做 `+` 拼接；改完除了 `py_compile` 还必须跑**运行时探针**（把该文件 import 一遍并打印你本次新增/改动的那几个名字，确认都真的定义了、路径也存在）。
32. **`py_compile` 只查语法，查不出「用了没导入」「str/Path 做除法」；用 AST 检查器兜底（2026-09-23 沉淀）**：第 1 批去本地化里有 6 个文件 `py_compile` 全绿，实际是 ① `build_framework.py` 用了 `tempfile` 没 import、且 `tempfile.gettempdir()`（str）与 Path 做 `/`；② 三处「替换丢行」导致的未定义名；③ 三处**历史遗留**未定义名（`audio-pipeline/cli.py` 阶段B 的 `make_source` 没导入、`audio-separator/_inspect_run.py` 用了 `time` 没 import、`py_test_runner/main.py` 注解用了没导入的 `DynamicTestResult`）。**固化工具**：`/tools/gate/check_undefined_names.py`（AST 收集 Load 名 vs import/赋值/def，报告全文件从未定义过的名字；支持 `--repo <仓>` 自动取「paths) 提交」改过的 .py）。**纪律**：改代码的收尾动作 = `py_compile` + `check_undefined_names.py` + 一次真实运行（哪怕只是 import 或 `--help`）。
33. **门禁类脚本的参数绑定要兼容 `-File` 调用（2026-09-23 沉淀）**：`pwsh -File scan_hardcoded.ps1 -Repos a,b,c` 里 `a,b,c` 是**一个字符串**（`-File` 走的是字符串绑定，不做 PowerShell 语言层的数组解析），于是报「仓不存在：/repos/a,b,c」并 exit 2。**纪律**：凡给 CLI 门禁做 `-Xxx` 列表参数，脚本内部都要 `-split ','` 展开一次，并让报错提示写明「多个值用英文逗号分隔」。

> **存量清零事实（2026-09-23 收盘）**：硬编码路径门禁存量 **99 条 → 0**（31 仓 36 个提交，未推送）；基线文件 `hardcoded_gate_baseline.csv` 已刷新为**空**，此后任何新增死路径都会被拦。配套工具两个：`/tools/gate/scan_hardcoded.ps1`（死根门禁，自带 `-SelfTest`）与 `/tools/gate/check_undefined_names.py`（AST 未定义名检查，弥补 py_compile 盲区）。本轮还顺带修掉 7 处静默缺陷（第 1 批遗留 3 处 + 历史遗留 4 处）与 25 处日期笔误。
> **推送凭据小坑（2026-09-23 实证）**：个别仓 `git push` 会稳定报 `could not read Username for 'https://gitee.com'`（且 `--dry-run` 也报），同机其它仓正常、两仓 `credential.*` 配置逐项一致 → 属 GCM 侧该仓凭据缺失/损坏，不是仓库配置问题。救急办法：用 `G:\私人令牌.txt` 的 gitee 令牌做**一次性 URL 推送**（`git -c credential.helper= push "https://siwpan:<tok>@gitee.com/siwpan/<repo>.git" <br>:<br>`），不落盘、不打印令牌；事后确认 `remote.origin.url` 仍为无令牌 URL。

34. **判「路径是否已失效」不能只看前几段（2026-09-23 沉淀，门禁口径实证）**：把路径前 1~3 段当「根」判存在性会漏掉一整类死路径——实证 `/Users/13122/Desktop/allin/aup/play.py` 的根 `/Users/13122` 存在，于是被判「活」，实际 `Desktop\allin` 早已不在（同类还有 `Desktop\{stay,santi,bofang,txt,waper}\…`、`WorkBuddy\<时间戳>\…`）。**正确口径 = 由浅到深检查「该路径的父目录是否存在」**；本工作区已把「代码行深层缺失」升级为门禁阻断项（文档类需 `-Deep`）。**同族坑**：路径里含 `spec/`、`tests/` 等字样会被「测试夹具」豁免整片漏检（`weor/legacy/spec/*.spec` 实证）——豁免规则必须限定文件类型与目录层级，不能只看片段子串。

35. **中文 Windows 上 `json.load(open(path))` / `json.dump(..., open(p,"w"))` 必须显式 `encoding="utf-8"`（2026-09-23 沉淀，musickit 实证）**：默认编码是 **GBK**，读写 UTF-8 的 JSON 会直接崩或**写出 GBK 文件**（后者更隐蔽：文件仍能生成，内容却被写坏）。实测 `index.json` / `styles_manifest.json` / `manifest_index.json` 三个文件在默认编码下加载**全部** `UnicodeDecodeError`；此前有人靠 `PYTHONUTF8=1` 绕过——**绕过的是症状，不是缺陷**。纪律：JSON/文本读写一律显式 `encoding="utf-8"`（写侧同样），修完**不设 `PYTHONUTF8`** 复跑一次才算修好。
36. **陈旧生成物要「重跑生成器」，不要手改产物（2026-09-23 沉淀，musickit 专辑流水线）**：`burbidge_album/index.json`（被跟踪、4.79 MB、26,978 条）里写着已失效的采样库根；正确处置＝先修生成器（含编码缺陷）→ **就地重跑** → 用 `git diff --numstat` 确认差异只落在预期字段（本例 1 增 1 删，只是 base+path 前缀）→ 再提交。**手改生成物会把「生成器与产物不一致」这个真问题掩盖成「看起来对了」。**

37. **git 配置里的「空值」不是「未设置」——`credential.helper=` 空值会清空 helper 链（2026-09-23 沉淀，players-unified 实证）**：该仓 `.git/config` 有一条空值 `credential.helper=`，于是系统级 `manager` 与 gitee 专用 `store` **全部失效**，每次 push 都报 `fatal: could not read Username for 'https://gitee.com'`（`--dry-run` 同样报）。**排查要点**：`git config --get credential.helper` 对「空值」和「未设置」都返回空，光看它查不出来——必须用 `git config --list --show-origin | Select-String credential` 看**有没有那一行**（或直接 grep `.git/config` 里的 `helper\s*=\s*$`）。**修复**：`git config --unset credential.helper`（可逆，且不动系统/全局配置）。**教训**：连续三次用「一次性令牌 URL」绕过报错属对症不对因，遇到重复出现的认证类故障，先做**配置差异比对**（同机正常的仓 vs 出问题的仓）。

38. **中文 Windows 控制台 GBK 会让带 `✓`/emoji 的输出直接崩，且「重定向输出时不复现」（2026-09-23 沉淀，wav_music_gen 实证）**：`python demo_vocal.py` 在 cmd 里 `exit 1`，报 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`；把输出重定向到文件或在管道里跑就**正常**——所以「跑过一次通过」可能是假象（本次即因为这个假象被漏掉）。**纪律**：① 入口脚本统一 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（本工作区 `build_framework.py` 已有先例）；② GUI/CLI 冒烟**必须在默认控制台直跑一次**，不能只看重定向输出；③ 同类已发现多处（sandbox `run.py`、mc-clone `launcher.py --probes`）。

39. **区分「链接期依赖目录」与「运行时目录」——别把脚本找错目录当成依赖坏了（2026-09-23 沉淀，pluginplayer/libass 实证并回头更正）**：libass 体检脚本原指向 `vendor/libass/bin`（32 个 DLL，**链接期**：include/lib + 部分 DLL，缺 MinGW 运行时三件套 libgcc/libstdc++/libwinpthread），报 `libass-9.dll` 加载失败 err=126；我当时判为「依赖链本身的既有问题」——**判断错误**。实测（新进程只加一个目录）：`pluginplayer/dist`（41 个 DLL，**运行时闭包**）单独可加载且 `ass_library_init` 成功；`build.py` 注释本就写明「运行时由 Windows 加载器从 dist/ 解析 libass-9.dll 及其闭包」。**纪律**：① 报「依赖缺失」前，先用「新进程 + 只加一个候选目录」逐个验证，并确认自己指的是**运行时**目录；② 修复方向应是**让脚本去对目录**（本次改为 `PP_LIBASS_BIN` → `dist/` → vendor 兜底 → fail-loud），而不是往链接期目录里塞运行时 DLL（`vendor/`、`dist/` 都不入库，塞了也不可复现）；③ 禁止为了「让它能跑」去依赖 mpv 之类跨盘外部目录——那是换机即坏类。

> **libass 运行时闭包已纳入依赖准备（2026-09-23）**：`tools/fetch_deps.py` 现在会补齐 `vendor/libass/bin` 缺的 MinGW 运行时三件套（libgcc_s_seh-1/libstdc++-6/libwinpthread-1），取件优先级 `PP_LIBASS_RUNTIME_SRC`/`PP_MINGW_BIN` → `PP_GXX` 目录 → `/mingw64/mingw64/bin` → 本仓 `dist/`；新增 `--libass-only`（秒级补齐+加载体检）与 `--skip-libass`。至此**构建前**用 vendor 目录也能跑通 libass 体检（17/17），不必等 `build.py` 产出 dist。

40. **批量改写的收尾动作必须「编译通过才允许提交」，不能只看日志里打印了什么（2026-09-23 沉淀，本轮真实事故）**：改写 `fetch_libass.py` 的提示语时把换行插进了 **f-string 字面量内部** → 该文件变成语法错误（`py_compile` exit 1）；而我的提交脚本**把 exit=1 打印出来后仍继续 `git commit` + `git push`**，于是坏文件进了远端，得再补一个修复提交。**纪律**：① 提交前对**本仓全部跟踪 .py**（不只改动文件）跑一次 `py_compile` 并**断言**全绿，不通过就中止；② f-string / 单行字符串里绝不能插换行（需要多行用三引号或先拼变量）；③ 日志里的 `exit=1` 必须被脚本判为失败——「打印了就继续」等于没有门禁。

41. **自检/验证脚本的退出码必须如实，禁止「打印提示就返回 0」的假绿（2026-09-23 沉淀，`_verify_libass_load.py` 实证）**：`players-unified/pluginplayer/_verify_libass_load.py` 原来任何分支都以 `exit 0` 结束——DLL 只加载成功 12/20 时只打印一行提示就正常退出，只有全绿才打印 `[PASS]`。我用它做「拿走运行时三件套」的阴性对照时，输出明明是失败，`$LASTEXITCODE` 却是 **0**。**纪律**：① 验证/自检脚本的退出码 = 判定结果（数量不齐、`ass_library_init` 返回 NULL 等一律非 0），提示语只是补充；② 新增或改动任何「体检脚本」时，**同时跑阳性与阴性对照**（本例：全量 20/20 → exit 0；人工移除三件套 → loaded 12/20、exit 1），只跑阳性等于没验证；③ 阴性对照要拿**真实产物**做（本例直接删三件套），不要用「注释掉判断」的方式模拟。

> **libass 运行时三件套改为默认随上游闭包抓取（2026-09-23；本段更新前一条 blockquote 里「刻意不抓」的口径）**：`tools/fetch_libass.py`（pluginplayer 与 players-unified/pluginplayer 两副本字节一致）里 `EXCLUDE_RUNTIME` → `RUNTIME_DLLS`，默认从上游 MSYS2 抓 `libgcc_s_seh-1.dll`/`libstdc++-6.dll`（同属 `mingw-w64-x86_64-gcc-libs`）与 `libwinpthread-1.dll`（`mingw-w64-x86_64-libwinpthread`），使得 `vendor/libass/bin` **在还没跑 build.py（无 dist/）时**即为完整可加载集（呼应 `build.py:328` 的「bin/ 下即完整可加载集」声明）；`--skip-runtime` 退回旧行为（三件套交 `fetch_deps.py --libass-only` 从本机工具链/dist 补齐，离线可用）。同时给传递依赖抓取阶段补上 `DOWNLOADS_SHA256` 钉死校验，并钉死 gcc-libs-16.2.0-3 / libwinpthread-14.0.0.r375 的实测哈希。**实测**：真实联网跑通（第 1 轮抓 gcc-libs → 第 2 轮抓 libwinpthread → 第 3 轮闭合），libass 闭包 17 → **20** 个 DLL；空 vendor + 空 tmp（无解包树、无 TOFU）从归档纯净重放后加载校验 **20/20 PASS**；`--skip-runtime` 路径 32 个 DLL、闭包完整、exit 0 且显式列出被跳过的两项；**篡改 gcc-libs 归档一字节 → 钉死校验硬失败 exit 1**。上游抓到的三件套与本机 MinGW 工具链版本**并非同一份二进制**（体积/哈希均不同：如 libgcc_s_seh-1 上游 150,998 B vs 工具链 142,336 B），两条来源路径都可用、不必互斥。提交：pluginplayer `dc8d6c3`（main）、players-unified `9ed3c93`（master），均已推送。

42. **「把文件搬到别处」是一类会静默弄坏门禁与链接的结构变更；副本仓的门禁必须单独跑（2026-09-23 沉淀，players-unified/pluginplayer 副本实证）**：该副本导入时（`2f146bb`）把 `AGENTS.md`/`CLAUDE.md`/`DEPLOY.md`/`ENHANCEMENT_PLAN.md`/`THIRD_PARTY_NOTICES.md` 放进了 `docs/`，引用却没跟着改，于是**三条门禁长期红**（`third-party-notices` 永远「文件不存在」、`doc-links` 17 处断链、`docs-index` 缺 2 篇），而**源仓 `pluginplayer` 同三条全绿**——只看源仓会得出「一切正常」的错误结论。**纪律**：① 搬动/移动文件后必须同时核三处：**相对链接**（含 README 内链）、**生成器与门禁里写死的路径**（本例 `gen_third_party_notices.py` 的 `OUT=ROOT/…` 与 `verify.py`）、**索引文件**（如 `docs/README.md`）；② **副本/镜像仓要单独跑该仓自己的门禁**，源仓绿 ≠ 副本绿；③ 判断「是不是我改坏的」用 `git status`（本次只有 5 条 `R100` 改名，门禁输入没变 → 失败必属既有漂移）。**同族发现**：门禁若把环境依赖（如 `host-js/node_modules`）当作事实来源，**没装依赖的检出会判红**——这类红先做环境补齐（`npm install`）再看，别急着改文档或改代码。

> **许可分布事实（2026-09-24 全域收尾逐仓核对）**：`G:\repos` **108 仓**（原记 107，见铁律 4 的仓数订正）= **107 个 MIT + 1 个 GPL**，唯一的非 MIT 是 **`pluginplayer`（`GPL-3.0-or-later`）**——它随包分发 gyan.dev 的 FFmpeg `full_build-shared`（该构建是 **GPL v3**）与 MinGW-w64 GCC 运行时，**属于必须随上游走 GPL、不能改 MIT** 的情形；仓库自己已把理由与合规义务写清（README「开源与合规」L216-233 + `THIRD_PARTY_NOTICES.md` 逐条证据与复核命令）。gitee API 复核两仓均 `public=true`（pluginplayer license=GPL-3.0 默认分支 main；players-unified license=MIT 默认分支 master）。**据此读铁律 0 的正确姿势**：默认「公开 + MIT」；但当发布物**链接/随包 GPL/AGPL 上游**时，许可必须随上游（改 MIT 反而是违规）。此处只记事实，未改铁律 0 文本与预设 persona（用户 2026-09-24 选择「只记事实」）。

> **全域同步事实（2026-09-24 收尾扫描 116 仓）**：`G:\repos` **108 仓**（原记 107，见铁律 4 的仓数订正）+ `G:\allin`、`G:\platform`、`/local/{markdown,novel-run}`、`/archive/`4 个归档、`/tmp/santi-remote` = **116 个仓，0 未提交、0 未推送**。扫描一度报 `calculator`（2 条）、`mathematical-formula-renderer`（1 条）「未推送」，`git ls-remote` 核实**远端 HEAD 与本地完全一致**——是本地 remote-tracking ref 陈旧（该仓此前用 URL 直推、后续没 fetch）导致的**假阳性**；`git fetch origin` 后差异归零。**教训**：判「未推送」只信 `git ls-remote`（对远端实际值），`origin/BR..BR` 只能当线索——同一坑已在 MEMORY 里出现过一次（推送凭据/ref 陈旧同族）。

43. **批量改写路径这类字符串时，Python 非 raw 字符串里的 `\a`/`\b`/`\f`/`\t`/`\v` 会被解释成控制字符（2026-09-24 沉淀，crawl-hub 实证）**：文档枢纽从 `G:\docs` 迁到 `/allin/docs` 后，`crawler_registry.py` 里那句提示文案 `f"...先查 /allin/docs/md/allin主工作区/端口分配表.md"` 运行时打印成 `/x07llin/docs/md/x07llin主工作区/端口分配表.md`——`\a` 变成 **BEL(0x07)**（旧路径 `/docs/md/allin主工作区/...` 就已经中过一次，改名只是又叠加一个）；`\d`/`\m` 是非法转义，只发 `SyntaxWarning`（**不报错，最容易被忽略**）。**纪律**：① 路径字面量一律用 **raw 字符串**（`r"..."` / `rf"..."`）或双反斜杠——Windows 路径里 `\a`（`\allin`/`\assets`）、`\t`（`\tmp`/`\tools`）、`\n`（`\new`）、`\b`（`\bin`）、`\v`、`\f` 全是高危；② 改写后必须**真实运行一次看输出**（`repr()` 或触发该分支），只看源码字符串看不出来；③ 验证时用 `python -W error::SyntaxWarning -m py_compile` 把非法转义升级成错误，能顺带抓出 `\d` 这类隐患。**同族**：PowerShell 单/双引号对 `\` 语义不同、JS 模板串里 `\` 仍需转义——跨语言批量改路径要逐语言确认转义规则。**第二次实证（同日，audio-generation）**：我在 **docstring** 里写了「与 /repos/zhuangtaiji 的 web/server.py 保持同一口径」，`\z` 立即被判非法转义；默认 `py_compile` 只发警告、代码照跑，是 `-W error::SyntaxWarning` 把它拦下的——**文档字符串同样属于字符串字面量，别忘了它**。

> **共享仓并发写入纪律的由来（2026-09-24 实证）**：文档枢纽迁入 `G:\allin` 并推送的过程中，**另一条会话/进程也在同一仓提交并推送**（我这边看到 `16688120` 出现在我推完之后；对方看到 `10929df6`；两条提交线性、互不覆盖、`is-ancestor` 均为 0）。值得记的教训是我这边的动作：当时 `git status` 报「有改动」，我按换行噪音处理跑了 **`git checkout -- .`**——跑之前 `git diff --ignore-cr-at-eol --numstat` 为空、事后 `git fsck` 今日无 dangling commit，所以没吞掉对方东西，但在**别人可能正在写的共享仓**里这就是危险动作。**纪律（见铁律 43）**：共享仓动任何写操作前后都要 `git fetch` + 看 `ls-remote`；禁止 `checkout -- .` / `reset --hard` / 强制推送；发现并发就停下来对齐分工。

> **目录索引.txt 的口径（2026-09-24 二次裁定：形态换代 —— 全盘快照 → 项目目录文档化索引）**：
> **旧形态已作废**：原 `目录索引.txt` 是 2026-08-28 15:12 的**全盘文件快照**（48.53 MB / 555,220 行，
> 逐条列每个文件；行构成 `repos` 44% + `Temp` 21.9% + `notpython` 19.1% + `assets` 8.5%，
> 其中大量是 `node_modules`/`dist` 里的第三方文件与临时区内容）。**它过于臃肿、无维护** ——
> 快照自带 08-28 时点，之后一切增删改名都不在其中。**用户裁定换形态**。
> **新形态**：**118 个项目 / 153 行 / 32.55 KB**，每个项目一条 = 标题 + 首段摘要(≤120字) +
> README 相对链接 + 体量。**以各项目自己的 README 为唯一事实源，本文件不复制正文**（要详情点进 README）。
> 覆盖 `repos`(108) + `local`(7，排除归档/构建输出) + `platform` + `tools` + `allin`。
> **生成器**：`/tools/build_dir_index.py`（干跑默认，`--apply` 落盘；带跨次运行的体量缓存
> `/tools/.dirsize-cache.json`，按 mtime 失效 —— 命中缓存时整轮 **0.1 s**）。
> **纪律**：① **改项目请改它的 README**，不要手改索引（手改会造成「生成器与产物不一致」，见调试铁律 36）；
> ② 新增项目**必须带 README**，否则生成器把它列入「缺 README」节（该节为空才是健康态）；
> ③ 索引**可以逐次提交**了 —— 32 KB 而非 50 MB，重生成的成本已可忽略。
> **旧快照已归档**：`/archive/目录索引-全盘快照-20260828/`（含 `MANIFEST.md`，
> SHA256 `1877C3D9ADB23A90F3F297D07867FB373307603BAA0682411E86B4DCA92D3475`）——
> 它是 08-28 那一刻现盘的**唯一证据**，保留以备追溯「当时某文件是否存在」。
> 历史脚本 `/logs/_gen_index_final.ps1` 等随之作废（不再适配）。

> **文档枢纽事实（2026-09-24 建设完成并公开）**：文档枢纽从 `G:\docs` 汇总整理（933 文件 / 122.1 MB → **253 文件 / 1.62 MB，只有 .md/.txt/.yaml**）后整体迁入 **`/allin/docs`**，随公开仓 `siwpan/allin` 发布（开发过程透明化、可供他处续做）。**现盘布局**：`/allin/docs/`（活文档在根：`MEMORY.md`、`记录/交接/`、`协作工作流程约定_2026-08-28.md`、`ports.yaml`、`端口分配表.md`、`README.md` 文档地图、`allin治理模式_建设指南.md`；历史树在 `md/`）；非文档内容 → `/archive/docs-nondoc-20260924/`（audit-fragments 含 token 扫描产物、XJ380 SDK、GURPS 第三方规则，**永不入库**）；门禁工具 → `/tools/gate/`（`scan_hardcoded.ps1`，基线在 `audit\`；`check_undefined_names.py`；`README.md`）。**约定**：① 枢纽**只放文档**，脚本/产物/二进制/第三方资料一律不放；② `MEMORY.md` 是**唯一事实源**，禁止复制第二份；③ 新增文档入库前过敏感串扫描（11 类模式）。**引用同步**：枢纽内 100 处 + platform 2 处（含 `registry.js` 的 `PORTS_YAML` 默认值）+ 5 个仓 + 预设 persona，全部改净并推送（platform `8164b19`、crawl-hub `8378c38`/`526eb20`、foolproof-operation `b387e5e`、pluginplayer `15db038`、players-unified `f7a303a`、private-radio-stations `206db91`）。详见交接 §74。

44. **共享仓（尤其是多人/多会话在写的仓）禁止破坏性工作区操作，写前先同步（2026-09-24 沉淀，`G:\allin` 并发写入实证）**：同一时段有两条会话/进程在 `G:\allin` 提交并推送（提交图线性、无覆盖），而我在其中一次 `git status` 报「有改动」时跑了 `git checkout -- .`（事后核对无内容差异、无丢失，但**差点就是数据损失**）。**纪律**：① 在共享仓写之前先 `git fetch` + `git ls-remote` 看远端是否已被推进，提交后**推之前再看一次**，被拒就 `pull --rebase` 而不是强推；② **禁止** `git checkout -- .`、`git reset --hard`、`git clean -fd`、`push --force`——工作区「看起来脏」时先 `git diff --ignore-cr-at-eol --numstat` 判断是不是换行噪音，是就放着别动或只对**自己改的文件**做 checkout；③ 发现并发写入时，先对齐分工（谁改哪个文件/目录），必要时停下等对方提交完再动；④ 推完必须核对 `ls-remote` 与本地一致，并检查是否有别人的新提交被自己漏看（`git log --oneline HEAD..origin/BR`）。

45. **铁律编号必须唯一且连续；续编前先扫全表取最大号（2026-09-24 沉淀，本表自身「缺 23 + 29/30 各两次」实证）**：本表曾有 44 个条目却只有 42 个唯一号——**「23」缺号、「29」「30」各出现两次**（四件不同的事共用两个号）。后果不是排版难看，而是**编号引用直接失效**：`会话交接` 引用「调试铁律 24/25/29/30」时无法判断指的是哪两条；`建设指南` 的事故表更是**整体错位**（其引用的编号在 40–43 立完之后没有随编号更新，8 行里 6 行指错，直到本次才按内容重定号）。**根因**：`建设指南` S4 立了「编号稳定（永不重排）」的规矩，却**没有任何机制保证编号唯一**——规矩只说了「不许改」，没说「不许重」。⇒ 冲突说明 S4 未落到实处，故本次按用户拍板**重排为 1..44 连续唯一**并同步全部引用（`会话交接` 9 处、`建设指南` 8 处 + 2 处正文）。**纪律**：① 往任何编号列表追加条目前，先扫描该表取**最大号 + 1**，禁止凭记忆续编；② 追加后立刻校验「编号 == 1..N 连续唯一」，不通过不得提交；③ 编号列表是**引用契约**，改号必须同步全部引用点（`grep 铁律\s*\d+` 全量核），并以「引用指向的条目内容是否与上下文语义相符」为验收标准——只看编号存在与否不够（本次正是靠内容比对才发现 6 行错位）。④ 编号唯一性的同类约束适用于所有带编号的事实源（铁律、端口、条目索引）。


### 借用外部文档与会话验收（46–47）

46. **借用外部文档必须做落点本地化，且落点属于"某台机器"而非"事实"（2026-09-25 沉淀）**：文档里的**绝对路径、用户名、盘符、设备名、卷标**都是**某台机器**的快照，不是通用事实。把它拷进工作区时，**必须先逐条实测核对本机**，再落库；核不上的就地改成本机事实，并在文档内标注**为何**改（否则下次又被人"照原样"抄回去）。**判据**：文档能不能在一台陌生机器上照着跑通，是它唯一的质量标准——文采与信息量都不算。本节的教训不是「文档写错了」，而是**同一工作区换硬件后，事实源（`新机挂载事实` 一节）已经更正，但被借鉴进来的外部文档没跟着同步** —— 这类「事实源已更新、派生文档未同步」的缺口，是记账时**最该主动去找**的一类。
    - 附：同一批文档里还有一类**同源不同机**的规律可复用 —— `G:\platform` 的远端是 **`siwpan/allin-platform`**（不是 `platform`）；匿名查 `siwpan/platform` 会 404。**仓名与本地目录名可以不一致，核远端一律以 `git config --get remote.origin.url` 为准，不要靠目录名猜。**
    - 附：`siwpan/*` 公开仓 **≥100 个**（API 单页上限 100，实际更多），抽样 5 仓 `private=False` —— 铁律 0「默认公开」在存量仓上成立，可作为后续建仓的现状基线。

47. **鉴权验收必须贯通"整条链"，不许拿链上任一单点的成功去代表链成功（2026-09-25 沉淀）**：本次实测 `gitee_release.py whoami` **失败**（本机无 store 文件可读，脚本要求显式令牌），但**同一时刻 `git push` 却成功**（凭据在 **Windows 凭据管理器**内，GCM 自动取用，文件式检查根本看不到：`~/.gcm/credentials` 等路径均不存在）。
    - **⇒ 「某条命令能推」不等于「脚本能取令牌」**，二者是**两条独立链路**（git 凭据管理器 vs API 令牌），必须**分别**取得证据。
    - **反方向的坑同样存在**：开始我依据「无 store 文件 + GCM 无存储 + selector=`<no helper>`」推断**推送会失败** —— 这个推断是**错的**，只是我当时的检查手段（文件式枚举）看不见凭据管理器。**"我查不到" ≠ "不存在"**：凭据类事实必须以**实推探针**为准。
    - **纪律**：① 鉴权结论一律用**实推探针**（文档 §3.8 分支探针：建临时分支 → push → 删 → `ls-remote` 复核）取证据，不用文件存在性推断；② 探针必须**自清理**（本次 `__probe_cred` 推送后即刻删除，复核远端只剩 `main`）；③ 报「能用/不能用」时，明说**验的是哪条链**。
    - **补充（2026-09-25 当日二次实测）**：**GCM 凭据缓存会「先成功后失败」** —— 同一次批量推送里，前 4 个仓 `git push` 成功，后 5 个立刻报 `fatal: could not read Username for 'https://gitee.com': terminal prompts disabled`（各仓 `credential.helper` 配置**完全相同**，非配置差异）。重试仍失败。**处置**：改用**一次性 URL**（`git -c credential.helper= push "https://siwpan:<TOKEN>@gitee.com/..."`，令牌取自 `G:\私人令牌.txt`），实测 5 仓全部推送成功且 `.git/config` 无凭据残留。⇒ **批量推送不要假设"第一个成功就都能成功"**，要么逐仓验证，要么直接走一次性 URL。

### Python 运行环境事实源（2026-09-25 实测，含一个 CPython 缺陷）

> 本节是本机**唯一**的 Python 选型事实源。核心结论：**不要用 `F:\Python314`（3.14.7）**，它有会导致进程崩溃的 CPython 缺陷。

48. **CPython 3.14.7 存在「包内失败的相对导入直接崩进程」缺陷，必须避开（2026-09-25 实测定位）**：
    - **症状**：`import` 某个包时进程**直接消失**，`exit=-1073741819`（`0xC0000005` 访问违规），**无 traceback、无 stderr、连 `print` 都不输出**（崩在模块加载/编译期）。
    - **最小复现**（20 行，与任何第三方包无关）：
      ```python
      # pkg/__init__.py
      from .reader import go
      # pkg/reader.py
      try:
          from ..missing import X        # 包内失败的相对导入（目标不存在）
      except ImportError:
          X = False
      def go(): return X
      ```
      `python -c "import pkg"` → **崩**。把 `from ..missing` 换成**绝对**导入（`import definitely_missing_xyz`）→ **exit 0**。
      ⇒ 触发条件 = **包内失败的相对导入（`from ..x import y`）**，与 try/except 无关。
    - **已排除**：文件损坏（与 PyPI 官方 wheel 逐字节比对，190 文件 0 差异）、`.pyc` 缓存（移走全部 `__pycache__` 仍崩）、重装（stdlib 手工覆盖 195 文件仍崩）、site-packages 污染（`-S`/`-E` 无效）、numpy+lxml 组合（任意顺序均 OK）、磁盘（`Get-PhysicalDisk` 报 Healthy）、调试器（有无 `-X faulthandler` 均崩）。
    - **官方对应**：gh-134100「use-after-free in `PyImport_ImportModuleLevelObject`」（[PR #134117](https://github.com/python/cpython/pull/134117)）。**3.14.8 预计 2026-10-06 才发布**（[Ubuntu FFe #2168150](https://bugs.launchpad.net/ubuntu/+source/python3.14/+bug/2168150)），Windows 当前最新即 3.14.7。
    - **受害者实例**：`openpyxl/reader/excel.py:16` 的 `from ..tests import KEEP_VBA`（tests 目录不随 wheel 分发，**必走失败路径**）⇒ 本机所有 3.14.7 环境下 `import openpyxl` 必崩。
    - **处置（按优先级）**：
      1. **用 Python 3.13.14**（本机已有，见 49），**不要用 F:\Python314**；
      2. 临时 workaround：把问题包的失败相对导入改成 `__import__('pkg.sub', fromlist=[...])`（openpyxl 已就地打补丁，备份 `excel.py.bak-20260925`）—— 但**重装包会丢补丁**，只能应急。
    - **纪律**：遇到「进程无输出直接消失」，先跑最小复现判定是否本缺陷，再去查自己的代码；**不要**在无 traceback 的情况下盲目调试业务逻辑。

49. **本机可用 Python 清单与选型（2026-09-25 实测）**：
    | 解释器 | 实际版本 | 可用性 |
    | --- | --- | --- |
    | `/workbuddy/.workbuddy/binaries/python/versions/3.13.12/python.exe` | **3.13.14** | ✅ **推荐**（实测最小复现 exit 0）|
    | `/Users/psw/.workbuddy/binaries/python/versions/3.13.12/python.exe` | **3.13.14** | ✅ 同上（同一份的副本）|
    | `/Python314/python.exe` | 3.14.7 | ❌ **有 48 的缺陷，勿用** |
    - **坑**：目录名写 `3.13.12`，**实际版本是 3.13.14** —— **判定版本一律用 `python -V`，不要信目录名**。
    - **另一个真损坏**：`/workbuddy/.workbuddy/binaries/python/envs/default/Scripts/python.exe` 是 venv，其 `pyvenv.cfg` 指向 **`/Users/13122/...`（旧机路径，已不存在）**，运行报 `did not find executable ... exit 103`。**这些 WorkBuddy venv 在换机后已全部失效，需重建**（本机死根路径门禁报出的 `/Users/13122` 多由此而来）。
    - **推荐用法**：给每个需要 Python 的项目建**项目级 `.venv`**：
      `/workbuddy/.workbuddy/binaries/python/versions/3.13.12/python.exe -m venv <项目>\.venv`，
      再 `\.venv\Scripts\python.exe -m pip install <依赖>`。
      ⇒ 隔离依赖、钉住版本、不受系统 PATH 里那个坏解释器影响。**并记得把 `.venv/` 写进 `.gitignore`**（`cordis-table-app` 原本漏了，会把整个虚拟环境提交进仓）。

50. **`python -c` 的多行代码不要用 PowerShell here-string 传（2026-09-25 反复踩，代价三轮误判）**：用 `@"... "@` 把多行 Python 喂给 `python -c` 时，**引号与换行会被破坏**，表现为「**什么都没执行就崩**」——极易误判成被测对象崩溃（本次据此错误推断过「大源码编译即崩」三次）。
    - **纪律**：多行 Python 一律**落成 `.py` 文件再执行**；只有单行、无嵌套引号的场景才用 `-c`。
    - 同族坑：`.cmd` 文件**不能存 UTF-8**（cmd 按 ANSI 解码，中文注释会让整条命令解析错乱，实测报 `'）' is not recognized`）—— 中文批处理要么存 ANSI，要么改用 pwsh。

51. **盘健康：外置 USB 盘必须关掉「休眠/选择性暂停」，否则会静默损坏 git 仓（2026-09-25 事故 + 处置）**：
    - **事故**：G: 盘（WD Game Drive，Disk 3，USB）全天持续 `disk 事件 153`（IO 重试，24h 内 190 次），19:07 触发 `Ntfs 事件 132`「**短时间内发生太多修复事件**」+ 9 次「卷 G: 上的文件系统结构现在已经修复」——**NTFS 在线自愈在写入过程中改坏了 git 对象**，造成 **4 个仓损坏**（`allin` 的 pack idx/commit-graph/index，`novel`/`novel-down`/`ncmturnmp3` 的 `.git\objects` 目录项损坏）。
    - **⚠ SMART 会说谎**：`Get-PhysicalDisk` 全程报 `HealthStatus=Healthy`，而盘正在重试 IO。**判盘健康必须看事件日志**（`disk` id 153 计数 + `Ntfs` id 130/132），不能只看 SMART。
    - **处置（已执行，可回滚）**：
      ```powershell
      powercfg /change disk-timeout-ac 0      # 硬盘永不关闭（原 0x4b0=1200s）
      powercfg /change disk-timeout-dc 0      # 原 0x258=600s
      powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
      powercfg /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
      powercfg /setactive SCHEME_CURRENT
      ```
    - **仍待处理**：`F:` **Dirty + Scan Needed** → `chkdsk F: /scan`（只读）；`D:` **Dirty + Full Repair Needed**（**exFAT 无日志，非正常拔插极易损坏**）→ `chkdsk D: /f`；3 个 `/repos/{novel,novel-down,ncmturnmp3}\.git-damaged` 损坏空壳 `rmdir` 也删不掉，需 `chkdsk /f`。以上**均需管理员**。
    - **教训**：外置盘上的 git 仓，在盘出现 IO 重试期间**不要做大批量写入**（本次 4 个仓就是在写入窗口内被改坏的）；**仓的权威副本必须在远端**，本地损坏才可无损恢复（本次 4 仓全部由重克隆恢复，工作树文件未丢）。

52. **`git push -u <带令牌的 URL>` 会把凭据写进 `.git/config` 的 `branch.<名>.remote`——最难发现的一处凭据残留（2026-09-25 实测）**：
    - **现象**：用一次性 URL 推送（`git push -u "https://user:<TOKEN>@gitee.com/..." main:main`）后，`remote.origin.url` 是干净的（因为没有 `set-url`），但 `.git/config` **仍然含令牌**。
    - **藏身处**：不在 `[remote "origin"] url`，而在 **`[branch "main"] remote`** —— `-u` 把**带凭据的那个 URL** 直接记成了分支的上游：
      ```ini
      [remote "origin"]
          url = https://gitee.com/siwpan/<repo>.git      # 干净
      [branch "main"]
          remote = https://siwpan:<TOKEN>@gitee.com/...  # ← 令牌在这
      ```
    - **为什么难查**：`git remote -v` 只显示 `remote.origin.url`（干净的），**看不见 branch 段**；只看 remote 就会误判"无残留"。本次即因此先误报了一次"已清理"。
    - **正确排查与处置**：
      ```powershell
      # 排查：直接扫 config 全文，别只扫 remote 段
      Select-String -Path .git\config -Pattern 'https://[^/\s]+:[0-9a-zA-Z]{20,}@'
      # 处置
      git remote set-url origin "https://gitee.com/<owner>/<repo>.git"
      git config --file .git/config branch.<branch>.remote origin   # ← 关键这一条
      ```
    - **连带坑**：`git config` / `[IO.File]::ReadAllBytes` 用**相对路径**时会**静默作用到会话 cwd**（本次 PowerShell 里 cwd 仍是 `D:\local`，导致"改了却没生效"、读数也读错文件）。⇒ **一律用绝对路径**，或用 `git config --file <绝对路径>`。
    - **纪律**：① 用一次性 URL 推送时**不要加 `-u`**（或推完立刻把 `branch.*.remote` 改回 `origin`）；② 凭据残留检查必须**扫 config 全文**并以「正则 `https://user:hex@` 是否命中」为准，不靠肉眼看 remote；③ 建仓后的收尾清单里，**必须包含这一项**。

53. **门禁的"排除项"是它最危险的部位 —— 一个过宽的排除会静默吃掉整类真问题（2026-09-26 实测，死根路径门禁漏检 3 处）**：
    - **现象**：`d20` 仓有 3 处 `E:/D20`（`E:` 盘在本机**不存在** ⇒ 真死根），而门禁报 **0 阻断**。
    - **根因**：排除项 `RxRegexArtifact` 的本意是滤掉文本里的**正则转义伪影**（`\d` `\w` `\s`），原式：
      ```powershell
      [\(\)\[\]\+]|\\(w|d|s|W|D|S)(?![A-Za-z])
      ```
      `E:\D20` 的 `\D` 后跟 `2`（非字母）→ 命中 → **整条路径被当成伪影排除**。
      于是「盘符后紧跟 w/d/s/W/D/S 字母」的路径**整类**被静默吃掉（`E:\D20`、`C:\Users`、`D:\data`、`C:\src`… 全部）。
    - **修法**：加负向后顾 —— 盘符分隔符前必是 `X:`，而真正的转义 `\d` 前不会是冒号：
      ```powershell
      [\(\)\[\]\+]|(?<!:)\\(w|d|s|W|D|S)(?![A-Za-z])
      ```
    - **验证方式（关键）**：修完必须**先跑门禁自检**确认「系统路径/URL/夹具/转义 零误报」仍通过 ——
      **不能为了修漏检而牺牲零误报**，否则是把一类误报换成另一类。本次自检三项仍全绿。
    - **纪律**：① **门禁的排除/白名单/豁免逻辑必须逐条能被自检用例覆盖**（正例能抓 + 反例不误报），
      只测"能抓"不测"不误伤"等于没测；② 发现一处漏检后，**必须反推该排除项的整类影响面**
      （本次是"盘符+w/d/s 字母"全类），不要只修当前这一例；③ 门禁报 0 时，若**同一事实用别的工具能查到**，
      优先怀疑门禁而不是事实 —— 本次正是 `git grep` 查到了 3 处而门禁报 0，才顺藤找出这个盲区。
    - **旁证**：修复后全工作区复扫仍 `阻断 0 / exit 0`，非阻断命中从 1033 升到 1044 —— 说明该排除项此前
      确实**吞掉了一整类**（11 处）被判为伪影的路径。

54. **`git add -A` 会把构建副产物一并提交；判"哪些是产物"不能靠文件名直觉（2026-09-26 实测）**：
    - **现象**：给 `d20` 补 `pyproject.toml` 后为验证可安装性跑了 `pip wheel`，产生了 `d20.egg-info/`；
      随后 `git add -A` 把它**一并提交**（6 个文件）并推送。
    - **为何危险**：`egg-info` 是 setuptools 生成的**构建元数据**，属于"产物入仓"，正是仓库卫生门禁 H3 的拦截对象；
      入库后每次构建都会产生 diff 噪音，且暴露本地绝对路径等信息。
    - **处置**：`git rm -r --cached <dir>` + `.gitignore` 补 `*.egg-info/`，再单独提交修正（**保留磁盘文件，只从跟踪面移除**）。
    - **纪律**：① **提交前先跑仓库卫生门禁**（`repo_hygiene.py --repo <仓>`），它专门拦 `dist/ build/ release/ output/`
      与 `*.egg-info/` 这类产物 —— 本次是**先提交、后跑门禁**才发现，顺序反了；② `git add -A` 前先 `git status --short`
      扫一眼**未预期的 `??` 项**，构建/测试刚跑过尤其要当心；③ 判断产物看**是不是生成出来的**，
      不看名字像不像（`data/` 可能是源码、`*.json` 可能是产物）。
    - **附**：门禁 H3 的 `ARTIFACT_DIRS` 当时**不含 `egg-info`**，故本次是"门禁没覆盖到"而非"门禁没拦住" ——
      已同步把 `*.egg-info/` 纳入判据（否则这条纪律没有机械保障）。

55. **外置数据盘无法在线 `chkdsk /f`；"开机检查"的落点是 `BootExecute`，不是脏位、也不是 `Autochk` 键（2026-09-26 实测）**：
    > 本条按**铁律 5（去符盘）**书写：盘符仅作"哪个卷"的标识，路径用去符盘形式。
    - **背景**：两块外置数据盘（依 `新机配置汇总` 的盘位约定：`D:` 数据盘 exFAT 7.4TB、`F:` 依赖盘 NTFS 3.7TB）
      双双 `Health=Warning`、脏位置位，需修复。
    - **事实一：`/f` 需要独占卷，外置数据盘做不到**。`chkdsk <盘>: /f` 报
      `Chkdsk cannot run because the volume is in use by another process.` 并抛出交互式提问
      `Would you like to force a dismount on this volume? (Y/N)`。本机占用源很具体：
      **依赖盘被当前 DSH 会话自己的 `python.exe` 占用**（它就是工作区的 Python 运行时，
      解释器目录 `/Python314` 在该盘）；
      **数据盘被每个工具调用所启动的 `pwsh.exe` 占用**（工具 shell 的镜像与工作目录都在该盘）
      ⇒ **只要会话活着，数据盘就一直锁着**，只会得到 `Cannot lock current drive`。
      **绝不选"强制卸除"** —— 它让该卷所有已打开句柄失效，等于自行制造数据损坏。
    - **事实二：光有"脏位"不会触发开机检查**。本次重启后两盘**仍脏、开机什么都没跑**
      （事件日志无任何 chkdsk 记录、无 `AUTOCHK*.pf`）。**必须显式排队**。
    - **事实三（最关键 —— 我最初的判据找错了落点）**：排队的落点是 **`BootExecute`**，不是 `Autochk` 子键：
      ```powershell
      $k = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
      (Get-ItemProperty $k -Name BootExecute).BootExecute   # REG_MULTI_SZ
      # 形如：
      #   autocheck autochk /p \??\F:      ← 对依赖盘做完整检查（chkdsk 交互确认 Y 后自己写入）
      #   autocheck autochk *               ← 系统原有默认项，别删
      ```
      **`Autochk` 子键可以完全不存在**，开机照样会检查 —— 拿它当判据会得出错误结论（我犯过）。
    - **事实四：exFAT 不支持"安排重启检查"这条退路**。同一操作在两卷上行为不同：
      NTFS 卷拒绝卸除后**会继续问** `Would you like to schedule this volume to be checked
      the next time the system restarts? (Y/N)`，答 `Y` 即入队；
      exFAT 卷拒绝卸除后**直接 `Cannot lock the drive` 结束**，没有排队提问。
    - **处置（本机已执行）**：给 `BootExecute` 追加 `autocheck autochk /p \??\D:`（数据盘）——
      与 NTFS 卷**同机制、同写法**，只是 exFAT 走不了官方交互路径，改为等效手写。
      回滚点存 `/allin-recovery-backup-20260925/bootexec-rollback.txt`（含完整恢复命令）。
    - **纪律**：
      ① 判"会不会开机检查"**只看 `BootExecute` 数组** —— 不看脏位、不看 `Autochk` 键；
      ② 外置盘修 `chkdsk /f`（或 WinRE / 挂到另一台机器），**永不选强制卸除**；
      ③ 安排前先查**有没有正在跑的服务把该盘当依赖**（本机依赖盘就是工作区 Python 运行时盘，
      卸它等于打断会话）；④ 开机检查期间该盘不可用、耗时可能很长（数据盘 7.4TB），**不要中途断电**；
      ⑤ 反悔方式：清脏位 `fsutil dirty clear <盘>:`，或把 `BootExecute` 恢复原值。

56. **⚠ 对 55 的重大更正：`BootExecute` 排队对本机三块 USB 外置盘「注定无效」——autochk 阶段根本看不到 USB 卷（2026-09-26 三次实测推翻自己）**：
    - **事实经过**：按 55 的结论，我把依赖盘（chkdsk 交互确认）与数据盘（手写等效条目）都排进
      `BootExecute`，随后**重启三次**（含用户手动重启），结果**三次全部无效**：
      | 观测 | 三次一致的结果 |
      |---|---|
      | 开机后 `BootExecute` | **队列原封不动**（`/p` 项未被消费）|
      | `C:\Windows\Prefetch\AUTOCHK*.pf` | **始终不存在** ⇒ autochk 从未真正检查过任何卷 |
      | 两卷脏位 / 卷状态 | **仍 Dirty / 仍 `Full Repair Needed`** |
      | `Wininit` 事件 | 有 12/14/18/19/23/24/25 一串 ⇒ **autochk 阶段确实走过，只是没检查卷** |
    - **根因（判断，证据一致且唯一能解释全部观测）**：**`autochk` 运行在 Windows 原生启动早期，
      那时 USB 存储栈尚未加载** ⇒ 本机**三块数据盘全部是 USB 外置**（`Get-Disk` 实测：
      仅系统盘 `Bus=NVMe`，其余 `Bus=USB`）⇒ autochk **枚举不到这些卷**，队列自然不被消费、
      脏位自然不动。旁证：`HiberbootEnabled=1`（快速启动开启）会进一步影响启动路径。
    - **⇒ 结论：`BootExecute` 排队是「内置盘」的手段，对外置 USB 盘不适用。** 55 条把"排队=解法"
      写成了通用纪律，这是**过度外推**（我拿内置盘的机制套外置盘），本条予以更正。
    - **外置盘真正的修复路径（仍需实测择一）**：
      1. **WinRE / 另一台机器**：在能加载 USB 的离线环境里对卷跑 `chkdsk /f`（最可靠）；
      2. **在线修复**：**停掉所有持有该卷句柄的进程**后，让 `chkdsk /f` 能拿到卷
      （本机依赖盘被会话的 python 占用、数据盘被工具 pwsh 占用 ⇒ 需先"腾空"再跑）；
      3. 数据盘是 exFAT 且**已用 52% 且承载迁移目标**时，**尤其不应盲跑** ——
         先确认卷可写、关键数据有第二份，再决定修或"清空重建"。
    - **纪律（新增，优先级高于 55 的 ②）**：
      ① 判"某盘能不能开机检查"**先看 `BusType`**：`Bus=USB` 的外置盘**不要指望 autochk**，
      ② 写这类"机制性结论"前**必须做 A/B 对照**（内置盘 vs 外置盘各试一次），
      不能用单一形态的观测外推成通用规律 —— 这是我本轮最大的方法错误；
      ③ 一个方案"排了队却没生效"时，**先查方案本身的前置假设**（这里就是"启动早期能不能看到该设备"），
      而不是反复重试同一方案（我重试了三次 + 让用户手动重启一次，白耗了用户时间）。
57. **同一「事实源」的两份声明互相矛盾时，权威归「随日期演进的事实流水」，带日期的快照降级（2026-09-26 订正）**：
    > 本条按**铁律 5（去符盘）**书写：盘符仅作"哪个卷"的标识，路径用去符盘形式。
    - **冲突（全哥按铁律 1 提出待核实）**：`新机配置汇总_2026-09-24.md` 记四盘 C/D/F/G、工作区根 `G:\`、
      且自声明为「盘位事实源」；治理段写 C:/D:/E: 三盘、F:/G: 已移除。两边矛盾、都称事实源。
    - **核实**：`Get-Volume` 实测**仅 C/D/E 三盘**（C system 118G / D dalang 405G / E erlang 407G），F:/G: 不存在。
      该文档记录的是 09-24 **上午**快照——其上午刚做的「订正」（F:/G: 已接入）在**当天 16:15 盘位再变**后数小时内即再次过期。
    - **处置**：快照内容按历史保全**不动**；`新机配置汇总_2026-09-24.md` 与 `本机硬件与差异摘要_2026-09-24.md`
      顶部各加「盘位已再次变更」订正块，其「盘位事实源」自我声明作废；**现行盘位/工作区事实源 = 本文件（事实流水）**。
      治理段「开卷四事实源」含该快照——agent 开卷先读顶部订正块，不会再被过期盘位误导。
    - **沉淀**：这是记账 46「事实源已更新、派生文档未同步」的同类缺口，但这次的缺口在**事实源自身的时间性**：
      快照型文档自我声明的「事实源」资格必须带**失效条款**——盘位/硬件类快照在环境变更后应在顶部加订正块声明降级，而非改写正文（历史保全）。
58. **盘位「在位性」是动态事实：任何盘位观测必须带「时点 + 观测工具」，权威流水自己也不例外（2026-09-27 凌晨）**：
    > 本条按**铁律 5（去符盘）**书写：盘符仅作"哪个卷"的标识，路径用去符盘形式。
    - **冲突（WorkBuddy 会话实测，全哥指示补记）**：记账 57 记「09-26 实测仅 C/D/E，F:/G: 不存在」；
      但**同一晚** 09-26 22:23 起的 WorkBuddy 会话**全程** C/D/F/G 在位——`/allin`（治理仓）与
      `/repos/deepseek-harness`（dsh 现役部署）持续正常读写数小时，中途无断连；04:40 复测**仍为 C/D/F/G，E 反而消失**。
    - **核实**：两次观测用的**工具不同**——记账 57 用 `Get-Volume`（Windows 卷视图），
      WorkBuddy 会话用 Git Bash 路径探测 `[ -d /g/ ]`（挂载点视图）+ 实际文件读写；且记账 57 的
      验证时点与提交时点（22:34）可能相距数小时，验证时刻未必是 22:34。两个候选解释**待 A/B 对照**：
      ① 外置盘物理在位状态在当晚确有变化（插拔/休眠断连）；
      ② **观测工具差异**——`Get-Volume` 在该会话环境（沙箱/会话上下文）下可能看不到部分可移动卷，
      而路径探测+真实读写看到的是「可用性」这一更贴近事实的信号。
    - **处置**：记账 57 按历史保全**不动**（其沉淀的「快照失效条款」原则依然成立且被本条再次印证）；
      本条只追加事实与判读。现行口径：**盘位在位性以「当次会话现场实测」为准**，
      读 `docs/MEMORY.md` 的盘位记录时先看观测时点与工具，再决定是否适用于当下。
    - **沉淀**：记账 57 沉淀的是「快照会过期」，本条补上更深一层——**流水条目自己也会过期，且不同观测工具
      看到的"盘位"可能不同**（卷视图 ≠ 挂载点视图 ≠ 可用性）。给 agent 的可执行规则：
      ① 涉及盘位的动作前，用**真实文件读写**（而非仅 `Get-Volume`）验证目标卷可用；
      ② 记录盘位观测时同时记「时点 + 工具」；③ 下次盘位存疑时做 `Get-Volume` 与路径探测的
      **双工具 A/B 对照**（记账 56 的方法教训在此同样适用：先查前置假设，再怀疑世界）。

59. **PowerShell 里对 UTF-8 无 BOM 的中文文件做 `Get-Content -Raw | Set-Content` 往返会烤坏文件（2026-09-27 沉淀，本次真实事故）**：
    我对 `governance/RULES.md`（UTF-8 无 BOM、中文正文）跑了一次「读全文 → 字符串替换 → 写回」，
    结果中文全部变成乱码、段落换行被吞——读取工具再打开时已认不出原文。**这与 35/38 同族**（编码默认值），
    但更隐蔽：**文件仍在、字数看着也对，只有内容是坏的**。**纪律**：① 改文本一律用编辑工具或
    **Python + 显式 `encoding="utf-8"`**；确要用 PowerShell 必须同时钉死读与写两侧编码
    （`-Encoding UTF8` + `[IO.File]::WriteAllText(path, text, UTF8Encoding($false))`）；
    ② 任何批量改写前先 `git status` 确认文件已被跟踪，**出事第一动作是 `git checkout -- <该文件>` 恢复**；
    ③ 写完立刻用**独立解码器**复核（`python -c "open(p, encoding='utf-8').read()"`），不要只看控制台回显
    ——本次乱码正是先由控制台回显暴露，而回显本身也可能是控制台编码造成的假象。

60. **`git add <目录>` 会被仓根 `.gitignore` 的通用规则静默吞掉子目录，且 `git status` 对它保持沉默（2026-09-27 沉淀，代价一次残缺提交）**：
    批 1 提交后用 `git ls-files governance` 核对，发现 `governance/lib/govlib.py` **根本没进提交通道**——
    仓根 `.gitignore` 有 pnpm 构建产物规则 `lib/`（无前导斜杠，任意深度匹配），把 `governance/lib/` 整个吞了；
    而 `git status --short` **不显示被忽略的文件**，所以我一路看着"干净"把残缺的树提交了。
    **后果**：已提交的治理目录在**克隆副本里根本跑不起来**（门禁 import 失败），本地全绿是假象。
    **纪律**：① 新增目录提交后，用 `git ls-files <目录>` 逐项核对**目录完整性**，别只信 `git status`；
    ② 目录名避开仓根已有的通用忽略模式（本次改名 `governance/runtime/` 而不是去和 ignore 规则搏斗）；
    ③ **验收必须在克隆副本里跑一遍**（`git clone . tmp/x` → 在副本里跑门禁），这是唯一能发现该类残缺的动作。

61. **门禁的「自检」必须断言具体判定结果，否则抓不出方向判反这类隐形缺陷（2026-09-27 沉淀）**：
    新写的推送实证门禁把 **`LOCAL_AHEAD` 与 `REMOTE_AHEAD` 判反了**（`merge-base --is-ancestor` 的两个方向搞混）：
    代码跑得通、输出也"像那么回事"，肉眼审阅两遍没看出来；是自检里那条
    「提交一次未推送的 commit → 必须报 local ahead」的用例把它抓出来的。
    **纪律**：① 自检用例要**断言分类/字段值**（`state == "LOCAL_AHEAD"`），不要只断言「非空」「有输出」；
    ② 有方向的判据（领先/落后、包含/被包含、前/后）每个方向都要有一条用例；
    ③ 同类：本次还靠自检抓出「插件序列比对正则漏 `re.MULTILINE` → 漂移永不报警」——判据"看起来在跑"不等于在跑。

62. **新机（台式机）硬件导出件脱敏入库、与旧机版成对；同轮双仓 ff 对齐实测（2026-09-27 深夜，全哥指令「先对齐后脱敏并提交推送」）**：
    - **事实（对齐）**：实测两仓均纯落后（0 领先），fast-forward 对齐无冲突——
      `deepseek-harness` 9775c2a→9cbe2b6（11 笔：governance 门禁 g00~g14 批量落地 + 分发版文档 + preset 探针），
      `allin` 0df1629→2dbdd79（5 笔）。顺带订正：「分发版治理机械保障落地」段所记
      「DSH 侧 6 笔本地提交均未推送」**状态已过时**——远端 master 已含各批次提交（现 HEAD 9cbe2b6），以本条为准。
    - **新增**：`siwpan新机电脑硬件信息 - 腾讯电脑管家检测结果.txt`（台式机 DESKTOP-8RSV60V，
      腾讯电脑管家导出 2026-09-27 23:17:37），置于仓根，与旧机版（6f69fc7 笔记本导出件）并列成对，
      文件名按仓内「新机/旧机」惯例区分。
    - **脱敏处置（照 6f69fc7 方法论第二次执行）**：4 块硬盘序列号（GALAX 500G / 闪迪 8T / 西数 4T x2）
      与有线网卡 MAC 一律掩为 `<已脱敏>`，文件头加脱敏声明行；CPU 序列号 BFEBFBFF00090672 是
      CPUID 签名（同型号 CPU 相同）予以保留；主板序列号为出厂占位符 "Default string" 原样保留；
      UTF-8 BOM 与 CRLF 行尾字节级保持，只做定点替换（4283→4449 字节）。
    - **实测**：脚本断言 5 标识各命中 1 次（无放大、无遗漏）、落盘后独立复核掩码 6 处（5 标识 + 1 声明行）、
      复扫残留 0；`git grep -F` 遍历全历史核对，6 标识全部 absent——本次推送即其首次公开。
      仓侧门禁（repo_hygiene 的 H5）只认密钥形态，**推送前全历史逐标识人工核对是这类内容唯一防线**，此法沿用旧机版惯例。
    - **提交与推送**：c47ae3e（单文件 143 行）推送成功，`ls-remote` 核对 IN_SYNC（remote=local=c47ae3e）。
    - **遗留待办**：原始未脱敏导出件（DESKTOP-8RSV60V 文件名版）仍在仓工作树**未跟踪**，
      不入库不推送；由全哥自行移出或删除，后续盘点工作树时按遗留处理，不入正式流水。
    - **闭环（2026-09-28 00:15 全哥确认，本会话实测）**：原始未脱敏导出件已由全哥删除——
      `git status` 工作树全净、文件不存在，遗留待办就此关闭，工作树仅余已跟踪内容。
    - **沉淀（硬件导出件入库「脱敏四步」，两台机器两次执行零偏差，后续照此办理）**：
      ① 掩码唯一标识（各盘序列号 / MAC / 唯一识别码）；
      ② 保留非唯一事实（CPUID 签名 / 出厂占位符 / 型号·频率·日期等）；
      ③ 字节级保持 BOM 与行尾，只做定点替换并以计数断言防放大遗漏；
      ④ 推送前 `git grep -F` 遍历全历史逐标识核对 absent（公开历史不可撤销，首推即定型）。
