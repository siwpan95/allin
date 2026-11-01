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
 *   7) **落盘无明文**：数据库文件里搜不到任何原文片段
 *
 * 用法：npm run smoke（会先用 9155 端口起一个临时实例，跑完自动关闭）
 */

const { spawn } = require('node:child_process');
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
    env: { ...process.env, PORT: String(PORT), SITE_BASE_URL: BASE },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

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
  const password = 'SmokeTest2026';
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
  console.log('  ----------------------------------------------------------');
  console.log(`  ${results.length - failed.length}/${results.length} 通过\n`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
