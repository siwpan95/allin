#!/usr/bin/env node
/**
 * 端到端三面冒烟（smoke:e2e，SC6 北极星）—— P3 测试与验收方案 §2 的实施。
 *
 * 一条命令串起三面贯通 + Agent 漂移判据，≥6 检查点：
 *   CP1 CLI 前门        python allin_cli.py preset list（只读，CLI 入口 + kernel 服务分发）
 *   CP2 kernel 探测     python allin_cli.py platform registry-count（只读支柱调度）
 *   CP3 portal 回环探活 复用优先：portal.port 存活 → 复用；否则 PORT=0 临时实例（防双 portal 竞态）
 *   CP4 website 临时探活 9156 端口临时实例：/healthz + 首页 marker + 匿名受保护区 302
 *   CP5 g21 漂移判据    tools/gate/agent_parity.py exit 0 + g21-runs.jsonl 尾行判红三条件
 *   CP6 verify-mount    Windows/DSH 专属：exit ≤1 通过（1=WARN）；非 Windows / CI 自动 skip
 *
 * 纪律（P3 §2）：
 *   - 零第三方依赖（node: 内建模块）；零盘符（路径全部仓根相对，Python 走 ALLIN_PYTHON env）；
 *   - 临时端口 9156 启动前程序化读 docs/事实源/ports.yaml，与任何已登记端口/保留段冲突即 fail-loud；
 *   - 证据落 tools/gate/audit/e2e-runs.jsonl（逐检查点一行 + 汇总一行，模式同 gate-runs，
 *     被根 .gitignore /tools/gate/audit/* 自动覆盖，零 .gitignore 改动）；
 *   - 任一检查点失败 exit 1，detail 指名失败面（cli / kernel / portal / website / 判据）；
 *   - 本脚本只读消费各面产物，不触碰 tools/gate、platform/、website/ 的任何实现文件。
 *
 * 用法：npm run smoke:e2e
 */

import { spawn, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolvePython, pythonEnv } from './resolve_python.mjs';
import isHomeMarkerPresent from './lib/homeMarker.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.ALLIN_ROOT ? path.resolve(process.env.ALLIN_ROOT) : path.resolve(__dirname, '..');
const E2E_PORT = Number(process.env.ALLIN_E2E_WEBSITE_PORT || 9156);

// 解释器解析**不另写一套**：与 scripts/run_all_gates.sh 共用 scripts/resolve_python.mjs
// （ALLIN_PYTHON → 仓内 .venv → PATH，且优先选带 PyYAML 的候选）。
//
// 2026-11-06 实测教训：此处原写 `process.env.ALLIN_PYTHON || 'python'`，默认落到
// PATH 上无 PyYAML 的便携 3.13.14 ⇒ CP1/CP2 报 `ModuleNotFoundError: yaml` 假红；
// 而 CI 两侧 job 都设了 ALLIN_PYTHON ⇒ **CI 永远绿、本机永远红**，本地跑批又不含
// 本脚本 ⇒ 这个盲区此前无人发现（「门禁写了不跑 = 没有门禁」的第四例）。
//
// ⚠ 修复点与加固点要分清：**假红的根因是解释器选错**（落到了 PATH 上无 PyYAML 的
// 便携 3.13.14），resolvePython() 选对解释器才是**修复**；连 PATH 一起注入是**加固**
// （防脚本内部再 spawn 裸 `python` 时回落），别把功劳记在后者头上。
const PY_RESOLVED = resolvePython();
const PY = PY_RESOLVED.python;
// 子进程环境：把解释器目录提到 PATH 最前，避免裸 `python` 落回便携解释器。
const PY_ENV = pythonEnv(PY_RESOLVED);
const AUDIT_DIR = process.env.ALLIN_GATE_AUDIT
  ? path.resolve(process.env.ALLIN_GATE_AUDIT)
  : path.join(ROOT, 'tools', 'gate', 'audit');
const EVIDENCE_FILE = path.join(AUDIT_DIR, 'e2e-runs.jsonl');
const PORTS_YAML = path.join(ROOT, 'docs', '事实源', 'ports.yaml');
const OVERALL_BUDGET_MS = 60_000;
// SC6 / P3 §2.2 判据：至少 5 个检查点**真正通过**才算达标；SKIP 不凑数。
const MIN_EFFECTIVE_CHECKPOINTS = 5;
const T0 = Date.now();

