#!/usr/bin/env node
/**
 * 仓内 Python 解释器解析器 —— **唯一实现**，供治理门禁与端到端冒烟共用。
 *
 * 为什么要有这一份（2026-11-06 评估实测）：
 *   `scripts/run_all_gates.sh` 早就把解释器钉死在仓内 `.venv`（否则 g18-exceptions
 *   会因 PATH 上的便携 Python 缺 PyYAML 而报「ledger-unusable」假红）；
 *   但 `scripts/smoke_e2e.mjs` 当时写的是 `process.env.ALLIN_PYTHON || 'python'`
 *   ⇒ 默认落到 PATH 上**无 PyYAML** 的便携 3.13.14 ⇒ CP1/CP2 报
 *   `ModuleNotFoundError: No module named 'yaml'` 假红。
 *   两边各写一套解析链，是「同一份规则两处实现」——**双形态漂移的温床**
 *   （本仓记忆月账 2026-11-01 17:40 条已就「判据扩展先量化再决定」记过同类教训：
 *   两份判据必然漂移，根治办法是让两边 import 同一份）。
 *
 * 本模块即那份「同一份」：门禁与冒烟都从这里取解释器，规则只此一处。
 *
 * 解析顺序（与 run_all_gates.sh 的既有口径逐条对齐，不得分叉）：
 *   1. `ALLIN_PYTHON` 环境变量 —— 显式指定优先，CI 两侧 job 都用它；
 *   2. 仓内 `.venv`（`Scripts/python.exe` 或 `bin/python`）—— 仓库自己钉住依赖集
 *      的唯一候选，含 PyYAML，换机/换人跑结论一致；
 *   3. PATH 上的 `python3` / `python`；
 *   4. Windows 上再扫一遍 PATH 里所有 `python.exe`（系统安装版可能不在 PATHEXT 里）。
 *
 * 候选是否可用，由**它自己**跑一次探针判定，不靠猜：
 *   - 版本 ≥ 3.9（仓要求下限）；
 *   - 能 `import yaml`（PyYAML）—— 只有 g18-exceptions 与 cordis 需要它。
 *     缺 PyYAML 的解释器**不是不能用**，只是会让依赖它的那一道红；故本模块
 *     **优先选有 PyYAML 的候选**，但一个都没有时**照样返回**（宁可少跑一道，
 *     也别把已跑的门禁一起丢掉 —— 与 run_all_gates.sh 的既有取舍同口径）。
 *
 * 零第三方依赖（只用 node: 内建模块）；零盘符字面量（g01 判据：路径全部仓根相对）。
 *
 * 用法：
 *   import { resolvePython, pythonEnv } from './resolve_python.mjs';
 *   const { python, hasYaml } = resolvePython();      // → { python, hasYaml, source }
 *   // 需要解释器子进程的环境变量（子进程按 PATH 找 python 时要显式补 PATH）：
 *   const env = pythonEnv({ python, hasYaml });
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** 仓根：本文件在 <仓根>/scripts/ 下，故上一级即仓根。 */
export const REPO_ROOT = path.resolve(__dirname, '..');

/** 仓内 .venv 的两个落点（Windows / POSIX）。 */
const VENV_CANDIDATES = [
  path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
  path.join(REPO_ROOT, '.venv', 'bin', 'python'),
];

/** PATH 上按此顺序找的解释器名。 */
const PATH_NAMES = ['python3', 'python'];

/**
 * 探针：某个候选解释器能不能用？
 * @returns {{ok: boolean, hasYaml: boolean, version: string|null, reason: string}}
 */
