/**
 * allin-console · 渲染层
 *
 * P0：列出项目 / 搜索 / 调 `info` 看 JSON
 * P1：启停（走 @allin/core）+ 运行态轮询
 * P3：治理面板常驻带（门禁红项 / 端口占用 / registry 审计）
 *
 * 没有 Node 权限，全部能力经 window.allin（preload 白名单）。
 */

const state = {
  items: [],
  filtered: [],
  selected: null,
  runningIds: new Set(),
  busy: false,
  panels: [],
}

const $ = (id) => document.getElementById(id)
const listEl = $('list')
const detailEl = $('detail')
const statsEl = $('stats')
const statusEl = $('status')
const noteEl = $('registry-note')
const searchEl = $('search')

function setStatus(text) {
  statusEl.textContent = text
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ))
}

function isRunning(id) {
  return state.runningIds.has(id)
}

function applyFilterCounts() {
  const infoCount = state.filtered.filter((x) => x.hasInfo).length
  const runningCount = state.items.filter((x) => isRunning(x.id)).length
  statsEl.textContent = `${state.filtered.length} / ${state.items.length} 项 · `
    + `${infoCount} 个有 info · ${runningCount} 个在跑`
}

function renderList() {
  if (!state.filtered.length) {
    listEl.innerHTML = '<div class="empty" style="margin-top:40px"><p class="empty-hint">没有匹配的项目</p></div>'
    return
  }
  const frag = document.createDocumentFragment()
  for (const it of state.filtered) {
    const row = document.createElement('div')
    const running = isRunning(it.id)
    row.className = 'item'
      + (state.selected?.id === it.id ? ' active' : '')
      + (it.valid ? '' : ' invalid')
    row.dataset.id = it.id
    row.innerHTML = `
      <span class="item-id">${running ? '<span class="dot-run"></span>' : ''}${esc(it.id)}</span>
      <span class="item-badges">
        ${it.hasInfo ? '<span class="badge cli">info</span>' : (it.hasCli ? '<span class="badge">cli</span>' : '')}
      </span>
      <span class="item-name">${esc(it.name)} · ${esc(it.category)}</span>
    `
    row.addEventListener('click', () => selectProject(it.id))
    frag.appendChild(row)
  }
  listEl.innerHTML = ''
  listEl.appendChild(frag)
}

function applyFilter() {
  const q = searchEl.value.trim().toLowerCase()
  state.filtered = q
    ? state.items.filter((it) =>
        it.id.toLowerCase().includes(q) ||
        (it.name || '').toLowerCase().includes(q) ||
        (it.category || '').toLowerCase().includes(q))
    : state.items
  renderList()
  applyFilterCounts()
}

function renderDetail() {
  const it = state.selected
  if (!it) {
    detailEl.innerHTML = `
      <div class="empty">
        <p class="empty-title">从左侧选一个项目</p>
        <p class="empty-hint">点卡片看详情；启停走 <code>@allin/core</code>，与 CLI / 门户共享同一份进程状态。</p>
      </div>`
    return
  }

  const running = isRunning(it.id)

  detailEl.innerHTML = `
    <h1>${esc(it.name)}</h1>
    <div class="sub">${esc(it.id)} · ${esc(it.category)}${it.version ? ' · v' + esc(it.version) : ''}
      ${running ? '<span class="pill-run">运行中</span>' : ''}</div>
    ${it.valid ? '' : '<div class="notice">该登记项校验未通过（见 registry problems），可读但可能不可用。</div>'}
    ${it.hasInfo ? '' : '<div class="notice">' + (it.hasCli
      ? '该项目有 CLI 但未实现 <code>info</code> 子命令（属早期 CLI 形态），console 暂不可调用。'
      : '该项目尚未提供 <code>cli.py</code> / <code>cli.mjs</code>（SPEC-205 §C1 B3 批次待补）。') + '</div>'}
    <dl class="kv">
      <dt>路径</dt><dd>${esc(it.path || '（无法解析）')}</dd>
      <dt>启动命令</dt><dd>${esc(it.launchCommand || '—')}</dd>
      <dt>自检命令</dt><dd>${esc(it.verifyCommand || '—')}</dd>
    </dl>
    <div class="actions">
      ${running
        ? '<button id="btn-stop" class="danger">停止</button>'
        : `<button id="btn-start" ${it.valid ? '' : 'disabled'}>启动</button>`}
      <button class="primary" id="btn-info" ${it.hasInfo ? '' : 'disabled'}>跑 info（JSON）</button>
      <button id="btn-version" ${it.hasInfo ? '' : 'disabled'}>version</button>
      <button id="btn-selfcheck" ${it.hasInfo ? '' : 'disabled'}>selfcheck</button>
      <button id="btn-logs">日志</button>
    </div>
    <div id="out"></div>
  `

  $('btn-start')?.addEventListener('click', () => startSelected())
  $('btn-stop')?.addEventListener('click', () => stopSelected())
  $('btn-info')?.addEventListener('click', () => runAndShow('info'))
  $('btn-version')?.addEventListener('click', () => runAndShow('version'))
  $('btn-selfcheck')?.addEventListener('click', () => runAndShow('selfcheck'))
  $('btn-logs')?.addEventListener('click', () => showLogs())
}

