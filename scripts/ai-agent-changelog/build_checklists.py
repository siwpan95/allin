# -*- coding: utf-8 -*-
"""生成 AI Agent 行业变更日志的 Markdown 与 Excel 清单。"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT_DIR = r"C:\Users\psw\WorkBuddy\2026-11-08-22-02-35"

# (章节, 发布日期, 发布主体, 事件/变化, 对照基线, 官方来源URL, 来源说明, 日期备注)
CONFIRMED = [
    ("第一章 前沿模型与代理能力（模型层）", "2026-10-13", "Google", "Gemini 4 Argon：面向长程多步 agentic 工作流，输出上限 64K→1M token；经 Fairwind 计划先向受信任网络防御者开放；定价 $2/$10（百万 token，缓存输入 95% 折扣）", "前代输出 64K，无分阶段前沿发布机制", "https://blog.google/intl/en-mena/company-news/technology/gemini-4-argon-our-next-era-of-frontier-intelligence", "blog.google · Gemini 4 Argon", ""),
    ("第一章 前沿模型与代理能力（模型层）", "2026-10 下旬", "Google", "Gemini 4 Carbon：迄今最强模型，主打长程工程与网络安全防御；SEC-bench Pro 88.2%、ExploitGym 54.8%、CWE-bench 71.0%；Terminal-Bench 4.0 作弊率 0.0%", "较 Argon 再大幅领先；此前无两周内连发两代前沿模型节奏", "https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-carbon", "blog.google · Gemini 4 Carbon", "精确日依「Argon 后约两周」推算"),
    ("第一章 前沿模型与代理能力（模型层）", "2026-10 月内", "Google", "Genie 4：实时交互世界模型，原生音频、自然语言实时操控场景；为机器人/agent 提供安全训练环境", "前代无原生音频与实时自然语操控", "https://blog.google/innovation-and-ai/models-and-research/google-deepmind/introducing-genie-4/", "blog.google · Genie 4 (DeepMind)", "官方列 10 月发布"),
    ("第一章 前沿模型与代理能力（模型层）", "2026-10-07", "Anthropic", "Claude Haiku 5.5：最快最强小模型，面向高吞吐；价格较 Haiku 4.5 低 90%/50%；Sonnet 5.5 缓存读取价腰斩；Python/TS SDK 新增 computer/browser use", "Haiku 4.5 更慢更贵、无 browser use", "https://anthropic.com/claude-haiku-5-5", "anthropic.com/claude-haiku-5-5", "10/7"),
    ("第一章 前沿模型与代理能力（模型层）", "2026-09-28", "Anthropic", "Claude Sonnet 5.5：提速 30%+、多数工作成本降低至多 30%", "Sonnet 5 更慢更贵", "https://anthropic.com", "anthropic.com 主页公告", "9/28"),
    ("第一章 前沿模型与代理能力（模型层）", "2026-09-22", "Anthropic", "Claude Opus 5.5：agentic coding 与知识工作领先，典型负载运行成本较 Opus 5 低 40%", "Opus 5 运行成本更高", "https://anthropic.com", "anthropic.com 主页公告", "9/22"),
    ("第一章 前沿模型与代理能力（模型层）", "2026-09-10", "DeepSeek", "DeepSeek-V4.1-Flash：552B MoE、原生视觉、新 Causal Encoder–Decoder 架构；KV cache 降至前代 1/4(HBM)/1/8(SSD)；MIT 许可、API 上线、非高峰半价", "V4-Flash/V4-Pro 无原生视觉、缓存成本更高", "https://deepseek.com/news/deepseek-v4-1-flash/", "deepseek.com/news/deepseek-v4-1-flash", ""),
    ("第一章 前沿模型与代理能力（模型层）", "2026-06-30", "Anthropic", "Fable 5 / Sonnet 5：出口管制解除后 7/1 全球可用；Sonnet 5 号称最 agentic；Claude Science 科研 agent 应用", "前代模型、无专用科研 agent 应用", "https://anthropic.com", "anthropic.com 主页公告", "6/30"),

    ("第二章 企业级平台与常驻代理（平台层）", "2026-10-08", "Google", "Gemini at Work：统一工作智能体，Workspace 内持久身份（独立邮箱/日历/Drive/目录项），跨 200+ 模型路由，连接 Workspace/M365/Slack/Jira 等及任意 MCP，加密签名非人类身份审计", "此前 Gemini 主要问答/单点助手，无常驻跨系统行动代理", "https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-at-work", "blog.google · Gemini at Work", "精确日待核（聚合 10/8）"),
    ("第二章 企业级平台与常驻代理（平台层）", "2026-09-29", "OpenAI", "DevDay 2026：Dots 常驻自主智能体（云端电脑、GPT-6 Astra 驱动）；GPT-6.1 Sol；Agents API 公测；Codex Cloud、Spaces", "此前无常驻自主代理、无统一 Agents API", "https://openai.com/index/devday-2026-recap/", "openai.com/index/devday-2026-recap", "9/29"),
    ("第二章 企业级平台与常驻代理（平台层）", "2026-09-29", "Perplexity", "Computer Automations：将 Scheduled Tasks 升级为事件触发、跨会话记忆、长期运行的自动化代理；支持 Slack/Gmail/Linear/GitHub 触发，设人工复核", "仅 Scheduled Tasks，每次从头", "https://perplexity.ai/hub/blog/computer-adds-automations-for-ongoing-work", "perplexity.ai 官方博客", "9/29"),
    ("第二章 企业级平台与常驻代理（平台层）", "2026-09-25", "Microsoft", "新版 Copilot（Autopilot）：Autopilot（原 Scout）数字同事，独立身份/记忆/电脑/工作区，长时间后台运行；Managed Runtime；Fabric IQ GA", "Scout 仅预览，无 Runtime 与数字同事式常驻代理", "https://blogs.microsoft.com/blog/2026/09/25/introducing-the-new-copilot-with-home-code-and-autopilot/", "blogs.microsoft.com · 9/25 Copilot", ""),
    ("第二章 企业级平台与常驻代理（平台层）", "2026-07-15", "Salesforce", "Agentforce Coworker：内建 Data 360 的自主 AI 队友，跨 300+ 企业源检索、主动洞察、编排 Agentforce；headless-first", "此前以客服/销售专项代理为主", "https://salesforce.com/jp/news/press-releases/2026/07/15/agentforce-coworker-salesforce-ai-teammate", "salesforce.com/jp · 7/15 新闻稿", ""),
    ("第二章 企业级平台与常驻代理（平台层）", "2026-06-08", "Apple", "Siri AI（WWDC26）：全重构 Siri，个人情境理解、屏幕感知、跨 App 操作、独立 Siri app、iCloud 同步；整合 iOS 27 等", "旧 Siri 语音指令/问答，无系统级 agent 能力与独立 app", "https://apple.com/newsroom/2026/06/apple-introduces-siri-ai-a-profoundly-more-capable-and-personal-assistant", "apple.com/newsroom · Siri AI", "6/8"),
    ("第二章 企业级平台与常驻代理（平台层）", "2026-06-02", "Microsoft", "Build 2026：Microsoft Agent Platform（IQ 驱动）；Microsoft IQ 上下文层；Scout 个人代理；MAI-Thinking-1；Agent 365 治理", "此前 Copilot 以辅助为主，无统一 Agent Platform 与跨栈上下文层", "https://blogs.microsoft.com/blog/2026/06/02/microsoft-build-2026-be-yourself-at-work/", "blogs.microsoft.com · Build 2026", ""),

    ("第三章 安全治理与开发者底座（基础层）", "2026-10-21", "NVIDIA", "OpenShell / Open Agent Safety Platform：OpenShell 开源运行时（沙箱+策略强制、零信任、进程外不可绕过）+ Sentry 硬件隔离监控（BlueField-4 带外、毫秒级隔离）+ Vera CPU；数十家共建", "此前缺面向代理的工业级安全治理参考架构", "https://nvidianews.nvidia.com/news/openshell-reference-architecture", "nvidianews.nvidia.com · 10/21 公告（GTC Berlin）", ""),
    ("第三章 安全治理与开发者底座（基础层）", "2026-09-30", "Anthropic", "Claude for Government：达 FedRAMP High 授权并 GA；与 GSA 扩展合作，40% 折扣、覆盖州/地方/部落/属地政府，预计省约 10 亿美元", "此前政府可用层级与覆盖范围更窄", "https://anthropic.com/news/expanding-partnership-gsa", "anthropic.com/news/expanding-partnership-gsa", "9/30 GA"),
    ("第三章 安全治理与开发者底座（基础层）", "2026-05-20", "Google", "I/O 2026：Gemini 3.5 Flash、Antigravity 2.0（代理开发/管理桌面，开发者调度代理中央枢纽）、Gemini Spark（个人 AI 代理、常驻、Chrome agentic browser、Android Halo）", "此前 Gemini 以问答/生成为主，代理能力有限", "https://blog.google/intl/zh-tw/sundar-pichai-io-2026/", "blog.google · I/O 2026", ""),
    ("第三章 安全治理与开发者底座（基础层）", "2026-04-15", "OpenAI", "Agents SDK 重大演进：原生 harness + 原生沙箱执行、Manifest 抽象、MCP/skills/AGENTS.md 原语、可配置记忆、快照与重水合、harness 与 compute 分离", "此前开发者需自行拼凑执行层，缺开箱即用安全沙箱与标准化 harness", "https://openai.com/index/the-next-evolution-of-the-agents-sdk/", "openai.com · Agents SDK 演进", "4/15"),
]

# (条目, 消息来源, 状态)
UNCONFIRMED = [
    ("Anthropic 内部评估事故（代理绕过限制访问真实网站，含美国政府站点）", "ainativeengineering.net", "未证实"),
    ("OpenAI 解雇三名安全研究员（Tomek Korbak / Mikita Balesni / Jasmine Wang）", "ainativeengineering.net", "未证实"),
    ("OpenClaw Enterprise（9/29，多租户持久代理控制面，Red Hat 创始成员）", "ainativeengineering.net", "未证实"),
    ("Cloudflare Monetization Gateway（10/1 beta，按请求向代理收费）", "orgtp.com / ainativeengineering.net", "未证实"),
    ("Meta Muse Spark Open（10/15，Muse 底层模型开放权重）", "orgtp.com", "未证实"),
    ("国内个人代理赛道（千问Go / 腾讯 LightVela / 字节 Spell / 微信小微）", "zgeo.net", "未证实"),
    ("第三方基准榜（PersonalAgentBench / Hermes Index）", "ainativeengineering.net", "未证实"),
]

# ---------- Markdown ----------
def gen_markdown():
    lines = []
    lines.append("# AI Agent 行业近期关键进展 · 结构化变更日志（核验修正版）\n")
    lines.append("> 时间窗口：2026-03 — 2026-11（近 8 个月） · 整理日期：2026-11-08  \n")
    lines.append("> 核验标准：厂商官方域名公告为 gold standard，传闻 / 泄露严格单列、逐条标注「未证实」。\n")
    lines.append("\n## 本轮（11-08）核验修正\n")
    lines.append("- Gemini 4 Argon 从「未证实」移入「已确认」（blog.google 官方公告 10/13）。")
    lines.append("- 新增同系列已确认条目 Gemini 4 Carbon、Genie 4。")
    lines.append("- 补齐精确日期：Apple Siri AI = 2026-06-08、NVIDIA OpenShell = 2026-10-21、Perplexity Automations = 2026-09-29。\n")

    chapters = []
    for c in CONFIRMED:
        ch = c[0]
        if ch not in chapters:
            chapters.append(ch)
    for ch in chapters:
        lines.append(f"\n## {ch}（已确认）\n")
        lines.append("| 发布日期 | 发布主体 | 事件 / 变化 | 对照基线（此前） | 官方来源 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for c in CONFIRMED:
            if c[0] != ch:
                continue
            date = c[1] + (f"（{c[7]}）" if c[7] else "")
            src = f"[{c[6]}]({c[5]})"
            lines.append(f"| {date} | {c[2]} | {c[3]} | {c[4]} | {src} |")
        lines.append("")

    lines.append("\n## 第四章 传闻与未证实消息（严格单列）\n")
    lines.append("> 下列条目**无法回溯到厂商官方公告**，全部标注「未证实」并列出来源，**不混入**已确认变更。\n")
    lines.append("| 条目 | 消息来源 | 状态 |")
    lines.append("| :--- | :--- | :--- |")
    for u in UNCONFIRMED:
        lines.append(f"| {u[0]} | {u[1]} | **{u[2]}** |")
    lines.append("")

    lines.append("\n## 核验说明与处理方式\n")
    lines.append("- **时间窗口**：限定 2026-03 — 2026-11（近 8 个月），覆盖行业从「对话式」转向「执行式 / 代理式」AI 的关键节点。")
    lines.append("- **无法核实精确发布日期者**：Google Gemini at Work（聚合 10/8）、Gemini 4 Carbon（依「Argon 后约两周」推算）、Genie 4（官方列 10 月）等，已标注「待核实 / 月内 / 推算」，不臆造官方日期。")
    lines.append("- **无法确认发布主体或仅见二级来源者**：一律归入「未证实」栏，与已确认严格区分；其中仅 Meta Muse Spark、OpenClaw 等「产品存在」被官方佐证，但所传细节 / 日期仍未被官方确认。")
    lines.append("- **核验方法**：以厂商官方域名为 gold standard，并用 WebFetch 直接核验关键页面；聚合博客仅作线索。")
    lines.append("- **局限性**：部分官方页面未暴露精确发布日期；个别事件类信息因敏感未在官方渠道公开，已归为未证实而非采信。")
    lines.append("\n> 注：「未证实」条目用于提示风险，不代表否定其真实性；如后续出现官方公告，应移入「已确认」栏并按格式补全基线对照与官方链接。\n")

    md_path = os.path.join(OUT_DIR, "ai-agent-changelog.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return md_path

# ---------- Excel ----------
def gen_excel():
    wb = Workbook()
    thin = Side(style="thin", color="D0D5DD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="171F2E")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    wrap = Alignment(vertical="top", wrap_text=True)
    center = Alignment(vertical="center", horizontal="center", wrap_text=True)

    # Sheet 1: 已确认变更
    ws = wb.active
    ws.title = "已确认变更"
    headers = ["章节", "发布日期", "发布主体", "事件 / 变化", "对照基线（此前）", "官方来源说明", "官方链接", "日期备注"]
    ws.append(headers)
    for ci, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border
    for c in CONFIRMED:
        ws.append([c[0], c[1], c[2], c[3], c[4], c[6], c[5], c[7]])
    widths = [34, 14, 12, 60, 38, 34, 50, 20]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for r in range(2, len(CONFIRMED) + 2):
        for ci in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=ci)
            cell.alignment = wrap
            cell.border = border
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(CONFIRMED)+1}"

    # Sheet 2: 未证实/传闻
    ws2 = wb.create_sheet("未证实传闻")
    headers2 = ["条目", "消息来源", "状态"]
    ws2.append(headers2)
    for ci, _ in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=ci)
        cell.fill = PatternFill("solid", fgColor="7B241C")
        cell.font = header_font
        cell.alignment = center
        cell.border = border
    for u in UNCONFIRMED:
        ws2.append(list(u))
    widths2 = [70, 36, 12]
    for i, w in enumerate(widths2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    for r in range(2, len(UNCONFIRMED) + 2):
        for ci in range(1, len(headers2) + 1):
            cell = ws2.cell(row=r, column=ci)
            cell.alignment = wrap
            cell.border = border
            if ci == 3:
                cell.font = Font(bold=True, color="C0392B")
    ws2.freeze_panes = "A2"

    # Sheet 3: 说明
    ws3 = wb.create_sheet("说明")
    notes = [
        ("时间窗口", "2026-03 — 2026-11（近 8 个月），覆盖行业从「对话式」转向「执行式 / 代理式」AI 的关键节点。"),
        ("收录口径", "仅收录「明确发布主体 + 可核实官方来源 + 发布日期」的变化；无法获取精确日期者标注「待核实 / 推算」，不臆造。"),
        ("Gold Standard", "openai.com / anthropic.com / blog.google / blogs.microsoft.com / apple.com / meta.com / salesforce.com / nvidia.com / deepseek.com / perplexity.ai；并用 WebFetch 核验关键页面。"),
        ("日期待核条目", "Google Gemini at Work（聚合 10/8）、Gemini 4 Carbon（依「Argon 后约两周」推算约 10/27）、Genie 4（官方列 10 月）标注待核，未臆造。"),
        ("未证实栏", "无法回溯官方公告者一律单列，逐条标注「未证实」并附来源，不混入已确认。"),
        ("本轮修正", "Gemini 4 Argon 由未证实移入已确认（blog.google 10/13）；新增 Gemini 4 Carbon、Genie 4；补齐 Apple Siri AI=6/8、NVIDIA OpenShell=10/21、Perplexity Automations=9/29。"),
        ("局限性", "部分官方页未暴露精确日期；个别事件类信息因敏感未在官方渠道公开，已归为未证实而非采信。"),
    ]
    ws3.append(["项目", "说明"])
    for ci in (1, 2):
        cell = ws3.cell(row=1, column=ci)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border
    for k, v in notes:
        ws3.append([k, v])
    ws3.column_dimensions["A"].width = 16
    ws3.column_dimensions["B"].width = 90
    for r in range(2, len(notes) + 2):
        for ci in (1, 2):
            cell = ws3.cell(row=r, column=ci)
            cell.alignment = wrap
            cell.border = border

    xlsx_path = os.path.join(OUT_DIR, "ai-agent-changelog.xlsx")
    wb.save(xlsx_path)
    return xlsx_path

if __name__ == "__main__":
    md = gen_markdown()
    xl = gen_excel()
    print("MD :", md)
    print("XLSX:", xl)
    print("confirmed rows:", len(CONFIRMED), "unconfirmed rows:", len(UNCONFIRMED))
