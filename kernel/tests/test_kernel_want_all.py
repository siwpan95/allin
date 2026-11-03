# -*- coding: utf-8 -*-
"""回归测试：WANT_ALL 支柱清单从 cordis.allin.yml 推导（ADR-0006）。

覆盖两条：
  1) 真实配置下 WANT_ALL == 四大支柱（推导正确）；
  2) yml 写入 registry.SERVICES 白名单外的 id → import kernel.tree 即报错
     （fail-loud 提前到导入期；用子进程 + ALLIN_CONFIGS 指向伪造配置树复现）。
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WantAllDerivationTest(unittest.TestCase):
    def test_want_all_derived_from_real_config(self):
        from kernel.tree import WANT_ALL

        self.assertEqual(WANT_ALL, ('docs', 'platform', 'preset', 'tools'))

    def test_unknown_id_fails_loud_at_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'cordis.allin.yml'), 'w', encoding='utf-8') as fh:
                fh.write('- name: docs\n  id: docs\n- name: evil\n  id: evil\n')
            env = dict(os.environ)
            env['ALLIN_CONFIGS'] = tmp
            result = subprocess.run(
                [sys.executable, '-c', 'import kernel.tree'],
                capture_output=True, text=True, env=env, cwd=ROOT, timeout=120,
            )
            self.assertNotEqual(result.returncode, 0, '白名单外的 id 必须让导入失败')
            combined = result.stdout + result.stderr
            self.assertIn('evil', combined, '报错必须点名越界的 id')
            self.assertIn('registry.SERVICES', combined, '报错必须指向封闭白名单')


if __name__ == '__main__':
    unittest.main()
