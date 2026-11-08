# -*- coding: utf-8 -*-
"""WJ-01 回归测试：preset apply() 双态可观测 + fail-loud。

覆盖：
  - 不存在的 preset ⇒ FileNotFoundError（fail-loud，不静默吞掉）。
  - dry_run=True（默认）⇒ 返回结构化结果 ok=True / applied=False / dry_run=True。
  - dry_run=False（CLI --yes）⇒ 真实落地逻辑未实现，返回 ok=False（绝不静默返回 None
    假装成功），CLI（allin_cli.dispatch）据此映射非零退出码，消除「--yes 零动作」假绿。
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import kernel.services.preset_service as ps  # noqa: E402


class _DummyReflect:
    def provide(self, *args, **kwargs):
        return None


class _DummyCtx:
    def __init__(self):
        self.reflect = _DummyReflect()


class PresetApplyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="preset-apply-")
        self._orig = ps.PRESET_DIR
        ps.PRESET_DIR = self._tmp

    def tearDown(self):
        ps.PRESET_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _make(self):
        return ps.PresetService(_DummyCtx())

    def test_missing_preset_raises(self):
        svc = self._make()
        with self.assertRaises(FileNotFoundError):
            svc.apply("does-not-exist", dry_run=True)

    def test_dry_run_true_returns_ok(self):
        os.makedirs(os.path.join(self._tmp, "demo"))
        res = self._make().apply("demo", dry_run=True)
        self.assertIsInstance(res, dict)
        self.assertTrue(res["ok"])
        self.assertFalse(res["applied"])
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["name"], "demo")

    def test_dry_run_false_not_implemented_fail_loud(self):
        os.makedirs(os.path.join(self._tmp, "demo"))
        res = self._make().apply("demo", dry_run=False)
        self.assertIsInstance(res, dict)
        self.assertFalse(res["ok"])
        self.assertFalse(res["applied"])
        self.assertFalse(res["dry_run"])
        self.assertIn("WJ-01", res["reason"])


if __name__ == "__main__":
    unittest.main()
