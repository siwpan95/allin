// model_route.js —— 大模型 LLM 降级选择的决策层（零依赖、纯函数、可单测）。
//
// 治理边界（2026-11-10）：本仓**不引入 LLM 运行时**（G3 裁决）。本模块只做「选档位」
// 决策——真实模型调用在仓外编排层（DSH / WorkBuddy）执行。降级策略声明在
// `preset/allin/allin.patch.yml` 的 GOVERNANCE 段与 `docs/事实源/模型凭据登记.yaml`，
// 凭据值由 dsvault / 环境变量在运行时解析，本仓只记槽位、不记值。
//
// 本仓 MCP 工具面是**全确定性**的：即使所有远程 LLM 不可达，25 个治理工具仍全可用，
// 天然构成降级终点（见 `model.fallback-catalog`）。

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
// platform/apps/mcp/src → repo root = 4 级 up；ALLIN_ROOT 优先（与门禁/CLI 同口径）。
const REPO_ROOT = process.env.ALLIN_ROOT
  ? path.resolve(process.env.ALLIN_ROOT)
  : path.resolve(__dirname, '..', '..', '..', '..')
const REGISTRY_YAML = path.join(REPO_ROOT, 'docs', '事实源', '模型凭据登记.yaml')

/** 模型不可用时仍可完成的任务（本仓确定性 MCP 工具面，天然降级终点）。 */
export const DETERMINISTIC_FALLBACK_TASKS = [
  'docs.search —— 文档枢纽全文检索与 citation 引用（BM25，不上向量库）',
  'facts.query —— 事实源台账结构化查询',
  'registry.query / registry.verify —— 项目注册表查询与无头验证',
  'gate.list / gate.run —— 治理门禁列举与执行',
  'project.status —— 单项目登记信息与本地克隆最后提交天数',
  'health.model —— 当前模型降级档位只读查询',
]

let _cache = null

/** 读取模型凭据登记表（机器可读、零明文）；读取失败返回空目录而非抛错。 */
export function loadModelCatalog() {
  if (_cache) return _cache
  try {
    const doc = yaml.load(fs.readFileSync(REGISTRY_YAML, 'utf8')) || {}
    _cache = { models: doc.models || [], tiers: doc.degradation_tiers || [] }
  } catch {
    _cache = { models: [], tiers: [] }
  }
  return _cache
}

/**
 * 降级决策纯函数。
 * @param {object} opts
 * @param {'ok'|'degraded'} [opts.health='ok'] 主模型健康状态
 * @param {boolean} [opts.budgetExceeded=false] 会话预算是否耗尽
 * @param {string|null} [opts.lastError=null] 主模型上次错误（429/5xx/timeout 等）
 * @param {'online'|'fallback'|'offline'|null} [opts.preferTier=null] 显式指定档位（如离线演练）
 * @returns {{tier:string, model:string|null, reason:string, fallbackFrom:string|null}}
 */
export function decideRoute({
  health = 'ok',
  budgetExceeded = false,
  lastError = null,
  preferTier = null,
} = {}) {
  const { models } = loadModelCatalog()

  if (preferTier === 'offline') {
    const offline = models.find((m) => m.tier === 'offline')
    return { tier: 'offline', model: offline ? offline.id : null, reason: 'explicit-offline', fallbackFrom: null }
  }

  const primary = models.find((m) => m.tier === 'primary') || models[0]
  if (health === 'ok' && !budgetExceeded) {
    return { tier: 'online', model: primary ? primary.id : null, reason: 'primary-available', fallbackFrom: null }
  }

  // 主模型不可用或预算耗尽 → 切到次高优先级 fallback
  const candidates = models
    .filter((m) => m.tier === 'primary' || m.tier === 'fallback')
    .filter((m) => m.tier !== 'primary')
    .sort((a, b) => (a.priority || 99) - (b.priority || 99))
  if (candidates.length) {
    return {
      tier: 'fallback',
      model: candidates[0].id,
      reason: budgetExceeded ? 'budget-exceeded' : lastError || 'primary-unavailable',
      fallbackFrom: 'primary',
    }
  }

  // 全远程不可达 → offline（本地 Ollama 或纯确定性工具面）
  const offline = models.find((m) => m.tier === 'offline')
  return {
    tier: 'offline',
    model: offline ? offline.id : null,
    reason: 'all-remote-unavailable',
    fallbackFrom: 'fallback',
  }
}
