# AICoding 架构设计 · 行业调研报告

> 本文档为《AICoding 架构设计》核心产物之一，定位为**行业调研报告（research_report）**。
> 上游输入：主理人转交的用户诉求与 material_digest.md；
> 下游输出：驱动 `business-architect`（业务架构师）的行业调研判断，最终落入《高层架构设计》的 §3 行业调研章节。

> **工具说明**：由 `research-analyst`（研究分析师 - 查有据）负责产出，经 G2 自动校验与人工审核通过后方可进入下游消费。
> **结构纪律**：全文按「事实 → 对比 → 建议 → 风险」四段式组织，严禁四段之间倒序或跳段。

---

## 0. 元信息：修订记录

```yaml
标题: BeeIdleRPG（蜂蜜挂机 RPG）- 行业调研报告 v1.0
版本: v1.0
状态: Reviewing
创建日期: 2026-07-15
最后更新: 2026-07-15
调研人: 查有据（research-analyst）
审核人:
  - 主理人（team-lead）

关联文档:
  上游输入:
    - 用户诉求: 由主理人注入 — 基于 D:\allin\right\bee 项目（BeeIdleRPG）生成完整架构方案
    - 调研目标: Godot 4 适配性、桥接方案对比、跨平台导出、音频迁移、一人团队风险、云端部署
    - material_digest.md: v1.0（6/6 份资料已解析）
  下游产出:
    - 高层架构设计 §3 行业调研: 将由 business-architect 整合到此章节
```

| 版本 | 日期 | 作者 | 变更内容 | 评审状态 |
| --- | --- | --- | --- | --- |
| v1.0 | 2026-07-15 | 查有据（research-analyst） | 初稿 | Reviewing |

---

## 1. 调研问题收敛

> 调研启动前，先围绕用户诉求收拢为明确的调研问题集合，确保调研不偏离当前项目背景。

### 1.1 原始调研种子

> 从 material_digest.md 下游关注要点与用户诉求中提取需要调研验证的论题，逐条给出调研优先级。

| 编号 | 待验证论题 | 来源（用户诉求要点） | 调研优先级 | 备注 |
| --- | --- | --- | --- | --- |
| S1 | Godot 4 引擎对零操作文字挂机 RPG 品类的适配性——是否有同类游戏成功案例 | material_digest §下游关注要点 1：品类渲染需求极低 | 高 | 决定引擎选型是否正确 |
| S2 | GDExtension 托管 Python vs 子进程 IPC 桥接方案——成熟度与 20FPS 性能对比 | material_digest §下游关注要点 2 + 冲突 X1：桥接方式分歧 | 高 | 当前阶段核心决策冲突 |
| S3 | Godot 跨平台导出能力——Windows/Linux/macOS/Web/移动端导出成熟度 | material_digest §下游关注要点 3：跨平台是迁移真实收益 | 高 | 决定迁移的 ROI |
| S4 | 音频系统迁移路径——numpy/scipy 程序化合成音频到 Godot AudioStream 的方案 | material_digest §下游关注要点 4：44KB Python 专属音频 | 中 | 影响内容完整性 |
| S5 | 一人团队引擎迁移的风险与最佳实践——停滞风险评估 | material_digest §下游关注要点 5 + 风险 R5 | 高 | 决定项目可行性 |
| S6 | 云端部署可能性——idle RPG 是否有云端运行/分发前景 | 用户选择 need_cloud_baseline_check=true | 中 | 影响长期架构方向 |

### 1.2 调研问题收敛

> 将 §1.1 的种子收敛为 5 个可执行的调研问题。每条问题必须明确调研对象、调研目标和产出预期。

| 编号 | 调研问题 | 调研对象 | 调研目标 | 预期产出 | 关联种子 |
| --- | --- | --- | --- | --- | --- |
| Q1 | Godot 4 是否适合零操作文字挂机 RPG 品类？行业中有哪些同类游戏使用 Godot 开发并成功发布？ | Godot 4 引擎 + 同类 idle/incremental RPG 游戏案例 | 验证 Godot 4 对低渲染需求、文本驱动、自动推进品类的适配性 | 引擎适配性评估 + 同类案例清单 | S1 |
| Q2 | GDExtension Python 内嵌与 TCP JSON-line IPC 桥接两种方案在成熟度、性能、维护成本上孰优孰劣？ | godot-python / py4godot / godot-python-extension 项目 + TCP IPC 工程实践（GodotAIGym 等） | 解决冲突 X1：为桥接方案选型提供证据链 | 方案对比矩阵 + 加权评分结论 | S2 |
| Q3 | Godot 4 的跨平台导出能力（桌面/移动/Web）是否足以支撑 BeeIdleRPG 的分发需求？Web 导出对桥接方案有何约束？ | Godot 4 官方文档 + 导出实践 | 评估迁移的真实收益和平台限制 | 平台导出成熟度矩阵 + Web 平台约束清单 | S3 |
| Q4 | BeeIdleRPG 当前的 numpy/scipy 程序化音频合成（44KB）在 Godot 中有哪些迁移路径？各自可行性如何？ | Godot AudioStreamGenerator / AudioStreamWAV API + 社区实践 | 为音频迁移提供技术路径建议 | 音频迁移路径对比 + 可行性评估 | S4 |
| Q5 | 一人团队从 Python/Tkinter 迁移到 Godot 4 的主要风险有哪些？行业有何最佳实践可降低停滞风险？独立开发者 idle RPG 的云端部署前景如何？ | 引擎迁移案例 + 独立开发者实践 + idle RPG 云端架构案例 | 评估项目可行性并为风险缓解提供建议；评估云端部署的可行路径 | 风险清单 + 缓解建议 + 云部署前景评估 | S5, S6 |

---

## 2. 事实：标杆系统盘点和方案详述

> **四段式「事实」段**。只陈列调研发现的事实，不做引申建议或边界裁决。

### 2.1 行业标杆清单

> 完整盘点调研覆盖的所有标杆系统，给出标签化画像。

**硬指标**：≥ 3 家；至少包含 1 家头部 SaaS/商业代表 + 1 家开源/自研代表。

| 编号 | 标杆系统 | 厂商 / 社区 | 部署形态 | 场景覆盖 | 技术亮点 | 商业模式 | 调研来源 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | GDExtension Python Binding（godot-python / py4godot / godot-python-extension） | 开源社区（touilleMan / niklas2902 / maiself） | 本地插件 | Python-Godot 进程内嵌绑定 | GDExtension 嵌入 CPython 解释器，Python 脚本可直接操作 Godot 节点 | 开源（MIT） | https://github.com/niklas2902/py4godot ; https://github.com/maiself/godot-python-extension |
| B2 | TCP JSON-line IPC Bridge（BeeIdleRPG 当前脚手架 + GodotAIGym 先例） | 自研 / 开源实践 | 子进程 IPC | Godot 前端通过 TCP JSON-line 驱动 Python 后端 SimCore | 127.0.0.1:18765 JSON-line 协议；init/step/state/new_game/quit | 自研 | https://blog.csdn.net/weixin_32060671/article/details/161274134 |
| B3 | A Dark Forest（GodotProjectZero） | 开源社区（N0best1rn / tiny_takin_teller） | 桌面 / Web | Godot 纯 GDScript 开发的增量放置游戏，灵感来自 A Dark Room | 纯 GDScript + Godot Resources；MIT 许可；Steam + itch.io 发布 | 开源 + 社区驱动 | https://github.com/N0best1rn/GodotProjectZero |
| B4 | Gaiadon: Eternal Quest | nadukkon（独立开发者） | Web（HTML5）+ Steam | Godot 开发的增量/idle RPG，含装备/日常任务/转生/宠物/大陆/Boss | Godot 引擎 + HTML5 WebAssembly 导出；Steam + itch.io + Patreon | 商业（免费 + Patreon 赞助） | https://nadukkon.itch.io/gaiadon-eternal-quest |

