// agent-trace.js —— agent 侧执行留痕（AgentOps 的最小闭环）
//
// 为什么存在
// ----------
// `gate-runs.jsonl` 记的是**门禁**的执行（仓库体检），`mcp-actions.jsonl` 记的是**写操作**
// （哪些文件被改了）。两者合起来仍答不了一个问题：
//
//     **这次 agent 任务，到底调了哪些工具、走了几步、成没成、花了多久？**
//
// 这正是 AgentOps 与「代码门禁」的分界线：门禁判**仓库**，trace 判**agent 的行为路径**。
// AgentOps 的失败模式不是「模型说错了」，而是「**做了无法解释、无法回滚的动作**」——
// 而要解释一个动作，必须先有动作序列的记录。
//
// 为什么落在 MCP 这一层
// --------------------
// ① MCP 是本仓**自有**的 agent 工具面（`platform/apps/mcp/src/index.js` 的 `TOOLS[]`），
//    唯一入口是 `callTool` —— 埋点一处即覆盖全部工具；
// ② MCP 走 stdio JSON-RPC，**一个进程 = 一个会话**，天然给出 trace 边界；
// ③ 对应 AgentOps 的一条硬原则：**遥测由中间件发出，不由模型自述**
//    （agent 不能自己声称「我没做坏事」—— 记录必须来自执行侧）。
//
// 字段命名
// --------
// 向 **OpenTelemetry GenAI 语义约定**对齐（`gen_ai.*`），但**不引入 OTel SDK**
// （本仓取向：零外部依赖、可审计、单仓自持）。已采用 canonical 命名
// （`gen_ai.tool.call.status` / `gen_ai.tool.call.id` / `gen_ai.operation.name` /
// `gen_ai.trace.id` 等），完整机械映射见 `OTEL_GENAI_MAP`。
// 将来若接 Phoenix/Langfuse/自有 collector，映射是机械改名，不需重写埋点 ⇒ 零锁定成本。
// 参考：https://opentelemetry.io/docs/specs/semconv/gen-ai/
//
// 只记元数据，不记内容
// ------------------
// 工具参数与返回值里可能有文档正文、记忆条目、路径 —— 一律**不落盘**。
// 只记「调了哪个工具、参数多大、成没成、多久」这类元数据：
// 这是 AgentOps 的 privacy 基线（不默认记录 prompt/response/文档内容）。

import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

/** OTel GenAI 字段映射表（零锁定成本）。
 * 本仓自产字段已向 OpenTelemetry GenAI 语义约定对齐
 * （https://opentelemetry.io/docs/specs/semconv/gen-ai/），**不引入 OTel SDK**。
 * 若将来接 Phoenix / Langfuse / 自有 collector，下表即机械改名对照，不需重写埋点 ⇒ 零锁定成本。 */
export const OTEL_GENAI_MAP = {
  'gen_ai.operation.name': 'execute_tool（一次工具执行）',
  'gen_ai.agent.name': 'allin-governance（产生 trace 的 agent）',
  'gen_ai.system': 'allin-governance（工具面归属）',
  'gen_ai.trace.id': '= trace_id（一次会话）',
  'gen_ai.tool.name': '= tool（被调工具名）',
  'gen_ai.tool.call.id': '= span_id（单次工具调用）',
  'gen_ai.tool.call.status': 'ok | rejected | error（rejected=策略拒绝，不计失败）',
  'gen_ai.tool.type': 'function（MCP 工具以函数调用形态触发）',
  'gen_ai.client.operation.duration': '= ms（毫秒）',
  'gen_ai.usage.input_tokens': '= args_bytes（以字节近似，非真 token）',
  'gen_ai.usage.output_tokens': '= result_bytes（以字节近似，非真 token）',
}

