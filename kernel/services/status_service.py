# -*- coding: utf-8 -*-
"""status 支柱服务：三面贯通只读状态汇总（纯文件事实源，零网络）。

P4-M1 · 对齐 P2 设计冻结版（deliverables/P2-后端服务与API实现.md v3）：
  - platform/data/running.json   → 平台运行态（pid 存活级 + 陈旧登记计数）
  - tools/gate/audit/gate-runs.jsonl → 门禁留痕尾部（逃逸率 / 最近运行 / 最近全绿）
  - tools/gate/audit/g21-runs.jsonl  → 编排判据尾行（路由数 / 漂移数 / 门禁自身故障）
  - platform/data/portal.port    → portal 发现文件存在性（CLI 不发 HTTP——G3 铁律：不依赖网络）

退出码纪律（主理人终裁）：**缺失=0 降级展示**（g21 未跑过属正常生命周期）；**损坏=1**；
``--strict`` 时损坏升级为 2（供 smoke:e2e 等机器消费方 fail-loud）。
「状态不好」（有漂移/逃逸）永不影响退出码——红不红由门禁判，status 不越权当门禁。

⚠️ Windows pid 存活探测**不得用 os.kill(pid, 0)**：CPython 在 Windows 上对非 CTRL 信号
一律走 TerminateProcess（探测即杀进程！），这里用 kernel32.OpenProcess 只读探测；
POSIX 平台才回退 signal 0。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys

from kernel.cordis import Service

from kernel.paths import ROOT

# ---- 文件事实源路径（全部由 ROOT 推导，零盘符；env 覆盖沿 ALLIN_GATE_RUNS 惯例）----
GATE_AUDIT_DIR = os.environ.get('ALLIN_GATE_AUDIT') or os.path.join(ROOT, 'tools', 'gate', 'audit')
GATE_RUNS = os.environ.get('ALLIN_GATE_RUNS') or os.path.join(GATE_AUDIT_DIR, 'gate-runs.jsonl')
G21_RUNS = os.environ.get('ALLIN_G21_RUNS') or os.path.join(GATE_AUDIT_DIR, 'g21-runs.jsonl')
RUNNING_JSON = os.path.join(ROOT, 'platform', 'data', 'running.json')
PORTAL_PORT = os.path.join(ROOT, 'platform', 'data', 'portal.port')

GATE_TAIL = 200          # 与 portal /api/gate-history 同口径
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _pid_alive(pid) -> bool:
    """pid 存活探测（只读，绝不误杀）。

    Windows：OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) 打开成功即存活——仅查询
    权限，不产生任何终止语义；打不开（句柄无效/已退出）即不存活。
    POSIX：os.kill(pid, 0) 是标准 signal-0 探活（EPERM 视为存活，对齐 launch.js 口径）。

    语义约定（R-02 2026-11-10 功能内聚整改）：本函数与
    platform/packages/core/src/launch.js:pidAlive 必须为同一语义（权限不足=存活，
    不存在/异常=不存活）。改动此处必须同步 Node 侧，否则 portal 与 kernel 对同一 pid
    给出不同「存活」结论。
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        try:
            k32 = ctypes.windll.kernel32
            # 2026-11-08 深度审核：未声明 restype/argtypes 时 ctypes 默认把
            # 句柄当 c_int 返回，64 位进程上会被截断 ⇒ CloseHandle 关错句柄。
            k32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.CloseHandle.argtypes = (ctypes.c_void_p,)
            k32.CloseHandle.restype = ctypes.c_int
            handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            k32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _read_json_state(path: str):
    """读单个 JSON 文件，返回 (state, data)：state ∈ missing / ok / corrupt。"""
    if not os.path.exists(path):
        return 'missing', None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return 'ok', json.load(fh)
    except (OSError, ValueError):
        return 'corrupt', None


def _read_last_json_line_state(path: str):
    """读 JSONL 尾行，返回 (state, data)：文件全坏行视为 corrupt，缺失视为 missing。"""
    if not os.path.exists(path):
        return 'missing', None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError:
        return 'corrupt', None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return 'ok', json.loads(line)
        except ValueError:
            continue        # 坏行跳过继续向前找（D1 纪律）
    return 'corrupt', None


