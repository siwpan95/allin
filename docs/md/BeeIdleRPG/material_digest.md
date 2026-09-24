# AICoding 架构设计 · 资料摘要

> 本文档做一件事：**精读主理人转交的全部原始资料，逐份、逐章节做出摘要**——后面任何人拿到这份摘要，都能通过章节号快速定位回原始文件的对应位置。

> 上游输入：主理人转交的全部原始资料（markdown / python / txt）；
> 产出者：`knowledge-ingest-engineer`（知识摄入工程师 - 闻资料），经 G1 校验与人工审核通过后交付。

---

## 0. 元信息

```yaml
标题: BeeIdleRPG（蜂蜜挂机 RPG）- 资料摘要 v1.0
版本: v1.0
状态: Draft
创建日期: 2026-07-15
整理人: knowledge-ingest-engineer（闻资料）
审核人:
  - team-lead（主理人）

原始资料清单:
  - D:\allin\right\bee\docs\architecture\adr\ADR-0001-engine-migration.md: 引擎迁移决策 ADR（Gate 0 已签核）
  - D:\allin\right\bee\docs\architecture\m1-report.md: M1 sim_core 抽取 Spike 报告 + Gate 1 裁定
  - D:\allin\right\bee\docs\architecture\migration-plan.md: 引擎迁移计划（B/C 路线执行蓝图）
  - D:\allin\right\bee\godot\README.md: Godot 前端脚手架 README（M2 / Phase C）
  - D:\allin\right\bee\main.pyw: 项目入口（Tkinter，69 行）
  - D:\allin\right\bee\requirements.txt: Python 依赖清单
```

| 版本 | 日期 | 作者 | 变更内容 |
| --- | --- | --- | --- |
| v1.0 | 2026-07-15 | knowledge-ingest-engineer（闻资料） | 初稿，覆盖 6 份原始资料逐份精读 |

---

## 1. 资料清单

> 列出全部原始资料，每份标注解析状态。解析失败或跳过的必须注明原因。

| 编号 | 文件名 | 类型 | 来源 | 解析状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| D1 | `ADR-0001-engine-migration.md` | md | `eng-lead-adr`（工程负责人/主程序） | 已解析 | 引擎迁移决策 ADR，175 行，评估 4 方案（维持 Tkinter / 迁移 Godot / 迁移 Unity / 换 UI 框架），用户签核 B/C |
| D2 | `m1-report.md` | md | `eng-lead-adr`（工程负责人/主程序） | 已解析 | M1 sim_core 抽取 Spike 报告，195 行，含 Gate 1 裁定（PASS）与三项收尾决策 |
| D3 | `migration-plan.md` | md | `eng-lead-adr`（工程负责人/主程序） | 已解析 | 引擎迁移执行计划，121 行，含 Godot 选型理由、sim_core 抽取范围、桥接方案评估、里程碑 M0-M4 |
| D4 | `godot/README.md` | md | `eng-lead-adr`（工程负责人/主程序） | 已解析 | Godot 前端脚手架说明，86 行，含 TCP JSON-line IPC 桥接架构与协议定义，状态 UNVERIFIED |
| D5 | `main.pyw` | pyw | `eng-lead-adr`（工程负责人/主程序） | 已解析 | Tkinter 项目入口，70 行，含路径初始化、崩溃钩子、根窗口创建 |
| D6 | `requirements.txt` | txt | `eng-lead-adr`（工程负责人/主程序） | 已解析 | Python 依赖清单，12 行，含 pystray/Pillow/openpyxl/sounddevice/numpy/scipy |

**类型说明**：本项目原始资料均为纯文本格式（Markdown / Python / TXT），非 docx/pdf/pptx/xlsx，但按解析能力归类，全部已完成精读。

---

## 2. 资料内容摘要

> 逐份文档按自身章节结构做摘要。每条摘要标注章节号（`D编号，§章节`），后面任何人想核实某个点，直接定位回原文对应位置即可。

### D1：`ADR-0001-engine-migration.md`

> 引擎迁移 vs 维持 Python/Tkinter 技术基座的架构决策记录（Gate 0），用户已签核采纳 B/C 迁移路径 — 来源：`eng-lead-adr`