### 2.2 标杆方案详述

> 每家标杆逐一展开；每段区分「已核实的事实」与「推断/假设」。

#### 2.2.1 B1 - GDExtension Python Binding（godot-python / py4godot / godot-python-extension）

| 维度 | 内容 | 置信度 |
| --- | --- | --- |
| 产品定位 | 为 Godot 引擎提供 Python 语言绑定的 GDExtension 插件，使开发者能像使用 GDScript 一样用 Python 编写游戏逻辑 | 已核实 |
| 目标用户 | 熟悉 Python 生态且希望在 Godot 中复用已有 Python 代码库（NumPy/SciPy/PyTorch 等）的开发者 | 已核实 |
| 核心能力 | 在 Godot 运行时内嵌入 CPython 解释器；Python 脚本可直接操作 Godot 节点/资源/信号；支持 _ready()/_process() 等引擎生命周期回调 | 已核实 |
| 架构特点 | 三层架构：底层 C++ 实现 GDExtension 接口 + 中层 Python 实现 godot 模块 + 上层实现 Python 脚本语言支持。通过 pybind11/CFFI 类机制完成 Godot Variant 类型与 Python 对象的双向转换 | 已核实（来源：py4godot 与 godot-python-extension 文档） |
| 部署形态 | 本地 GDExtension 插件，放置于 Godot 项目 addons/ 目录。需针对目标平台预编译 .dll/.so/.dylib | 已核实 |
| 集成方式 | GDExtension 动态库加载，需在 .gdextension 配置文件中声明 entry_symbol 和 compatibility_minimum | 已核实 |
| 定价模式 | 全部开源（MIT 许可），免费使用 | 已核实 |
| 优势 | 进程内调用无 IPC 延迟；可直接调用 NumPy/SciPy 等 Python 库；Python 脚本可作为 Godot 节点脚本挂载 | 已核实 |
| 局限 | 三个项目均明确标注「实验性」「非生产就绪」「早期开发阶段，不要用于大型项目」；仅 py4godot 支持 Windows/Linux/macOS/Android/iOS 但仍为 alpha 版本（4.6-alpha15）；GDExtension 在 Godot 4.0 到 4.1 之间发生过二进制兼容性破坏，每次 Godot 小版本升级需重新编译；Web 导出需启用 Extension Support 且要求跨域隔离 | 已核实（来源：三个项目的 GitHub README 与 Release Tags） |
| 对本项目的参考价值 | 证明 GDExtension Python 内嵌技术路线存在但尚未成熟。对于一人团队，构建复杂度（需配置 C++ 编译环境、处理多平台构建、版本耦合）和稳定性风险（实验性标注）可能超出可承受范围 | 推断（来源：综合三个项目的状态声明与 GDExtension 版本兼容性文档） |

#### 2.2.2 B2 - TCP JSON-line IPC Bridge

| 维度 | 内容 | 置信度 |
| --- | --- | --- |
| 产品定位 | Godot 前端通过 TCP JSON-line 协议驱动独立 Python 后端进程的桥接方案。BeeIdleRPG 当前 M2 阶段脚手架已实现此方案 | 已核实（来源：material_digest D4 godot/README.md） |
| 目标用户 | 已有成熟 Python 模拟内核（sim_core）且希望迁移到 Godot 前端的游戏开发者 | 已核实 |
| 核心能力 | TCP 连接（127.0.0.1:18765）；JSON-line 协议（每行一个 JSON 对象）；支持 init/step/state/new_game/quit 命令；SimCore.update(dt) 纯推进可被 Godot 每帧 tick | 已核实（来源：material_digest D2/D4） |
| 架构特点 | Godot 前端通过 StreamPeerTCP 连接 Python 后端；Python 后端运行 sim_core headless；双方遵循请求-响应同步模型。game_controller 已退化为薄前端（161 行） | 已核实（来源：material_digest D2 m1-report.md） |
| 部署形态 | 本地子进程：Godot 导出后启动 Python 子进程，或用户预装 Python 运行时。Web 导出不支持原生 TCP（需 WebSocket 适配器） | 已核实（来源：Godot Web 导出文档） |
| 集成方式 | sim_core 零改动即可运行（SimCore.update(dt) 纯推进，不持时钟/UI 引用）；Godot 侧 sim_bridge.gd 负责协议驱动 | 已核实（来源：material_digest D2） |
| 定价模式 | 自研，无外部许可成本 | 已核实 |
| 优势 | 实现简单（JSON 可读可调试）；语言无关（Python 侧独立于 Godot 版本）；sim_core golden test 139/139 一致可复用；GodotAIGym 先例验证 TCP socket step() 平均延迟 1.7ms（i7-11800H） | 已核实（来源：material_digest D2 + GodotAIGym 实测数据） |
| 局限 | 进程管理复杂度（需处理 Python 子进程启动/崩溃/退出）；Web 导出不支持 TCP（浏览器安全限制，仅支持 HTTP/WebSocket/WebRTC）；多一个进程增加分发复杂度（需打包 Python 运行时或要求用户预装） | 已核实（来源：Godot Web 导出文档 + 通用子进程管理知识） |
| 对本项目的参考价值 | 最务实的过渡方案：保留 sim_core 投资、最小改动、可独立调试。性能上 1.7ms 延迟占 20FPS 帧预算（50ms）的 3.4%，完全可接受。但 Web 导出限制需通过 WebSocket 适配解决 | 综合归纳（来源：GodotAIGym 实测 + Godot Web 文档 + material_digest 基线事实） |

#### 2.2.3 B3 - A Dark Forest（GodotProjectZero）

| 维度 | 内容 | 置信度 |
| --- | --- | --- |
| 产品定位 | 受 A Dark Room 启发的增量放置游戏，使用 Godot 引擎和纯 GDScript 开发。开源 MIT 许可 | 已核实（来源：GitHub README） |
| 目标用户 | 喜欢极简增量放置游戏的玩家；对学习 Godot 游戏开发感兴趣的开发者 | 已核实 |
| 核心能力 | 资源采集、自动生产、Boss 战、被动资源生成、多语言本地化（法语/中文/葡萄牙语/泰语/波兰语）、存档系统 | 已核实（来源：GitHub README + open-awesome.com 项目分析） |
| 架构特点 | 纯 GDScript + Godot Resources；使用 GDScript Toolkit（Format on Save + gdLinter）；场景树驱动；MIT 许可代码 + 各贡献者独立资产许可 | 已核实（来源：GitHub README） |
| 部署形态 | 桌面（Steam Demo）+ Web（itch.io，曾登上 New & Popular 首页）；导出预设配置 export_presets.cfg | 已核实（来源：GitHub README + Steam/itch.io 页面） |
| 集成方式 | 纯 Godot 原生，无外部语言绑定。场景树编辑器 + GDScript 脚本 | 已核实 |
| 定价模式 | 免费开源（MIT 许可代码）；资产由各贡献者分别许可 | 已核实 |
| 优势 | 完全原生 Godot 开发，无需桥接层；社区活跃（10+ 贡献者，Discord + Trello）；已在 Steam 和 itch.io 发布验证可行性；多语言支持证明 Godot 本地化能力；代码开源可学习参考 | 已核实（来源：GitHub README + open-awesome.com） |
| 局限 | 开发设置较复杂（需安装 GDScript Toolkit + Python 虚拟环境 + 自定义插件）；资产许可分散不利于商业再分发；更新节奏不稳定（周更已停止，改为社区贡献驱动） | 已核实（来源：open-awesome.com Cons 分析） |
| 对本项目的参考价值 | 直接证明 Godot + 纯 GDScript 可成功开发并发布增量放置游戏。其架构模式（Resources 驱动、场景树组织）可作为 BeeIdleRPG 迁移的参考蓝图。但纯 GDScript 意味着 BeeIdleRPG 的 8,466 行 sim_core 需全部用 GDScript 重写 | 综合归纳（来源：GitHub 项目结构 + 与 BeeIdleRPG 的品类对比） |