def _gate_summary(gate_runs: str):
    if not os.path.exists(gate_runs):
        return 'missing', {}
    try:
        with open(gate_runs, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError:
        return 'corrupt', {}
    runs = []
    corrupt = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            corrupt = True      # 坏行计数，但不阻塞（与 portal 侧跳过口径一致）
            continue
        if not isinstance(rec, dict):
            # 2026-11-08 深度审核：合法 JSON 但非 dict（list/int/str）会让下面
            # r.get(...) / tail[-1].get('ts') 抛未捕获 AttributeError。
            corrupt = True
            continue
        runs.append(rec)
    tail = runs[-GATE_TAIL:]
    # SKIP 单列：仅 `skipped is True` 才算 SKIP；旧留痕无该字段按真跑兼容回放。
    # SKIP 不计入 failed / escapeRate / lastOkAt；inTail 与 lastRunAt 仍按全量 tail。
    tail_real = [r for r in tail if r.get('skipped') is not True]
    failed = sum(1 for r in tail_real if r.get('exit') != 0)
    ok_runs = [r for r in tail_real if r.get('exit') == 0]
    summary = {
        'readable': True,
        'inTail': len(tail),
        'failed': failed,
        'skipped': len(tail) - len(tail_real),
        'escapeRate': round(failed / len(tail_real), 4) if tail_real else 0,
        'lastRunAt': tail[-1].get('ts') if tail else None,
        'lastOkAt': ok_runs[-1].get('ts') if ok_runs else None,
    }
    # 只有「整份无一行可解析」才算 corrupt；个别坏行容忍（与 portal 口径一致）
    return ('corrupt' if corrupt and not runs else 'ok'), summary


def _platform_summary(running_json: str = RUNNING_JSON, portal_port: str = PORTAL_PORT):
    """running.json 投影 + portal.port 存在性。返回 (state, summary)。"""
    state, data = _read_json_state(running_json)
    if state == 'corrupt':
        # 原子写备份（launch.js 现制）：主文件损坏回退 .bak，仍坏才报 corrupt
        bak_state, bak = _read_json_state(running_json + '.bak')
        if bak_state == 'ok' and isinstance(bak, dict):
            state, data = 'ok', bak
        else:
            return 'corrupt', {}
    entries = data if isinstance(data, dict) else {}
    alive = {eid: rec for eid, rec in entries.items()
             if isinstance(rec, dict) and _pid_alive(rec.get('pid'))}
    stale = len(entries) - len(alive)
    port = None
    # R-01（2026-11-10 收尾）：kernel 面端口发现读取——G3 铁律零网络，仅判存在性 + 尝试 int，
    # 不探活、不校验 1-65535（那是 website 三态降级的职责）。残留垃圾文件 → 视同未发现。
    # 与 website（1-65535 触发降级）/ cli（探活兜底）/ harness（port>0）口径有意不同，不可强行统一。
    if os.path.exists(portal_port):
        try:
            with open(portal_port, 'r', encoding='utf-8') as fh:
                port = int(fh.read().strip())
        except (OSError, ValueError):
            port = None         # 残留垃圾文件 → 视同未发现（与 website 代理口径一致）
    summary = {
        'readable': state == 'ok',
        'portFile': port,
        'portFilePresent': port is not None,
        'total': len(entries),
        'running': len(alive),
        'stale': stale,
        'runningIds': sorted(alive.keys()),
    }
    return state, summary


def _orchestration_summary(g21_runs: str = G21_RUNS):
    """g21-runs.jsonl 尾行投影。

    对齐 agent-app-engineer 落盘的真实 schema（宽容兼容 P2 草案字段）：
      真实行：{type:'g21-run', checkedAt, commit, routesFile, routesReadable,
              routes[], results[], summary{total,ok,drift,warn}, error?}
      时间取 checkedAt（兼容 lastCheckAt）；漂移计数优先 summary.drift；
      findings = drift[] ∪ results[]（severity=error 参与判红）。
    """
    state, data = _read_last_json_line_state(g21_runs)
    data = data if isinstance(data, dict) else {}
    findings = [d for d in (data.get('drift') or []) if isinstance(d, dict)]
    findings += [d for d in (data.get('results') or []) if isinstance(d, dict)]
    summary_blk = data.get('summary') if isinstance(data.get('summary'), dict) else {}
    drift_count = summary_blk['drift'] if isinstance(summary_blk.get('drift'), int) else len(findings)
    err = data.get('error') if isinstance(data.get('error'), dict) else None
    summary = {
        'readable': state == 'ok',
        'routes': len(data['routes']) if isinstance(data.get('routes'), list) else 0,
        'drift': drift_count,
        'lastCheckAt': data.get('checkedAt') or data.get('lastCheckAt'),
        'lastCheckError': {'code': str(err.get('code') or 'GATE_CRASHED'),
                           'msg': str(err.get('msg') or '')[:500]} if err else None,
        'healthy': not (data.get('routesReadable') is False
                        or any(d.get('severity') == 'error' for d in findings)
                        or drift_count > 0) if state == 'ok' else False,
    }
    return state, summary


def collect_status(running_json: str = RUNNING_JSON, gate_runs: str = GATE_RUNS,
                   g21_runs: str = G21_RUNS, portal_port: str = PORTAL_PORT) -> dict:
    """聚合三面只读状态。返回 report；损坏源记录在 report['corrupt'] 供退出码判定。"""
    plat_state, platform = _platform_summary(running_json, portal_port)
    gate_state, gates = _gate_summary(gate_runs)
    orch_state, orchestration = _orchestration_summary(g21_runs)
    corrupt = [name for name, st in (('running.json', plat_state),
                                     ('gate-runs.jsonl', gate_state),
                                     ('g21-runs.jsonl', orch_state)) if st == 'corrupt']
    return {'platform': platform, 'gates': gates, 'orchestration': orchestration, 'corrupt': corrupt}


def exit_code_of(corrupt, strict: bool) -> int:
    """退出码纪律（主理人终裁）：缺失已在此前归为空 corrupt → 0；损坏=1；strict 损坏=2。"""
    if corrupt:
        return 2 if strict else 1
    return 0


class StatusService(Service):
    """allin status 子命令实现（第五支柱；只读，零网络，零子进程）。"""

    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'status')

    def __cordis_init__(self):
        return None

    def summary(self, as_json: bool = False, strict: bool = False) -> int:
        """打印状态汇总并返回退出码（缺失=0 降级；损坏=1；strict 时损坏=2）。"""
        report = collect_status()
        if as_json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            p = report['platform']
            if p.get('portFilePresent'):
                plat = f'portal 端口文件存在（{p["portFile"]}，待探活）'
            else:
                plat = 'portal 未启动（无端口发现文件）'
            plat += f'；运行中项目 {p["running"]}/{p["total"]}'
            if p.get('stale'):
                plat += f'；陈旧登记 {p["stale"]} 条'
            print(f'平台运行    {plat}')
            g = report['gates']
            if g.get('readable'):
                verdict = '全绿' if g.get('failed') == 0 else f'失败 {g["failed"]} 次'
                print(f'门禁健康    近 {g["inTail"]} 次逃逸率 {g["escapeRate"]:.1%}（{verdict}）；'
                      f'最近运行 {g["lastRunAt"]}；上次全绿 {g["lastOkAt"]}')
            else:
                print('门禁健康    留痕文件尚未生成（跑 scripts/run_all_gates.sh 后可见）')
            o = report['orchestration']
            if o.get('readable'):
                line = (f'{o["routes"]} 条路由 · 漂移 {o["drift"]} · 判据时间 {o["lastCheckAt"]}')
                if o.get('lastCheckError'):
                    line += f' · 门禁故障 {o["lastCheckError"]["code"]}: {o["lastCheckError"]["msg"]}'
                print(f'编排台账    {line}')
            else:
                print('编排台账    g21 判据产物尚未生成（跑 agent-parity 门禁后可见）')
            if report['corrupt']:
                print(f'数据源损坏  {", ".join(report["corrupt"])}'
                      + ('（--strict 下将以退出码 2 结束）' if not strict else ''))
        # 退出码：缺失=0（降级是正常生命周期）；损坏=1；strict 损坏=2（fail-loud 终裁）
        return exit_code_of(report['corrupt'], strict)
