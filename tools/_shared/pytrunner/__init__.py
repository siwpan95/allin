"""探针式测试内核（上提自 py_test_runner / PyPI `pytrunner`）。

来源与许可证
------------
- 原仓：https://gitee.com/siwpan/py_test_runner （MIT）
- PyPI：`pytrunner` 1.0.0
- 上提时点：2026-11-24 ｜ 范围：`core/error_types.py`、`core/log_manager.py`、
  `core/test_probe.py` 三个文件原样迁入（本仓 MIT-0 与原 MIT 兼容，保留原版权）。
- 未迁：`main.py`（852 行的 CLI/GUI 壳）、`gui/`、`probes/` 具体探针集、`console/` ——
  这些是它作为独立工具的外壳，本仓只用它的**探针内核**（Probe / ProbeManager）。

为什么上提而不是依赖 pytrunner
------------------------------
repocheck 要新增「这个项目的测试是否真的能跑」这类判据。自己重写一套探针注册与
汇总逻辑没必要 —— py_test_runner 已经把这层抽象做完了（Probe 可注册、可按分类/标签筛选、
可批量跑并汇总 TestError）。上提内核后，规则实现只需定义 Probe 子类。

为什么不 `pip install pytrunner` 而是内联
----------------------------------------
全哥明确「跨仓依赖改内联」。依赖一个自己维护的 PyPI 包来做门禁判据，等于给门禁引入了
一个「对方版本变了判据就变」的隐形变量 —— 门禁最不该有这种东西。
"""