#### 2.2.4 B4 - Gaiadon: Eternal Quest

| 维度 | 内容 | 置信度 |
| --- | --- | --- |
| 产品定位 | 增量/idle RPG，使用 Godot 引擎开发。玩家在 Gaiadon 大陆冒险、战斗、收集装备、转生、完成日常任务 | 已核实（来源：itch.io 页面） |
| 目标用户 | idle/incremental RPG 爱好者，偏好放置成长 + 装备收集 + 转生机制的玩家 | 已核实 |
| 核心能力 | 装备系统（多层级升级）、日常任务、转生（Prestige）、宠物收集与升级、大陆解锁、Boss 狩猎（恶魔/泰坦）、名声试炼、英雄收集、技能系统、腐化领域模式 | 已核实（来源：itch.io 页面描述） |
| 架构特点 | Godot 引擎开发，HTML5（WebAssembly）导出发布于 itch.io，Steam 也有发布。使用 Godot 的 2D 渲染（标签含 2D/Godot/Idle/Incremental/Indie/Singleplayer） | 已核实（来源：itch.io 页面标签与描述） |
| 部署形态 | Web（HTML5，itch.io）+ Steam。 itch.io 评分 3.8/5（12 条评价），平均会话时长数小时 | 已核实（来源：itch.io 页面） |
| 集成方式 | 纯 Godot 原生开发（推测，基于 itch.io 标签和平台特征） | 推断 |
| 定价模式 | 免费游玩 + Patreon 赞助 + Steam 发布。处于 Early Access 状态 | 已核实（来源：itch.io 页面 Status: In development） |
| 优势 | 商业化验证：独立开发者使用 Godot 成功开发并发布功能丰富的 idle RPG；HTML5 导出让玩家无需安装即可游玩；功能广度（装备/转生/宠物/Boss/技能）与 BeeIdleRPG 的 RPG 模拟深度可对标 | 已核实（来源：itch.io 页面） |
| 局限 | 仍处于 Early Access / In Development 状态；评分中等（3.8/5）；HTML5 性能在移动端可能受限 | 已核实 + 推断 |
| 对本项目的参考价值 | 从商业角度验证 Godot + idle RPG 的市场可行性。HTML5 Web 导出是 idle 游戏的重要分发渠道（浏览器即开即玩），这恰好是 BeeIdleRPG 迁移到 Godot 的核心收益之一。但同时也暴露了 Web 导出的音频限制（Godot 4.3+ Web 平台不支持程序化音频生成） | 综合归纳（来源：itch.io 商业数据 + Godot Web 导出文档） |

### 2.3 关键技术能力横向事实

> 不评分、不排序，仅按能力维度横陈各方案事实。

| 能力维度 | B1 GDExtension Python | B2 TCP IPC Bridge | B3 A Dark Forest（纯 GDScript） | B4 Gaiadon（商业 Godot idle RPG） | 说明 / 来源 |
| --- | --- | --- | --- | --- | --- |
| Python sim_core 复用 | 直接 import，进程内调用 | TCP JSON-line 驱动，零改动 | 需全部重写为 GDScript | 需全部重写为 GDScript | material_digest D2：sim_core 8,466 行纯 Python |
| 20FPS 模拟性能 | 进程内调用，延迟极低（理论 8-15ms 含 RL 推理） | TCP localhost step() 平均 1.7ms（GodotAIGym 实测 i7-11800H） | GDScript 原生，无 IPC 开销 | GDScript 原生，无 IPC 开销 | GodotAIGym 实测数据；GDExtension RL 实测数据 |
| 生产就绪状态 | 实验性/alpha，三个项目均标注「不要用于大型项目」 | TCP IPC 成熟稳定，JSON-line 协议简单可调试 | GDScript 是 Godot 官方语言，最稳定 | 已发布商业产品，验证可用 | py4godot/godot-python-extension README；GodotAIGym 文档 |
| 版本耦合 | 强耦合：Godot 小版本升级需重新编译 GDExtension | 无耦合：Python 侧独立于 Godot 版本 | 无耦合：GDScript 随 Godot 版本演进 | 无耦合 | Godot 4.0→4.1 GDExtension 二进制兼容性破坏文档 |
| Web 导出支持 | 需启用 Extension Support + 跨域隔离，限制较多 | 不支持原生 TCP（需 WebSocket 适配器） | 原生支持（WebGL 2.0 + WebAssembly） | 已发布 HTML5 版本 | Godot Web 导出官方文档 |
| 音频程序化合成 | 可直接调用 NumPy/SciPy | 可在 Python 侧用 NumPy/SciPy 合成后传输 | AudioStreamGenerator 支持（GDScript 性能受限，建议降低采样率） | 未公开音频实现细节 | Godot AudioStreamGenerator 文档；Oni Hunters 开发者经验 |
| 跨平台导出 | 需为每个目标平台预编译 GDExtension 动态库 | 需为每个目标平台打包 Python 运行时 | 原生支持所有 Godot 导出平台 | 已验证 Web + Steam 导出 | Godot 特性列表文档 |
| 调试便利性 | 三层架构（C++/Python/Godot）调试复杂 | JSON-line 可读可抓包，Python 侧可独立 pytest | Godot 编辑器内置调试器，全链路可视化 | 同 B3 | py4godot 文档；material_digest golden test |
| 分发复杂度 | 高：需打包 GDExtension 动态库 + Python 运行时 | 中：需打包 Python 运行时或要求预装 | 低：Godot 一键导出，自包含 | 低：已验证可分发 | Godot 导出文档；PyInstaller 文档 |
| 一人团队友好度 | 低：C++/Python/Godot 三栈知识要求 | 高：Python 侧已有 golden test，Godot 侧仅薄前端 | 中：需学习 GDScript，但生态最完善 | 高：独立开发者已验证可行 | material_digest R5；各方案文档 |

---

## 3. 对比：对比矩阵与加权评分

> **四段式「对比」段**。在 §2 的事实基础上建立对比矩阵，赋予权重并打分。

### 3.1 对比矩阵

> **每行权重之和 = 1.00**。评估维度与权重根据本次调研问题调整，但保留并给出理由。

