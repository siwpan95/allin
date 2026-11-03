# -*- coding: utf-8 -*-
"""回归测试：watchdog 缺席时 cordis（含 hmr）必须仍可导入。

背景（2026-11-04 工程审查实测缺陷）：vendor/cordis/src/cordis/hmr.py 曾在
``except ImportError: FileSystemEventHandler = None`` 之后无条件执行
``class _WatchHandler(FileSystemEventHandler)`` —— watchdog 缺席时该行抛
``TypeError: NoneType takes no arguments``，连锁导致 ``from kernel.cordis
import Service`` 失败，kernel 在零依赖环境下完全不可导入。

本测试在子进程中用 meta_path finder 屏蔽 watchdog（无论本机是否装了它都能
复现"缺席"分支），再导入 kernel.cordis，验证降级路径真实可用。
使用标准库 unittest（不依赖 pytest），以便裸 CI runner 也能跑。
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class NoWatchdogImportTest(unittest.TestCase):
    def test_kernel_cordis_importable_without_watchdog(self):
        blocker = (
            "import importlib.abc, importlib.machinery, sys\n"
            "class _BlockWatchdog(importlib.abc.MetaPathFinder):\n"
            "    def find_spec(self, fullname, path=None, target=None):\n"
            "        if fullname == 'watchdog' or fullname.startswith('watchdog.'):\n"
            "            raise ImportError('watchdog blocked for regression test')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _BlockWatchdog())\n"
            "for _m in [m for m in sys.modules if m == 'watchdog' or m.startswith('watchdog.')]:\n"
            "    del sys.modules[_m]\n"
            "import cordis.hmr as hmr\n"
            "assert hmr.WATCHDOG_AVAILABLE is False, 'watchdog should be blocked'\n"
            "from kernel.cordis import Service\n"
            "assert Service is not None\n"
            "print('OK: cordis imports cleanly without watchdog')\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [ROOT, os.path.join(ROOT, "vendor", "cordis", "src")]
            + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        # 确保子进程拿不到已安装的 watchdog：-S 跳过 site-packages 不可取（会连 vendor 定位一起破坏），
        # 这里靠 meta_path 屏蔽即可，与安装与否无关。
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            capture_output=True, text=True, env=env, timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            "kernel/cordis must import without watchdog.\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
        )
        self.assertIn("OK: cordis imports cleanly without watchdog", result.stdout)


if __name__ == "__main__":
    unittest.main()
