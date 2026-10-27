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

自测覆盖 7 条断言（协议版本、工具数量、各工具返回结构、写工具未确认即拒绝、未知工具报错）。

## 工具（7 个，6 读 1 写）

| 工具 | 作用 | 是否写入 |
| --- | --- | --- |
| `gate.list` | 列出治理门禁（id / title / tier / 基线） | 只读 |
| `gate.run` | 跑单个门禁（指定 `gate`）或整套聚合（`all=true`） | 只读（执行检查） |
| `registry.query` | 按 id / category 查项目注册表 | 只读 |
| `registry.verify` | 无头验证登记项目（`only` / `category` / `limit`） | 只读（执行验证） |
| `docs.search` | 文档枢纽全文检索（不含 `md/` 历史树） | 只读 |
| `project.status` | 单项目登记信息 + 本地克隆最后提交天数 + 上次验证结论 | 只读 |
| `record.append` | 起草治理记录 | **写**（必须 `confirm=true`） |

### 安全边界

- **只读默认**：除 `record.append` 外全部只读。
- **写操作要显式确认**：`record.append` 不带 `confirm=true` 直接返回 `isError`。
- **写入落在 `tools/gate/audit/mcp-drafts/`**，不进 `docs/`——否则会立刻触发文档索引契约
  D1「文件未登记」；草稿要成为正式记录，须由人移入 `docs/记录/` 并在 `INDEX.md` 登记。
- **每次接受写操作都落审计** `tools/gate/audit/mcp-actions.jsonl`（ts / tool / file）。
- 工具失败返回 `isError: true` + 原因，绝不返回空成功。

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
