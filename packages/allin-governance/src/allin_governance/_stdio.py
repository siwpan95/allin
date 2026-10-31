"""控制台编码兜底：把 stdout/stderr 固定成 UTF-8。

**为什么需要这个模块**（2026-10-31 真实 CI 事故，Windows runner）：

`allin-governance init` 在 Windows 上直接崩：

    UnicodeEncodeError: 'charmap' codec can't encode characters in position 2-3

原因不是代码错了，而是**输出的默认编码跟着终端走**：GitHub Actions 的
`windows-latest` 控制台是 cp1252，而这套工具的每一行提示都是中文。
同一份代码在 Linux 上绿、在 Windows 上崩，只因为后者默认编码不是 UTF-8。

这**不是「CI 环境问题」**：一个面向中文用户的工具，必须在任何默认编码的终端上
都能把话说出来，否则它在二分之一的机器上等于不可用。而且这类崩溃发生在
**打印阶段**，会让一个已经成功完成的动作（文件都写好了）以非 0 退出 ——
用户看到「失败」，磁盘上却是成功的，那是最坏的一种信号。

`errors="replace"` 而不是 `strict`：宁可显示成 `?`，也不要因为一个字符
把整条命令变成失败。真正丢掉的信息可以在日志文件里看，但退出码不能说谎。
"""

from __future__ import annotations

import sys

__all__ = ["configure"]


def configure() -> None:
    """把标准输出/错误重配为 UTF-8（幂等，可重复调用）。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # 被测试替身或非文本流替换过，跳过
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # 已分离或不可重配的流
            pass
