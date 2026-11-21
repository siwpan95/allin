/**
 * allin-console · 渲染层（P0）
 *
 * 只做三件事：列出项目、搜索过滤、选中后调 `cli.py info --json`。
 * 没有 Node 权限，全部能力经 window.allin（preload 白名单）。
 */

const state = {
  items: [],
  filtered: [],
  selected: null,
  running: false,
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

function renderList() {
  if (!state.filtered.length) {
    listEl.innerHTML = '<div class="empty" style="margin-top:40px"><p class="empty-hint">没有匹配的项目</p></div>'
    return
  }
  const frag = document.createDocumentFragment()
  for (const it of state.filtered) {
    const row = document.createElement('div')
    row.className = 'item' + (state.selected?.id === it.id ? ' active' : '') + (it.valid ? '' : ' invalid')
    row.dataset.id = it.id
    row.innerHTML = `
      <span class="item-id">${esc(it.id)}</span>
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
  const infoCount = state.filtered.filter((x) => x.hasInfo).length
  statsEl.textContent = `${state.filtered.length} / ${state.items.length} 项 · ${infoCount} 个有 info`
}

function renderDetail() {
  const it = state.selected
  if (!it) {
    detailEl.innerHTML = `
      <div class="empty">
        <p class="empty-title">从左侧选一个项目</p>
        <p class="empty-hint">P0 只做只读：列出登记项目 + 调 <code>cli.py info --json</code>。启停与日志在 P1。</p>
      </div>`
    return
  }

  detailEl.innerHTML = `
    <h1>${esc(it.name)}</h1>
    <div class="sub">${esc(it.id)} · ${esc(it.category)}${it.version ? ' · v' + esc(it.version) : ''}</div>
    ${it.valid ? '' : '<div class="notice">该登记项校验未通过（见 registry problems），可读但可能不可用。</div>'}
    ${it.hasInfo ? '' : '<div class="notice">' + (it.hasCli ? '该项目有 CLI 但未实现 <code>info</code> 子命令（属早期 CLI 形态），console 暂不可调用。' : '该项目尚未提供 <code>cli.py</code> / <code>cli.mjs</code>（SPEC-205 §C1 B3 批次待补）。') + '</div>'}
    <dl class="kv">
      <dt>路径</dt><dd>${esc(it.path || '（无法解析）')}</dd>
      <dt>启动命令</dt><dd>${esc(it.launchCommand || '—')}</dd>
      <dt>自检命令</dt><dd>${esc(it.verifyCommand || '—')}</dd>
    </dl>
    <div class="actions">
      <button class="primary" id="btn-info" ${it.hasInfo ? '' : 'disabled'}>跑 info（JSON）</button>
      <button id="btn-version" ${it.hasInfo ? '' : 'disabled'}>version</button>
      <button id="btn-selfcheck" ${it.hasInfo ? '' : 'disabled'}>selfcheck</button>
    </div>
    <div id="out"></div>
  `

  $('btn-info')?.addEventListener('click', () => runAndShow('info'))
  $('btn-version')?.addEventListener('click', () => runAndShow('version'))
  $('btn-selfcheck')?.addEventListener('click', () => runAndShow('selfcheck'))
}

function renderOutput({ subcommand, result }) {
  const out = $('out')
  if (!out) return
  const ok = result.ok
  const head = `
    <div class="out-head">
      <span class="dot ${ok ? 'ok' : 'bad'}"></span>
      <span>${esc(subcommand)} · 退出码 ${result.code ?? '—'} · ${result.durationMs} ms</span>
    </div>`

  let body
  if (subcommand === 'info' && result.json) {
    body = `<pre class="out">${esc(JSON.stringify(result.json, null, 2))}</pre>`
  } else if (result.stdout || result.stderr) {
    body = `<pre class="out">${esc((result.stdout || '') + (result.stderr ? '\n--- stderr ---\n' + result.stderr : ''))}</pre>`
  } else {
    body = `<pre class="out">${esc(result.summary || '（无输出）')}</pre>`
  }
  out.innerHTML = head + body
}

async function runAndShow(subcommand) {
  const it = state.selected
  if (!it || state.running) return
  state.running = true
  const buttons = detailEl.querySelectorAll('button')
  buttons.forEach((b) => { b.disabled = true })
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
    state.running = false
    buttons.forEach((b) => {
      if (!state.selected?.hasInfo) return
      b.disabled = false
    })
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
    noteEl.textContent = data.problems?.length
      ? `registry problems: ${data.problems.length}`
      : ''
    setStatus(`已加载 ${state.items.length} 个项目`)
  } catch (e) {
    setStatus('加载失败：' + e)
    listEl.innerHTML = `<div class="empty"><p class="empty-hint">${esc(String(e))}</p></div>`
  }
}

searchEl.addEventListener('input', applyFilter)
boot()