function probe(candidate) {
  if (!candidate) {
    return { ok: false, hasYaml: false, version: null, reason: '空候选' };
  }
  // 绝对路径必须真实存在；PATH 上的裸命令名交由 spawn 解析。
  const isPathLike = candidate.includes('/') || candidate.includes('\\');
  if (isPathLike && !fs.existsSync(candidate)) {
    return { ok: false, hasYaml: false, version: null, reason: '候选不存在' };
  }
  const versionProbe = spawnSync(candidate, ['-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], {
    encoding: 'utf8',
    windowsHide: true,
  });
  if (versionProbe.error || versionProbe.status !== 0) {
    return {
      ok: false,
      hasYaml: false,
      version: null,
      reason: versionProbe.error ? String(versionProbe.error.message || versionProbe.error) : '无法执行',
    };
  }
  const version = (versionProbe.stdout || '').trim();
  const [major, minor] = version.split('.').map(Number);
  if (!(major > 3 || (major === 3 && minor >= 9))) {
    return { ok: false, hasYaml: false, version, reason: `版本 ${version} < 3.9` };
  }
  const yamlProbe = spawnSync(candidate, ['-c', 'import yaml'], { encoding: 'utf8', windowsHide: true });
  return { ok: true, hasYaml: yamlProbe.status === 0, version, reason: 'ok' };
}

/** PATH 上按名字找解释器（不落盘路径，交给 spawn 解析）。 */
function pathCandidates() {
  const out = [];
  for (const name of PATH_NAMES) out.push(name);
  return out;
}

/**
 * Windows 上再扫一遍 PATH 里所有 python.exe —— 系统安装版常不在 PATHEXT 解析里，
 * 但 `where python` 能找到它。此处不落盘绝对路径（交给 spawn 解析），故不违反 g01。
 */
