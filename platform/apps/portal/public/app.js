// allin-platform 前台逻辑：库/工坊/引擎三页签。
const $ = (sel) => document.querySelector(sel)

async function api(path, options) {
  const res = await fetch(path, options)
  return res.json()
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
}

let currentGameplay = 'all'

async function renderLibrary() {
  const data = await api('/api/library')
  const box = $('#library')
  const prob = $('#problems')
  prob.textContent = data.problems.length ? '清单校验问题:\n' + data.problems.join('\n') : ''
  prob.style.display = data.problems.length ? 'block' : 'none'

  // 玩法筛选 chips（受控枚举动态收集）
  const counts = new Map()
  for (const it of data.items) {
    for (const g of it.gameplay || []) counts.set(g, (counts.get(g) || 0) + 1)
  }
  const chipNames = [...counts.keys()].sort()
  if (!counts.has(currentGameplay)) currentGameplay = 'all'
  const chipsHtml = [`<button class="chip ${currentGameplay === 'all' ? 'active' : ''}" data-gp="all">全部 (${data.items.length})</button>`]
    .concat(chipNames.map(g => `<button class="chip ${currentGameplay === g ? 'active' : ''}" data-gp="${esc(g)}">${esc(g)} (${counts.get(g)})</button>`))
    .join('')
  $('#chips').innerHTML = chipsHtml

  let items = currentGameplay === 'all'
    ? data.items
    : data.items.filter(it => (it.gameplay || []).includes(currentGameplay))

  // 玩法子视图：同玩法内按 order 排序 + 族谱条（note 展示代际/特色）
  const ordered = items.filter(it => it.order !== null && it.order !== undefined)
  if (ordered.length) {
    items = [...items].sort((a, b) => ((a.order ?? 999) - (b.order ?? 999)))
  }
  const lineage = ordered.map(it =>
    `<div class="lineage-item"><span class="badge gp">#${it.order}</span> <strong>${esc(it.name)}</strong>${it.note ? `<span class="sub"> — ${esc(it.note)}</span>` : ''}</div>`
  ).join('')
  $('#lineage').innerHTML = lineage ? `<div class="lineage"><div class="lineage-title">玩法子视图（代际排序）</div>${lineage}</div>` : ''
  $('#lineage').style.display = lineage ? 'block' : 'none'

  box.innerHTML = items.map((it) => {
    const status = it.running ? '<span class="badge on">运行中</span>' : '<span class="badge off">未运行</span>'
    const bad = it.valid ? '' : '<span class="badge bad">校验失败</span>'
    const gps = (it.gameplay || []).map(g => `<span class="badge gp">${esc(g)}</span>`).join('')
    const ord = it.order ? ` <span class="badge">#${esc(it.order)}</span>` : ''
    const note = it.note ? `<div class="meta">${esc(it.note)}</div>` : ''
    const panel = it.port ? `<a class="badge" href="http://localhost:${it.port}" target="_blank">面板 :${it.port}</a>` : ''
    const disable = it.valid ? '' : 'disabled'
    return `
      <div class="card">
        <h3>${esc(it.name)}${ord} <span class="badge">${esc(it.category)}</span></h3>
        <div class="meta">${esc(it.id)} · v${esc(it.version)} · ${it.manual ? '手动型' : '自动型'}</div>
        ${note}
        <div>${status}${bad}${gps}${panel}</div>
        <div class="row">
          <button class="act" data-act="start" data-id="${esc(it.id)}" ${disable}>启动</button>
          <button class="act" data-act="stop" data-id="${esc(it.id)}" ${disable}>停止</button>
        </div>
      </div>`
  }).join('')
}

async function renderWorkshop() {
  const data = await api('/api/workshop')
  const box = $('#workshop')
  box.innerHTML = data.catalog.map((it) => {
    let btns
    if (!it.subscribed) {
      btns = `<button class="act" data-sub="subscribe" data-id="${esc(it.id)}">订阅</button>`
    } else {
      btns = `
        <button class="act" data-sub="update" data-id="${esc(it.id)}">更新</button>
        <button class="act" data-sub="rollback" data-id="${esc(it.id)}">回滚</button>
        <button class="act" data-sub="unsubscribe" data-id="${esc(it.id)}">取消订阅</button>`
    }
    const up = it.updateAvailable ? '<span class="badge on">有更新</span>' : ''
    const commit = it.commit ? esc(it.commit.slice(0, 8)) : '无记录'
    return `
      <div class="item">
        <div class="info">
          <strong>${esc(it.name)}</strong> ${up}
          <div class="sub">${esc(it.repo)}${it.branch !== 'master' ? ' #' + esc(it.branch) : ''} · v${esc(it.version)} · 提交 ${commit}${it.subscribedAt ? ' · 订阅于 ' + esc(it.subscribedAt.slice(0, 10)) : ''}</div>
        </div>
        ${btns}
      </div>`
  }).join('') || '<div class="item">暂无发布面（注册表中没有 publish.repo 的项目）</div>'
}

