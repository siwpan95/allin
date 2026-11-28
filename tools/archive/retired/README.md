# 退役仓归档（retired）

这里放**已退役仓**的 git bundle 与退役记录。约定：

- 每个仓一对文件：`<name>-<date>.bundle`（`git bundle verify` 通过、complete history）+ `<name>-RETIRE.md`；
- 退役必须同时满足：包仍在被消费（如 PyPI 保留）、bundle 可恢复、下游测试通过；
- 先例：`py_test_runner`（2026-11-24）、`zhuangtaiji`（2026-11-28，状态机被 govrule 吃掉，仅留 PyPI）。

## 索引

| 仓 | 日期 | 去向 | 记录 |
|---|---|---|---|
| zhuangtaiji | 2026-11-28 | PyPI 1.1.1（govrule 依赖） | `zhuangtaiji-RETIRE.md` |