/** 展示 tasks.log 里该项目的最近记录（只读，来自 @allin/core） */
async function showLogs() {
  const it = state.selected
  if (!it || state.busy) return
  setStatus(`读取 ${it.id} 的任务日志 …`)
  try {
    const r = await window.allin.logs(it.id, 60)
    const out = $('out')
    if (!out) return
    if (!r.ok) {
      out.innerHTML = `<div class="out-head"><span class="dot bad"></span><span>日志读取失败</span></div>
        <pre class="out">${esc(r.message || '')}</pre>`
      return
    }
    if (!r.entries.length) {
      out.innerHTML = `<div class="out-head"><span class="dot"></span><span>暂无日志</span></div>
        <pre class="out">${esc(r.missing
          ? `tasks.log 尚未生成（${r.path}）\n启动或停止过项目后才会产生记录。`
          : '该项目还没有启停记录。')}</pre>`
      return
    }
    const text = r.entries.map((e) => {
      const t = (e.ts || '').replace('T', ' ').slice(0, 19)
      const parts = [t, (e.action || '?').padEnd(6), `seq=${e.seq ?? '-'}`]
      if (e.exit_code !== undefined) parts.push(`exit=${e.exit_code}`)
      if (e.duration_ms !== undefined) parts.push(`${e.duration_ms}ms`)
      if (e.error) parts.push(`error=${e.error}`)
      if (e.command) parts.push(`cmd=${e.command}`)
      return parts.join('  ')
    }).join('\n')
    out.innerHTML = `<div class="out-head"><span class="dot ok"></span>
      <span>任务日志 · ${r.entries.length} 条 · ${esc(r.path)}</span></div>
      <pre class="out">${esc(text)}</pre>`
    setStatus(`${it.id} · 日志 ${r.entries.length} 条`)
  } catch (e) {
    setStatus(`日志异常：${e}`)
  }
}

function renderOutput({ subcommand, result }) {
  const out = $('out')
  if (!out) return
  const ok = result.ok
  const head = `
    <div class="out-head">
      <span class="dot ${ok ? 'ok' : 'bad'}"></span>
      <span>${esc(subcommand)} · 退出码 ${result.code ?? '—'} · ${result.durationMs ?? 0} ms</span>
    </div>`

  let body
  if (subcommand === 'info' && result.json) {
    body = `<pre class="out">${esc(JSON.stringify(result.json, null, 2))}</pre>`
  } else if (result.stdout || result.stderr) {
    body = `<pre class="out">${esc((result.stdout || '') + (result.stderr ? '\n--- stderr ---\n' + result.stderr : ''))}</pre>`
  } else {
    body = `<pre class="out">${esc(result.summary || result.message || '（无输出）')}</pre>`
  }
  out.innerHTML = head + body
}

function lockUi(lock) {
  state.busy = lock
  detailEl.querySelectorAll('button').forEach((b) => { b.disabled = lock })
}

async function runAndShow(subcommand) {
  const it = state.selected
  if (!it || state.busy) return
  lockUi(true)
  setStatus(`执行 ${it.id} · ${subcommand} …`)
  try {
    const result = await window.allin.runCli(it.id, subcommand)
    renderOutput({ subcommand, result })
    setStatus(result.ok
      ? `${it.id} · ${subcommand} 完成（${result.durationMs} ms）`
      : `${it.id} · ${subcommand} 失败：${result.summary || result.reason || '未知'}`)
  } catch (e) {
    renderOutput({ subcommand, result: { ok: false, code: null, durationMs: 0, summary: String(e) } })
    setStatus(`调用异常：${e}`)
  } finally {
    // 只解禁按钮，**不要重建详情区** —— renderDetail() 会连同 #out 一起重建，
    // 刚渲染出来的 JSON 会当场消失（2026-11-22 冒烟抓到的回归）。
    lockUi(false)
  }
}

