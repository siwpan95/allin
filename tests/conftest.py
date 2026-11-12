"""pytest 全局夹具（本目录）。

**只做一件事**：把子进程的文本输出编码钉死为 UTF-8。

为什么需要：`tests/` 下多个用例用 `subprocess.run(..., text=True, encoding="utf-8")`
调起本仓 CLI / 门禁脚本，而子进程在没有 `PYTHONIOENCODING` 时按**本机控制台代码页**
输出（Windows 中文默认为 GBK/936）。于是子进程写 GBK 字节、父进程按 UTF-8 解码，
断言里的中文子串全部变乱码 —— 表现为「测试在本机红、在 UTF-8 控制台的机器绿」，
属跨机可移植性缺陷而非判据失效（2026-11-11 本机实测：
`test_broken_auth_cli_nonzero` 期望 `不得判绿`，实际解码成 `\ufffd\ufffd`）。

放在 conftest 而非逐个用例：`os.environ` 会被 `subprocess` 继承，是**单一注入点**，
新增用例无需重复声明；也避免给每个调用点散落一份 `env=` 拼装（与「判据只有一份」同源）。
`setdefault` 语义：调用方已显式指定时不自作主张。
"""

import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