| 章节 | 内容摘要 |
| --- | --- |
| D1，§0 摘要（TL;DR） | BeeIdleRPG 是 Progress Quest 风格、玩家零输入的文字挂机 RPG。约 9,570 行 `src/` 源码中约 8,319 行（~87%）是引擎无关的纯 Python 模拟/内容生成逻辑，仅约 1,251 行（~13%）绑定 Tkinter/pystray。运行期内容来自 JSON 池而非 Excel，存档是引擎无关的 JSON（`save.json`）。ADR 推荐方案 A（维持 Python），但用户签核了 B/C（迁移 Godot/Unity），前置条件是先抽 sim_core。 |
| D1，§1.1 技术栈 | 语言/运行时：Python 3.8+（CPython）。UI：标准库 `tkinter` + `tk.Canvas` + `pystray`（系统托盘）。音频：`numpy` + `scipy` 程序化合成，`sounddevice` 实时播放（纯 Python 音频管线）。内容配置：`openpyxl` 读取 Excel（构建期），`json`（运行期）由 `json_pool.py` 单例池按需加载。存档：JSON（`save.json`）。打包：PyInstaller。架构风格：MVC + Mixin 控制器拆分。 |
| D1，§1.2 模块划分与代码规模 | `src/` 共 9,570 行。模拟/服务层 `src/app/services/`（19 个 service，~270KB）零 Tkinter。模型层 `src/app/models/`（6 个，~73KB）零 Tkinter。数据/工具 `json_pool.py` + `logging_config.py`（~10KB）。ECS 层 `src/app/ecs/__init__.py`（238 行，当前无引用/休眠）。控制器/UI 层 `game_controller.py`(306) + `game_render.py`(422) + `game_init.py`(310) + `game_tray.py`(144) + `main.pyw`(69) = 1,251 行，绑定 Tkinter/pystray。UI 耦合占比 ~13%。 |
| D1，§1.3 内容驱动方式 | 运行期只读取 JSON 池（`json_pool.py` 文件头注释明确"只读 JSON，不读 Excel"），`data_service.py:7,17` 通过 `get_pool()` 取数据。Excel 是构建期内容创作工具：`excel_to_json.py`/`gen_new_excels.py`/`excel_service.py`(44KB) 把约 24 张配置表转成 JSON。推论：运行期不依赖 Excel，内容迁移风险被显著高估。 |
| D1，§1.4 构建/发布现状 | 入口 `main.pyw`：初始化 `sys.path`、设置崩溃钩子、`tk.Tk()` 创建根窗口、`GameController(root)`、`root.mainloop()`。主循环驱动在 UI 线程：`game_controller.py:172-179` 的 `_game_loop` 用 `root.after(50, self._game_loop)`（20 FPS，与 `settings.py:16 FPS=20` 一致）；每帧 `_update_game(dt)` 后 `_redraw()`。`BeeIdleRPG.spec` 的 hiddenimports 含 pystray/win32gui/PIL/openpyxl/numpy/scipy/sounddevice。 |
| D1，§1.5 模拟逻辑 vs UI 渲染的边界 | 模拟/内容逻辑已事实解耦于 UI：对 `services/` 与 `models/` 全量 Grep（模式 `tkinter|tk\.\|Canvas\|messagebox\|pystray\|Tk\(\)\|GameController`）零命中。UI 耦合高度集中在 4 个控制器文件：`game_render.py`（Canvas 文本绘制）、`game_init.py`（角色创建对话框）、`game_tray.py`（pystray 托盘）、`game_controller.py`（上帝对象，混合模拟编排与 UI 胶水）。架构体检结论：当前唯一结构性缺陷是 `game_controller.py` 的上帝对象把模拟编排与 Tkinter 绑死，是指向"抽取 sim_core"的重构信号而非"迁移引擎"的信号。 |
| D1，§2 候选方案 | 方案 A：维持 Tkinter + 抽取 `sim_core`（推荐）。方案 B：迁移 Godot（GDScript），模拟逻辑整体重写或 GDExtension/子进程 IPC 托管。方案 C：迁移 Unity（C#），模拟逻辑整体重写为 C# 或 IPC 桥接。方案 D：维持 Python，仅替换 UI 框架（PyQt6/textual/浏览器）。 |
| D1，§3 成本-收益矩阵 | A 模拟重写量 ~0 行（仅抽取编排），UI 重写 0 行，适合度 5 星。B 模拟重写 ~8,319 行或 IPC 桥接，UI 重写 ~1,095 行，适合度 2 星。C 模拟重写 ~8,319 行或 IPC 桥接，适合度 1 星。D 模拟重写 0 行，UI 重写 ~1,095 行，适合度 3 星。诚实补充：该品类渲染需求极低（文本+滚动日志+简单分隔条），Godot/Unity 的场景图/物理/着色器/3D/GPU 粒子能力在本作中几乎全部闲置。 |
| D1，§4 风险与缓解 | R1 Python↔引擎语言边界（高，仅 B/C）：~8,319 行重写易语义漂移。R2 存档格式兼容（低）：`save.json` 引擎无关。R3 24 张 Excel 配置迁移（低，被高估）：运行期只读 JSON。R4 构建/分发变化（中）：PyInstaller→引擎导出。R5 一人团队维护成本（高，仅 B/C）。R6 混合桥接 IPC 额外风险（高）：20 FPS 高频日志序列化引入延迟与复杂度。R7 音频系统（中）：numpy/scipy/sounddevice 是 Python 专属。R8 上帝对象（中）：game_controller 绑死 UI，无论选哪个方案都应修。 |
| D1，§5 推荐 | 推荐方案 A——维持 Python/Tkinter，抽取 sim_core，把资源投向 Phase 6。理由：价值主体已解耦（87% 纯 Python 零 UI）、品类不需引擎能力、迁移代价与团队规模错配、内容/存档风险被高估。直面用户选择：先打磨采纳落地为 A 路线，迁移引擎当前不执行降级为触发式未来决策。 |
| D1，§6 决策记录 | Decision：SIGNED-OFF — 用户签核采纳 B/C 迁移 Godot/Unity；前置条件=先抽 sim_core（ADR 风险 R1/R8 要求），再评具体桥接方案。用户裁决议覆盖了 ADR 原推荐 A。若签核 B/C 的后果：~8,319 行模拟重写或 IPC 桥接、音频返工、构建管线重搭、一人团队高停滞风险；强烈建议先做 A 的 sim_core 抽取再评估。建议下一步门控：Phase 6 打磨启动 + sim_core 抽取 spike + 品类扩展信号监测。 |

### D2：`m1-report.md`

> M1 sim_core 抽取 Spike 报告 + Gate 1 裁定，记录 sim_core 抽取完成、golden test 100% 一致、三项收尾决策执行 — 来源：`eng-lead-adr`

