# ADR-0003 —— MCP 工具默认只读，写入必须显式确认

- 状态：**accepted**（2026-10-28 落地：`platform/apps/mcp/src/index.js`）
- 相关：调研线 3（MCP 生态）：「read-only default + secret filtering + audit + rate limiting」

## Problem

治理能力要能被 AI agent 用起来，就要暴露成 MCP 工具（`gate.list` / `gate.run` / `registry.query` …）。
问题随之而来：agent 是**会犯错的自动化**，而治理仓是**唯一事实源**。
把「写文档」也做成工具，等于允许一个概率性系统直接改制度。给不给写权限，怎么给？

## Decision

**默认只读，写入是显式例外。** MCP server 的 7 个工具里 6 个只读，唯一能写的
`record.append` 必须满足三条件才落盘：

1. 调用方显式传 `confirm: true`——不传即拒绝，且拒绝是默认路径而非报错路径；
2. 内容写进 `tools/gate/audit/mcp-drafts/`（**草稿区，不进 `docs/`**），
   绕过 `docs_index` 的 D1「文档存在但没登记」红；
3. 每次接受写操作都追加一条到 `tools/gate/audit/mcp-actions.jsonl`（ts / tool / file），
   成为可审计的痕迹。

要成为正式记录，必须由人移入 `docs/记录/` 并在 `docs/INDEX.md` 登记——
**AI 起草，人发布**。这条界线不是不信任模型，而是：制度的可追溯性要求
「谁在什么时点让这句话生效」有唯一答案，而自动化没有人格。

配套：PreToolUse 钩子（`platform/apps/mcp/src/hook-pretool.js`）在落笔/落命令**之前**
跑 `g01-paths` 与 `g03-credentials`，红则 `exit 2` 阻断并把原因写进 stderr。
钩子是硬栅栏，不依赖模型自觉。

## Alternatives considered

| 方案 | 为什么没选 |
| --- | --- |
| 全只读，不提供写工具 | agent 只能查不能记，调研/巡检结论仍需人手誊写，MCP 的收益砍半 |
| 直接写 `docs/记录/` 并自动登记 INDEX | 让自动化直接触碰唯一事实源与索引；一次误写即污染 D1/D8 计数，且撤销成本高于收益 |
| 写入前弹人工确认（交互式） | MCP 是 stdio 协议，agent 侧无人可应答；交互确认要么被硬编码放行，要么永远超时 |

## Consequences

- 正：写能力可用，但爆炸半径被限制在 gitignore 的草稿区，且留痕可审计。
- 正：`record.append` 的「不进 `docs/`」使它与既有文档契约（D1/D8）正交，不制造新的红。
- 负：**多一步人工**——草稿要变成记录仍需人来搬。这是刻意保留的摩擦，不是缺陷。
- 负：`mcp-actions.jsonl` 与 `mcp-drafts/` 都在被忽略的目录里，
  不进版本库意味着**换机即丢**；需要留档时必须主动复制出来。
- 复核触发条件：若草稿转正的频次高到人工搬运成为瓶颈，再考虑受控的自动登记（仍带审计行）。