| 评估维度 | 权重 | 权重理由 | B1 得分 | B2 得分 | B3 得分 | B4 得分 |
| --- | --- | --- | --- | --- | --- | --- |
| 场景契合度 | 0.30 | BeeIdleRPG 是零操作文字挂机 RPG，核心需求是保留 sim_core 投资 + 低渲染 UI + 自动推进模拟。方案能否直接复用 8,466 行已测试的 Python 模拟内核是最高优先级 | 4 | 4 | 5 | 5 |
| 技术成熟度 | 0.25 | 一人团队无法承担实验性技术栈的稳定性风险。生产就绪状态和社区支持程度直接决定项目能否持续推进 | 2 | 4 | 5 | 4 |
| 集成难度（反向） | 0.20 | sim_core 已完成抽取且 golden test 139/139 一致，方案对已有代码的侵入性越低越好。反向计分：分数越高表示集成越容易 | 3 | 5 | 2 | 2 |
| 成本（反向） | 0.15 | 一人团队资源有限，初始开发成本和长期维护成本均需可控。反向计分：分数越高表示成本越低 | 3 | 4 | 2 | 2 |
| 合规可控性 | 0.10 | 方案的版本独立性、平台可移植性、分发自由度。无供应商锁定和许可限制为佳 | 2 | 4 | 5 | 5 |
| **加权总分** | **1.00** | — | **2.95** | **4.20** | **3.95** | **3.70** |

**评分标尺**：每项 1~5 分，1 = 严重不符合，3 = 基本满足但存在明显局限，5 = 完美契合。

**评分计算明细**：

- B1（GDExtension Python Binding）：4×0.30 + 2×0.25 + 3×0.20 + 3×0.15 + 2×0.10 = 1.20 + 0.50 + 0.60 + 0.45 + 0.20 = **2.95**
- B2（TCP JSON-line IPC Bridge）：4×0.30 + 4×0.25 + 5×0.20 + 4×0.15 + 4×0.10 = 1.20 + 1.00 + 1.00 + 0.60 + 0.40 = **4.20**
- B3（A Dark Forest / 纯 GDScript）：5×0.30 + 5×0.25 + 2×0.20 + 2×0.15 + 5×0.10 = 1.50 + 1.25 + 0.40 + 0.30 + 0.50 = **3.95**
- B4（Gaiadon / 商业 Godot idle RPG）：5×0.30 + 4×0.25 + 2×0.20 + 2×0.15 + 5×0.10 = 1.50 + 1.00 + 0.40 + 0.30 + 0.50 = **3.70**

### 3.2 评分结论

> 基于 §3.1 加权总分，形成分层结论。每层结论必须引用得分作为依据。

- **优先借鉴**：B2 TCP JSON-line IPC Bridge — 加权总分 4.20，在所有方案中得分最高。理由：场景契合度 4/5（完美适配 idle RPG 低频更新特性，20FPS 帧预算 50ms 中 IPC 延迟仅占 3.4%）；技术成熟度 4/5（TCP IPC 是数十年工程实践验证的成熟技术，JSON-line 协议简单可调试）；集成难度 5/5（sim_core 零改动，game_controller 已退化为 161 行薄前端，脚手架已存在）；成本 4/5（初始成本低——脚手架已有，维护成本低——Python 侧独立于 Godot 版本）；合规可控性 4/5（无版本耦合，Python 侧 golden test 可独立运行，唯一短板是 Web 导出需 WebSocket 适配）。**这是当前阶段对一人团队风险最低、投资保护最好的方案。**

- **部分借鉴**：B3 A Dark Forest（纯 GDScript 重写）— 加权总分 3.95，排名第二。借鉴点：Godot 原生 GDScript 的场景树架构、Resources 驱动模式、UI 组织方式可直接参考其开源代码；其 Steam + itch.io 发布流程可复用。不借鉴的部分：全量 GDScript 重写路径（8,466 行 sim_core + 139 行 golden test 全部需移植，对一人团队成本不可接受——集成难度仅 2/5、成本仅 2/5）。理由：虽然纯 GDScript 是技术上最干净的长期目标，但短期重写成本过高，应作为分阶段迁移的远期目标而非当前阶段的首选。

- **不借鉴（否决）**：B1 GDExtension Python Binding — 加权总分 2.95，排名最低。否决理由：技术成熟度仅 2/5——三个社区项目（godot-python、py4godot、godot-python-extension）均明确标注「实验性」「非生产就绪」「早期开发阶段，不要用于大型项目」；合规可控性仅 2/5——GDExtension 在 Godot 4.0→4.1 之间发生过二进制兼容性破坏，每次小版本升级需重新编译，且需为每个目标平台预编译动态库。对于一人团队，C++/Python/Godot 三栈调试复杂度和版本耦合维护成本构成不可接受的风险。**建议持续关注其成熟度，但不作为当前阶段的桥接方案。**

> B4 Gaiadon（3.70）作为商业验证标杆，不作为独立方案借鉴，其价值在于从商业角度验证了 Godot + idle RPG 的市场可行性，为 B3 的长期可行性提供佐证。

### 3.3 方案组合分析

> 调研发现单一方案无法同时满足「保留 sim_core 投资」和「Web 导出原生支持」两个需求，需要组合分析。

| 组合方式 | 覆盖哪些能力 | 未覆盖能力 | 组合复杂度 | 总体成本估算 |
| --- | --- | --- | --- | --- |
| B2 IPC 为主 + B3 GDScript 逐步迁移（推荐组合） | 桌面端：IPC 保留 sim_core，零改动上线；Web 端：GDScript 重写核心模拟逻辑，或用 WebSocket 适配 IPC | Web 端程序化音频（Godot 4.3+ Web 不支持 AudioStreamGenerator） | 中——需维护 IPC 协议层 + 逐步移植的 GDScript 模块，但可按模块渐进 | 低初始成本（IPC 脚手架已有）+ 渐进移植成本（按模块分摊） |
| B2 IPC + WebSocket 适配（纯桥接组合） | 桌面端：TCP IPC；Web 端：WebSocket 替代 TCP，Python 后端改为 WebSocket 服务 | Web 端仍需 Python 后端（Serverless 或云端运行 sim_core） | 中高——需实现 WebSocket 协议适配 + 云端 Python 后端部署 | 中——需额外维护 WebSocket 适配层和云端后端 |

---

## 4. 建议：取舍决策支持

> **四段式「建议」段**。基于 §2 事实 + §3 对比，给出可被 `business-architect` 直接采用的建议。本节是建议而非最终裁决，最终边界由业务架构师冻结。

### 4.1 自研 / 采购 / 复用边界建议

| 能力项 | 建议方式 | 建议依据 | 候选方案 / 系统 | 关键前提 |
| --- | --- | --- | --- | --- |
| 游戏模拟内核（sim_core） | 复用（已有底座） | sim_core 8,466 行已抽取完成，golden test 139/139 一致，SimCore.update(dt) 纯推进可被 Godot 每帧 tick。B2 IPC 方案集成难度 5/5 | BeeIdleRPG 现有 sim_core（src/sim_core/） | 维持 save.json schema 冻结、data/ JSON 池不迁不分叉（material_digest 不可变约束） |
| Godot 前端 UI 层 | 自研 | 无现成 UI 框架可直接复用；B3 A Dark Forest 的 GDScript UI 模式可参考但需适配 BeeIdleRPG 的 MVC+Mixin 架构 | 自研 GDScript UI（参考 B3 场景树模式） | 需将 1,251 行 Tkinter 绑定控制器迁移为 GDScript UI 逻辑 |
| Python-Godot 桥接层 | 复用（已有脚手架）+ 自研（WebSocket 适配） | B2 IPC 脚手架已存在（sim_bridge.gd），加权总分 4.20 最高。桌面端直接复用；Web 端需自研 WebSocket 适配 | BeeIdleRPG 现有 sim_bridge.gd + 自研 WebSocket 适配器 | M2 阶段需验证 IPC 在 Godot 4 中的实际性能（当前 UNVERIFIED 状态） |
| 音频系统 | 自研（GDScript 移植） | numpy/scipy 程序化合成逻辑需移植为 Godot AudioStreamGenerator 或预渲染为 AudioStreamWAV。B1 GDExtension 虽可调用 NumPy 但被否决（实验性） | GDScript AudioStreamGenerator 或构建期预渲染 WAV | 需评估 44KB 音频逻辑的移植复杂度；Web 端需预渲染方案（Web 不支持程序化生成） |
| 跨平台导出 | 复用（Godot 原生能力） | Godot 4 原生支持 Windows/macOS/Linux/Android/iOS/Web 一键导出，这是迁移的核心收益。B3 和 B4 均已验证 | Godot 4 导出模板 | 桌面端导出无障碍；Web 端受 TCP/音频限制需适配；移动端需测试 |