| 章节 | 内容摘要 |
| --- | --- |
| D2，§1 M1 目标与范围 | 按 migration-plan §2 + 主理人签核增量规格（1a-1e）执行首次改源码。1a 抓黄金基准（固定 `random.seed(12345)` + 固定缺失存档，跑 200 步 dt=0.05，记录 139 行日志 + 状态指纹）。1b 建 `src/sim_core/` 包（19 service + 6 model + json_pool + logging_config 迁入，engine.py 新增 SimCore，音频改事件队列）。1c 黄金测试。1d 瘦身 game_controller + mixins。1e 冒烟 + Gate 1 报告。硬约束：不改 save.json schema/data/Excel/24 表 JSON，非破坏性，不 git commit，用户真实 tkinter 机器行为不变。 |
| D2，§2 Gate 1 成功标准核对 | 5 项标准全部 PASS：①`import sim_core` 不触发 tkinter/pystray（40/40 模块可导入）；②`SimCore.update(dt)` 逐字节复现 `_update_game`（139/139 日志行逐字一致，指纹 100% 一致）；③services+models+json_pool headless 可跑（集成态，逐 service 单测为 Phase 6 后续工作）；④game_controller 退化为薄前端（161 行，仅持 SimCore + UI 胶水，迁移逻辑全部移除）；⑤save.json schema 不变（to_dict/from_dict 逐字移植）。 |
| D2，§3 迁移指标 | 迁入 `src/sim_core/` 的模拟逻辑共 8,466 行：services/ 19 个（5,757 行）、models/ 6 个（1,229 行）、engine.py（1,050 行新增 SimCore 编排宿主）、json_pool.py（342 行）、logging_config.py（88 行）。非破坏性 shim 193 行（原路径 `from sim_core... import *` 再导出，保护内容工具）。控制器薄前端：game_controller.py 161 行（重写）、game_render.py 422 行（12 处机械改写）、game_io.py 38 行（重写）、game_init.py 133 行（仅保留角色创建 UI）、game_tray.py 144 行（未改）、game_combat/exploration/achievements.py 已删除。 |
| D2，§4 测试结果 | `test_sim_core_golden.py` 2 passed（日志逐字+指纹一致+零 GUI 导入）。headless 全量 import 扫描 40/40 OK。控制器 headless 烟雾 ALL CHECKS PASS。`test_tag_system.py` 4 passed（仓库既有测试不受 M1 影响）。`test_refactor.py` 收集错误（legacy import 路径，M1 前即坏，非本次引入）。Golden 复现率 100%。音频解耦：`SimCore.update` 不再直接调 `self.audio.sfx_*()`，改为 `self.audio_events.append(("sfx_*", ()))`；薄前端每帧消费并真实播放（含 try/except 容错）。200 步实测产生 9 条音频事件。 |
| D2，§5 关键架构/技术决策 | ①非破坏性 shim（无 git 仓库前提下保护用户工具）：真实实现迁入 sim_core/，原路径改为再导出，已验证 shim 别名指向同一对象，用户的内容工具/游戏入口零改动即可继续工作。②属性代理（最小侵入）：GameController.paused/_game_over/_add_log 经 property 代理到 self.sim；game_render.py 仅改数据源前缀。③音频事件队列：消除 sim 对 audio 实现的硬依赖。④SimCore 自包含驱动：update(dt) 纯推进，不持时钟/UI 引用，可直接被 Godot 主循环每帧 tick(dt)。 |
| D2，§6 偏离计划处 | D1：json_pool 落在 sim_core/json_pool.py 而非计划的 sim_core/data/json_pool.py（纯路径差异，接受）。D2：sim_core/config/settings.py 采用再导出子集而非整体拆为双源（接受且更优：模拟参数经 sim_core.config.settings 暴露，UI 参数留前端，单源防漂移）。D3：ECS（238 行休眠零引用）未迁移（接受：死代码零收益，择机清理）。D4：_show_character_creation 成为孤儿（接受：原基准即用默认角色自动开局，golden 已证明启动态一致；建议 M2 前补新游戏动作）。附注：difficulty_service.py:567 有预存 `[DDA-PROBE]` 调试 print（M1 前即存在，建议单独清理）。 |
| D2，§7 引擎风险与知识缺口 | 无新增引擎知识缺口：本次为纯 Python 提取，未触及 Godot 4 API。M2 桥接（GDExtension 托管 / 子进程 IPC）的 Godot 具体 API 仍待原型验证（对应 ADR R6）。R6（IPC 延迟）：M1 已证明 SimCore.update(dt) 为纯推进、可 headless 驱动，为"前端每帧喂 dt"契约铺路。R7（音频）：已通过事件队列隔离，M3 按宿主重做音频时 sim_core 零返工。 |
| D2，§8 待用户审批项 | ①Gate 1 裁定=PASS，是否同意推进 M2？②D4 角色创建孤儿：维持默认角色自动开局还是 M2 前接回？③D1 json_pool 路径：是否需 M2 前平移？④D3 ECS：保留休眠代码还是清理？⑤预存 [DDA-PROBE] 调试 print：是否授权单独清理？ |
| D2，§9 下一步建议 | M2（引擎原型验证）：以 Godot 4 为目标，建最小场景（日志文本框+状态面板），用 GDExtension（首选 A）或子进程 IPC（降级 B）托管 sim_core，验证"前端每帧 sim_core.update(dt)→渲染日志/状态"与跨平台导出；定夺桥接方式。Phase 6 测试补强（建议提前）：为 19 个 service 补 per-service headless 单测。修复 test_refactor.py legacy import。 |
| D2，§10 产物路径清单 | 模拟内核：`src/sim_core/engine.py`、`src/sim_core/services/`（19）、`src/sim_core/models/`（6）、`src/sim_core/json_pool.py`、`src/sim_core/utils/logging_config.py`、`src/sim_core/config/settings.py`。黄金安全网：`tests/test_sim_core_golden.py`、`tests/golden_baseline.json`。薄前端：`src/app/controllers/game_controller.py`、`game_render.py`、`game_io.py`、`game_init.py`、`game_tray.py`。非破坏性 shim：`src/app/services/*.py`、`src/app/models/*.py`、`src/app/utils/logging_config.py`、`src/json_pool.py`。执行纪律确认：未 git commit；未改 save.json schema/data/Excel/24 表 JSON。 |
| D2，§11 M1 收尾（三项签核决策执行） | 主理人签核三项收尾（全按推荐）。§11.1 D4 角色创建接回：engine.py 新增 `_init_new_game(self, race=None, char_class=None, name=None, seed=None)`，默认无参路径与迁移前逐字一致（golden 等价性不变），自定义路径做完整重开（重置计时器/日志/重建服务/固定 RNG）；game_init.py 的 on_confirm 调用 `self.sim._init_new_game(...)`。刻意未做：未在 game_controller 新增"新游戏"触发键/按钮（避免超出授权范围），建议 M2 前补 `Key-N` 绑定或 UI 按钮（待审批）。§11.2 [DDA-PROBE] 清理：删 difficulty_service.py 测试探针整块，grep 全树 0 命中。§11.3 休眠 ECS 删除：grep 确认零外部引用后删 `src/app/ecs/` 整个目录，grep 全树 0 命中。§11.4 验证结果：test_sim_core_golden.py 2 passed、test_init_new_game.py 2 passed（新增 D4 回归）、全量 4 passed、sim_core 零 tkinter/pystray grep 0 命中、headless import 38/38（较 M1 少 2=已删 ECS 包）。§11.5 改动文件清单 5 项。§11.6 Gate 1 收尾结论：PASS 维持，可推进 M2。待审批随访：是否授权在 game_controller.py 增加"新游戏"触发入口。 |

