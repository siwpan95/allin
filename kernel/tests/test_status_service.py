# -*- coding: utf-8 -*-
"""status 支柱服务冒烟：导入可达 + 纯文件读取/退出码语义（夹具临时目录，不碰真实数据源）。

标准库 unittest（与 test_kernel_smoke 同口径，裸 CI runner 可跑）；
夹具全部落在 tempfile 临时目录，只读纪律下绝不写仓库真实状态文件。
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from kernel.services.status_service import (  # noqa: E402
    StatusService,
    collect_status,
    exit_code_of,
)


class StatusServiceSmokeTest(unittest.TestCase):
    def test_service_importable_and_mountable(self):
        # 导入冒烟一条：SERVICES 白名单短名与实现类可解析（kernel/tests 惯例）
        from kernel.registry import SERVICES
        self.assertIn('status', SERVICES)
        self.assertTrue(SERVICES['status'].endswith('StatusService'))
        self.assertTrue(hasattr(StatusService, 'summary'))

    def test_missing_files_degrade_with_exit_zero(self):
        # 缺失=0 降级（主理人终裁）：全部事实源缺席时 report 完整、corrupt 为空
        with tempfile.TemporaryDirectory() as tmp:
            report = collect_status(
                running_json=os.path.join(tmp, 'nope.json'),
                gate_runs=os.path.join(tmp, 'nope.jsonl'),
                g21_runs=os.path.join(tmp, 'nope.jsonl'),
                portal_port=os.path.join(tmp, 'nope.port'),
            )
        self.assertEqual(report['corrupt'], [])
        self.assertFalse(report['platform']['portFilePresent'])
        self.assertFalse(report['gates'].get('readable', False))
        self.assertFalse(report['orchestration']['readable'])

    def test_g21_tail_line_and_healthy_calc(self):
        # 尾行生效 + 判红三条件（真实 schema：checkedAt/summary.drift/results[]）
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'g21-runs.jsonl')
            lines = [
                json.dumps({'type': 'g21-run', 'checkedAt': '2026-11-04T13:00:00Z',
                            'routesFile': 'tools/orchestration/routes.yaml',
                            'routesReadable': True, 'routes': [{'id': 'a'}],
                            'results': [], 'summary': {'total': 15, 'ok': 15, 'drift': 0, 'warn': 0}}),
                json.dumps({'type': 'g21-run', 'checkedAt': '2026-11-04T14:00:00Z',
                            'routesFile': 'tools/orchestration/routes.yaml',
                            'routesReadable': False, 'routes': [],
                            'results': [{'routeId': 'x', 'side': 'routes', 'severity': 'error',
                                         'reason': 'anchor missing'}],
                            'summary': {'total': 15, 'ok': 14, 'drift': 1, 'warn': 0},
                            'error': {'code': 'PARSE_FAILED', 'msg': 'yaml boom'}}),
            ]
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(lines) + '\n')
            report = collect_status(g21_runs=path,
                                    running_json=os.path.join(tmp, 'nope.json'),
                                    gate_runs=os.path.join(tmp, 'nope.jsonl'))
            o = report['orchestration']
            self.assertTrue(o['readable'])
            self.assertEqual(o['routes'], 0)          # 尾行为准（首行的 1 条被覆盖）
            self.assertEqual(o['drift'], 1)           # summary.drift 优先
            self.assertEqual(o['lastCheckAt'], '2026-11-04T14:00:00Z')   # checkedAt 字段
            self.assertFalse(o['healthy'])            # routesReadable=false + severity:error + drift>0
            self.assertEqual(o['lastCheckError']['code'], 'PARSE_FAILED')

    def test_corrupt_source_counts_for_exit_code(self):
        # 损坏=1（strict=2）：running.json 半截 JSON → corrupt 命中
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, 'running.json')
            with open(bad, 'w', encoding='utf-8') as fh:
                fh.write('{"web": {"pid": 123,"')      # 半截
            report = collect_status(running_json=bad,
                                    gate_runs=os.path.join(tmp, 'nope.jsonl'),
                                    g21_runs=os.path.join(tmp, 'nope.jsonl'))
            self.assertIn('running.json', report['corrupt'])
            self.assertEqual(exit_code_of(report['corrupt'], strict=False), 1)   # 损坏=1
            self.assertEqual(exit_code_of(report['corrupt'], strict=True), 2)    # strict=2
            self.assertEqual(exit_code_of([], strict=True), 0)                   # 缺失/健康=0

    def test_gate_summary_separates_skips(self):
        # SKIP 单列：较新的 SKIP(exit=0, skipped=true) 不得污染 lastOkAt / 逃逸率分母。
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'gate-runs.jsonl')
            lines = [
                json.dumps({'ts': '2026-11-04T10:00:00Z', 'commit': 'c1',
                            'label': 'real-ok', 'exit': 0, 'ms': 10}),
                json.dumps({'ts': '2026-11-04T11:00:00Z', 'commit': 'c1',
                            'label': 'real-red', 'exit': 1, 'ms': 10}),
                json.dumps({'ts': '2026-11-04T12:00:00Z', 'commit': 'c1',
                            'label': 'skip', 'exit': 0, 'ms': 0, 'skipped': True}),
            ]
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(lines) + '\n')
            g = collect_status(gate_runs=path,
                               running_json=os.path.join(tmp, 'nope.json'),
                               g21_runs=os.path.join(tmp, 'nope.jsonl'))['gates']
        self.assertEqual(g['skipped'], 1)
        self.assertEqual(g['failed'], 1)
        self.assertAlmostEqual(g['escapeRate'], 0.5, places=4)  # 分母 2（真跑），非 1/3
        self.assertEqual(g['inTail'], 3)
        self.assertEqual(g['lastRunAt'], '2026-11-04T12:00:00Z')  # 全量 tail 末行时间不受影响
        # 关键：lastOkAt 停在较旧的真跑绿，不被较新的 SKIP(exit=0) 行污染
        self.assertEqual(g['lastOkAt'], '2026-11-04T10:00:00Z')

    def test_gate_summary_legacy_compat_without_skipped_field(self):
        # 兼容回放：所有行都无 `skipped` 字段时，行为与改动前一致（仅多出 skipped=0）。
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'gate-runs.jsonl')
            lines = [
                json.dumps({'ts': '2026-11-04T10:00:00Z', 'exit': 0, 'label': 'a', 'ms': 10}),
                json.dumps({'ts': '2026-11-04T11:00:00Z', 'exit': 1, 'label': 'b', 'ms': 10}),
                json.dumps({'ts': '2026-11-04T12:00:00Z', 'exit': 0, 'label': 'c', 'ms': 10}),
            ]
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(lines) + '\n')
            g = collect_status(gate_runs=path,
                               running_json=os.path.join(tmp, 'nope.json'),
                               g21_runs=os.path.join(tmp, 'nope.jsonl'))['gates']
        self.assertEqual(g['skipped'], 0)
        self.assertEqual(g['failed'], 1)
        self.assertAlmostEqual(g['escapeRate'], round(1 / 3, 4), places=4)
        self.assertEqual(g['inTail'], 3)
        self.assertEqual(g['lastRunAt'], '2026-11-04T12:00:00Z')
        self.assertEqual(g['lastOkAt'], '2026-11-04T12:00:00Z')


if __name__ == '__main__':
    unittest.main()
