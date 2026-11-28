# zhuangtaiji 退役记录（2026-11-28）

- 仓：`siwpan/zhuangtaiji`（Gitee），本地 `发布区/zhuangtaiji`
- 退役前 HEAD：`c796809`，21 个提交
- 归档：同目录 `zhuangtaiji-2026-11-28.bundle`（285 KB，`git bundle verify` 通过，历史完整）
- 包：PyPI `zhuangtaiji` 1.1.1 **保留**（下游 `govrule>=0.99` 依赖）
- 理由：状态机内核已被 govrule「吃掉」（`govrule order` 直接依赖 PyPI 包），
  外壳（Tkinter/Web 工作台、多范式演示）不再需要独立仓维护。
- 判据：PyPI 包可独立安装运行；bundle 可完整恢复；govrule 测试通过。
