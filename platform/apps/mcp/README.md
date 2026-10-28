# allin MCP server（治理即工具）

把 allin 的治理面暴露成 **MCP 工具**，让任何 MCP 客户端（DeepSeek Harness、WorkBuddy、
Cursor、Claude…）都能直接调用门禁，而不只是"读一遍规则文本"。

零第三方依赖，只用 `node:` 内置模块；路径一律由本文件位置推导，不写死盘符。

## 跑起来

```bash
node platform/apps/mcp/src/index.js            # stdio（默认，供 MCP 客户端拉起）
node platform/apps/mcp/src/index.js --selftest # 自检：脚本化会话走一遍 initialize→tools/list→tools/call
node platform/apps/mcp/src/index.js --list-tools
```

自测覆盖 13 条断言（协议版本、工具数量、各工具返回结构、两个写工具未确认即拒绝、非法 layer 拒绝、未知工具报错）。

## 工具（13 个，11 读 2 写）

| 工具 | 作用 | 是否写入 |
| --- | --- | --- |
| `gate.list` | 列出治理门禁（id / title / tier / 基线） | 只读 |
| `gate.run` | 跑单个门禁（指定 `gate`）或整套聚合（`all=true`） | 只读（执行检查） |
| `gate.history` | 汇总门禁执行留痕：总次数 / 失败 / 各标签最近退出码 / 最近 N 条 | 只读 |
| `metrics.snapshot` | 跑 `gate_metrics.py --json`：逃逸率 / 证据新鲜度 / 例外燃尽 / 性能预算 | 只读 |
| `exceptions.list` | 读例外台账（id / kind / gate / status / expires + open/closed 计数） | 只读 |
| `registry.query` | 按 id / category 查项目注册表 | 只读 |
| `registry.verify` | 无头验证登记项目（`only` / `category` / `limit`） | 只读（执行验证） |
| `docs.search` | 文档枢纽全文检索（不含 `md/` 历史树） | 只读 |
| `project.status` | 单项目登记信息 + 本地克隆最后提交天数 + 上次验证结论 | 只读 |
| `memory.read` | 召回 agent 长期记忆（`docs/记录/记忆/` 按月卷；可按关键词/层过滤，默认隐藏已取代条目） | 只读 |
| `memory.promotable` | 记忆晋升看板：同 tag ≥阈值条且未晋升 ⇒ 固化为 skill 的候选清单 | 只读 |
| `record.append` | 起草治理记录 | **写**（必须 `confirm=true`） |
| `memory.append` | 向当月记忆卷追加一条带日期的经验（自学习回路记账入口） | **写**（必须 `confirm=true`） |

### 安全边界

- **只读默认**：除 `record.append` / `memory.append` 外全部只读。
- **写操作要显式确认**：两个写工具不带 `confirm=true` 直接返回 `isError`。
- **`record.append` 写在 `tools/gate/audit/mcp-drafts/`**，不进 `docs/`——否则会立刻触发
  文档索引契约 D1「文件未登记」；草稿要成为正式记录，须由人移入 `docs/记录/` 并在 `INDEX.md` 登记。
- **`memory.append` 只追加、不新建**：目标必须是**已存在且已在 `docs/INDEX.md` §4 登记**的
  当月卷 `docs/记录/记忆/<YYYY-MM>.md`（未登记直接拒绝，避免 D1 打红）；开新卷属治理动作，
  由人（或走完整文档流程）完成。条目**只增不改**，纠错另起新条目注明取代关系。
- **每次接受写操作都落审计** `tools/gate/audit/mcp-actions.jsonl`（ts / tool / file）。
- **工具失败返回 `isError: true` + 原因，绝不返回空成功。**
- **调用成功 ≠ 任务完成**：`gate.run` / `registry.verify` 额外返回 `verified` 与 `verifiedBy`
  —— 退出码 0 也要以实证为准（整套门禁须出现「N/N gate(s) clean」且两数相等；
  验证项目须无 FAIL 行），否则 `verified=false` 并把 FAIL 行数报出来。
