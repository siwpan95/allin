# allin 统一调度内核（cordis 编排）：docs/platform/preset/status/tools 四大支柱。
#
# ── stdio 编码钉死（2026-11-12）────────────────────────────────────────
# 为什么在这里钉，而不是逐个服务里钉：
#   kernel 是**库**——CI 的 `unittest discover -s kernel/tests` 与
#   `pytest tests/test_p2_*` 都**直接 import kernel.services.***，不经 CLI 入口。
#   四个服务（docs / platform / preset / status / tools）都有中文 print，
#   逐个加 reconfigure = 同一份规则抄五遍（判据/规则「只有一份」的同源纪律）。
#   ⇒ 钉在**包入口**：任何 `import kernel.*` 都会先执行本文件，一处覆盖全部。
#
# 为什么必须钉：
#   Windows 控制台缺省 cp1252（中文机 cp936），中文 print 直接
#   UnicodeEncodeError —— 实测 `kernel/services/preset_service.py:83` 的
#   `print(f'{verb} preset: ...')` 里 `【`（U+3010）即崩：
#     UnicodeEncodeError: 'charmap' codec can't encode character '\u3010'
#   unittest 无输出捕获（直写控制台），pytest 的 fd 捕获也不改 sys.stdout 的编码
#   ⇒ 两条路径都会崩，且**与代码逻辑无关**（本机 UTF-8 控制台全绿）。
#
# 与 `scripts/run_all_gates.sh:74` 的告诫不冲突：
#   那条禁的是 `export PYTHONIOENCODING`（**环境变量会被 subprocess 继承**，
#   会把「测试 spawn 的子进程」的解码口径一起改掉 ⇒ 旧测试按 cp1252 解码 UTF-8
#   中文而崩）。本处是 `reconfigure`（只改**本进程**的 stdio 编码，
#   **不传给子进程**）—— 两者作用面完全不同。
#
# reconfigure 是 3.7+ API；被 pytest 捕获/替换的流可能没有该方法 ⇒ 静默跳过。
import sys as _sys

for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