### D3：`migration-plan.md`

> 引擎迁移执行计划（B/C 路线），核心纪律是先抽 sim_core 再评桥接 — 来源：`eng-lead-adr`

| 章节 | 内容摘要 |
| --- | --- |
| D3，§1 引擎选型建议 | 推荐 Godot 4（GDScript），Unity（C#）备选。理由：①模拟层是 Python 且将被托管而非重写，Godot 的 GDExtension+Python 绑定或子进程+IPC 路径比 Unity 更直接；②GDScript 语法近似 Python，上手成本低；③Godot 场景树+Control 节点做文字/日志 UI 比 Tkinter Canvas 更结构化，导出管线天然跨平台；④Godot 导出体积极小、编辑器一体化，单人维护成本更低。选型裁定：先以 Godot 4 为目标做原型验证（M2），最终桥接方式在 sim_core 就绪后于 M2 定夺，Unity 仅当 Godot 不满足时启用。 |
| D3，§2.1 sim_core 抽取范围 | 新建 `src/sim_core/`，迁入：编排循环（game_controller._update_game 迁为 SimCore.update(dt)）、服务层 19 个 service（原样移动）、模型层 6 个 model（原样移动）、json_pool.py（移到 sim_core/data/json_pool.py）、配置/日志工具（settings 中 FPS/REGION_CHANGE_INTERVAL 等模拟参数属 sim_core，WINDOW_WIDTH/HEIGHT 等 UI 参数留前端）、ECS（可选移动）。全部纯 Python、零 tkinter/pystray 依赖、可被 pytest headless 直接 import。 |
| D3，§2.2 明确不动 | 留在 Tkinter 前端不改写：game_render.py（422 行 Canvas 绘制）、game_init.py（310 行角色创建对话框）、game_tray.py（144 行 pystray 托盘）、game_controller.py 的 UI 胶水方法（_build_ui/_on_resize/_on_split_*/_on_close/_on_minimize 及键盘绑定 :112-170, :122-126）、main.pyw（Tkinter 入口）。src/ 下任何业务语义代码在抽取阶段只改 import 路径、不改逻辑。 |
| D3，§2.3 主循环改造 | 现状：root.after(50, _game_loop) 每帧 _update_game(dt)+_redraw()，循环由 Tkinter 事件循环驱动。目标：sim_core 自带与 UI 无关的定时驱动。headless 模式：while running: dt = clock.tick(1/20); sim_core.update(dt)。前端模式：前端每帧以 dt≈0.05s 调用 sim_core.update(dt)，再读取状态快照与日志缓冲做渲染。关键契约：SimCore.update(dt) 是纯函数式推进——输入 dt 与内部状态，输出状态变更+日志/音频事件队列；不调用 tk/pystray/canvas。 |
| D3，§2.4 Gate 1 成功标准 | ①import sim_core 不触发任何 tkinter/pystray/GUI 导入；②现有 _update_game 的全部行为可经 SimCore.update(dt) 复现：给定相同初始存档+相同 dt 序列，产出逐字节一致的日志序列与状态变更（golden-test）；③services/+models/+json_pool 全量 pytest headless 用例通过；④game_controller.py 缩减为薄前端；⑤save.json 的 to_dict/from_dict schema 不变。 |
| D3，§3 桥接方案评估 | 方案 A GDExtension 托管 Python：代价中等，适配度 4 星，首选，保留全部 Python 领域逻辑，Godot 仅渲染。方案 B 子进程+IPC：代价中高，适配度 3 星，隔离最彻底但本作文字挂机无需此隔离，R6 复杂度不划算，仅当 A 不可行时降级。方案 C 整体重写 GDScript/C#：代价极高，适配度 1 星，强烈避免，违反 ADR 纪律。裁定原则：桥接而非重写。 |
| D3，§4 里程碑 | M0 准备（文档，已完成）。M1 sim_core spike（强制前置，已完成）。M2 引擎原型验证：以 Godot 4 为目标建最小场景，用 GDExtension 或子进程托管 sim_core，跑通"前端每帧喂 dt→sim_core 推进→渲染日志/状态"，验证桥接延迟与跨平台导出，定夺桥接方式（A/B）。M3 内容/存档迁移：JSON 内容池与 save.json 直接复用（几乎零成本），Excel→JSON 导出器保留构建期，音频管线按宿主重做（R7）。M4 切换发布：双轨并行（Tkinter 旧前端+引擎新前端），验证一致后切换默认入口，保留 Tkinter 前端作回退。 |
| D3，§5 明确声明不动 | save.json 存档格式（引擎无关 JSON，schema 冻结+版本号，跨 Tkinter/Godot/Unity 直接复用）。data/ 存档目录与运行数据（不迁不分叉，sim_core 仍读写同一目录）。Excel 配置（保持 excel_to_json.py/excel_service.py 构建期产出 JSON，不逐表手工迁移）。24 张表 JSON（运行期内容即 JSON 池，原样复用，仅做完整性/冗余审计）。上述资产在 M1-M4 全程保持不变。 |
| D3，§6 已知风险与缓解 | R1：M1 抽 sim_core + M2 桥接而非重写，golden-test 防语义漂移。R2：save.json schema 冻结+版本号全程不动。R3：运行期只读 JSON，Excel 构建期保留，不手工迁移。R4：M4 双轨并行+新 CI，Tkinter 前端留作回退。R5：优先 Godot（轻量），sim_core 保留 Python 知识资产。R6：首选 GDExtension（A）而非子进程 IPC（B）。R7：M3 按宿主重做音频，sim_core 仅发音频事件。R8：M1 直接解决（_update_game 迁入 sim_core，game_controller 退化为薄前端）。 |