async function renderAudit() {
  const data = await api('/api/workshop/audit')
  const box = $('#audit')
  const lines = (data.audit || []).map(a => `${a.ts || ''} ${a.project || ''} ${a.action || ''}`).join('\n')
  box.textContent = lines || '暂无工坊操作流水'
  box.style.display = 'block'
}

async function renderEngine() {
  const box = $('#engine')
  box.innerHTML = '<pre>加载 alloy 装配视图 …</pre>'
  const data = await api('/api/engine')
  if (!data.ok) {
    box.innerHTML = `<pre>${esc(data.error || '未知错误')}</pre>`
    return
  }
  const p = data.profile
  const services = Object.entries(p.services || {}).map(([k, v]) =>
    `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')
  const deps = Object.entries(p.optional_deps || {}).map(([k, v]) =>
    `<span class="badge ${v.includes('OK') ? 'on' : 'off'}">${esc(k)} ${esc(v)}</span>`).join(' ')
  const presets = (data.presets || []).map(x => `<span class="badge">${esc(x)}</span>`).join(' ')
  box.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <h3>装配档案：${esc(p.profile)}</h3>
      <div class="meta">插件：${esc((p.plugins || []).join(' · '))}</div>
      <div class="meta" style="margin-top:6px">预设库：${presets || '无'}</div>
    </div>
    <div class="card" style="margin-bottom:14px">
      <h3>已注册服务</h3>
      <table class="svc"><tr><th>key</th><th>类型</th></tr>${services}</table>
    </div>
    <div class="card" style="margin-bottom:14px">
      <h3>可选依赖</h3>
      <div style="margin-top:6px">${deps || '无'}</div>
    </div>
    <details><summary>原始 JSON（dump-profile --json）</summary>
      <pre>${esc(JSON.stringify(data, null, 2))}</pre>
    </details>`
}

async function refresh() {
  try {
    const st = await api('/api/status')
    $('#uptime').textContent = `平台在线 ${Math.round(st.uptime)}s`
  } catch { /* 平台本身不可达时忽略 */ }
  if ($('#tab-library').classList.contains('active')) await renderLibrary()
}

// 页签切换
for (const btn of document.querySelectorAll('.tab')) {
  btn.addEventListener('click', async () => {
    for (const b of document.querySelectorAll('.tab')) b.classList.toggle('active', b === btn)
    for (const p of document.querySelectorAll('.panel')) p.classList.toggle('active', p.id === 'tab-' + btn.dataset.tab)
    if (btn.dataset.tab === 'library') await renderLibrary()
    if (btn.dataset.tab === 'workshop') await renderWorkshop()
    if (btn.dataset.tab === 'engine') await renderEngine()
  })
}

// 事件委托：启动/停止/订阅/取消
for (const box of [$('#library'), $('#workshop')]) {
  box.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('button[data-act], button[data-sub]')
    if (!btn) return
    const id = btn.dataset.id
    if (btn.dataset.act === 'start') { await api(`/api/library/${id}/start`, { method: 'POST' }) }
    if (btn.dataset.act === 'stop') { await api(`/api/library/${id}/stop`, { method: 'POST' }) }
    if (btn.dataset.sub === 'subscribe') { await api(`/api/workshop/${id}/subscribe`, { method: 'POST' }) }
    if (btn.dataset.sub === 'unsubscribe') { await api(`/api/workshop/${id}/unsubscribe`, { method: 'POST' }) }
    if (btn.dataset.sub === 'update') { await api(`/api/workshop/${id}/update`, { method: 'POST' }) }
    if (btn.dataset.sub === 'rollback') { await api(`/api/workshop/${id}/rollback`, { method: 'POST' }) }
    await refresh()
  })
}

$('#workshop').parentElement.querySelector('[data-audit]').addEventListener('click', renderAudit)

$('#chips').addEventListener('click', (ev) => {
  const chip = ev.target.closest('button[data-gp]')
  if (!chip) return
  currentGameplay = chip.dataset.gp
  renderLibrary()
})

renderLibrary()
setInterval(refresh, 5000)