/** 单条 trace 的字段名（与 OTel GenAI 对齐的部分加注释，便于将来机械映射）。 */
export function buildSpan({ toolName, ok, errorKind, ms, argsBytes, resultBytes, sessionId, spanIndex, tier, budgetExceeded, degradationTier, degradationReason, fallbackFrom }) {
  const spanId = crypto.randomBytes(8).toString('hex')
  return {
    ts: new Date().toISOString(),
    // ── 追踪标识（OTel 标准属性）──
    trace_id: sessionId,                                   // 一次 MCP 会话 = 一个 trace
    span_id: spanId,                                       // 单次工具调用 = 一个 span
    span_index: spanIndex,                                 // 会话内序号（步数）
    session_id: sessionId,
    // ── OTel GenAI 对齐段（canonical 命名，见 OTEL_GENAI_MAP；不引入 OTel SDK）──
    'gen_ai.operation.name': 'execute_tool',               // 本 span 是一次工具执行
    'gen_ai.agent.name': 'allin-governance',               // 产生该 trace 的 agent / 系统
    'gen_ai.system': 'allin-governance',                   // 工具面归属（本仓自有 MCP server）
    'gen_ai.trace.id': sessionId,                          // 一次会话 = 一个 trace（GenAI 约定属性名）
    'gen_ai.tool.name': toolName,                          // gen_ai.tool.name
    'gen_ai.tool.call.id': spanId,                         // 单次工具调用 id（= span_id）
    'gen_ai.tool.call.status': ok ? 'ok' : (errorKind === 'rejected' ? 'rejected' : 'error'),
    'gen_ai.tool.type': 'function',                        // MCP 工具以函数调用形态触发
    'gen_ai.client.operation.duration': ms,                // gen_ai.client.operation.duration（毫秒）
    'gen_ai.usage.input_tokens': argsBytes,                // 以参数字节数近似输入规模（非真 token）
    'gen_ai.usage.output_tokens': resultBytes,             // 以返回字节数近似输出规模（非真 token）
    // ── 本仓自有段（治理语义，jq/grep 直读）──
    tool: toolName,                                        // 便于 jq/grep 直读
    ok,
    error_kind: errorKind,                                 // 'rejected'（策略拒绝）| 'failed'（真失败）
    tier,                                                  // 'read' | 'write-reversible' | 'write-irreversible'
    budget_exceeded: budgetExceeded || false,              // 是否因会话调用预算耗尽被熔断器拦截
    ms,
    args_bytes: argsBytes,
    result_bytes: resultBytes,
    error: ok ? undefined : (errorKind === 'rejected'
      ? 'rejected by policy or validation'
      : 'tool failed or threw'),
    // ── LLM 降级可观测段（2026-11-10）：当本次调用伴随模型降级决策时记录档位，
    // 便于事后从 agent-runs.jsonl 复盘「为何落到 offline / fallback」。字段名对齐
    // GenAI 约定（degradation.tier / .reason / .fallback_from）。
    'degradation.tier': degradationTier || null,          // 'online' | 'fallback' | 'offline'
    'degradation.reason': degradationReason || null,      // 触发原因（budget-exceeded / primary-unavailable / explicit-offline ...）
    'degradation.fallback_from': fallbackFrom || null,    // 从哪个档位降级而来
  }
}

/** 参数/返回值的字节规模（只算大小，不留内容）。 */
export function byteSize(value) {
  if (value === undefined || value === null) return 0
  try {
    return Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value), 'utf8')
  } catch {
    return 0
  }
}

/**
 * Trace 记录器：一次会话一个实例。
 * 落盘采用 **append-only JSONL**（与 `gate-runs.jsonl` / `mcp-actions.jsonl` 同范式）。
 * 写失败**不得影响工具执行** —— 遥测不可用时，agent 仍要能干活（但要留证据）。
 */
export class AgentTrace {
  constructor(auditDir, { enabled = true } = {}) {
    this.file = path.join(auditDir, 'agent-runs.jsonl')
    this.sessionId = crypto.randomBytes(8).toString('hex')
    this.spanIndex = 0
    this.enabled = enabled
    this.failures = 0
  }

  /** 记录一次工具调用。返回落盘后的 span（便于自检断言）。 */
  record(span) {
    this.spanIndex += 1
    const full = { ...span, span_index: this.spanIndex }
    if (!this.enabled) return full
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true })
      fs.appendFileSync(this.file, JSON.stringify(full) + '\n', 'utf8')
    } catch {
      // 遥测写失败只计数，不抛出 —— 但计数本身要能被看见（自检读这个字段）。
      this.failures += 1
    }
    return full
  }

  /** 会话内已记录的步数。 */
  get steps() {
    return this.spanIndex
  }
}