const results = [];
const runId = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14) + '-' + Math.random().toString(16).slice(2, 6);
const spawnedChildren = [];   // teardown 保证全杀（可逆效应，对齐 harness effect 登记）
let portalReused = false;
let portalPort = null;       // CP3 探活得到的真实 portal 端口（复用或临时实例）
let portalPortFile = null;   // CP7 把该端口写入此文件，供 website 实例的 PORTAL_PORT_FILE 指向
let cp7DataDir = null;       // CP7 website 实例用的临时数据目录（DB/KEY，零污染真实 data/）

function step(id, name, ok, detail = '', skipped = false, ms = 0) {
  results.push({ id, name, ok, detail, skipped, ms });
  const mark = skipped ? 'SKIP' : (ok ? 'PASS' : 'FAIL');
  console.log(`  ${mark}  ${`[${id}] ${name}`.padEnd(44, ' ')}${detail}`);
  // GitHub Actions 的 job logs 端点匿名 403（需 admin），annotations 是唯一公开
  // 可读通道。失败检查点逐条推成 ::error::，否则 CI 红了只看到通用 exit code 1。
  // workflow command 数据里的 % / CR / LF 必须百分号编码，否则 annotation 会被截断。
  if (!ok && !skipped && process.env.GITHUB_ACTIONS === 'true') {
    const msg = `e2e [${id}] ${name} 失败：${detail}`
      .replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A');
    console.log(`::error::${msg}`);
  }
}

function elapsed() { return Date.now() - T0; }

/** 带超时的 fetch（AbortController，零依赖） */
function fetchT(url, opts = {}, ms = 5000) {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), ms);
  return fetch(url, { ...opts, signal: ac.signal }).finally(() => clearTimeout(t));
}

