/**
 * @allin/cordis-js —— console 的插件宿主（SPEC-205 §C2）
 *
 * 为什么是 JS 版重写而不是桥接 Python cordis：
 *   `vendor/cordis` 是 cordis-py 4.0.0，跑在 Python 里，无法参与 Electron 主进程的
 *   界面生命周期。而插件价值恰恰在于「能往 UI 加面板、加命令、挂钩子」——桥接做不到。
 *   治理事实查询仍桥接 kernel（只读 CLI），两者职责不重叠。
 *
 * 只开三个扩展点，**不扩**：
 *   · console.command  命令面板里的可执行项
 *   · console.panel    UI 插槽
 *   · ctx.on(event)    生命周期钩子（project:started / project:exited / cli:error）
 *
 * 纪律：
 *   · 插件抛异常**不阻断**启动，降级为「不可用」条目（SPEC §C2.3）
 *   · 插件不得自行 spawn —— CLI 调用一律经宿主注入的 runner
 */
import { Context } from '@cordisjs/core'

/** 插件可以钩的事件名白名单。 */
export const HOOK_EVENTS = [
  'project:started',
  'project:stopped',
  'project:exited',
  'cli:error',
]

/** UI 插槽白名单。 */
export const PANEL_SLOTS = ['sidebar', 'tab', 'statusbar', 'detail']

/**
 * 创建一个插件宿主。
 *
 * @param {object} [opts]
 * @param {(level: string, msg: string) => void} [opts.logger]
 * @param {object} [opts.deps] 注入给插件的受控依赖（**唯一**的能力来源）。
 *   约定只放：`core`（@allin/core 的只读/启停能力）、`runCli`（CLI 总线）、
 *   `registry`（项目清单）。插件不得自行 require electron / fs / child_process。
 * @returns {{ctx: Context, commands: object[], panels: object[], errors: object[],
 *            load: (plugins: object[]) => Promise<object[]>, emit: (event: string, payload?: any) => void}}
 */
export function createHost({ logger = () => {}, deps = {} } = {}) {
  const ctx = new Context()

  /** @type {object[]} */
  const commands = []
  /** @type {object[]} */
  const panels = []
  /** @type {object[]} */
  const errors = []

  // 宿主能力：直接挂属性（实测无 cordis 的 inject 警告，且插件内可读）
  const consoleApi = {
    /** 注册一个命令面板条目 */
    command(def) {
      if (!def || typeof def.id !== 'string' || typeof def.run !== 'function') {
        throw new Error('console.command 需要 { id: string, title?: string, run: Function }')
      }
      if (commands.some((c) => c.id === def.id)) {
        throw new Error(`命令 id 重复：${def.id}`)
      }
      commands.push({
        id: def.id,
        title: def.title || def.id,
        description: def.description || '',
        plugin: def.plugin || '',
        run: def.run,
      })
      logger('info', `注册命令 ${def.id}`)
    },

    /**
     * 注册一个 UI 面板。
     *
     * 两种形态（P3 起）：
     *   ① 动态面板（常驻治理视图用）：`render: async () => ({ status, summary, rows })`
     *      —— 返回**结构化数据**，由渲染层自己画。不用 HTML 字符串，避免插件注入
     *      任意标记（渲染层 CSP 只允许 'self' 的 script，HTML 字符串会绕过这层防护）。
     *   ② 静态面板：`html: '<p>…</p>'` —— 一次性文本，保留兼容。
     */
    panel(def) {
      if (!def || typeof def.id !== 'string') {
        throw new Error('console.panel 需要 { id: string, slot: string, ... }')
      }
      if (!PANEL_SLOTS.includes(def.slot)) {
        throw new Error(`未知插槽 ${def.slot}，允许：${PANEL_SLOTS.join('/')}`)
      }
      const hasRender = typeof def.render === 'function'
      if (!hasRender && typeof def.html !== 'string') {
        throw new Error(`面板 ${def.id} 需要 render() 或 html 之一`)
      }
      panels.push({
        id: def.id,
        slot: def.slot,
        title: def.title || def.id,
        html: def.html || '',
        render: hasRender ? def.render : null,
        plugin: def.plugin || '',
      })
      logger('info', `注册面板 ${def.id}@${def.slot}`)
    },

    /** 只读事件订阅（白名单之外的事件名直接抛错，防止插件自造协议） */
    on(event, handler) {
      if (!HOOK_EVENTS.includes(event)) {
        throw new Error(`未支持的事件 ${event}，允许：${HOOK_EVENTS.join('/')}`)
      }
      return ctx.on(event, handler)
    },
  }

  ctx.console = consoleApi
  // 受控依赖：插件只能从这里拿能力，拿不到 electron / fs / spawn
  ctx.deps = Object.freeze({ ...deps })

  /**
   * 加载插件数组。单个插件失败只记录，不影响其他插件与宿主。
   * @param {object[]} plugins 每个形如 { name, inject?, apply(ctx, config?), config? }
   */
  async function load(plugins = []) {
    const loaded = []
    for (const p of plugins) {
      const name = p?.name || '(未命名插件)'
      try {
        if (typeof p?.apply !== 'function') {
          throw new Error('插件必须导出 apply(ctx, config)')
        }
        ctx.plugin({
          name,
          // 不传 inject：cordis 的 inject 会**挂起插件**直到该服务被 provide，
          // 而宿主是把能力直接挂在 ctx 上（非 Service），一旦声明 inject 就永远
          // 等不到 ⇒ 插件加载成功但 apply 从不执行（实测 2 个插件、0 个命令）。
          apply: p.apply,
          config: p.config,
        })
        loaded.push(name)
        logger('info', `插件已加载：${name}`)
      } catch (e) {
        // 降级：记下来，继续加载下一个
        errors.push({ plugin: name, error: e?.message || String(e) })
        logger('warn', `插件加载失败：${name} —— ${e?.message || e}`)
      }
    }
    return loaded
  }

  function emit(event, payload) {
    if (!HOOK_EVENTS.includes(event)) return
    try {
      ctx.emit(event, payload)
    } catch (e) {
      logger('warn', `钩子 ${event} 抛错：${e?.message || e}`)
    }
  }

  return { ctx, commands, panels, errors, load, emit }
}