async function startSelected() {
  const it = state.selected
  if (!it || state.busy) return
  lockUi(true)
  setStatus(`启动 ${it.id} …`)
  try {
    const r = await window.allin.start(it.id)
    setStatus(r.ok
      ? `${it.id} 已启动${r.pid ? `（pid ${r.pid}）` : ''}`
      : `${it.id} 启动失败：${r.message || r.reason || '未知'}`)
    await refreshRunning(true)
  } catch (e) {
    setStatus(`启动异常：${e}`)
  } finally {
    lockUi(false)
    renderDetail()
    renderList()
    applyFilterCounts()
  }
}

async function stopSelected() {
  const it = state.selected
  if (!it || state.busy) return
  lockUi(true)
  setStatus(`停止 ${it.id} …`)
  try {
    const r = await window.allin.stop(it.id)
    setStatus(r.ok ? `${it.id} 已停止` : `${it.id} 停止失败：${r.message || r.reason || '未知'}`)
    await refreshRunning(true)
  } catch (e) {
    setStatus(`停止异常：${e}`)
  } finally {
    lockUi(false)
    renderDetail()
    renderList()
    applyFilterCounts()
  }
}

async function refreshRunning(force = false) {
  try {
    const { ids } = await window.allin.runningIds()
    const next = new Set(ids || [])
    const prev = state.runningIds
    let changed = force || next.size !== prev.size
    if (!changed) {
      for (const id of next) if (!prev.has(id)) { changed = true; break }
    }
    // 详情区只在「当前选中项的运行态真的变了」时重建 —— 否则每次轮询都会
    // 抹掉用户正在看的 CLI 输出。
    const sel = state.selected
    const selChanged = Boolean(sel) && prev.has(sel.id) !== next.has(sel.id)
    state.runningIds = next
    if (changed) {
      renderList()
      applyFilterCounts()
    }
    if (selChanged) renderDetail()
  } catch {
    /* 轮询失败不打断 UI */
  }
}

function selectProject(id) {
  const it = state.items.find((x) => x.id === id)
  if (!it) return
  state.selected = it
  renderList()
  renderDetail()
}

async function boot() {
  setStatus('读取 registry …')
  try {
    const data = await window.allin.listProjects()
    state.items = data.items || []
    applyFilter()
    noteEl.textContent = data.problems?.length ? `registry problems: ${data.problems.length}` : ''
    setStatus(`已加载 ${state.items.length} 个项目`)
    await refreshRunning()
    setInterval(refreshRunning, 3000)
    // P3：治理面板常驻带，首次拉取 + 定时刷新（15s：端口状态要新鲜，
    // 门禁留痕与 registry 审计变化很慢，15s 足够且不浪费）
    await refreshGov()
    setInterval(refreshGov, 15000)
  } catch (e) {
    setStatus('加载失败：' + e)
    listEl.innerHTML = `<div class="empty"><p class="empty-hint">${esc(String(e))}</p></div>`
  }
}

searchEl.addEventListener('input', () => { applyFilter() })

/* ---------------- 治理面板常驻带（P3） ---------------- */

/**
 * 渲染治理面板。
 *
 * ⚠ 面板数据来自插件（本地代码，但**不受信任**：插件可能来自用户目录）。
 *   因此一律用 DOM API 建节点 + textContent 赋值，**不拼 innerHTML** ——
 *   渲染层 CSP 虽只允许 'self' 的 script，但 innerHTML 能绕过这层防护注入标记。
 */