### D4：`godot/README.md`

> Godot 前端脚手架说明（M2 / Phase C），描述 TCP JSON-line IPC 桥接架构，状态 UNVERIFIED — 来源：`eng-lead-adr`

| 章节 | 内容摘要 |
| --- | --- |
| D4，§架构 | Godot 前端（game.gd + sim_bridge.gd）通过 TCP JSON-line（127.0.0.1:18765）驱动 Python 侧 sim_core 桥接服务（`python -m src.sim_core.bridge`）。模拟内核 SimCore 完全在 Python 侧运行（headless，无 GUI 依赖）。Godot 仅作渲染/输入前端。证明"UI 与模拟彻底解耦"：内核可在独立进程中复现黄金基准（见 tests/test_sim_bridge.py）。 |
| D4，§运行步骤 | ①在 bee/ 根目录启动桥接服务 `python -m src.sim_core.bridge --port 18765`（启动后向 stdout 打印 READY 18765）。②用 Godot 4.x 打开 godot/ 作为项目。③按 F5 运行，UI 应显示 idle RPG 日志与状态（等级/金币/区域/时间/击杀/死亡），实时推进。④退出 Godot 项目时 game.gd._exit_tree 发送 quit 关闭桥接服务。 |
| D4，§协议速查 | 客户端→服务端命令：`{"cmd":"init","seed":12345,"save_path":""}`（固定种子确定性新建）、`{"cmd":"step","dt":0.05}`（推进一帧）、`{"cmd":"state"}`（取回 log_messages+fingerprint）、`{"cmd":"new_game","name":..,"race":..,"char_class":..,"seed":?}`（角色创建后重开）、`{"cmd":"quit"}`（优雅退出）。服务端响应：`{"ok":true,...}` 或 `{"ok":false,"error":"..."}`。race/char_class 为字符串 ID（如 WARRIOR/HUMAN，大小写不敏感），由桥接服务解析为枚举。 |
| D4，§注意 | sim_bridge.gd 的 PORT 必须与启动桥接服务时的 --port 一致（默认 18765）。端口固定便于 Godot 连接；若需多开改 --port 与 PORT 常量。接入角色创建 UI：Godot 侧收集 name/race/class 后调用 _bridge.new_game(...)。 |
| D4，§Phase C 验收清单 | 前置：本机安装 Godot 4.x（建议 4.3+，更高版本打开时点"升级"即可，config_version=5 向后兼容无害）。步骤：先起 bridge 服务，再用 Godot 打开 godot/ 按 F5 运行 game.tscn。预期（PASS 判定）：①bridge 终端首行打印 READY 18765；②Godot 运行后 Stats 从"等待连接..."变为实时刷新（Lv N/金币 N/区域 N/时间 N.N/击杀 N/死亡 N）；③LogView 出现 idle RPG 日志文本并持续滚动（约每 0.05s 一帧）；④退出 Godot 项目→bridge 终端收到 quit 并退出。设计预期澄清：Godot 端不要求逐字节等于 golden_baseline.json，字节级黄金一致性由 tests/test_sim_bridge.py（子进程 Python 跑）守护。排错：连接失败确认 bridge 先启动/端口一致/防火墙未拦截；中文乱码检查 Godot 文本编码设置；bridge 单连接 listen(1) 同一时刻只接一个 Godot 实例。 |

### D5：`main.pyw`

> Tkinter 项目入口，70 行，含路径初始化、崩溃钩子、根窗口创建 — 来源：`eng-lead-adr`