### 4.2 MVP 范围建议

> 对用户诉求中的功能给出「是否可在 MVP 内实现」的调研侧建议。

| 功能（对齐用户诉求） | 建议 MVP？ | 理由 |
| --- | --- | --- |
| Godot 4 前端 + TCP IPC 桥接 sim_core（桌面端） | ✅ | B2 IPC 脚手架已存在，sim_core 零改动可运行。M2 阶段验证 IPC 实际性能后即可推进。GodotAIGym 先例验证 TCP step() 1.7ms 延迟可接受 |
| save.json 存档兼容（schema 冻结） | ✅ | sim_core 不修改存档逻辑，save.json schema 已冻结。Godot 前端通过 IPC 调用 new_game/state 命令即可 |
| 24 表 JSON 内容池原样复用 | ✅ | data/ 不迁不分叉是不可变约束。sim_core 通过 json_pool.py 读取 JSON 池，Godot 前端无需直接访问 |
| 跨平台桌面导出（Windows/Linux/macOS） | ✅ | Godot 4 桌面导出成熟稳定（B3/B4 均已验证）。需打包 Python 运行时或使用 PyInstaller 打包 sim_core 为独立可执行文件 |
| 音频系统迁移 | ✅（简化版） | 建议先预渲染常用音效为 WAV 文件（构建期用 Python numpy/scipy 生成），Godot 端加载 AudioStreamWAV 播放。程序化实时合成留作后续迭代 |
| Web 导出（HTML5 浏览器即开即玩） | ❌（完整版） | Web 导出不支持 TCP（需 WebSocket 适配）+ 不支持程序化音频生成。需额外开发 WebSocket 适配层和音频预渲染方案。建议作为 MVP 后的独立迭代 |
| 云端 sim_core 后端部署 | ❌（MVP 阶段） | 云端部署需 Serverless/容器化 Python 后端 + WebSocket 网关。对一人团队初期成本过高。建议先验证桌面端 IPC 方案，云端作为后续扩展 |
| 移动端导出（Android/iOS） | ❌（MVP 阶段） | 移动端 Godot 导出支持但需测试 IPC 子进程管理在移动端的兼容性。建议桌面端验证后推进 |

### 4.3 技术栈参考建议

| 技术层 | 推荐方案 | 替代方案 | 选择理由 |
| --- | --- | --- | --- |
| 游戏引擎 | Godot 4.x（GDScript） | Unity（用户已签核 B/C 迁移，ADR-0001 备选 C） | 用户已签核迁移 Godot（ADR-0001 SIGNED-OFF）；Godot MIT 开源无运行时费用；B3/B4 验证 idle RPG 可行；一人团队友好 |
| Python-Godot 桥接 | TCP JSON-line IPC（127.0.0.1:18765） | WebSocket 适配（Web 端）/ GDExtension Python（远期关注） | B2 加权总分 4.20 最高；sim_core 零改动；脚手架已存在；GodotAIGym 先例验证 1.7ms 延迟可接受 |
| 前端脚本语言 | GDScript | C#（.NET edition） | GDScript 是 Godot 官方语言，社区资源最丰富，编辑器支持最好，无需额外 .NET 运行时；B3 A Dark Forest 使用纯 GDScript 验证可行 |
| 音频方案 | 构建期预渲染 WAV + 运行期 AudioStreamWAV 播放 | AudioStreamGenerator 实时合成（桌面端）/ NumPy via IPC（桌面端） | 预渲染方案跨平台兼容（含 Web）；AudioStreamGenerator 官方建议从 C#/GDExtension 使用，GDScript 性能受限；Web 平台不支持程序化生成 |
| 存档格式 | JSON（save.json，schema 冻结） | — | 不可变约束：save.json schema 冻结，sim_core 不修改存档逻辑 |
| 内容管线 | Excel 构建期工具（24 表 → JSON） | — | 不可变约束：Excel 构建期保留，data/ JSON 池原样复用 |
| 桌面分发 | Godot 一键导出 + PyInstaller 打包 sim_core | Godot 导出 + 要求用户预装 Python | PyInstaller 可将 sim_core 打包为独立可执行文件，用户无需安装 Python |
| Web 分发（远期） | Godot Web 导出 + WebSocket 适配 sim_core | Godot Web 导出 + GDScript 重写核心逻辑 | WebSocket 适配保留 sim_core 投资；GDScript 重写是长期目标但成本高 |

---

## 5. 风险与待确认项

> **四段式「风险」段**。列出调研中发现的主要风险、不确定信息、待业务架构师进一步裁决的依赖项。

### 5.1 主要风险清单

| 编号 | 风险描述 | 触发条件 | 影响范围 | 严重程度 | 缓解建议 |
| --- | --- | --- | --- | --- | --- |
| R-01 | IPC 桥接方案在 Godot 4 中的实际性能未验证（当前 UNVERIFIED 状态） | M2 阶段原型验证发现 IPC 延迟超过帧预算（50ms 的 10% 以上） | 整体迁移方案需调整 | 高 | M2 阶段优先验证 IPC 性能基线：在 Godot 4 中实测 step() 延迟和状态同步耗时；若超预期，评估降低 step 频率（如 10FPS 推进 + 20FPS 渲染分离）或预取状态缓存 |
| R-02 | Python 子进程在 Godot 导出后的管理和分发复杂度 | Godot 导出为独立可执行文件后，需同时管理 Python 子进程的生命周期（启动/崩溃恢复/优雅退出） | 用户体验和分发流程 | 高 | 使用 PyInstaller 将 sim_core 打包为独立可执行文件；Godot 前端通过 OS.execute() 管理子进程；实现崩溃检测和自动重启机制；提供明确的错误提示 |
| R-03 | Web 导出无法使用 TCP IPC，需额外开发 WebSocket 适配层 | 用户需要 Web 端分发（idle 游戏的重要渠道，B4 Gaiadon 已验证） | Web 平台分发能力 | 中 | 分阶段实施：MVP 先支持桌面端 TCP IPC；Web 端作为独立迭代，开发 WebSocket 适配层（Python 侧改为 WebSocket Server，Godot 侧改为 WebSocketPeer） |
| R-04 | 一人团队迁移停滞风险（material_digest R5） | 开发者在学习 GDScript + Godot 编辑器 + IPC 调试过程中遇到阻塞性问题，导致项目长期停滞 | 项目整体进度 | 高 | 制定分阶段里程碑（M2 验证 → M3 内容迁移 → M4 切换发布），每阶段设定明确验收标准；优先保留 sim_core 投资（IPC 方案降低重写风险）；参考 B3 A Dark Forest 的开源代码学习 Godot idle game 模式 |
| R-05 | GDExtension Python 绑定项目未来可能停止维护 | 若选择 B1 方案且项目停止维护，Godot 新版本将无法使用 | 若选择 B1 则影响整体 | 中 | 不选择 B1 作为当前方案（已否决）；持续关注 py4godot（1,573 commits，2026 年 5 月仍活跃）成熟度；若未来达到生产就绪可重新评估 |
| R-06 | 音频系统迁移导致音质损失或功能缺失 | numpy/scipy 程序化合成的音频效果无法在 Godot 中完美复现 | 游戏体验完整性 | 中 | 优先采用构建期预渲染方案：用 Python numpy/scipy 在构建期生成所有音效 WAV 文件，Godot 端直接加载播放；保留 Python 侧合成代码作为构建工具；实时合成留作桌面端后续迭代 |

