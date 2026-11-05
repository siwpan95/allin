# -*- coding: utf-8 -*-
"""回归测试：WANT_ALL 支柱清单从 cordis.allin.yml 推导（ADR-0006）。

覆盖两条：
  1) 真实配置下 WANT_ALL == 四大支柱 + status 只读汇总（推导正确）；
  2) yml 写入 registry.SERVICES 白名单外的 id → import kernel.tree 即报错
     （fail-loud 提前到导入期；用子进程 + ALLIN_CONFIGS 指向伪造配置树复现）。

子进程输出含中文（RuntimeError 点名越界 id），故 subprocess.run 必须显式
encoding="utf-8"：只给 text=True 会按宿主 locale 解码，Windows CI 的 cp1252
读线程抛 UnicodeDecodeError 后 stderr 变 None，测试会以 TypeError 假红（2026-11-04）。
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

        self.assertEqual(
            WANT_ALL, ('docs', 'platform', 'preset', 'tools', 'status')
        )

    def test_unknown_id_fails_loud_at_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'cordis.allin.yml'), 'w', encoding='utf-8') as fh:
                fh.write('- name: docs\n  id: docs\n- name: evil\n  id: evil\n')
            env = dict(os.environ)
            env['ALLIN_CONFIGS'] = tmp
            result = subprocess.run(
                [sys.executable, '-c', 'import kernel.tree'],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=env, cwd=ROOT, timeout=120,
            )
            self.assertNotEqual(result.returncode, 0, '白名单外的 id 必须让导入失败')
            combined = result.stdout + result.stderr
            self.assertIn('evil', combined, '报错必须点名越界的 id')
            self.assertIn('registry.SERVICES', combined, '报错必须指向封闭白名单')

    def test_want_all_follows_config_subset(self):
        """ADR-0006 演练：WANT_ALL 必须随 yml 子集推导，而不是钉死的四元组。

        用临时配置树只登记 docs+tools 两支柱（均 ∈ registry.SERVICES 合法集），
        断言推导结果 == ('docs', 'tools') —— 证明「改 yml 即改清单」真实成立，
        这是新增第五支柱（先合法登记、再进 yml）时同一条推导路径的预演。
        """
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'cordis.allin.yml'), 'w', encoding='utf-8') as fh:
                fh.write('- name: tools\n  id: tools\n- name: docs\n  id: docs\n')
            env = dict(os.environ)
            env['ALLIN_CONFIGS'] = tmp
            result = subprocess.run(
                [sys.executable, '-c',
                 'import kernel.tree; print(repr(kernel.tree.WANT_ALL))'],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=env, cwd=ROOT, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("('tools', 'docs')", result.stdout)


if __name__ == '__main__':
    unittest.main()