| 章节 | 内容摘要 |
| --- | --- |
| D5，§文件头注释 | 蜂蜜挂机 RPG - 项目入口。基于 MVC 架构，逻辑与数据解耦。运行方式：python main.py（开发模式）/ python build_exe.py（打包为 exe）。依赖：Python 3.8+, tkinter（内置）, 可选 pystray/Pillow/openpyxl。 |
| D5，§路径初始化 | 行 18-24：如果 `sys.frozen`（PyInstaller 打包后），`sys.path.insert(0, sys._MEIPASS)`；否则开发环境将项目根目录加入 sys.path。必须在 import src.* 之前完成。 |
| D5，§main() 函数 | 行 27-65：import tkinter as tk；from src.app.utils.logging_config import setup_root_logger；from src.app.controllers.game_controller import GameController。初始化日志系统 setup_root_logger()。设置 sys.excepthook 捕获未处理异常（写入 crash.log + 调用 sys.__excepthook__）。root = tk.Tk()。设置窗口图标（打包后从 exe 读取，否则从 BeeIdleRPG.ico 读取，失败不影运行）。root.resizable(True, True)（Canvas 自适应）。GameController(root)。root.mainloop()。 |

### D6：`requirements.txt`

> Python 依赖清单，12 行 — 来源：`eng-lead-adr`

| 章节 | 内容摘要 |
| --- | --- |
| D6，§依赖列表 | pystray>=0.19.0（系统托盘功能，可选）。Pillow>=9.0.0（pystray 依赖，可选）。openpyxl>=3.1.0（Excel 配置导入支持，可选，没有则回退 JSON）。sounddevice>=0.4.6（音频实时播放，可选，缺失时自动禁用音效）。numpy>=1.24.0（音频合成引擎，必需）。scipy>=1.10.0（音频合成引擎，必需）。 |
| D6，§依赖分类 | 与 UI 框架正交的第三方库（音频/Excel/托盘），与 Tkinter 无强绑定（见 D1，§1.4 BeeIdleRPG.spec hiddenimports）。numpy/scipy 为必需依赖（音频合成引擎），其余为可选。 |

---

## 3. 冲突记录

> 不同资料对同一事实描述矛盾时，**并列保留两个版本**，不做裁决。

| 编号 | 冲突主题 | 版本 A | 出处 A | 版本 B | 出处 B | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | 桥接方式：GDExtension（首选）vs 子进程 IPC（实际实现） | GDExtension 托管 Python 为首选（方案 A，适配度 4 星）；子进程 IPC 仅当 A 不可行时降级使用（方案 B，适配度 3 星） | D3，§3 桥接方案评估 | Godot 前端脚手架实际采用 TCP JSON-line 子进程 IPC（127.0.0.1:18765），而非 GDExtension | D4，§架构 | D3 计划推荐 GDExtension 为首选、IPC 为降级方案，但 D4 的实际脚手架已实现 IPC 方案。D2 §7 注明"M2 桥接（GDExtension 托管 / 子进程 IPC）的 Godot 具体 API 仍待原型验证"，即最终桥接方式尚未定夺。此处为计划推荐与实际实现之间的差异，需在 M2 阶段裁决。 |
| X2 | ADR 推荐方案 vs 用户签核方案 | 推荐方案 A（维持 Python/Tkinter + 抽 sim_core），适合度 5 星；方案 B/C（迁移 Godot/Unity）当前不推荐 | D1，§5 推荐 + §3 成本-收益矩阵 | 用户签核采纳 B/C（迁移 Godot/Unity），前置条件=先抽 sim_core | D1，§6 决策记录 | ADR 基于代码实情推荐 A（低风险高回报），但用户裁决议选择了 B/C（高风险路径）。ADR 明确指出"结论不迎合迁移引擎的字面选择，而基于代码实情"，最终拍板权在用户。此为推荐与决策之间的已知分歧，已在 ADR 中显式记录。 |
| X3 | 模拟逻辑行数：ADR 估算 vs M1 实测 | 约 8,319 行（~87%）为引擎无关纯 Python 模拟/内容生成逻辑 | D1，§0 摘要 + §1.2 模块划分 | 迁入 src/sim_core/ 的模拟逻辑共 8,466 行（含新增 engine.py 1,050 行） | D2，§3 迁移指标 | 差异 147 行可解释：ADR 的 8,319 行是对现有 services+models+utils 的估算值（"约"），M1 的 8,466 行是实际迁移后实测值，且包含新增的 engine.py（SimCore 编排宿主，1,050 行新代码，非原有逻辑）。两者口径不同，非真冲突，但下游引用行数时需注意区分"原有模拟逻辑规模"与"sim_core 迁移后总规模"。 |
| X4 | ECS 处理方式：迁移 vs 不迁移 vs 删除 | 计划列为"可选移动"到 sim_core/ecs/，择机决定是否接入 | D3，§2.1 抽取范围 | M1 偏离 D3 决定不迁移（休眠死代码零引用零收益）；M1 收尾签核后直接删除 src/app/ecs/ 整个目录 | D2，§6 偏离 D3 + §11.3 休眠 ECS 删除 | 计划阶段保留可选项，M1 执行时先决定不迁移，收尾时进一步决定删除。演进路径清晰，非冲突，但下游需知 ECS 已不存在，不应在架构设计中引用 ECS 概念。 |
| X5 | json_pool 落位路径 | 计划指定移动到 sim_core/data/json_pool.py | D3，§2.1 抽取范围 | M1 实际落在 sim_core/json_pool.py（偏离 D1，接受：纯路径差异功能等价，M2 如需可平移） | D2，§6 偏离 D1 | 路径差异已裁定接受，非未决冲突，但下游引用 json_pool 路径时需以实际落位 sim_core/json_pool.py 为准。 |
| X6 | 角色"新游戏"入口可达性 | M1 收尾已接回 _show_character_creation → SimCore._init_new_game，对话框功能化 | D2，§11.1 D4 角色创建接回 | 对话框已功能化但需一个触发入口才能被用户触达，当前 game_controller 未新增"新游戏"触发键/按钮 | D2，§11.1 刻意未做 + §11.6 待审批随访 | 功能已接回但 UI 入口缺失，用户当前无法通过界面触发自定义角色创建。待审批：是否授权在 game_controller.py 增加"新游戏"触发入口（建议 `Key-N` 或 UI 按钮）。此为待决项而非信息冲突。 |