### 5.2 待确认项（需主理人 / 业务方反馈）

> 调研中因外部信息不可得而暂不能确认的事实。

| 编号 | 待确认项 | 不确定性说明 | 若无法确认的备选路径 |
| --- | --- | --- | --- |
| U-01 | BeeIdleRPG sim_core 在 Godot 4 TCP IPC 中的实际 step() 延迟是多少？ | material_digest D4 标注 UNVERIFIED（编写时本机未安装 Godot）。GodotAIGym 的 1.7ms 是 RL 场景数据，BeeIdleRPG 的 sim_core 复杂度可能不同 | M2 阶段在 Godot 4 中实测 step() 延迟；若超过 5ms 则评估降低 step 频率或优化 JSON 序列化 |
| U-02 | BeeIdleRPG 的 44KB numpy/scipy 音频代码具体实现了哪些音效？是否有实时参数化需求？ | material_digest 仅提及「numpy/scipy/sounddevice 音频」但未详述具体音效类型和合成方式 | 审查 src/ 中的音频代码；若全部为固定音效则预渲染为 WAV；若有实时参数化需求则桌面端保留 IPC 传音频缓冲 |
| U-03 | 用户是否将 Web 导出（浏览器即开即玩）视为 MVP 必须功能？ | B4 Gaiadon 验证了 Web 端是 idle 游戏重要分发渠道，但 Web 导出需额外 WebSocket 适配层 | 若 Web 为 MVP 必须：优先开发 WebSocket 适配；若非必须：MVP 先桌面端，Web 作为后续迭代 |
| U-04 | PyInstaller 打包 sim_core 后的体积和启动时间是否可接受？ | sim_core 依赖 numpy/scipy（较大），PyInstaller 打包后体积可能超过 100MB | 实测 PyInstaller 打包体积和冷启动时间；若过大可考虑裁剪不必要的依赖或改用 Nuitka |

### 5.3 需业务架构持续关注的依赖项

> 调研中发现但不由 `research-analyst` 裁决的下游问题。

| 编号 | 依赖项 | 说明 | 建议关注阶段 |
| --- | --- | --- | --- |
| D-01 | IPC 协议契约（init/step/state/new_game/quit）需在高层架构中冻结为接口契约 | B2 IPC 方案的协议定义直接影响 system-architect 的接口设计和 product-story-designer 的验收标准 | 高层架构设计 §3 方案决策 |
| D-02 | Web 导出是否纳入 MVP 范围影响整体架构选型 | 若 Web 为 MVP 必须，需在架构中预留 WebSocket 适配层；若非必须，架构可先按桌面端 TCP IPC 设计 | 高层架构设计 §4 业务架构 |
| D-03 | 音频迁移策略（预渲染 vs 实时合成）影响构建管线设计 | 预渲染方案需在构建管线中增加 Python 音频生成步骤；实时合成需在运行时架构中保留音频 IPC 通道 | 系统设计 §技术选型 |
| D-04 | sim_core 打包分发方式（PyInstaller vs Nuitka vs 要求预装 Python）影响部署设计 | 不同打包方式的体积、启动时间、跨平台兼容性差异显著 | 部署设计 §资源清单 |
| D-05 | 云端 sim_core 后端的长期架构方向 | 若未来需要云端部署（多设备同步、防作弊），需在架构中预留 sim_core 服务化接口 | 高层架构设计 §5 产品需求（远期规划） |

---

## 6. 关键来源目录

> 集中列出全部调研所使用的公开资料、官方文档、社区仓库、分析报告等。每条来源不低于 URL 粒度，关键来源给出具体章节或段落。

**硬指标**：
- ≥ 3 条来源，至少覆盖每家标杆。
- 关键数据（准确率、性能基准、定价）必须指定来源段落/图表位置。

| 编号 | 来源类型 | 标题 / 名称 | URL / 路径 | 相关章节 | 最后访问日期 |
| --- | --- | --- | --- | --- | --- |
| SR-01 | 开源仓库 | py4godot — Python scripting for Godot via GDExtension | https://github.com/niklas2902/py4godot | B1, §2.2.1, §2.3 | 2026-07-15 |
| SR-02 | 开源仓库 | godot-python-extension — Python language bindings for Godot | https://github.com/maiself/godot-python-extension | B1, §2.2.1 | 2026-07-15 |
| SR-03 | 开源仓库 | A Dark Forest（GodotProjectZero）— Godot 增量放置游戏 | https://github.com/N0best1rn/GodotProjectZero | B3, §2.2.3, §2.3 | 2026-07-15 |
| SR-04 | 商业产品页面 | Gaiadon: Eternal Quest — Godot idle RPG on itch.io | https://nadukkon.itch.io/gaiadon-eternal-quest | B4, §2.2.4, §2.3 | 2026-07-15 |
| SR-05 | 技术博客 | GodotAIGym: 基于 TCP 的仿真环境构建（含 step() 延迟实测数据） | https://blog.csdn.net/weixin_32060671/article/details/161274134 | B2, §2.2.2, §3.1 | 2026-07-15 |
| SR-06 | 官方文档 | Godot 4 特性列表（跨平台支持） | https://docs.godotengine.org/zh-cn/4.3/about/list_of_features.html | §2.3, §4.1, §4.3 | 2026-07-15 |
| SR-07 | 官方文档 | Godot 4 为 Web 导出（HTML5/WebAssembly 限制） | https://docs.godotengine.org/zh-cn/4.3/tutorials/export/exporting_for_web.html | §2.3, §5.1 R-03, §4.2 | 2026-07-15 |
| SR-08 | 官方文档 | Godot 4 GDExtension 是什么（版本兼容性说明） | https://docs.godotengine.org/zh-cn/4.3/tutorials/scripting/gdextension/what_is_gdextension.html | B1, §2.2.1, §3.2 | 2026-07-15 |
| SR-09 | 官方文档 | Godot 4 AudioStreamGenerator 类文档 | https://docs.godotengine.org/de/latest/classes/class_audiostreamgenerator.html | §2.3, §4.1, §4.3, R-06 | 2026-07-15 |
| SR-10 | 官方文档 | Godot 4 Audio Streams 文档（AudioStreamWAV/OGG/Generator） | https://mintlify.wiki/godotengine/godot/audio/audio-streams | §2.3, §4.3 | 2026-07-15 |
| SR-11 | 技术博客 | Godot 与 Python 集成三种方案详解（GDExtension/IPC/重写对比） | http://www.xxmr.cn/news/30765 | B1, B2, §2.3 | 2026-07-15 |
| SR-12 | 开源仓库 | Progress Quest Web（TypeScript/React 移植版）— 原始 idle RPG 架构参考 | https://github.com/fernicar/ProgressQuest-TypeScript | §1, §2.3 | 2026-07-15 |
| SR-13 | 开源仓库 | HackerIdleGame — Godot 4.4.1 移动端 idle game | https://github.com/dallatIkes/HackerIdleGame | §2.1, §2.3 | 2026-07-15 |
| SR-14 | 开源仓库 | Increledger — 100% 后端驱动的增量游戏服务器（防作弊架构） | https://github.com/Saucistophe/increledger | §4.2, D-05 | 2026-07-15 |
| SR-15 | 技术博客 | 独立开发者从 Unity 迁移到 Godot 实战经验（Oni Hunters 案例） | http://www.gamelook.com.cn/2023/09/528193/ | §2.2.4, §4.1, R-04 | 2026-07-15 |
| SR-16 | 性能基准 | IPC Benchmark Suite（TCP localhost / Unix Domain Socket 延迟基准） | https://github.com/redhat-performance/rusty-comms | B2, §2.2.2 | 2026-07-15 |
| SR-17 | 技术分析 | A Dark Forest 项目分析（open-awesome.com） | https://open-awesome.com/projects/godotprojectzero | B3, §2.2.3 | 2026-07-15 |
| SR-18 | 行业分析 | Idle Game Illusion: How Delta-Time Powers Progress（idle 游戏架构原理） | https://www.geekextreme.com/idle-games-offline-progression-math/ | §1, §2.3 | 2026-07-15 |
| SR-19 | 云架构案例 | 阿里云函数计算助力轻休闲游戏构建（Serverless 游戏后端） | http://developer.aliyun.com:443/article/1677296 | D-05, §4.2 | 2026-07-15 |

