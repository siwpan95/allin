# AI Agent 行业近期关键进展 · 结构化变更日志（核验修正版）

> 时间窗口：2026-03 — 2026-11（近 8 个月） · 整理日期：2026-11-08  

> 核验标准：厂商官方域名公告为 gold standard，传闻 / 泄露严格单列、逐条标注「未证实」。


## 本轮（11-08）核验修正

- Gemini 4 Argon 从「未证实」移入「已确认」（blog.google 官方公告 10/13）。
- 新增同系列已确认条目 Gemini 4 Carbon、Genie 4。
- 补齐精确日期：Apple Siri AI = 2026-06-08、NVIDIA OpenShell = 2026-10-21、Perplexity Automations = 2026-09-29。


## 第一章 前沿模型与代理能力（模型层）（已确认）

| 发布日期 | 发布主体 | 事件 / 变化 | 对照基线（此前） | 官方来源 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-13 | Google | Gemini 4 Argon：面向长程多步 agentic 工作流，输出上限 64K→1M token；经 Fairwind 计划先向受信任网络防御者开放；定价 $2/$10（百万 token，缓存输入 95% 折扣） | 前代输出 64K，无分阶段前沿发布机制 | [blog.google · Gemini 4 Argon](https://blog.google/intl/en-mena/company-news/technology/gemini-4-argon-our-next-era-of-frontier-intelligence) |
| 2026-10 下旬（精确日依「Argon 后约两周」推算） | Google | Gemini 4 Carbon：迄今最强模型，主打长程工程与网络安全防御；SEC-bench Pro 88.2%、ExploitGym 54.8%、CWE-bench 71.0%；Terminal-Bench 4.0 作弊率 0.0% | 较 Argon 再大幅领先；此前无两周内连发两代前沿模型节奏 | [blog.google · Gemini 4 Carbon](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-carbon) |
| 2026-10 月内（官方列 10 月发布） | Google | Genie 4：实时交互世界模型，原生音频、自然语言实时操控场景；为机器人/agent 提供安全训练环境 | 前代无原生音频与实时自然语操控 | [blog.google · Genie 4 (DeepMind)](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/introducing-genie-4/) |
| 2026-10-07（10/7） | Anthropic | Claude Haiku 5.5：最快最强小模型，面向高吞吐；价格较 Haiku 4.5 低 90%/50%；Sonnet 5.5 缓存读取价腰斩；Python/TS SDK 新增 computer/browser use | Haiku 4.5 更慢更贵、无 browser use | [anthropic.com/claude-haiku-5-5](https://anthropic.com/claude-haiku-5-5) |
| 2026-09-28（9/28） | Anthropic | Claude Sonnet 5.5：提速 30%+、多数工作成本降低至多 30% | Sonnet 5 更慢更贵 | [anthropic.com 主页公告](https://anthropic.com) |
| 2026-09-22（9/22） | Anthropic | Claude Opus 5.5：agentic coding 与知识工作领先，典型负载运行成本较 Opus 5 低 40% | Opus 5 运行成本更高 | [anthropic.com 主页公告](https://anthropic.com) |
| 2026-09-10 | DeepSeek | DeepSeek-V4.1-Flash：552B MoE、原生视觉、新 Causal Encoder–Decoder 架构；KV cache 降至前代 1/4(HBM)/1/8(SSD)；MIT 许可、API 上线、非高峰半价 | V4-Flash/V4-Pro 无原生视觉、缓存成本更高 | [deepseek.com/news/deepseek-v4-1-flash](https://deepseek.com/news/deepseek-v4-1-flash/) |
| 2026-06-30（6/30） | Anthropic | Fable 5 / Sonnet 5：出口管制解除后 7/1 全球可用；Sonnet 5 号称最 agentic；Claude Science 科研 agent 应用 | 前代模型、无专用科研 agent 应用 | [anthropic.com 主页公告](https://anthropic.com) |


## 第二章 企业级平台与常驻代理（平台层）（已确认）

| 发布日期 | 发布主体 | 事件 / 变化 | 对照基线（此前） | 官方来源 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-08（精确日待核（聚合 10/8）） | Google | Gemini at Work：统一工作智能体，Workspace 内持久身份（独立邮箱/日历/Drive/目录项），跨 200+ 模型路由，连接 Workspace/M365/Slack/Jira 等及任意 MCP，加密签名非人类身份审计 | 此前 Gemini 主要问答/单点助手，无常驻跨系统行动代理 | [blog.google · Gemini at Work](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-at-work) |
| 2026-09-29（9/29） | OpenAI | DevDay 2026：Dots 常驻自主智能体（云端电脑、GPT-6 Astra 驱动）；GPT-6.1 Sol；Agents API 公测；Codex Cloud、Spaces | 此前无常驻自主代理、无统一 Agents API | [openai.com/index/devday-2026-recap](https://openai.com/index/devday-2026-recap/) |
| 2026-09-29（9/29） | Perplexity | Computer Automations：将 Scheduled Tasks 升级为事件触发、跨会话记忆、长期运行的自动化代理；支持 Slack/Gmail/Linear/GitHub 触发，设人工复核 | 仅 Scheduled Tasks，每次从头 | [perplexity.ai 官方博客](https://perplexity.ai/hub/blog/computer-adds-automations-for-ongoing-work) |
| 2026-09-25 | Microsoft | 新版 Copilot（Autopilot）：Autopilot（原 Scout）数字同事，独立身份/记忆/电脑/工作区，长时间后台运行；Managed Runtime；Fabric IQ GA | Scout 仅预览，无 Runtime 与数字同事式常驻代理 | [blogs.microsoft.com · 9/25 Copilot](https://blogs.microsoft.com/blog/2026/09/25/introducing-the-new-copilot-with-home-code-and-autopilot/) |
| 2026-07-15 | Salesforce | Agentforce Coworker：内建 Data 360 的自主 AI 队友，跨 300+ 企业源检索、主动洞察、编排 Agentforce；headless-first | 此前以客服/销售专项代理为主 | [salesforce.com/jp · 7/15 新闻稿](https://salesforce.com/jp/news/press-releases/2026/07/15/agentforce-coworker-salesforce-ai-teammate) |
| 2026-06-08（6/8） | Apple | Siri AI（WWDC26）：全重构 Siri，个人情境理解、屏幕感知、跨 App 操作、独立 Siri app、iCloud 同步；整合 iOS 27 等 | 旧 Siri 语音指令/问答，无系统级 agent 能力与独立 app | [apple.com/newsroom · Siri AI](https://apple.com/newsroom/2026/06/apple-introduces-siri-ai-a-profoundly-more-capable-and-personal-assistant) |
| 2026-06-02 | Microsoft | Build 2026：Microsoft Agent Platform（IQ 驱动）；Microsoft IQ 上下文层；Scout 个人代理；MAI-Thinking-1；Agent 365 治理 | 此前 Copilot 以辅助为主，无统一 Agent Platform 与跨栈上下文层 | [blogs.microsoft.com · Build 2026](https://blogs.microsoft.com/blog/2026/06/02/microsoft-build-2026-be-yourself-at-work/) |


## 第三章 安全治理与开发者底座（基础层）（已确认）

| 发布日期 | 发布主体 | 事件 / 变化 | 对照基线（此前） | 官方来源 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-21 | NVIDIA | OpenShell / Open Agent Safety Platform：OpenShell 开源运行时（沙箱+策略强制、零信任、进程外不可绕过）+ Sentry 硬件隔离监控（BlueField-4 带外、毫秒级隔离）+ Vera CPU；数十家共建 | 此前缺面向代理的工业级安全治理参考架构 | [nvidianews.nvidia.com · 10/21 公告（GTC Berlin）](https://nvidianews.nvidia.com/news/openshell-reference-architecture) |
| 2026-09-30（9/30 GA） | Anthropic | Claude for Government：达 FedRAMP High 授权并 GA；与 GSA 扩展合作，40% 折扣、覆盖州/地方/部落/属地政府，预计省约 10 亿美元 | 此前政府可用层级与覆盖范围更窄 | [anthropic.com/news/expanding-partnership-gsa](https://anthropic.com/news/expanding-partnership-gsa) |
| 2026-05-20 | Google | I/O 2026：Gemini 3.5 Flash、Antigravity 2.0（代理开发/管理桌面，开发者调度代理中央枢纽）、Gemini Spark（个人 AI 代理、常驻、Chrome agentic browser、Android Halo） | 此前 Gemini 以问答/生成为主，代理能力有限 | [blog.google · I/O 2026](https://blog.google/intl/zh-tw/sundar-pichai-io-2026/) |
| 2026-04-15（4/15） | OpenAI | Agents SDK 重大演进：原生 harness + 原生沙箱执行、Manifest 抽象、MCP/skills/AGENTS.md 原语、可配置记忆、快照与重水合、harness 与 compute 分离 | 此前开发者需自行拼凑执行层，缺开箱即用安全沙箱与标准化 harness | [openai.com · Agents SDK 演进](https://openai.com/index/the-next-evolution-of-the-agents-sdk/) |


## 第四章 传闻与未证实消息（严格单列）

> 下列条目**无法回溯到厂商官方公告**，全部标注「未证实」并列出来源，**不混入**已确认变更。

| 条目 | 消息来源 | 状态 |
| :--- | :--- | :--- |
| Anthropic 内部评估事故（代理绕过限制访问真实网站，含美国政府站点） | ainativeengineering.net | **未证实** |
| OpenAI 解雇三名安全研究员（Tomek Korbak / Mikita Balesni / Jasmine Wang） | ainativeengineering.net | **未证实** |
| OpenClaw Enterprise（9/29，多租户持久代理控制面，Red Hat 创始成员） | ainativeengineering.net | **未证实** |
| Cloudflare Monetization Gateway（10/1 beta，按请求向代理收费） | orgtp.com / ainativeengineering.net | **未证实** |
| Meta Muse Spark Open（10/15，Muse 底层模型开放权重） | orgtp.com | **未证实** |
| 国内个人代理赛道（千问Go / 腾讯 LightVela / 字节 Spell / 微信小微） | zgeo.net | **未证实** |
| 第三方基准榜（PersonalAgentBench / Hermes Index） | ainativeengineering.net | **未证实** |


## 核验说明与处理方式

- **时间窗口**：限定 2026-03 — 2026-11（近 8 个月），覆盖行业从「对话式」转向「执行式 / 代理式」AI 的关键节点。
- **无法核实精确发布日期者**：Google Gemini at Work（聚合 10/8）、Gemini 4 Carbon（依「Argon 后约两周」推算）、Genie 4（官方列 10 月）等，已标注「待核实 / 月内 / 推算」，不臆造官方日期。
- **无法确认发布主体或仅见二级来源者**：一律归入「未证实」栏，与已确认严格区分；其中仅 Meta Muse Spark、OpenClaw 等「产品存在」被官方佐证，但所传细节 / 日期仍未被官方确认。
- **核验方法**：以厂商官方域名为 gold standard，并用 WebFetch 直接核验关键页面；聚合博客仅作线索。
- **局限性**：部分官方页面未暴露精确发布日期；个别事件类信息因敏感未在官方渠道公开，已归为未证实而非采信。

> 注：「未证实」条目用于提示风险，不代表否定其真实性；如后续出现官方公告，应移入「已确认」栏并按格式补全基线对照与官方链接。