function windowsPythonCandidates() {
  if (process.platform !== 'win32') return [];
  const where = spawnSync('where', ['python'], { encoding: 'utf8', windowsHide: true });
  if (where.error || where.status !== 0) return [];
  return (where.stdout || '')
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * 解析仓内 Python 解释器 —— 本仓**唯一**的解析实现。
 * @returns {{python: string, hasYaml: boolean, source: string, version: string|null}}
 */
export function resolvePython() {
  const tried = [];

  // 1) 显式指定优先 —— CI 两侧 job 都设它，且它是最强意图。
  //    ⚠ 但「显式」不等于「无条件采纳」：若它**缺 PyYAML**，则 g18-exceptions 与
  //    cordis 必红 ⇒ 继续往后找带 PyYAML 的候选（这与 run_all_gates.sh 的
  //    can_yaml「优先项」口径一致：优先而非硬性要求，显式指定的解释器仍要
  //    满足「能用」这个底线，否则宁可换一个能用的）。
  //    这条正是本轮假红的镜像情形：**有人（或某台机的 PATH）指定了一个残缺环境**，
  //    若无条件采纳，假红就会从「PATH 解析」搬到「env 指定」上继续存在。
  const explicit = process.env.ALLIN_PYTHON;
  if (explicit) {
    const r = probe(explicit);
    tried.push(`ALLIN_PYTHON=${explicit} → ${r.reason}`);
    if (r.ok && r.hasYaml) {
      return { python: explicit, hasYaml: true, source: 'ALLIN_PYTHON', version: r.version };
    }
    if (r.ok) {
      // 能跑但缺 PyYAML：留作兜底（若后面没有更好的），先记一笔。
      tried.push(`ALLIN_PYTHON 缺 PyYAML，降级继续找`);
    }
  }

  // 2) 仓内 .venv —— 仓库自己钉住依赖集的唯一候选。
  for (const cand of VENV_CANDIDATES) {
    const r = probe(cand);
    tried.push(`${path.relative(REPO_ROOT, cand) || cand} → ${r.reason}`);
    if (r.ok) {
      return { python: cand, hasYaml: r.hasYaml, source: 'venv', version: r.version };
    }
  }

  // 3) + 4) PATH 探测 —— 先按名字，再扫 Windows 的全部 python.exe。
  //    两轮都先挑「有 PyYAML」的：g18-exceptions 与 cordis 需要它，
  //    拿到它就少一道假红（与 run_all_gates.sh 的 can_yaml 优先项同口径）。
  const fallback = [];
  for (const cand of [...pathCandidates(), ...windowsPythonCandidates()]) {
    const r = probe(cand);
    tried.push(`${cand} → ${r.reason}`);
    if (r.ok) fallback.push({ python: cand, hasYaml: r.hasYaml, version: r.version });
  }
  const withYaml = fallback.find((c) => c.hasYaml);
  if (withYaml) {
    return { python: withYaml.python, hasYaml: true, source: 'path', version: withYaml.version };
  }
  if (fallback.length) {
    return {
      python: fallback[0].python,
      hasYaml: false,
      source: 'path',
      version: fallback[0].version,
    };
  }
  // 一个能跑的都没有 —— 但显式指定的那个**能用**，那就用它（缺 PyYAML 只是
  // 少跑一道门禁，不该把整批门禁丢掉：这与 run_all_gates.sh 的取舍同口径）。
  if (explicit) {
    const r = probe(explicit);
    if (r.ok) {
      return { python: explicit, hasYaml: false, source: 'ALLIN_PYTHON', version: r.version };
    }
  }

  const detail = tried.join('\n  - ');
  const err = new Error(
    `找不到可用的 Python 3.9+。已试：\n  - ${detail}\n` +
      '用 ALLIN_PYTHON=<完整解释器> 指定，或先跑 bash scripts/bootstrap.sh 建仓内 .venv。',
  );
  err.code = 'ENV_ERROR';
  throw err;
}

/**
 * 构造子进程环境变量 —— 让被 spawn 的解释器**不依赖调用者的 PATH**。
 *
 * 为什么改 PATH（2026-11-06 实测定性）：
 *   本次假红的**根因是解释器选错**（落到了 PATH 上无 PyYAML 的便携 3.13.14），
 *   不是 PATH 解析次序 —— 实测：直接用 `.venv` 解释器跑 `allin_cli.py` 即 exit 0，
 *   因为 yaml 来自该解释器自身的 site-packages，不经 PATH 查找。
 *   那为什么还要改 PATH？**防御性的一层**：若被 spawn 的脚本内部再 spawn 裸命令
 *   `python`（本仓 `vendor/cordis` 与部分包装器确有此形态），那次 spawn 会按
 *   **调用者 PATH** 找解释器 ⇒ 可能重新落回便携解释器 ⇒ 同一个坑复发。
 *   把解释器目录提到 PATH 最前，等于把「这次跑批用哪个解释器」这件事
 *   **对整棵子进程树**钉住，而不只钉住第一跳。
 *
 *   ⚠ 纪律：这一层是**加固**，不是**修复**。别把它当成假红已修的证据 ——
 *   真正的修复是 resolvePython() 选对了解释器。归因记错会让下一个人
 *   「只改 PATH 不改解析」而问题复发（本仓记忆月账 2026-11-01 21:20 条：
 *   「脚本自报成功 ≠ 写对了」；归因同理）。
 *
 * @param {{python: string, hasYaml: boolean}} resolved resolvePython() 的返回值
 * @returns {Record<string,string>} 追加了 PATH / VIRTUAL_ENV 的环境变量副本
 */
export function pythonEnv(resolved) {
  const env = { ...process.env };
  if (!resolved || !resolved.python) return env;

  // 把解释器所在目录提到 PATH 最前 —— 裸命令名 `python` 会先命中它。
  const binDir = path.dirname(resolved.python);
  const key = process.platform === 'win32' ? 'Path' : 'PATH';
  const current = env[key] || env.PATH || '';
  const parts = current.split(path.delimiter).filter(Boolean);
  const first = parts[0] === binDir ? parts : [binDir, ...parts];
  env[key] = first.join(path.delimiter);
  // Windows 上 Node 有时只认大写 PATH，POSIX 只认 PATH —— 两条都写，别赌。
  env.PATH = env[key];

  // 若选中的是仓内 .venv，附带 VIRTUAL_ENV，让依赖解析（pip / importlib）认准它。
  // .venv 的布局有两种，VIRTUAL_ENV 指的是**venv 根**本身：
  //   <repo>/.venv/Scripts/python.exe  → 上溯 2 层
  //   <repo>/.venv/bin/python          → 上溯 1 层
  // 统一做法：从解释器目录往上找 basename 为 .venv 的那层，找不到就不设
  // （猜错层级会给出指向错误目录的 VIRTUAL_ENV，比不设更坏 —— 2026-11-06 实测）。
  let probeDir = binDir;
  for (let i = 0; i < 4; i += 1) {
    if (path.basename(probeDir).toLowerCase() === '.venv') {
      env.VIRTUAL_ENV = probeDir;
      break;
    }
    const parent = path.dirname(probeDir);
    if (parent === probeDir) break;
    probeDir = parent;
  }
  return env;
}

export default resolvePython;