---

## 7. 硬指标清单

> 汇总本模板所有章节的硬指标，供自动校验与人工审核使用。

| 章节 | 硬指标项 | 当前状态 | 备注 |
| --- | --- | --- | --- |
| §1 | 调研问题已收敛为 ≥ 3 条可执行问题 | ✅ | 5 条调研问题（Q1~Q5） |
| §2.1 | 标杆系统 ≥ 3 家，含 ≥ 1 家头部 SaaS / 商业代表 | ✅ | 4 家标杆（B1~B4），B4 Gaiadon 为商业代表 |
| §2.1 | 标杆系统 ≥ 1 家开源或自研代表 | ✅ | B1（开源）、B2（自研）、B3（开源） |
| §2.2 | 每家标杆有独立详述卡片 | ✅ | B1~B4 均有 10 维度详述卡片 |
| §2.3 | 关键能力横向事实无遗漏 | ✅ | 10 个能力维度横向对比 |
| §3.1 | 对比矩阵含 5 维度 + 权重 + 评分 | ✅ | 权重之和 = 0.30+0.25+0.20+0.15+0.10 = 1.00 |
| §3.2 | 评分结论含优先/部分/不借鉴三层 | ✅ | 优先=B2(4.20)，部分=B3(3.95)，不借鉴=B1(2.95) |
| §4.1 | 自研/采购/复用边界有明确建议 | ✅ | 5 项能力边界建议 |
| §4.2 | MVP 范围建议与用户诉求对齐 | ✅ | 8 项功能 MVP 判断 |
| §5.1 | 主要风险 ≥ 3 条，有缓解建议 | ✅ | 6 条风险（R-01~R-06），每条有缓解建议 |
| §6 | 关键来源可追溯（URL / 章节） | ✅ | 19 条来源（SR-01~SR-19），全部含 URL |
| 全文 | 明确区分事实 / 推断 / 建议 / 风险 | ✅ | §2 事实段标注置信度；§3 对比段；§4 建议段；§5 风险段 |
| 全文 | 不存在编造来源或占位符 | ✅ | 全部来源为真实公开 URL，无占位符残留 |

---

## 附录 A：中间确认自检报告

> 按 `intermediate_confirmation.md` 协议 §2.4 要求，在关键章节产出后进行自检。本附录记录四次自检的结果，作为 G2 审核追溯材料。

### A.1 自检 1：§1 调研问题收敛完成后

**§2.1 方案分歧型触发标准判定**：
1. 当前决策点是否存在 ≥ 2 种方案且无法单方裁决？——否。调研问题收敛是从用户诉求中提取论题，不存在多方案选择。
2. 该决策是否影响下游成员产出？——否。调研问题本身不直接影响接口契约或业务边界。
3. 用户原始诉求是否未对该决策点做出明确选择？——不适用，这不是决策点。

**判定**：未命中 §2.1。

**§2.3 反向验证 3 问**：
- **Q1（返工成本）**：若调研问题 3 个月后需修订，返工范围 = 重新搜索 1~2 个主题 + 更新 §1 表格 + 修订相关 §2 详述卡片。切换成本约 0.5~1 人日。**可控。**
- **Q2（用户/客户/监管感知）**：调研问题收敛是内部分析文档，用户/客户/监管无法感知到调研问题的表述方式。**感知不到。** 判断依据：调研报告是架构设计内部产物，不直接暴露给最终用户。
- **Q3（与用户诉求一致性）**：material_digest 明确列出「research-analyst 需关注」6 个调研重点（Godot 适配、桥接对比、跨平台导出、音频迁移、一人团队风险、云端部署），我的 Q1~Q5 完全覆盖这 6 点。**一致。** 引用原文：「1. Godot 4 适配 2. 桥接方案对比 3. 跨平台导出 4. 音频迁移 5. 一人团队风险 6. 云端部署可能性」。

**结论**：Q1 可控、Q2 不可感知、Q3 一致，均未命中 §2.2。**无需发起中间确认。**

### A.2 自检 2：§2.1 标杆清单完成后

**§2.1 方案分歧型触发标准判定**：
1. 是否存在 ≥ 2 种方案无法裁决？——否。标杆清单共 4 家（B1~B4），在 3~5 家合理范围内，无取舍分歧。
2. 是否影响下游产出？——否。标杆选择是调研分析方法，不直接影响下游接口或边界。
3. 用户是否未做明确选择？——用户未指定具体标杆，但 material_digest 的调研重点已隐含覆盖范围。

**判定**：未命中 §2.1。

**§2.3 反向验证 3 问**：
- **Q1（返工成本）**：若标杆清单需调整（如增减 1 家），返工范围 = 修订 §2.1 表格 1 行 + §2.2 详述卡片 1 张 + §2.3 横向事实表 1 列 + §3.1 矩阵 1 列。切换成本约 0.5 人日。**可控。**
- **Q2（用户/客户/监管感知）**：标杆选择是内部调研方法，用户/客户/监管无法感知。**感知不到。** 判断依据：标杆系统是调研分析工具，不出现在最终产品中。
- **Q3（与用户诉求一致性）**：material_digest 调研重点要求覆盖 Godot 适配、桥接方案、跨平台、音频、风险、云端。B1 覆盖桥接方案（GDExtension），B2 覆盖桥接方案（IPC），B3 覆盖 Godot idle game 案例，B4 覆盖商业 Godot idle RPG + Web 导出。**一致。**

**结论**：Q1 可控、Q2 不可感知、Q3 一致，均未命中 §2.2。**无需发起中间确认。**

### A.3 自检 3：§3.1 权重分配前

**§2.1 方案分歧型触发标准判定**：
1. 权重分配是否存在 ≥ 2 种合理方案？——是。场景契合度权重可在 0.25~0.35 之间调整，技术成熟度可在 0.20~0.30 之间调整，不同权重分配可能影响 B2 与 B3 的排名。
2. 是否影响下游产出？——权重分配影响推荐结论，进而影响 business-architect 的方案选型。
3. 用户是否未做明确选择？——用户未指定权重。

