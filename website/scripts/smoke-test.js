'use strict';

/**
 * 冒烟验证：起真实服务 → 跑真实 HTTP 请求 → 校验页面、认证、权限与加密落盘。
 *
 * 覆盖：
 *   1) 四个页面可达、导航与样式就位
 *   2) 图片来自数据库（/media/<key>），不存在的 key 回占位图 404
 *   3) 未登录访问受保护区 → 302 跳登录带提示；JSON 请求 → 401 结构化响应
 *   4) 注册 / 登录 / 会话保持 / 登出
 *   5) 越权访问管理台 → 403
 *   6) 留言表单（含附件）入库
 *   7) 治理看板：匿名 401/302、member 403 写拒绝、platform 离线 200 + 降级标记
 *   8) **落盘无明文**：数据库文件里搜不到任何原文片段
 *
 * 用法：npm run smoke（会先用 9155 端口起一个临时实例，跑完自动关闭）
 * 注：临时实例强制 PORTAL_PORT_FILE 指向不存在路径 → 治理代理走确定性离线降级链路。
 */

const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PORT = 9155;
const BASE = `http://127.0.0.1:${PORT}`;
const COOKIE_NAME = process.env.SESSION_COOKIE_NAME || 'allin_sid';

const results = [];

function step(name, ok, detail = '') {
  results.push({ name, ok });
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(30, ' ')}${detail}`);
}

async function request(pathname, { method = 'GET', headers = {}, body = null, cookie = null } = {}) {
  const res = await fetch(BASE + pathname, {
    method,
    headers: { ...headers, ...(cookie ? { cookie } : {}) },
    body,
    redirect: 'manual',
  });
  const buffer = Buffer.from(await res.arrayBuffer());
  const setCookies = typeof res.headers.getSetCookie === 'function' ? res.headers.getSetCookie() : [];
  return { status: res.status, headers: res.headers, buffer, text: buffer.toString('utf8'), setCookies };
}

function sessionFrom(setCookies) {
  for (const raw of setCookies) {
    const match = /^([^=]+)=([^;]*)/.exec(raw);
    if (match && match[1] === COOKIE_NAME) return `${COOKIE_NAME}=${match[2]}`;
  }
  return null;
}

function form(fields) {
  return new URLSearchParams(fields).toString();
}

async function waitReady(child) {
  let stderr = '';
  child.stderr.on('data', (d) => { stderr += d.toString(); });
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch(`${BASE}/healthz`);
      if (res.ok) return true;
    } catch {
      /* 还没起来 */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  console.error(stderr);
  return false;
}

async function main() {
  const child = spawn(process.execPath, ['--experimental-sqlite', path.join(ROOT, 'src', 'server.js')], {
    cwd: ROOT,
    env: {
      ...process.env,
      PORT: String(PORT),
      SITE_BASE_URL: BASE,
      // 治理看板冒烟用确定性离线：端口发现文件指向不存在的路径 → PORTAL_UNREACHABLE 降级
      PORTAL_PORT_FILE: path.join(ROOT, 'data', 'smoke-no-portal.port'),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  // 2026-11-08 复评增量：异常路径（main().catch / 未就绪 / 意外退出）同样回收
  // 临时实例。process.exit 会触发 'exit' 事件，闭包内 child 此时仍可访问，
  // 避免 9155 端口/进程残留导致后续冒烟 flaky。正常路径的显式 kill 保留。
  process.on('exit', () => { try { child.kill('SIGKILL'); } catch { /* 已退出 */ } });

  const ready = await waitReady(child);
  if (!ready) {
    console.error('  服务未能在 20 秒内启动');
    child.kill('SIGKILL');
    process.exit(1);
  }

  console.log('\n  allin 官网 · 冒烟验证');
  console.log('  ----------------------------------------------------------');

  // 1) 页面
  for (const [pathName, marker] of [['/', 'ALLIN LAB'], ['/services', '产品服务'], ['/about', '关于我们'], ['/contact', '联系我们']]) {
    const res = await request(pathName);
    step(`页面 ${pathName} 可达`, res.status === 200 && res.text.includes(marker), `HTTP ${res.status}`);
  }
  const css = await request('/css/cyberpunk.css');
  step('样式表可加载', css.status === 200 && css.text.includes('--cyan'), `HTTP ${css.status}`);

  // 2) 图片来自数据库
  const img = await request('/media/site_home_hero_01');
  step(
    '配图由数据库解密投递',
    img.status === 200 && img.headers.get('content-type') === 'image/jpeg' && img.buffer[0] === 0xff && img.buffer[1] === 0xd8,
    `${img.headers.get('content-type')} · ${img.buffer.length} 字节`
  );
  const missing = await request('/media/site_not_exist_01');
  step('缺失资源回占位图', missing.status === 404 && missing.text.includes('<svg'), `HTTP ${missing.status}`);

  // 3) 未登录访问受保护区
  const anon = await request('/member');
  step(
    '匿名访问受保护区跳转登录',
    anon.status === 302 && (anon.headers.get('location') || '').includes('/login?next=%2Fmember'),
    anon.headers.get('location') || ''
  );
  const anonJson = await request('/member', { headers: { accept: 'application/json' } });
  step(
    '匿名 JSON 请求返回 401',
    anonJson.status === 401 && JSON.parse(anonJson.text).code === 'LOGIN_REQUIRED',
    `HTTP ${anonJson.status}`
  );

  // 4) 注册 → 会话保持 → 控制台
  const email = `smoke_${Date.now()}@example.com`;
  // 每次运行随机生成口令（保证同时含字母与数字，满足校验策略），不在源码里留固定凭据
  const password = `${crypto.randomBytes(10).toString('base64url').replace(/[^A-Za-z0-9]/g, '').slice(0, 10)}${crypto.randomInt(0, 10)}`;
  const reg = await request('/register', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: form({ email, displayName: '冒烟用户', password, passwordConfirm: password }),
  });
  const memberCookie = sessionFrom(reg.setCookies);
  step('注册成功并下发会话', reg.status === 302 && !!memberCookie, `HTTP ${reg.status}`);

  const memberHome = await request('/member', { cookie: memberCookie });
  step('登录后可进控制台', memberHome.status === 200 && memberHome.text.includes('服务工单'), `HTTP ${memberHome.status}`);

  const mdFile = await request('/member/files/member_delivery_checklist_01', { cookie: memberCookie });
  step('会员文件可下载（解密投递）', mdFile.status === 200 && mdFile.text.includes('客户交付清单'), `HTTP ${mdFile.status}`);
  const mdAnon = await request('/member/files/member_delivery_checklist_01');
  step('会员文件对匿名重定向登录', mdAnon.status === 302, `HTTP ${mdAnon.status}`);

  // 5) 越权
  const adminDenied = await request('/admin', { cookie: memberCookie });
  step('普通会员访问管理台被拒', adminDenied.status === 403, `HTTP ${adminDenied.status}`);

  // 5.5) 治理看板：可达性 / 越权 / platform 离线降级（portal.port 文件已被强制指向不存在路径）
  const govAnon = await request('/member/dashboard');
  step('匿名访问治理看板跳登录', govAnon.status === 302 && (govAnon.headers.get('location') || '').includes('/login'), govAnon.headers.get('location') || '');
  const govApiAnon = await request('/member/api/governance/overview', { headers: { accept: 'application/json' } });
  step(
    '匿名治理 API 返回 401',
    govApiAnon.status === 401 && JSON.parse(govApiAnon.text).code === 'LOGIN_REQUIRED',
    `HTTP ${govApiAnon.status}`
  );
  const dash = await request('/member/dashboard', { cookie: memberCookie });
  step(
    '治理看板可达（platform 离线仍 200）',
    dash.status === 200 && dash.text.includes('治理看板') && dash.text.includes('gov-config'),
    `HTTP ${dash.status}`
  );
  const govOverview = await request('/member/api/governance/overview', { headers: { accept: 'application/json' }, cookie: memberCookie });
  const govOverviewBody = JSON.parse(govOverview.text);
  step(
    'platform 离线时总览 API 200 + 降级标记',
    govOverview.status === 200 && govOverviewBody.ok === true && govOverviewBody.degraded && govOverviewBody.degraded.code === 'PORTAL_UNREACHABLE',
    `HTTP ${govOverview.status} · degraded=${govOverviewBody.degraded ? govOverviewBody.degraded.code : 'null'}`
  );
  const govOrch = await request('/member/api/governance/orchestration', { headers: { accept: 'application/json' }, cookie: memberCookie });
  const govOrchBody = JSON.parse(govOrch.text);
  step(
    'platform 离线时编排 API 200 + 降级不报错',
    govOrch.status === 200 && govOrchBody.ok === true && govOrchBody.degraded && govOrchBody.degraded.code === 'PORTAL_UNREACHABLE',
    `HTTP ${govOrch.status}`
  );
  const govCsrf = (dash.text.match(/data-csrf="([^"]+)"/) || [])[1] || '';
  const govWriteMember = await request('/member/api/governance/entries/smoke-entry/stop', {
    method: 'POST',
    headers: { accept: 'application/json', 'content-type': 'application/x-www-form-urlencoded' },
    cookie: memberCookie,
    body: form({ _csrf: govCsrf }),
  });
  step(
    'member 调治理写接口被拒 403',
    govWriteMember.status === 403 && JSON.parse(govWriteMember.text).code === 'FORBIDDEN',
    `HTTP ${govWriteMember.status}`
  );

  // 6) 留言（含附件）
  const fd = new FormData();
  fd.append('name', '冒烟测试');
  fd.append('email', email);
  fd.append('topic', '体检与咨询');
  fd.append('body', '这是一条冒烟验证留言，用于确认内容加密入库。');
  fd.append('attachment', new Blob([Buffer.from('smoke attachment payload')], { type: 'text/plain' }), 'smoke.txt');
  const contact = await request('/contact', { method: 'POST', body: fd });
  step(
    '留言提交（含附件）成功',
    contact.status === 302 && (contact.headers.get('location') || '').includes('notice=contact_sent'),
    contact.headers.get('location') || `HTTP ${contact.status}`
  );

  // 7) 管理员登录 → 管理台
  const accountsFile = path.join(ROOT, 'data', 'seed-accounts.json');
  const adminCookie = (() => {
    try {
      const file = JSON.parse(fs.readFileSync(accountsFile, 'utf8'));
      return file.accounts.find((a) => a.email === 'admin@allin.local');
    } catch {
      return null;
    }
  })();
  if (!adminCookie) {
    step('管理台可达', false, `未找到 ${path.relative(ROOT, accountsFile)}，请先 npm run seed`);
  } else {
    const login = await request('/login', {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: form({ email: adminCookie.email, password: adminCookie.password }),
    });
    const cookie = sessionFrom(login.setCookies);
    const adminPage = await request('/admin', { cookie });
    step(
      '管理员登录并进入管理台',
      login.status === 302 && adminPage.status === 200 && adminPage.text.includes('联系留言'),
      `HTTP ${adminPage.status}`
    );
    step('管理台能看到刚提交的留言', adminPage.text.includes('冒烟测试'), '');

    // 7.5) 治理管理页（admin）与写接口 CSRF 闸门
    const govAdmin = await request('/admin/governance', { cookie });
    step(
      '管理员进入治理管理页',
      govAdmin.status === 200 && govAdmin.text.includes('治理管理') && govAdmin.text.includes('审计流水'),
      `HTTP ${govAdmin.status}`
    );
    const govWriteNoCsrf = await request('/member/api/governance/entries/smoke-entry/stop', {
      method: 'POST',
      headers: { accept: 'application/json', 'content-type': 'application/x-www-form-urlencoded' },
      cookie,
      body: form({}),
    });
    step('治理写接口缺 CSRF 被拒 403', govWriteNoCsrf.status === 403, `HTTP ${govWriteNoCsrf.status}`);
    const govWriteBadId = await request('/member/api/governance/entries/SMOKE_BAD/stop', {
      method: 'POST',
      headers: { accept: 'application/json', 'content-type': 'application/json', 'x-csrf-token': (govAdmin.text.match(/data-csrf="([^"]+)"/) || [])[1] || '' },
      cookie,
      body: JSON.stringify({}),
    });
    step('治理写接口非法 id 被拒 400', govWriteBadId.status === 400, `HTTP ${govWriteBadId.status}`);
  }

  // 8) 登出
  const logout = await request('/logout', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    cookie: memberCookie,
    body: form({ _csrf: (await request('/member', { cookie: memberCookie })).text.match(/name="_csrf" value="([^"]+)"/)?.[1] || '' }),
  });
  step('登出后会话失效', logout.status === 302, `HTTP ${logout.status}`);

  // 9) 落盘无明文
  const dbFile = path.join(ROOT, 'data', 'site.db');
  const dbBytes = fs.readFileSync(dbFile);
  const markers = ['治理内核落地与平台开发', '客户交付清单', '这是一条冒烟验证留言'];
  const leaks = markers.filter((m) => dbBytes.includes(Buffer.from(m, 'utf8')));
  step('数据库内无业务明文', leaks.length === 0, leaks.length ? `泄漏：${leaks.join(' / ')}` : `已检查 ${markers.length} 个标记`);

  child.kill('SIGKILL');

  const failed = results.filter((r) => !r.ok);
  // B4：把「分母自定」改成机器可读、可冻结的判据。
  //   - case ID 唯一性：条件分支若重复记同名 step，属夹具缺陷，判红；
  //   - 项数下限：无 seed 态实测 23 项、正常态 28 项；低于下限说明有分支被静默跳过，判红；
  //   - 汇总行供 PR / CI 引用，不再用「X/X」这种自报自话的分母。
  const ids = results.map((r) => r.name);
  const duplicates = [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
  const MIN_EXPECTED_STEPS = 23;
  const countShort = results.length < MIN_EXPECTED_STEPS;
  const status = failed.length || duplicates.length || countShort ? 'incomplete' : 'clean';
  console.log('  ----------------------------------------------------------');
  console.log(`  ${results.length - failed.length}/${results.length} 通过`);
  console.log(`  SMOKE_SUMMARY total=${results.length} passed=${results.length - failed.length} failed=${failed.length} min_expected=${MIN_EXPECTED_STEPS} duplicate_cases=${duplicates.length} status=${status}\n`);
  if (duplicates.length) console.error(`  [FAIL] 重复 case ID：${duplicates.join(' / ')}`);
  if (countShort) console.error(`  [FAIL] 冒烟项数 ${results.length} < 冻结下限 ${MIN_EXPECTED_STEPS}：有分支被静默跳过`);
  process.exit(failed.length || duplicates.length || countShort ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