---

## 4. 硬指标清单

| 章节 | 硬指标 | 状态 |
| --- | --- | --- |
| §1 | 每份资料有解析状态，失败/跳过注明原因 | ✅ 6/6 份资料全部已解析，无失败/跳过 |
| §2 | 每份文档按章节逐条摘要，每条标注了 `D编号，§章节` | ✅ D1-D6 共 6 份，每条均标注 `D编号，§章节`，可追溯至原文件对应位置 |
| §3 | 冲突信息并列保留，不做裁决 | ✅ 共识别 6 条记录（X1-X6），其中 X1/X2 为真冲突（计划推荐 vs 实际实现/用户决策），X3-X6 为差异/待决项，均并列保留双版本并标注出处，未做裁决 |

---

## 术语表

> 项目专有名词索引，供下游成员查阅。

| 术语 | 含义 | 出处 |
| --- | --- | --- |
| BeeIdleRPG | 蜂蜜挂机 RPG，Progress Quest 风格、玩家零输入的文字挂机 RPG | D1，§0 |
| sim_core | 模拟内核，纯 Python 包，零 tkinter/pystray 依赖，可被 pytest headless 直接 import 与运行 | D3，§2.1 |
| SimCore | sim_core 的核心类，承载全部模拟编排，`update(dt)` 为纯函数式推进 | D2，§5 |
| SimCore.update(dt) | 纯函数式推进契约：输入 dt 与内部状态，输出状态变更+日志/音频事件队列；不调用 tk/pystray/canvas | D3，§2.3 |
| golden test | 黄金测试，固定 random.seed(12345)+固定缺失存档，跑 200 步 dt=0.05，记录 139 行日志+状态指纹，逐字复现验证 | D2，§1 |
| golden_baseline.json | 黄金基准夹具文件，位于 tests/golden_baseline.json | D2，§1 |
| DDA | Dynamic Difficulty Adjustment（动态难度调整），difficulty_service.py 实现 | D2，§6 |
| DDA-PROBE | difficulty_service.py:567 的预存调试 print 输出，M1 收尾已清理 | D2，§6 + §11.2 |
| ECS | Entity Component System（实体组件系统），原 src/app/ecs/ 238 行，休眠零引用，M1 收尾已删除 | D1，§1.2 + D2，§11.3 |
| GDExtension | Godot 的 C++/Python 扩展机制，可托管 Python sim_core，迁移计划桥接方案 A（首选） | D3，§1 + §3 |
| IPC | Inter-Process Communication（进程间通信），子进程+IPC 为迁移计划桥接方案 B（降级） | D3，§3 |
| TCP JSON-line IPC | Godot 前端脚手架实际采用的桥接协议，127.0.0.1:18765，每行一个 JSON 命令 | D4，§架构 |
| sim_bridge.gd | Godot 侧桥接脚本，负责 TCP 连接与命令收发 | D4，§架构 |
| json_pool | 运行期只读 JSON 数据池，位于 src/sim_core/json_pool.py（原 src/json_pool.py） | D1，§1.3 + D2，§3 |
| Excel→JSON 构建管线 | excel_to_json.py/excel_service.py 在构建期把约 24 张配置表转成 JSON，运行期不读 Excel | D1，§1.3 |
| save.json | 引擎无关的 JSON 存档格式，由 to_dict/from_dict 序列化，schema 冻结+版本号 | D1，§1.1 + D3，§5 |
| ADR-0001 | 架构决策记录，引擎迁移 vs 维持 Python/Tkinter，状态 SIGNED-OFF（用户签核 B/C） | D1，§0 |
| Gate 0 | 架构决策门（P0 阻塞质量门），ADR-0001 在此签核 | D1，§0 |
| Gate 1 | sim_core 抽取验收门，5 项成功标准全部 PASS | D2，§2 |
| M0-M4 | 迁移里程碑：M0 准备（已完成）→ M1 sim_core spike（已完成）→ M2 引擎原型验证（当前）→ M3 内容/存档迁移 → M4 切换发布 | D3，§4 |
| R1-R8 | ADR 风险编号：R1 语言边界/R2 存档兼容/R3 Excel 迁移/R4 构建分发/R5 一人团队成本/R6 IPC 风险/R7 音频系统/R8 上帝对象 | D1，§4 |
| D1-D4（M1 偏离） | M1 阶段偏离计划记录：D1 json_pool 路径/D2 settings 再导出/D3 ECS 不迁移/D4 角色创建孤儿 | D2，§6 |
| Phase 6 | 打磨阶段：测试覆盖、性能剖析、24 表资产审计 | D1，§5 |
| Progress Quest | 零操作文字挂机 RPG 品类参考 | D1，§0 |
| PyInstaller | Python 打包工具，输出 Windows exe，Excel/JSON 资源外放至 dist/resources/ | D1，§1.1 |
| pystray | Python 系统托盘库，game_tray.py 144 行使用 | D1，§1.1 |
| shim | 非破坏性再导出垫片，原路径改为 `from sim_core... import *`，保护用户内容工具 | D2，§5 |