**判定**：命中 §2.1 条件 1 和 3。但需进一步评估条件 2：权重分配是否真的会反转推荐排名？

**敏感性分析**：当前权重下 B2(4.20) vs B3(3.95) 差距 0.25。若将场景契合度从 0.30 降到 0.25、技术成熟度从 0.25 升到 0.30：B2 = 4×0.25 + 4×0.30 + 5×0.20 + 4×0.15 + 4×0.10 = 1.00+1.20+1.00+0.60+0.40 = 4.20；B3 = 5×0.25 + 5×0.30 + 2×0.20 + 2×0.15 + 5×0.10 = 1.25+1.50+0.40+0.30+0.50 = 3.95。排名不变。若将集成难度从 0.20 升到 0.30、场景契合度从 0.30 降到 0.20：B2 = 4×0.20 + 4×0.25 + 5×0.30 + 4×0.15 + 4×0.10 = 0.80+1.00+1.50+0.60+0.40 = 4.30；B3 = 5×0.20 + 5×0.25 + 2×0.30 + 2×0.15 + 5×0.10 = 1.00+1.25+0.60+0.30+0.50 = 3.65。B2 优势更大。

**结论**：在合理权重调整范围内（±0.05~0.10），B2 始终排名第一，B1 始终排名最后。权重分配不会反转推荐排名。

**§2.3 反向验证 3 问**：
- **Q1（返工成本）**：若权重 3 个月后需修订，返工范围 = §3.1 矩阵权重列 + §3.2 结论段落。切换成本约 0.3 人日。**可控。**
- **Q2（用户/客户/监管感知）**：权重分配是内部分析方法，用户/客户/监管无法感知。**感知不到。** 判断依据：权重是评估工具参数，不出现在最终产品或对外承诺中。
- **Q3（与用户诉求一致性）**：material_digest 未指定权重分配方法。但 material_digest 强调一人团队风险（R5）和 sim_core 投资保护（不可变约束），这与本报告将「技术成熟度」权重设为 0.25（第二高）和「集成难度」设为 0.20（第三高）一致。**一致。**

**结论**：虽然命中 §2.1 条件 1 和 3，但敏感性分析证明权重调整不会反转推荐排名，因此不存在真正的「方案分歧」。Q1 可控、Q2 不可感知、Q3 一致。**无需发起中间确认。**

### A.4 自检 4：§5.2 待确认项整理时（最终复核）

**§2.1 方案分歧型触发标准判定**：
1. 待确认项中是否存在 ≥ 2 种方案无法裁决？——U-03（Web 导出是否为 MVP 必须）存在两种理解（是/否），但这需要用户决策而非调研裁决。
2. 是否影响下游产出？——U-03 影响架构选型（TCP IPC vs WebSocket 适配）。
3. 用户是否未做明确选择？——material_digest 未明确 Web 导出是否为 MVP 必须。

**判定**：U-03 命中 §2.1 三条全部成立。

**§2.3 反向验证 3 问**：
- **Q1（返工成本）**：若 U-03 决策 3 个月后被推翻（从「Web 非 MVP」改为「Web 是 MVP」），返工范围 = 高层架构设计的桥接层方案（TCP→WebSocket）+ 系统设计的接口契约 + 部署设计的分发方案。切换成本约 1~2 人月。**不可控。**
- **Q2（用户/客户/监管感知）**：Web 导出是否支持直接影响用户可见行为——浏览器即开即玩 vs 需下载安装。**用户可感知。** 感知点：产品分发形态（Web vs 桌面安装包）。
- **Q3（与用户诉求一致性）**：material_digest 提到「跨平台导出：Godot 天然跨平台是迁移真实收益」，暗示跨平台（含 Web）是迁移动机之一。但未明确 Web 是否为 MVP 必须。用户原始诉求为「生成完整架构方案」，未细化 MVP 范围。**部分一致但存在偏差风险。**

**结论**：Q1 不可控（命中 §2.2.1 不可逆代价——返工范围可能超过当前阶段产物 30%）+ Q2 用户可感知（命中 §2.2.2 跨界感知——用户可见行为）+ Q3 存在偏差风险（命中 §2.2.3 偏离原始诉求）。

**但是**：U-03 的本质是「MVP 范围定义」问题，这属于 business-architect 的裁决范围（高层架构设计 §5 产品需求），而非 research-analyst 的调研范围。调研侧已提供充分证据（B4 Gaiadon 验证 Web 是 idle 游戏重要渠道；Godot Web 导出文档列明 TCP 限制），将其列为待确认项 U-03 并标注备选路径，已履行调研职责。

**最终判定**：U-03 作为待确认项提交给主理人和 business-architect 裁决，不在调研阶段发起中间确认。调研报告在 §4.2 MVP 范围建议中已明确标注 Web 导出为「❌（完整版）——建议作为 MVP 后的独立迭代」，并给出理由。此建议供 business-architect 参考，最终 MVP 边界由业务架构师冻结。

---

## 附录 B：生成方法论与工具清单

> 本附录描述调研报告的生成方法论与使用的工具，属于元信息。

### B.1 调研方法论

1. **种子提取**：从 material_digest.md 的「下游关注要点」和用户诉求中提取 6 个调研种子（S1~S6）。
2. **问题收敛**：将 6 个种子收敛为 5 个可执行调研问题（Q1~Q5），每个问题明确调研对象、目标和产出。
3. **标杆搜索**：通过 WebSearch 工具搜索 9 组关键词，覆盖 Godot idle RPG 案例、GDExtension vs IPC 对比、跨平台导出、音频系统、迁移实践、godot-python 项目状态、idle 游戏架构、Web 导出限制、IPC 性能基准。
4. **事实提取**：从搜索结果中提取已核实事实，区分「已核实」「推断」「综合归纳」三种置信度。
5. **加权评分**：建立 5 维度加权对比矩阵，权重之和 = 1.00，按 1~5 分标尺打分。
6. **敏感性分析**：对权重分配进行敏感性分析，验证推荐排名的稳定性。
7. **风险识别**：识别 6 条主要风险，每条给出触发条件、影响范围、严重程度和缓解建议。
8. **自检报告**：在 4 个关键节点按中间确认协议进行自检，记录反向验证 3 问的答案与证据。

### B.2 工具清单

| 工具 | 用途 |
| --- | --- |
| WebSearch | 搜索行业标杆、官方文档、社区仓库、技术博客 |
| Read | 读取 agent 定义文件、模板文件、协议文件 |
| Write | 写入 research_report.md |
| TaskUpdate | 更新任务状态 |
| SendMessage | 回传结果给主理人 |

### B.3 调研覆盖度声明

| 调研主题 | 覆盖状态 | 对应章节 |
| --- | --- | --- |
| Godot 4 对 idle RPG 适配性 | ✅ 已覆盖 | §2.1 B3/B4, §2.2.3, §2.2.4, §2.3 |
| GDExtension vs IPC 桥接对比 | ✅ 已覆盖 | §2.1 B1/B2, §2.2.1, §2.2.2, §2.3, §3.1 |
| Godot 跨平台导出能力 | ✅ 已覆盖 | §2.3, §4.1, §4.2, §4.3, R-03 |
| 音频系统迁移路径 | ✅ 已覆盖 | §2.3, §4.1, §4.3, R-06, U-02 |
| 一人团队迁移风险 | ✅ 已覆盖 | §5.1 R-04, §A.4 |
| 云端部署可能性 | ✅ 已覆盖 | §4.2, D-05, SR-14, SR-19 |