- **检索口径诚实**：`docs.search` 只索引 Markdown，返回 `skippedNonText` 计数并声明
  「PDF/表格/扫描件未索引」——专用解析引擎与本机零依赖原则冲突，**明确不做**，
  但必须把跳过量报出来，避免 agent 误以为「搜过但没结果」。

## 自学习回路（memory.* 的用法契约）

```
观察（gate.history / metrics.snapshot / 任务结果）
  → 提炼一条可复用经验
  → memory.append（confirm=true）记账到当月卷
  → 下次会话 memory.read 召回，避免重踩
```

## 记忆的分层 · 取代 · 晋升

| 机制 | 做法 | 为什么 |
| --- | --- | --- |
| **分层** | `memory.append` 带 `layer`：`临时`（默认，可被晋升）/ `永久`（已固化或长期事实） | 让「将来要被提炼的」和「已定型的」分开，晋升时才扫得动 |
| **取代** | 纠错不删旧条目，另起新条目带 `supersedes: <被取代条目日期>`；`memory.read` **默认隐藏**被取代者，`includeSuperseded=true` 才显示 | 「只增不改」与「记忆会过期」的矛盾，用覆盖而非删除解决，不需要遗忘策略 |
| **晋升** | 同 tag 有效条目 ≥`threshold`（默认 3）进 `memory.promotable` 候选 → 走文档流程固化为专项 skill（建 skill → 同步双载体 → 过门禁）→ 回写一条「已晋升」条目 | 经验从「被读到」升级为「被执行」，同时防止月卷无限膨胀 |

DSH 官方的外接记忆方案（`docs/user/guide/mcp-memory`）同样是「记忆经 MCP 暴露」；
本服务器把记忆落在**受治理的文档月卷**里（git 版本化 + D1/D8 + g19 快照豁免），
比第三方记忆服务的黑盒存储更符合本仓「文档即事实源」的口径。

## 接到 DeepSeek Harness

DSH 用 `@deepseek-ai/dsh-mcp-client` 桥接（**一个插件实例 = 一个 MCP server**），
工具以 `mcp__<serverName>__<tool>` 形式进入 `ctx.tools`，并受 DSH 的工具治理
（allow/deny、超时、结果重写）约束。在 `cordis.yml` / patch 里 insert：

```yaml
- insert:
    - id: mcp-allin
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: allin
        transport: stdio
        command: node
        args: ['platform/apps/mcp/src/index.js']
        cwd: <allin 仓根>
        toolCallTimeoutMs: 180000
        failOnStartupError: false
```

挂上后工具名为 `mcp__allin__gate_run`、`mcp__allin__registry_query` …
（详见 `preset/allin/agent.cordis.yml` 里已有的 MCP 配方说明）。

---

# DSH Hook 栅栏：让治理对 agent 真的生效

文本注入只能告诉 agent「规则是什么」；**Hook 能拦住它**。DSH 的 Hook Protocol 规定
`PreToolUse` 钩子 **exit 2 = 阻断操作**，stderr 作为给 agent 的阻断理由。

- 脚本：`src/hook-pretool.js`（读 stdin 的事件 JSON，判目标是否在 allin 仓内 → 跑快速门禁
  `g01-paths` + `g03-credentials` → 红则 exit 2）
- 配置：`preset/allin/hooks.json`（Claude Code 方言，即 `@deepseek-ai/dsh-hooks-claude-code`）

```bash
node platform/apps/mcp/src/hook-pretool.js --selftest
echo '{"tool_name":"Write","tool_input":{"file_path":"README.md"}}' | node platform/apps/mcp/src/hook-pretool.js
```

自检三条：仓外写入直接放行（不跑门禁）、仓内写入且门禁绿 → 放行、门禁红 → exit 2 且
stderr 给出阻断理由。命令用**相对路径**（`node platform/apps/mcp/src/hook-pretool.js`），
在会话 cwd = 仓根时生效，源码里不出现盘符。

> 保守设计：只判本仓内的目标、只跑快到能进 agent 关键路径的两道门禁；
> 钩子自身故障记为 warning，既不静默放行也不硬拦。