/** 带超时的子进程执行，resolve {code, out, err}，绝不 throw */
function runCmd(cmd, args, { cwd = ROOT, timeoutMs = 30_000, env = {} } = {}) {
  return new Promise((resolve) => {
    let out = '', err = '';
    let child;
    try {
      child = spawn(cmd, args, { cwd, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      return resolve({ code: -1, out: '', err: String(e) });
    }
    const t = setTimeout(() => { try { child.kill('SIGKILL'); } catch { /* 已退出 */ } }, timeoutMs);
    child.stdout.on('data', (d) => { out += d.toString(); });
    child.stderr.on('data', (d) => { err += d.toString(); });
    child.on('error', (e) => { clearTimeout(t); resolve({ code: -1, out, err: err + String(e) }); });
    child.on('close', (code) => { clearTimeout(t); resolve({ code: code ?? -1, out, err }); });
  });
}

function killChild(child) {
  try { child.kill('SIGKILL'); } catch { /* 已退出 */ }
}

/** 读 docs/事实源/ports.yaml，返回 {ports:Set, ranges:[[a,b]]}；解析失败 fail-loud */
function loadBannedPorts() {
  const text = fs.readFileSync(PORTS_YAML, 'utf8');
  const ports = new Set();
  const ranges = [];
  for (const m of text.matchAll(/^\s*-\s*port:\s*(\d+)/gm)) ports.add(Number(m[1]));
  for (const m of text.matchAll(/(?:reserved|range):\s*([\d\s,-]+)/g)) {
    for (const part of m[1].split(',')) {
      const mm = part.trim().match(/^(\d+)\s*-\s*(\d+)$/);
      if (mm) ranges.push([Number(mm[1]), Number(mm[2])]);
    }
  }
  return { ports, ranges };
}

/** 端口纪律（P3 §1：先查 ports.yaml）——冲突返回冲突描述，无冲突返回 null */
function portConflict(port, { ports, ranges }) {
  if (ports.has(port)) return `端口 ${port} 已在 ports.yaml 登记（先查本表，禁止撞车）`;
  for (const [a, b] of ranges) if (port >= a && port <= b) return `端口 ${port} 落在 ports.yaml 保留/登记段 ${a}-${b} 内`;
  return null;
}

function tailLastLine(file) {
  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  return lines.length ? JSON.parse(lines[lines.length - 1]) : null;
}

function shortCommit() {
  try { return execSync('git rev-parse --short HEAD', { cwd: ROOT, encoding: 'utf8' }).trim(); }
  catch { return 'unknown'; }
}

/** 落盘证据：逐检查点一行 + 汇总一行（追加写，天然原子；目录已被 .gitignore 覆盖） */
function writeEvidence(meta) {
  try {
    fs.mkdirSync(AUDIT_DIR, { recursive: true });
    const lines = [];
    for (const r of results) {
      lines.push(JSON.stringify({
        type: 'e2e-checkpoint', runId, checkedAt: new Date().toISOString(),
        id: r.id, name: r.name, ok: r.ok, skipped: r.skipped, detail: r.detail, ms: r.ms,
      }));
    }
    const summary = {
      total: results.length,
      ok: results.filter((r) => r.ok && !r.skipped).length,
      skipped: results.filter((r) => r.skipped).length,
      fail: results.filter((r) => !r.ok && !r.skipped).length,
    };
    lines.push(JSON.stringify({
      type: 'e2e-run', runId,
      startedAt: new Date(T0).toISOString(), finishedAt: new Date().toISOString(),
      commit: shortCommit(), node: process.version, platform: process.platform,
      tempWebsitePort: E2E_PORT, portalReused,
      summary, exit: summary.fail > 0 ? 1 : 0,
      ...meta,
    }));
    fs.appendFileSync(EVIDENCE_FILE, lines.join('\n') + '\n', 'utf8');
    console.log(`\n  证据已落盘：${path.relative(ROOT, EVIDENCE_FILE)}（${lines.length} 行）`);
  } catch (e) {
    console.error(`  [warn] 证据落盘失败（不影响退出码判据）：${e.message}`);
  }
}

async function checkpointCliFront() {
  const t = Date.now();
  const r = await runCmd(PY, ['allin_cli.py', 'preset', 'list'], { timeoutMs: 30_000, env: PY_ENV });
  const ok = r.code === 0 && r.out.trim().length > 0;
  step('CP1', 'CLI 前门（preset list 只读）', ok,
    ok ? 'exit 0' : `cli 面 exit=${r.code} ${r.err.split('\n')[0] || '无输出'}`.slice(0, 160),
    false, Date.now() - t);
}

async function checkpointKernelProbe() {
  const t = Date.now();
  const r = await runCmd(PY, ['allin_cli.py', 'platform', 'registry-count'], { timeoutMs: 30_000, env: PY_ENV });
  const ok = r.code === 0 && /registry 项目条目/.test(r.out);
  step('CP2', 'kernel 探测（platform registry-count 只读）', ok,
    ok ? r.out.trim().split('\n')[0] : `kernel 面 exit=${r.code} ${(r.err || r.out).split('\n')[0]}`.slice(0, 160),
    false, Date.now() - t);
}

/** portal 复用优先：portal.port 存活 → 复用；否则 PORT=0 临时实例（避免覆盖常驻实例端口文件） */
async function portalDiscover() {
  const portFile = path.join(ROOT, 'platform', 'data', 'portal.port');
  try {
    const n = Number(fs.readFileSync(portFile, 'utf8').trim());
    if (Number.isInteger(n) && n > 0 && n <= 65535) {
      const res = await fetchT(`http://127.0.0.1:${n}/api/status`, {}, 1500);
      if (res.ok) {
        const j = await res.json();
        if (j && j.platform === 'allin-platform') {
          portalReused = true;
          portalPort = n;
          return { port: n, child: null, log: '' };
        }
      }
    }
  } catch { /* 无文件或未存活 → 走临时实例 */ }

  const child = spawn(process.execPath, [path.join('platform', 'apps', 'portal', 'src', 'index.js')], {
    cwd: ROOT,
    env: { ...process.env, PORT: '0' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  spawnedChildren.push({ child, name: 'portal-temp' });
  let stdout = '';
  let exited = null;
  child.stdout.on('data', (d) => { stdout += d.toString(); });
  child.stderr.on('data', (d) => { stdout += d.toString(); });
  child.on('exit', (code, signal) => { exited = { code, signal }; });
  child.on('error', (e) => { stdout += `\n[spawn error] ${e.message}`; exited = { code: -1, signal: null }; });

  // 就绪判据优先匹配启动行（含实际端口），兜底探活 /api/status。
  // 20s 窗口（原 6s）与 CP4 website 对齐，给冷启动留余量；但 2026-11-05
  // run 42030794703 实测：CI Windows 干净检出缺 platform/node_modules 时，
  // portal 的 ESM import '@allin/core' 会 ERR_MODULE_NOT_FOUND **启动即崩**，
  // 此时再等 20s 纯属空转，且旧 detail 只报「未就绪」把真因藏住。
  // 故监听 exit 立刻跳出，把「启动即崩」与「冷启动慢」分开报。
  for (let i = 0; i < 80; i += 1) {   // ≤20s
    if (exited) break;
    const m = /\[allin-platform portal\] http:\/\/127\.0\.0\.1:(\d+)\//.exec(stdout);
    if (m) {
      try {
        const res = await fetchT(`http://127.0.0.1:${m[1]}/api/status`, {}, 1500);
        if (res.ok) { portalPort = Number(m[1]); return { port: Number(m[1]), child, log: stdout, exited: null }; }
      } catch { /* 还没起来 */ }
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  return { port: null, child, log: stdout, exited };
}

async function checkpointPortal() {
  const t = Date.now();
  const { port, child, log, exited } = await portalDiscover();
  if (!port) {
    const tail = (log || '').trim().slice(-300) || '(子进程无任何输出)';
    const why = exited
      ? `临时实例启动即退出（exit=${exited.code}${exited.signal ? ` signal=${exited.signal}` : ''}）`
      : '临时实例 20s 内未就绪（启动行/探活均未命中）';
    // 干净检出最常见的启动崩溃：scripts/bootstrap.sh 只装 Python 依赖，
    // platform 的 workspace 链接不存在。给出可执行命令，避免下次又只看到
    // 「未就绪」去猜超时（上一轮就是这样误判成冷启动慢，白等 20s）。
    const hint = /Cannot find package '@allin\/core'/.test(log || '')
      ? '；缺 platform workspace 依赖 —— 先跑 cd platform && npm install（CI 见 gates.yml 的 npm ci --prefix platform）'
      : '';
    step('CP3', 'portal 回环探活（临时实例）', false,
      `portal 面：${why}${hint}；子进程输出尾部：${tail}`,
      false, Date.now() - t);
    return;
  }
  try {
    const res = await fetchT(`http://127.0.0.1:${port}/api/status`, {}, 3000);
    const j = await res.json();
    const ok = res.status === 200 && j.platform === 'allin-platform' && Number.isInteger(j.port);
    step('CP3', 'portal 回环探活（临时实例）', ok,
      ok ? `HTTP 200 port=${port} version=${j.version}${portalReused ? '（复用存活实例）' : ''}`
         : `portal 面：HTTP ${res.status} body=${JSON.stringify(j).slice(0, 120)}`,
      false, Date.now() - t);
  } catch (e) {
    step('CP3', 'portal 回环探活（临时实例）', false, `portal 面：探活异常 ${String(e).slice(0, 140)}`, false, Date.now() - t);
  }
}

async function checkpointWebsite() {
  const t = Date.now();
  const BASE = `http://127.0.0.1:${E2E_PORT}`;
  const child = spawn(process.execPath, ['--experimental-sqlite', path.join('src', 'server.js')], {
    cwd: path.join(ROOT, 'website'),
    env: {
      ...process.env,
      PORT: String(E2E_PORT),
      SITE_BASE_URL: BASE,
      // CP7 接线：把真实 portal 端口文件指给 website 的 portal 代理；用临时数据目录零污染真实 data/
      DB_PATH: cp7DataDir ? path.join(cp7DataDir, 'site.db') : process.env.DB_PATH,
      KEY_DIR: cp7DataDir ? path.join(cp7DataDir, 'keys') : process.env.KEY_DIR,
      PORTAL_PORT_FILE: portalPortFile || process.env.PORTAL_PORT_FILE,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  spawnedChildren.push({ child, name: 'website-temp' });

  // waitReady（对齐 website smoke-test.js：80×250ms = 20s 上限）
  let ready = false;
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetchT(`${BASE}/healthz`, {}, 1500);
      if (res.ok) { ready = true; break; }
    } catch { /* 还没起来 */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  if (!ready) {
    step('CP4', 'website 临时实例探活', false, `website 面：${E2E_PORT} 端口 20s 内未就绪（/healthz 未 200）`, false, Date.now() - t);
    return;
  }
  try {
    // B5：/healthz 200 不代表首页已渲染完。对 marker 做带退避的有限重试（最多 3 次），
    // 消除同 commit 间歇性「首页 marker 未命中」flaky（历史 runId 20261104142329-f795）。
    let homeOk = false;
    for (let attempt = 0; attempt < 3 && !homeOk; attempt += 1) {
      try {
        const home = await fetchT(`${BASE}/`, {}, 5000);
        // B5：判定收口到纯函数 isHomeMarkerPresent（scripts/lib/homeMarker.js），
        // 其「marker 缺失 → false」已被单测正面证明，防 false-green（见 homeMarker.test.js）
        homeOk = isHomeMarkerPresent(home.status, await home.text());
      } catch { /* 首页尚未就绪 */ }
      if (!homeOk) await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
    }
    const anon = await fetchT(`${BASE}/member`, { redirect: 'manual' }, 5000);
    const loc = anon.headers.get('location') || '';
    const anonOk = anon.status === 302 && loc.includes('/login');
    const ok = homeOk && anonOk;
    step('CP4', 'website 临时实例探活', ok,
      ok ? `healthz 200 · 首页 marker 命中 · 匿名 /member 302→login`
         : `website 面：${homeOk ? '' : '首页 marker 未命中 '}${anonOk ? '' : `匿名鉴权链异常（HTTP ${anon.status} ${loc.slice(0, 60)}）`}`,
      false, Date.now() - t);
  } catch (e) {
    step('CP4', 'website 临时实例探活', false, `website 面：探活异常 ${String(e).slice(0, 140)}`, false, Date.now() - t);
  }
}

/** CP7 · 治理看板在线联动：真实 portal 接通后，website 治理 API 必须 degraded:null
 *
 * 设计（柯砚 P1）：CP3 起真实 portal 后把实际端口写入 CP4 website 实例的
 * PORTAL_PORT_FILE，断言治理看板 API 返回 degraded:null —— 证明 website↔portal
 * BFF 在"平台真在线"时确实接通、而非永远降级。
 *
 * 取会话走 /register（governance overview 仅需 requireAuth，不必 admin），
 * 零预置账号、零 node:sqlite 依赖；用临时数据目录确保不污染真实 data/。
 */
async function checkpointGovernanceWiring() {
  const t = Date.now();
  if (!portalPort || !portalPortFile) {
    step('CP7', '治理看板在线联动（portal→website degraded:null）', true,
      'portal 面未就绪或端口文件未落（CP3 失败），skip（skip ≠ fail）', true, Date.now() - t);
    return;
  }
  const BASE = `http://127.0.0.1:${E2E_PORT}`;
  try {
    // 注册通道建一个临时会员并直接拿到会话 Cookie（overview 仅需 requireAuth）
    const email = `cp7-smoke-${Date.now()}@allin.local`;
    const password = 'Cp7Smoke2026';
    const regRes = await fetchT(`${BASE}/register`, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded', accept: 'application/json' },
      body: `email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`
        + `&passwordConfirm=${encodeURIComponent(password)}&displayName=CP7Smoke`,
      redirect: 'manual',
    }, 5000);
    const setCookie = regRes.headers.get('set-cookie');
    const sid = setCookie && /allin_sid=([^;]+)/.exec(setCookie);
    if (regRes.status !== 302 || !sid) {
      const bodyText = await regRes.text().catch(() => '');
      step('CP7', '治理看板在线联动（portal→website degraded:null）', false,
        `注册/登录失败：HTTP ${regRes.status} setCookie=${Boolean(setCookie)} body=${bodyText.slice(0, 120)}`,
        false, Date.now() - t);
      return;
    }
    // 带会话请求治理总览
    const govRes = await fetchT(`${BASE}/member/api/governance/overview`, {
      headers: { cookie: `allin_sid=${sid[1]}`, accept: 'application/json' },
    }, 5000);
    let j = null;
    try { j = await govRes.json(); } catch { /* 非 JSON */ }
    const ok = govRes.status === 200 && j && j.degraded === null && j.ok === true;
    step('CP7', '治理看板在线联动（portal→website degraded:null）', ok,
      ok ? `HTTP 200 · degraded:null · portal 端口=${portalPort} 已接通 website`
         : `治理看板异常：HTTP ${govRes.status} body=${JSON.stringify(j).slice(0, 160)}`,
      false, Date.now() - t);
  } catch (e) {
    step('CP7', '治理看板在线联动（portal→website degraded:null）', false, `异常 ${String(e).slice(0, 140)}`, false, Date.now() - t);
  }
}

/** g21 判据断言：门禁 exit 0 + g21-runs.jsonl 尾行判红三条件全不成立（v3 冻结口径） */
async function checkpointG21() {
  const t = Date.now();
  const gate = path.join(ROOT, 'tools', 'gate', 'agent_parity.py');
  if (!fs.existsSync(gate)) {
    step('CP5', 'g21 漂移判据', true, 'g21 门禁尚未实施（tools/gate/agent_parity.py 不存在），skip（skip ≠ fail）', true, Date.now() - t);
    return;
  }
  const r = await runCmd(PY, [gate], { timeoutMs: 60_000, env: PY_ENV });
  if (r.code !== 0) {
    step('CP5', 'g21 漂移判据', false, `判据面：g21 exit=${r.code}，输出：${(r.err || r.out).trim().split('\n')[0]}`.slice(0, 160), false, Date.now() - t);
    return;
  }
  try {
    const last = tailLastLine(path.join(ROOT, 'tools', 'gate', 'audit', 'g21-runs.jsonl'));
    // 判红三条件（v3）：routesReadable:false ∨ 行含 error ∨ summary.drift>0
    const red = !last || last.routesReadable === false
      || (last.error !== undefined && last.error !== null)
      || (last.summary && Number(last.summary.drift) > 0);
    step('CP5', 'g21 漂移判据', !red,
      red ? `判据面：g21-runs.jsonl 尾行判红（${!last ? '文件缺失/空' : last.routesReadable === false ? 'routesReadable:false' : last.error ? `error:${JSON.stringify(last.error).slice(0, 80)}` : `drift=${last.summary?.drift}`}）`
          : `exit 0 · 尾行 drift=0 · checkedAt=${last.checkedAt}`,
      false, Date.now() - t);
  } catch (e) {
    step('CP5', 'g21 漂移判据', false, `判据面：g21-runs.jsonl 尾行解析失败 ${String(e).slice(0, 120)}`, false, Date.now() - t);
  }
}

/** verify-mount：Windows/DSH 专属；非 Windows / CI 自动 skip（skip ≠ fail） */
async function checkpointVerifyMount() {
  const t = Date.now();
  const ps1 = path.join(ROOT, 'preset', 'allin', 'verify-mount.ps1');
  if (process.platform !== 'win32' || process.env.CI) {
    step('CP6', 'verify-mount 漂移层', true,
      `${process.env.CI ? 'CI 环境' : '非 Windows'}无 DSH 挂载层，skip（skip ≠ fail）`, true, Date.now() - t);
    return;
  }
  if (!fs.existsSync(ps1)) {
    step('CP6', 'verify-mount 漂移层', true, 'preset/allin/verify-mount.ps1 不存在，skip', true, Date.now() - t);
    return;
  }
  const r = await runCmd('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1], { timeoutMs: 90_000 });
  // 退出码语义（对齐 g21 P2 §3.1）：0=绿；1=WARN（挂载层刷新提示，通过）；≥2=红
  const ok = r.code === 0 || r.code === 1;
  step('CP6', 'verify-mount 漂移层', ok,
    ok ? `exit ${r.code}${r.code === 1 ? '（WARN：挂载层刷新提示）' : ''}`
       : `判据面：verify-mount exit=${r.code}，输出：${(r.err || r.out).trim().split('\n').slice(-1)[0]}`.slice(0, 160),
    false, Date.now() - t);
}

async function main() {
  console.log('\n  allin · 端到端三面冒烟（smoke:e2e）');
  console.log('  ----------------------------------------------------------');

  // Preflight 0：Node ≥22.5（website 临时实例 --experimental-sqlite 需要）
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 5)) {
    console.error(`  Node ${process.versions.node} < 22.5，website 临时实例需要 node:sqlite`);
    process.exit(1);
  }
  // Preflight 1：端口纪律——程序化读 ports.yaml，先查本表
  try {
    const banned = loadBannedPorts();
    const conflict = portConflict(E2E_PORT, banned);
    if (conflict) {
      console.error(`  [端口纪律 fail-loud] ${conflict}`);
      process.exit(1);
    }
  } catch (e) {
    console.error(`  [端口纪律 fail-loud] ports.yaml 不可读：${e.message}`);
    process.exit(1);
  }

  await checkpointCliFront();
  await checkpointKernelProbe();
  await checkpointPortal();

  // CP7 前置：把探活到的真实 portal 端口写入临时端口文件 + 备好 website 临时数据目录
  if (portalPort) {
    portalPortFile = path.join(AUDIT_DIR, 'cp7-portal.port');
    try {
      fs.mkdirSync(AUDIT_DIR, { recursive: true });
      fs.writeFileSync(portalPortFile, String(portalPort));
      cp7DataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'allin-cp7-data-'));
    } catch (e) {
      portalPortFile = null;
      cp7DataDir = null;
    }
  }

  await checkpointWebsite();
  await checkpointGovernanceWiring();
  await checkpointG21();
  await checkpointVerifyMount();

  // teardown：全部自拉子进程 SIGKILL（finally 语义：任何路径都执行）
  for (const { child, name } of spawnedChildren) killChild(child);
  // 清理 CP7 临时数据目录（DB/KEY），避免残留临时文件
  if (cp7DataDir) {
    try { fs.rmSync(cp7DataDir, { recursive: true, force: true }); } catch { /* 已退出 */ }
  }

  const fail = results.filter((r) => !r.ok && !r.skipped);
  const skipped = results.filter((r) => r.skipped);
  const effectivePassed = results.length - fail.length - skipped.length;
  const budgetExceeded = elapsed() > OVERALL_BUDGET_MS;
  console.log('  ----------------------------------------------------------');
  console.log(`  ${effectivePassed}/${results.length} 通过（skip ${skipped.length}）`);
  console.log(`  ALLIN_E2E_SUMMARY effectivePassed=${effectivePassed} skipped=${skipped.length} failed=${fail.length} budgetExceeded=${budgetExceeded}\n`);

  writeEvidence({
    budgetMs: elapsed(),
    budgetExceeded,
    effectivePassed,
    skipped: skipped.length,
  });
  // 判据落地（P3 §2.2 / §5.2 Go 条件 3）：
  //   ① 有效检查点 ≥5（SKIP 不凑数，CI 上 CP6 必 skip 时恰为 5，无余量也应如实呈现）；
  //   ② 60s 整体硬预算超时视为失败（此前只写进证据、不读回退出码）；
  //   ③ 任一检查点失败即红。
  const insufficient = effectivePassed < MIN_EFFECTIVE_CHECKPOINTS;
  if (insufficient) {
    console.error(`  [FAIL] 有效检查点 ${effectivePassed} < ${MIN_EFFECTIVE_CHECKPOINTS}（SKIP 不凑数）`);
  }
  if (budgetExceeded) {
    console.error(`  [FAIL] 超过 ${OVERALL_BUDGET_MS / 1000}s 整体硬预算（elapsed=${elapsed()}ms）`);
  }
  process.exit(fail.length > 0 || insufficient || budgetExceeded ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  for (const { child } of spawnedChildren) killChild(child);
  if (cp7DataDir) {
    try { fs.rmSync(cp7DataDir, { recursive: true, force: true }); } catch { /* 已退出 */ }
  }
  writeEvidence({});
  process.exit(1);
});
