"""facts 子系统退出码词汇 —— 单一事实源（R-08 收敛，2026-11-10）。

0 干净 / 1 有 finding（blocking）/ 2 用法错 / 3 环境错。
所有 facts 工具（cli / verify_facts / measure）从本模块 import，勿在各自文件重定义
—— 此前三处各自声明且 measure.py 漏了 EXIT_BLOCKING 档，易漂移。
"""
EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
