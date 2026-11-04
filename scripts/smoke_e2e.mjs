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
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.ALLIN_ROOT ? path.resolve(process.env.ALLIN_ROOT) : path.resolve(__dirname, '..');
const E2E_PORT = Number(process.env.ALLIN_E2E_WEBSITE_PORT || 9156);
const PY = process.env.ALLIN_PYTHON || 'python';
const AUDIT_DIR = process.env.ALLIN_GATE_AUDIT
  ? path.resolve(process.env.ALLIN_GATE_AUDIT)
  : path.join(ROOT, 'tools', 'gate', 'audit');
const EVIDENCE_FILE = path.join(AUDIT_DIR, 'e2e-runs.jsonl');
const PORTS_YAML = path.join(ROOT, 'docs', '事实源', 'ports.yaml');
const OVERALL_BUDGET_MS = 60_000;
const T0 = Date.now();

const results = [];
const runId = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14) + '-' + Math.random().toString(16).slice(2, 6);
const spawnedChildren = [];   // teardown 保证全杀（可逆效应，对齐 harness effect 登记）
let portalReused = false;

function step(id, name, ok, detail = '', skipped = false, ms = 0) {
  results.push({ id, name, ok, detail, skipped, ms });
  const mark = skipped ? 'SKIP' : (ok ? 'PASS' : 'FAIL');
  console.log(`  ${mark}  ${`[${id}] ${name}`.padEnd(44, ' ')}${detail}`);
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
  const r = await runCmd(PY, ['allin_cli.py', 'preset', 'list'], { timeoutMs: 30_000 });
  const ok = r.code === 0 && r.out.trim().length > 0;
  step('CP1', 'CLI 前门（preset list 只读）', ok,
    ok ? 'exit 0' : `cli 面 exit=${r.code} ${r.err.split('\n')[0] || '无输出'}`.slice(0, 160),
    false, Date.now() - t);
}

async function checkpointKernelProbe() {
  const t = Date.now();
  const r = await runCmd(PY, ['allin_cli.py', 'platform', 'registry-count'], { timeoutMs: 30_000 });
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
          return { port: n, child: null };
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
  child.stdout.on('data', (d) => { stdout += d.toString(); });
  child.stderr.on('data', (d) => { stdout += d.toString(); });

  // 就绪判据优先匹配启动行（含实际端口），兜底探活 /api/status
  for (let i = 0; i < 24; i += 1) {   // ≤6s
    const m = /\[allin-platform portal\] http:\/\/127\.0\.0\.1:(\d+)\//.exec(stdout);
    if (m) {
      try {
        const res = await fetchT(`http://127.0.0.1:${m[1]}/api/status`, {}, 1500);
        if (res.ok) return { port: Number(m[1]), child };
      } catch { /* 还没起来 */ }
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  return { port: null, child };
}

async function checkpointPortal() {
  const t = Date.now();
  const { port, child } = await portalDiscover();
  if (!port) {
    step('CP3', 'portal 回环探活（临时实例）', false, 'portal 面：临时实例 6s 内未就绪（启动行/探活均未命中）', false, Date.now() - t);
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
    env: { ...process.env, PORT: String(E2E_PORT), SITE_BASE_URL: BASE },
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
    const home = await fetchT(`${BASE}/`, {}, 5000);
    const homeOk = home.status === 200 && (await home.text()).includes('ALLIN LAB');
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

/** g21 判据断言：门禁 exit 0 + g21-runs.jsonl 尾行判红三条件全不成立（v3 冻结口径） */
async function checkpointG21() {
  const t = Date.now();
  const gate = path.join(ROOT, 'tools', 'gate', 'agent_parity.py');
  if (!fs.existsSync(gate)) {
    step('CP5', 'g21 漂移判据', true, 'g21 门禁尚未实施（tools/gate/agent_parity.py 不存在），skip（skip ≠ fail）', true, Date.now() - t);
    return;
  }
  const r = await runCmd(PY, [gate], { timeoutMs: 60_000 });
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
  await checkpointWebsite();
  await checkpointG21();
  await checkpointVerifyMount();

  // teardown：全部自拉子进程 SIGKILL（finally 语义：任何路径都执行）
  for (const { child, name } of spawnedChildren) killChild(child);

  const fail = results.filter((r) => !r.ok && !r.skipped);
  const skipped = results.filter((r) => r.skipped);
  console.log('  ----------------------------------------------------------');
  console.log(`  ${results.length - fail.length - skipped.length}/${results.length} 通过（skip ${skipped.length}）\n`);

  writeEvidence({
    budgetMs: elapsed(),
    budgetExceeded: elapsed() > OVERALL_BUDGET_MS,
  });
  process.exit(fail.length > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  for (const { child } of spawnedChildren) killChild(child);
  writeEvidence({});
  process.exit(1);
});
