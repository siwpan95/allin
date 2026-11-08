/* allin 官网 · 治理看板前端逻辑（无框架、无依赖、IIFE，风格对齐 main.js）
   职责：
     1) 首帧 fetch 填充 SSR 骨架卡片（overview 5s / orchestration 30s / entries 30s[admin]）
     2) 轮询纪律：单飞锁、页面不可见暂停、连续 3 次失败退避 15s、成功复位
     3) 降级三态渲染：PORTAL_UNREACHABLE「平台未启动」/ UPSTREAM_TIMEOUT 快照+时间戳 / PORTAL_FORBIDDEN 报警
     4) 编排卡三态：门禁自身故障 / 全绿 / 判出漂移（severity:error 进清单，warn 只计数）
     5) 写操作（admin）：两段式确认 + 防重复提交 + X-CSRF-Token 头（表单隐藏域兜底）
*/

(function () {
  'use strict';

  var cfgEl = document.getElementById('gov-config');
  if (!cfgEl) return; // 非治理页直接退出

  var CFG = {
    csrf: cfgEl.getAttribute('data-csrf') || '',
    admin: cfgEl.getAttribute('data-admin') === '1',
    apiOverview: cfgEl.getAttribute('data-api-overview') || '/member/api/governance/overview',
    apiOrchestration: cfgEl.getAttribute('data-api-orchestration') || '/member/api/governance/orchestration',
    apiEntries: cfgEl.getAttribute('data-api-entries') || '/member/api/governance/entries',
  };

  var OVERVIEW_INTERVAL = 5000;
  var ORCH_INTERVAL = 30000;
  var ENTRIES_INTERVAL = 30000;
  var BACKOFF_INTERVAL = 15000;
  var BACKOFF_AFTER = 3; // 连续失败次数达到后进入退避

  // ---------- 工具 ----------

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fmtClock(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    return isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('zh-CN', { hour12: false });
  }

  function fmtUptime(sec) {
    var n = Number(sec);
    if (!isFinite(n) || n < 0) return '—';
    if (n < 60) return Math.round(n) + ' 秒';
    var m = Math.floor(n / 60);
    if (m < 60) return m + ' 分钟';
    var h = Math.floor(m / 60);
    if (h < 24) return h + ' 小时 ' + (m % 60) + ' 分';
    return Math.floor(h / 24) + ' 天 ' + (h % 24) + ' 小时';
  }

  function pillHtml(state, icon, label, title) {
    return '<span class="tag tag--' + esc(state) + ' gov-pill" role="status"' +
      (title ? ' title="' + esc(title) + '"' : '') + '>' +
      '<span class="gov-pill__icon" aria-hidden="true">' + esc(icon) + '</span>' +
      '<span>' + esc(label) + '</span></span>';
  }

  function noticeHtml(kind, text) {
    return '<div class="notice notice--' + esc(kind) + '" role="status">' +
      '<span aria-hidden="true">▍</span><span>' + esc(text) + '</span></div>';
  }

  function kvHtml(rows) {
    // 默认对每格 esc()（防服务端数据 XSS，WJ-02 整改）；仅当某格显式传 {html: '...'}
    // （构建期常量、无服务端/用户数据）才按受信 HTML 原样输出，杜绝静默假绿。
    return '<dl class="kv">' + rows.map(function (r) {
      var k = (r[0] && r[0].html != null) ? r[0].html : esc(r[0]);
      var v = (r[1] && r[1].html != null) ? r[1].html : esc(r[1]);
      return '<dt>' + k + '</dt><dd>' + v + '</dd>';
    }).join('') + '</dl>';
  }

  function setCard(name, pill, bannerHtml, bodyHtml) {
    var pillEl = $('gov-pill-' + name);
    var bannerEl = $('gov-banner-' + name);
    var bodyEl = $('gov-body-' + name);
    if (pillEl) pillEl.innerHTML = pill;
    if (bannerEl) bannerEl.innerHTML = bannerHtml || '';
    if (bodyEl) {
      bodyEl.innerHTML = bodyHtml;
      bodyEl.setAttribute('aria-busy', 'false');
    }
  }

  var inlineTimer = null;
  function showInline(kind, text) {
    var el = $('gov-inline');
    if (!el) return;
    el.innerHTML = noticeHtml(kind, text);
    if (inlineTimer) clearTimeout(inlineTimer);
    inlineTimer = setTimeout(function () { el.innerHTML = ''; }, 8000);
  }

  function showFatal(text) {
    showInline('error', text);
  }

  // ---------- 降级三态公共渲染 ----------

  function renderStale(payload) {
    var el = $('gov-stale');
    if (!el) return;
    var dg = payload && payload.degraded;
    if (dg && dg.code === 'PORTAL_UNREACHABLE') {
      el.innerHTML = pillHtml('warn', '▲', '平台未启动', dg.message);
    } else if (dg && dg.code === 'PORTAL_FORBIDDEN') {
      el.innerHTML = pillHtml('error', '×', '围栏报警', dg.message);
    } else if (dg && dg.code === 'UPSTREAM_TIMEOUT') {
      el.innerHTML = pillHtml('info', '◷', '数据截至 ' + fmtClock(payload.snapshotAt) + '（快照）', dg.message);
    } else if (payload && payload.snapshotAt) {
      el.innerHTML = pillHtml('info', '◷', '数据截至 ' + fmtClock(payload.snapshotAt));
    }
  }

  /** 概览/门禁/编排/项目四类卡共用的"上游整体不可用"渲染。 */
  function renderDegrade(name, payload) {
    var code = payload.degraded.code;
    if (code === 'PORTAL_FORBIDDEN') {
      setCard(name, pillHtml('error', '×', '故障'),
        noticeHtml('error', payload.degraded.message),
        '<p class="muted" style="margin:0">回环围栏校验失败属于 fail-loud 安全事件，请检查 platform 配置。</p>');
      return;
    }
    // PORTAL_UNREACHABLE / UPSTREAM_TIMEOUT（无快照时）
    setCard(name, pillHtml('warn', '▲', '未连接'),
      noticeHtml('warn', payload.degraded.message),
      '<p class="muted" style="margin:0">治理面（portal）当前离线；恢复后本卡会在下个轮询周期自动刷新，站点其他功能不受影响。</p>');
  }

  // ---------- 卡片渲染 ----------

  function renderOverview(payload) {
    renderStale(payload);
    if (payload.degraded && !payload.data) return renderDegrade('overview', payload);
    var d = payload.data || {};
    var p = d.portal || {};
    var lib = d.library || {};
    var rows = [
      ['版本', p.version || '—'],
      ['运行时长', fmtUptime(p.uptime)],
      ['端口', p.port == null ? '—' : p.port],
      ['登记项目', lib.total == null ? '不可读' : lib.total + ' 个'],
      ['运行中', lib.running == null ? '—' : lib.running + ' 个'],
      ['异常登记', lib.invalid == null ? '—' : lib.invalid + ' 个'],
    ];
    setCard('overview', pillHtml('ok', '●', '正常'),
      payload.degraded ? noticeHtml('info', '网络波动，数据截至 ' + fmtClock(payload.snapshotAt) + '（快照）') : '',
      kvHtml(rows));
  }

  function renderGate(payload) {
    if (payload.degraded && !payload.data) return renderDegrade('gate', payload);
    var g = payload.data && payload.data.gates;
    if (!g) {
      setCard('gate', pillHtml('warn', '▲', '不可读'), '',
        '<p class="muted" style="margin:0">门禁摘要暂不可读（等待治理桥接端点提供 gate 维度；kernel 门禁留痕本身不受影响）。</p>');
      return;
    }
    var state, icon, label;
    if (g.escapeRate && Number(g.escapeRate) > 0) {
      state = 'warn'; icon = '▲'; label = '降级';
    } else if (!g.lastOkAt) {
      state = 'warn'; icon = '▲'; label = '未运行';
    } else {
      state = 'ok'; icon = '●'; label = '门禁健康';
    }
    setCard('gate', pillHtml(state, icon, label), '',
      kvHtml([
        ['最近运行', fmtClock(g.lastRunAt)],
        ['最近通过', fmtClock(g.lastOkAt)],
        ['逃逸率', g.escapeRate == null ? '—' : g.escapeRate],
      ]));
  }

  function driftRowsHtml(drift, severity) {
    var list = (drift || []).filter(function (d) { return (d.severity || 'error') === severity; });
    if (!list.length) return '';
    return '<table class="table" style="margin-top:.6rem"><thead><tr><th>路由</th><th>侧</th><th>原因</th></tr></thead><tbody>' +
      list.map(function (d) {
        return '<tr class="gov-drift-row"><td class="mono" style="font-size:.82rem">' + esc(d.routeId) +
          '</td><td class="mono" style="font-size:.82rem">' + esc(d.side) +
          '</td><td style="font-size:.85rem">' + esc(d.reason) + '</td></tr>';
      }).join('') + '</tbody></table>';
  }

  function renderOrchestration(payload) {
    if (payload.degraded && !payload.data) return renderDegrade('orchestration', payload);
    var d = payload.data || {};
    var unreadable = !d.readable && !(d.routes || []).length && !d.lastCheckAt;
    var warnCount = (d.drift || []).filter(function (x) { return (x.severity || 'error') === 'warn'; }).length;
    var errorCount = (d.drift || []).filter(function (x) { return (x.severity || 'error') === 'error'; }).length;

    if (unreadable) {
      // 判红口径：路由表不可读 ≠ 0 条路由 = 健康
      setCard('orchestration', pillHtml('error', '×', '路由表不可读'),
        noticeHtml('error', '编排路由表不可读（routes.yaml 缺失或桥接端点未上线），按治理纪律判红。'),
        kvHtml([['路由条目', '不可读'], ['最近校验', '—']]));
      return;
    }

    // 三态：① 门禁自身故障 → ② 全绿 → ③ 判出漂移
    var pill, banner, body;
    if (d.lastCheckError) {
      pill = pillHtml('error', '×', '门禁故障');
      banner = noticeHtml('error',
        '判据门禁未正常运行（' + (d.lastCheckError.code || 'UNKNOWN') + '）：' +
        String(d.lastCheckError.msg || '').slice(0, 500));
      body = '<p class="muted" style="margin:0">g21 门禁上次运行崩溃，本轮漂移结论不可信，请先修复门禁再核对双形态。</p>';
    } else if (d.healthy) {
      pill = pillHtml('ok', '●', '双形态已同步');
      banner = '';
      body = kvHtml([
        ['漂移计数', errorCount + ' 条（error）'],
        ['warn 级差异', warnCount ? { html: '<span class="tag tag--warn">▲ ' + warnCount + ' 条</span>' } : '0 条'],
        ['最近校验', fmtClock(d.lastCheckAt)],
      ]) + driftRowsHtml(d.drift, 'error');
    } else {
      pill = pillHtml('error', '×', '存在漂移');
      banner = noticeHtml('error', 'g21 判据发现 error 级漂移，请对账 routes.yaml ⇄ SKILL.md ⇄ allin.patch.yml 三方。');
      body = kvHtml([
        ['漂移计数', errorCount + ' 条（error）'],
        ['warn 级差异', warnCount ? { html: '<span class="tag tag--warn">▲ ' + warnCount + ' 条</span>' } : '0 条'],
        ['最近校验', fmtClock(d.lastCheckAt)],
      ]) + driftRowsHtml(d.drift, 'error');
    }
    setCard('orchestration', pill, banner, body);

    // 路由明细（折叠区，含 warn 级标记行）
    var routesEl = $('gov-routes-body');
    if (routesEl) {
      var driftMap = {};
      (d.drift || []).forEach(function (x) {
        driftMap[x.routeId] = driftMap[x.routeId] || [];
        driftMap[x.routeId].push(x);
      });
      var routes = d.routes || [];
      routesEl.innerHTML = routes.length
        ? '<div class="panel" style="margin-top:.8rem;overflow-x:auto"><table class="table"><thead><tr><th>路由</th><th>入口</th><th>双形态</th><th>触发条件</th><th>漂移</th></tr></thead><tbody>' +
          routes.map(function (r) {
            var marks = (driftMap[r.id] || []);
            var hasError = marks.some(function (m) { return (m.severity || 'error') === 'error'; });
            var hasWarn = marks.some(function (m) { return (m.severity || 'error') === 'warn'; });
            var mark = hasError ? '<span class="tag tag--error">× ' + esc(marks[0].reason || '漂移') + '</span>'
              : hasWarn ? '<span class="tag tag--warn">▲ warn</span>'
              : '<span class="tag tag--ok">●</span>';
            return '<tr><td class="mono" style="font-size:.82rem">' + esc(r.id) +
              '</td><td class="mono" style="font-size:.82rem">' + esc(r.entry || '—') +
              '</td><td>' + (r.forms || []).map(function (f) { return '<span class="tag tag--info">' + esc(f) + '</span>'; }).join(' ') +
              '</td><td style="font-size:.85rem">' + esc(r.trigger || '—') +
              '</td><td>' + mark + '</td></tr>';
          }).join('') + '</tbody></table></div>'
        : '<p class="muted" style="margin:.8rem 0 0">路由表暂无条目。</p>';
    }
  }

  function entryStatus(e) {
    if (e.valid === false) return { state: 'warn', icon: '▲', label: 'invalid' };
    if (e.running) return { state: 'ok', icon: '●', label: 'running' };
    return { state: 'dim', icon: '■', label: 'stopped' };
  }

  function entryActionHtml(e) {
    if (!CFG.admin) return '<span class="muted" style="font-size:.82rem">只读</span>';
    var st = entryStatus(e);
    if (st.label === 'invalid') return '<span class="muted" style="font-size:.82rem">登记异常，禁止操作</span>';
    var action = st.label === 'running' ? 'stop' : 'start';
    var label = action === 'stop' ? '停止' : '启动';
    var confirmAttr = action === 'stop' ? ' data-confirm="停止该项目"' : '';
    return '<form class="gov-action" method="post" action="/member/api/governance/entries/' + esc(e.id) + '/' + action + '" style="margin:0">' +
      '<input type="hidden" name="_csrf" value="' + esc(CFG.csrf) + '">' +
      '<button class="btn btn--sm' + (action === 'stop' ? ' btn--ghost' : '') + '" type="submit" data-gov-action' + confirmAttr + ' data-id="' + esc(e.id) + '">' + label + '</button>' +
      '</form>';
  }

  function renderEntries(payload) {
    if (payload.degraded && !payload.data) return renderDegrade('entries', payload);
    var items = (payload.data && payload.data.items) || [];
    if (!items.length) {
      setCard('entries', pillHtml('dim', '■', '空'), '',
        '<p class="muted" style="margin:0">注册表中没有登记项目。</p>');
      return;
    }
    setCard('entries', pillHtml('info', '●', items.length + ' 项'), '',
      '<div style="overflow-x:auto"><table class="table"><thead><tr><th>项目</th><th>分类</th><th>端口</th><th>状态</th><th>操作</th></tr></thead><tbody>' +
      items.map(function (e) {
        var st = entryStatus(e);
        return '<tr><td class="mono" style="font-size:.82rem">' + esc(e.id) + '<br><span class="muted">' + esc(e.name || '') + '</span></td>' +
          '<td style="font-size:.85rem">' + esc(e.category || '—') + '</td>' +
          '<td class="mono" style="font-size:.82rem">' + (e.port == null ? '—' : esc(e.port)) + '</td>' +
          '<td>' + pillHtml(st.state, st.icon, st.label) + '</td>' +
          '<td>' + entryActionHtml(e) + '</td></tr>';
      }).join('') + '</tbody></table></div>');
  }

  // ---------- 轮询器：单飞锁 + visibility 暂停 + 失败退避 ----------

  var pollers = [];

  function createPoller(url, intervalMs, renderFn) {
    var inFlight = false;
    var fails = 0;
    var timer = null;
    var stopped = false;

    function currentDelay() { return fails >= BACKOFF_AFTER ? BACKOFF_INTERVAL : intervalMs; }

    function loop() {
      timer = setTimeout(function () {
        tick();
        loop();
      }, currentDelay());
    }

    async function tick() {
      if (stopped || inFlight || document.hidden) return;
      inFlight = true;
      try {
        var res = await fetch(url, { headers: { accept: 'application/json' } });
        if (res.status === 401) {
          stopAll();
          var b = await res.json().catch(function () { return null; });
          location.assign((b && b.loginUrl) || '/login');
          return;
        }
        if (res.status === 403) {
          stopAll();
          showFatal('权限不足：治理数据访问被拒绝（403），已停止轮询。');
          return;
        }
        var payload = await res.json();
        fails = 0;
        renderFn(payload);
      } catch (e) {
        fails += 1;
        if (fails === BACKOFF_AFTER) showInline('warn', '治理数据暂时不可用，轮询已退避至 15 秒，恢复后自动回到正常频率。');
      } finally {
        inFlight = false;
      }
    }

    function stopAll() {
      stopped = true;
      if (timer) clearTimeout(timer);
    }

    loop();
    return { tickNow: tick, stop: stopAll };
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) return;
    pollers.forEach(function (p) { p.tickNow(); });
  });

  // ---------- 折叠明细 ----------

  var toggle = $('gov-routes-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var body = $('gov-routes-body');
      if (!body) return;
      var open = body.hidden;
      body.hidden = !open;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.textContent = open ? '收起路由明细' : '展开路由明细';
    });
  }

  // ---------- 写操作：两段式确认 + 防重复提交 ----------

  function disarm(btn) {
    if (btn._armTimer) { clearTimeout(btn._armTimer); btn._armTimer = null; }
    delete btn.dataset.armed;
    if (btn.dataset.orig) btn.textContent = btn.dataset.orig;
    btn.classList.remove('gov-btn--armed');
  }

  document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-gov-action]');
    if (!btn) return;
    event.preventDefault();

    // 两段式确认（仅带 data-confirm 的破坏性操作）
    if (btn.dataset.confirm && !btn.dataset.armed) {
      btn.dataset.armed = '1';
      btn.dataset.orig = btn.textContent;
      btn.textContent = '再次点击确认' + btn.dataset.confirm;
      btn.classList.add('gov-btn--armed');
      btn._armTimer = setTimeout(function () { disarm(btn); }, 3000);
      return;
    }
    disarm(btn);
    submitAction(btn);
  });

  async function submitAction(btn) {
    var form = btn.closest('form');
    if (!form || btn.disabled) return;
    btn.disabled = true;
    btn.dataset.orig = btn.dataset.orig || btn.textContent;
    btn.textContent = '执行中…';
    try {
      var res = await fetch(form.action, {
        method: 'POST',
        headers: {
          'accept': 'application/json',
          'content-type': 'application/json',
          'x-csrf-token': CFG.csrf, // CSRF 双通道之一；表单隐藏域 _csrf 为 JS 失效兜底
        },
        body: JSON.stringify({}),
      });
      if (res.status === 401) {
        var b401 = await res.json().catch(function () { return null; });
        location.assign((b401 && b401.loginUrl) || '/login');
        return;
      }
      var payload = await res.json().catch(function () { return null; });
      if (res.ok && payload && payload.ok) {
        showInline('ok', '操作已执行：' + payload.id + '（结果已记入审计流水）。');
        repollNow();
      } else {
        var code = payload && payload.code ? '（' + payload.code + '）' : '';
        var msg = payload && payload.message ? payload.message : '平台未返回原因。';
        showInline('error', '操作未成功' + code + '：' + msg);
      }
    } catch (e) {
      showInline('error', '请求未能完成（网络异常），该次尝试已在服务端留痕或可重试。');
    } finally {
      btn.disabled = false;
      btn.textContent = btn.dataset.orig;
      delete btn.dataset.orig;
    }
  }

  function repollNow() {
    pollers.forEach(function (p) { p.tickNow(); });
  }

  // ---------- 启动 ----------

  pollers.push(createPoller(CFG.apiOverview, OVERVIEW_INTERVAL, renderOverview));
  pollers.push(createPoller(CFG.apiOrchestration, ORCH_INTERVAL, renderOrchestration));
  if (CFG.admin) pollers.push(createPoller(CFG.apiEntries, ENTRIES_INTERVAL, renderEntries));
})();
