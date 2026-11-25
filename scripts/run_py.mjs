#!/usr/bin/env node
/**
 * run_py.mjs —— 用**仓内唯一解析链**跑一个 Python 脚本，供 `package.json` 的 npm 脚本使用。
 *
 * 为什么需要这一层（2026-11-25 实测）：
 *   `package.json` 里 10 个脚本写的是裸 `python`。裸名由 PATH 决定，而 PATH 上的解释器
 *   因机而异：本机是便携 3.13（**没有** `allin_governance`）⇒ `npm run check` 第一步
 *   `check:docs` 直接 `ModuleNotFoundError` ⇒ `&&` 串联下**后面每一步都不执行**，
 *   人会以为「门禁挂了」，其实只是入口找不到对的那个解释器。
 *   这不是新问题：2026-11-06 就把解析抽成了 `scripts/resolve_python.mjs`（记忆月账
 *   当日 05:45 条：「同一规则两处实现必然漂移……修法不是两边各补一行，而是抽出唯一
 *   实现 + 两边共用」），`run_all_gates.sh` 与 `smoke_e2e.mjs` 都接了，
 *   **`package.json` 这一层漏了**。本文件补的就是这个漏接点。
 *
 * 纪律：
 *   * **不自己解析解释器**。一律 `resolvePython()`，规则只此一处；本文件只做
 *     「拿到路径 → spawn → 透传退出码」三件事。自己再写一套解析 = 又多一个真相源。
 *   * 用 `pythonEnv()` 而不是裸 env：它把解释器所在目录提到 PATH 最前，
 *     让脚本内部的子进程（例如门禁再调 `python`）也命中同一个解释器。
 *   * 退出码透传（`spawn` 的 status），不加解释、不吞 0 —— 调用方（npm / CI）看到的就是
 *     被判脚本的结论。解释器起不来 = exit 3（环境错），不伪装成 1（判据红）。
 *
 * 用法（package.json）：
 *   "check:docs": "node scripts/run_py.mjs tools/gate/docs_index.py"
 *   "check:ps1":  "node scripts/run_py.mjs tools/gate/check_ps1_bom.py --root ."
 * 手工：
 *   node scripts/run_py.mjs tools/gate/agent_parity.py
 *   node scripts/run_py.mjs --print tools/gate/agent_parity.py   # 只打印选中的解释器
 *
 * 零第三方依赖（只用 node: 内建模块）；零盘符字面量（g01 判据）。
 */
import { spawnSync } from 'node:child_process';
import { resolvePython, pythonEnv } from './resolve_python.mjs';

const argv = process.argv.slice(2);

if (argv.length === 0 || argv[0] === '--help' || argv[0] === '-h') {
  console.error('usage: node scripts/run_py.mjs [--print] <script.py> [args...]');
  process.exit(2);
}

const printOnly = argv[0] === '--print';
const rest = printOnly ? argv.slice(1) : argv;
const [script, ...scriptArgs] = rest;

if (!script) {
  console.error('usage: node scripts/run_py.mjs [--print] <script.py> [args...]');
  process.exit(2);
}

const resolved = resolvePython();
if (!resolved || !resolved.python) {
  console.error('[run_py] 找不到可用的 Python —— 设 ALLIN_PYTHON，或建仓内 .venv（bash scripts/bootstrap.sh）');
  process.exit(3);
}

if (printOnly) {
  console.log(resolved.python);
  process.exit(0);
}

// 一行到 stderr：让「这次到底用哪个解释器跑的」可审计（stdout 留给被判脚本）。
// 不静默回退是关键 —— 环境坏门（跑了但环境错被吞成 0）正是本仓 ADR-0011 §D3 要防的形态。
console.error(`[run_py] python ${resolved.version || '?'} via ${resolved.source}` +
  `${resolved.hasYaml ? '' : '（缺 PyYAML）'} -> ${script}`);

const r = spawnSync(resolved.python, [script, ...scriptArgs], {
  stdio: 'inherit',
  env: pythonEnv(resolved),
});

if (r.error) {
  console.error(`[run_py] 无法启动解释器 ${resolved.python}：${r.error.message}`);
  process.exit(3);
}
if (r.signal) {
  console.error(`[run_py] 解释器被信号 ${r.signal} 终止`);
  process.exit(3);
}
process.exit(r.status ?? 1);
