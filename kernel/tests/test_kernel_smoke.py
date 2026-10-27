# -*- coding: utf-8 -*-
"""kernel 冒烟测试：验证四大服务支柱可被导入、Cordis 重导出可用。

Cordis 运行时由仓库内 vendored 源码提供（kernel/_cordis_locate），本测试从仓库根运行，
确保 ``vendor/cordis/src`` 能被定位并加入 sys.path。
使用标准库 unittest（不依赖 pytest），以便裸 CI runner 也能跑。
"""
import os
import sys
import unittest

# 让仓库根（含 vendor/cordis/src）在 import 路径上
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import kernel._cordis_locate as loc  # noqa: E402
from kernel.cordis import Service  # noqa: E402


class KernelSmokeTest(unittest.TestCase):
    def test_cordis_resolvable(self):
        # vendored cordis 必须可被定位并导入
        self.assertTrue(loc.ensure(strict=False))
        self.assertIsNotNone(Service)

    def test_services_importable(self):
        # 四大支柱服务均可导入（其基类来自 kernel.cordis 重导出）
        import kernel.services.docs_service  # noqa: F401
        import kernel.services.platform_service  # noqa: F401
        import kernel.services.preset_service  # noqa: F401
        import kernel.services.tools_service  # noqa: F401


if __name__ == "__main__":
    unittest.main()
