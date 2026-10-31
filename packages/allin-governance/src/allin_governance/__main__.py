"""让 `python -m allin_governance` 等价于 `allin-governance`。

存在的理由：没装入口点脚本时（源码树里直接跑、CI 里临时验一次），
`python -m` 是最短的那条路，而不是先 `pip install -e .` 再说。
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