---

## 下游关注要点

> 明确下游成员（business-architect、research-analyst）需要关注的关键约束与决策基线。

### business-architect 需关注

1. **项目定位**：BeeIdleRPG 是 Progress Quest 风格、玩家零输入的文字挂机 RPG，一人团队（全哥，独立开发者）。（D1，§0）
2. **当前架构基线**：Python 3.8+ / Tkinter，MVC + Mixin 控制器拆分，~9,570 行 src/ 源码。sim_core 已抽取完成（8,466 行纯 Python），game_controller 退化为薄前端（161 行）。（D1，§1.2 + D2，§3）
3. **已签核决策**：ADR-0001 SIGNED-OFF 采纳 B/C（迁移 Godot/Unity），前置条件 sim_core 抽取已完成（Gate 1 PASS）。当前处于 M2 阶段（Godot 4 引擎原型验证）。（D1，§6 + D2，§2 + D3，§4）
4. **桥接方式待定**：计划推荐 GDExtension（A 首选）但实际脚手架已实现子进程 IPC（B），M2 需定夺。（D3，§3 + D4，§架构 + X1）
5. **不可变约束**：save.json schema 冻结+版本号、data/ 存档目录不迁不分叉、Excel 构建期保留不手工迁移、24 表 JSON 原样复用。（D3，§5）
6. **音频解耦**：SimCore 通过事件队列发布音频事件，前端消费并播放；M3 按宿主重做音频时 sim_core 零返工。（D2，§5 + D3，§6 R7）
7. **待决项**：角色"新游戏"UI 入口缺失（D2，§11.6）；Godot 脚手架状态 UNVERIFIED（D4，§开头）。

### research-analyst 需关注

1. **调研重点-Godot 4 引擎适配**：本作品类为零操作文字挂机 RPG，渲染需求极低（文本+滚动日志+简单分隔条），Godot/Unity 的渲染/物理/着色器/3D/GPU 粒子能力在本作中几乎全部闲置。（D1，§3 + D3，§1）
2. **调研重点-桥接方案对比**：GDExtension 托管 Python（方案 A，首选，保留全部 Python 逻辑）vs 子进程 IPC（方案 B，降级，隔离彻底但 R6 延迟复杂度）。需调研 GDExtension Python 绑定成熟度与 IPC 在 20 FPS 高频日志场景下的性能表现。（D3，§3 + D4，§架构 + X1）
3. **调研重点-跨平台导出**：Godot 导出管线天然跨平台（Windows/Linux/macOS/Web/移动），这是迁移的真实收益之一。（D3，§1）
4. **调研重点-音频系统迁移**：当前 numpy/scipy/sounddevice 程序化音频（44KB 代码）是 Python 专属，M3 需改用 Godot AudioStream。需调研 Godot 音频 API 对程序化合成音频的支持能力。（D1，§4 R7 + D3，§6）
5. **调研重点-一人团队风险**：全哥为独立开发者，迁移引擎的维护成本与停滞风险需重点评估（R5）。（D1，§4 + D3，§6）
6. **基线事实**：sim_core 已可 headless 独立运行与测试（Gate 1 PASS），SimCore.update(dt) 为纯推进契约，可直接被 Godot 主循环每帧 tick(dt)。（D2，§2 + §5）

---

## 附录 A：生成流程

### 流程总览

| 步骤 | 动作 | 落入章节 |
| --- | --- | --- |
| Step0 | 读取模板 + 全部原始资料（6 份：D1-D6） | — |
| Step1 | 盘点资料清单，标注解析状态 | §1 |
| Step2 | 逐份打开资料，按自身章节结构逐条摘要 | §2 |
| Step3 | 交叉比对不同资料，发现并记录矛盾 | §3 |
| Step4 | 逐项核验硬指标 | §4 |
| Step5 | 提取项目专有名词，编制术语表 | 术语表 |
| Step6 | 整理下游关注要点（business-architect / research-analyst） | 下游关注要点 |

```mermaid
flowchart LR
    S0[读取模板与资料] --> S1[盘点资料清单]
    S1 --> S2[逐份精读逐章节摘要]
    S2 --> S3[交叉比对记录冲突]
    S3 --> S4[硬指标自检]
    S4 --> S5[编制术语表]
    S5 --> S6[整理下游关注要点]
```

### 整理原则

1. **逐份精读，不跨文档归并**：摘要按文档自身章节结构组织，不做跨文档的主题重组（那是下游的事）
2. **出处即章节号**：每条摘要标注 `D编号，§章节`，直接映射回原文位置
3. **冲突保留**：矛盾信息并列保留两个版本，不擅自裁决
4. **事实驱动**：以原始资料中的事实为准，不添加主观推断

### 引用方式说明

本摘要中的引用方式包括：
- **直接引用**：直接引述原文关键语句（如决策字段、行数数据）
- **数据提取**：从原文表格/列表中提取数值（如行数、测试通过数）
- **综合归纳**：将原文多个段落的要点归纳为一条摘要
- **推断**：基于原文事实做出的逻辑推论（均已标注出处，且标注为"推论"）

---

## 附录 B：解析 Skill

本项目原始资料均为纯文本格式（Markdown / Python / TXT），未使用 docx/pdf/pptx/xlsx 格式。解析方式为直接读取文件全文并逐章节精读。以下为模板标准解析能力映射，供后续阶段如有新格式资料时参考：

- `docx`：Word 类产品/业务文档
- `pdf`：PDF 类规范、手册、报告
- `pptx`：PPT 类方案/汇报
- `xlsx`：Excel 类数据清单、指标表