function renderGovStrip() {
  const cards = $('gov-cards')
  cards.textContent = ''
  if (!state.panels.length) {
    const d = document.createElement('div')
    d.className = 'gov-loading'
    d.textContent = '没有插件提供治理面板（plugins/ 目录为空或加载失败）'
    cards.appendChild(d)
    return
  }
  for (const p of state.panels) {
    const card = document.createElement('div')
    card.className = `gov-card tone-${p.status || 'dim'}`

    const head = document.createElement('div')
    head.className = 'gov-card-head'
    const dot = document.createElement('span')
    dot.className = 'gov-dot'
    const title = document.createElement('span')
    title.className = 'gov-card-title'
    title.textContent = p.title
    head.append(dot, title)
    if (p.summary) {
      const sum = document.createElement('span')
      sum.className = 'gov-card-sum'
      sum.textContent = p.summary
      head.appendChild(sum)
    }
    card.appendChild(head)

    const rows = Array.isArray(p.rows) ? p.rows : []
    if (rows.length) {
      const list = document.createElement('div')
      list.className = 'gov-rows'
      for (const r of rows) {
        const line = document.createElement('div')
        // 长列表（多端口）允许换行，否则尾部会被裁掉
        line.className = `gov-row tone-${r.tone || 'dim'}`
          + (r.wrap ? ' wrap' : '')
        const l = document.createElement('span')
        l.className = 'gov-row-label'
        l.textContent = r.label ?? ''
        const v = document.createElement('span')
        v.className = 'gov-row-value'
        v.textContent = r.value ?? ''
        line.append(l, v)
        list.appendChild(line)
      }
      card.appendChild(list)
    } else if (p.status === 'error') {
      const err = document.createElement('div')
      err.className = 'gov-rows'
      err.textContent = p.summary || '面板渲染失败'
      card.appendChild(err)
    }
    cards.appendChild(card)
  }
  const ts = $('gov-ts')
  if (ts) {
    const now = new Date()
    ts.textContent = `更新于 ${String(now.getHours()).padStart(2, '0')}:`
      + `${String(now.getMinutes()).padStart(2, '0')}:`
      + `${String(now.getSeconds()).padStart(2, '0')}`
  }
}

/** 拉取治理面板数据。 */
async function refreshGov() {
  try {
    const r = await window.allin.panelData('sidebar')
    state.panels = r.panels || []
    renderGovStrip()
  } catch (e) {
    state.panels = []
    renderGovStrip()
    setStatus('治理面板刷新失败：' + e)
  }
}

$('gov-refresh')?.addEventListener('click', () => {
  setStatus('刷新治理面板 …')
  refreshGov()
})

/* ---------------- 命令面板（插件注册的命令） ---------------- */

const cmdOverlay = $('cmd-overlay')
const cmdListEl = $('cmd-list')
const cmdOutEl = $('cmd-out')

async function openCmdPanel() {
  cmdOverlay.hidden = false
  cmdOutEl.hidden = true
  cmdListEl.innerHTML = '<div class="cmd-empty">加载插件命令…</div>'
  try {
    const st = await window.allin.pluginState()
    const cmds = st.commands || []
    $('cmd-count').textContent = cmds.length ? cmds.length : ''
    if (!cmds.length) {
      cmdListEl.innerHTML = '<div class="cmd-empty">没有插件注册命令（plugins/ 目录为空或加载失败）</div>'
      return
    }
    cmdListEl.innerHTML = ''
    for (const c of cmds) {
      const row = document.createElement('div')
      row.className = 'cmd-item'
      row.innerHTML = `<div class="cmd-title">${esc(c.title)}<span class="cmd-plugin">${esc(c.plugin)}</span></div>
        <div class="cmd-desc">${esc(c.description || c.id)}</div>`
      row.addEventListener('click', () => runCmd(c.id))
      cmdListEl.appendChild(row)
    }
    if (st.errors?.length) {
      const err = document.createElement('div')
      err.className = 'cmd-empty'
      err.textContent = `插件加载失败 ${st.errors.length} 个：` + st.errors.map((e) => e.plugin).join(', ')
      cmdListEl.appendChild(err)
    }
  } catch (e) {
    cmdListEl.innerHTML = `<div class="cmd-empty">读取插件状态失败：${esc(String(e))}</div>`
  }
}

async function runCmd(id) {
  cmdOutEl.hidden = false
  cmdOutEl.textContent = `执行 ${id} …`
  setStatus(`插件命令 ${id} …`)
  try {
    const r = await window.allin.runPluginCommand(id)
    const head = r.ok ? `✓ ${r.summary || '完成'}` : `✗ ${r.summary || r.message || '失败'}`
    const detail = r.detail ? '\n\n' + JSON.stringify(r.detail, null, 2) : ''
    cmdOutEl.textContent = `${head}（${r.durationMs ?? 0} ms）${detail}`
    setStatus(`${id} ${r.ok ? '完成' : '未通过'}（${r.durationMs ?? 0} ms）`)
  } catch (e) {
    cmdOutEl.textContent = `调用异常：${e}`
    setStatus(`插件命令异常：${e}`)
  }
}

$('btn-cmd')?.addEventListener('click', openCmdPanel)
$('cmd-close')?.addEventListener('click', () => { cmdOverlay.hidden = true })
cmdOverlay?.addEventListener('click', (e) => {
  if (e.target === cmdOverlay) cmdOverlay.hidden = true
})
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && cmdOverlay && !cmdOverlay.hidden) cmdOverlay.hidden = true
})

boot()
