"""
日志管理器 — 统一管理控制台输出、GUI 回调和文件写入。

功能：
    - 同时输出到多个目标（控制台/GUI 回调/文件）
    - 按错误级别自动着色
    - 自动创建带时间戳的日志文件
    - 线程安全
"""

import threading
from datetime import datetime
from typing import Optional, Callable, List
from pathlib import Path

from .error_types import ErrorCode, TestError, ErrorCategory


class LogManager:
    """多路日志管理器"""

    # 控制台颜色（Windows 10+ 支持 ANSI）
    COLORS = {
        ErrorCategory.PASS: "\033[32m",
        ErrorCategory.FAIL: "\033[31m",
        ErrorCategory.ERROR: "\033[35m",
        ErrorCategory.SKIP: "\033[33m",
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "header": "\033[1;36m",
    }

    def __init__(self, log_dir: str = "logs", use_color: bool = True):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.log_dir / f"test_run_{timestamp}.log"
        self.error_path = self.log_dir / f"test_errors_{timestamp}.log"

        self._lock = threading.RLock()
        self._gui_callbacks: List[Callable[[str], None]] = []
        self._error_callbacks: List[Callable[[TestError], None]] = []
        self._errors: List[TestError] = []
        self._log_entries: List[str] = []
        self._use_color = use_color

        self._write_to_file(self.log_path, f"=== 测试日志 === 开始时间: {datetime.now()}\n", mode='w')
        self._write_to_file(self.error_path, f"=== 错误日志 === 开始时间: {datetime.now()}\n\n", mode='w')

    # ── 回调注册 ──
    def on_log(self, callback: Callable[[str], None]):
        self._gui_callbacks.append(callback)

    def on_error(self, callback: Callable[[TestError], None]):
        self._error_callbacks.append(callback)

    # ── 写入 ──
    def _write_to_file(self, path: Path, text: str, mode: str = 'a'):
        try:
            with open(path, mode, encoding='utf-8') as f:
                f.write(text)
        except OSError:
            pass

    def _notify_gui(self, line: str):
        for cb in self._gui_callbacks:
            try:
                cb(line)
            except Exception:
                pass

    def _notify_error(self, error: TestError):
        for cb in self._error_callbacks:
            try:
                cb(error)
            except Exception:
                pass

    # ── 日志方法 ──
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {msg}"
        with self._lock:
            self._log_entries.append(line)
            self._write_to_file(self.log_path, line + "\n")
            self._notify_gui(line)

    def info(self, msg: str):
        self.log(msg, "INFO")

    def warning(self, msg: str):
        self.log(msg, "WARN")

    def debug(self, msg: str):
        self.log(msg, "DEBUG")

    def error(self, test_error: TestError):
        """记录结构化错误"""
        with self._lock:
            self._errors.append(test_error)
            self._write_to_file(self.error_path, test_error.detail() + "\n")
            line = f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {test_error.brief()}"
            self._log_entries.append(line)
            self._write_to_file(self.log_path, line + "\n")
            self._notify_gui(line)
            self._notify_error(test_error)

    def section(self, title: str):
        """打印分隔标题"""
        line = f"\n{'━'*50}\n  {title}\n{'━'*50}"
        with self._lock:
            self._log_entries.append(line)
            self._write_to_file(self.log_path, line + "\n")
            self._notify_gui(line)

    # ── 控制台输出 ──
    def print_colored(self, msg: str, category: Optional[ErrorCategory] = None, bold: bool = False):
        """带颜色的控制台输出"""
        if self._use_color:
            color = self.COLORS.get(category, "")
            style = self.COLORS["bold"] if bold else ""
            reset = self.COLORS["reset"]
            print(f"{style}{color}{msg}{reset}", flush=True)
        else:
            print(msg, flush=True)

    def print_result(self, error_code: ErrorCode, test_name: str, duration: float = 0):
        """打印单条测试结果"""
        emoji = error_code.emoji
        duration_str = f"({duration:.3f}s)" if duration > 0 else ""
        msg = f"  {emoji} {test_name:<40} {error_code.code:<10} {duration_str}"
        self.print_colored(msg, category=error_code.category)

    # ── 汇总报告 ──
    def print_summary(self):
        """控制台打印汇总报告"""
        total = len(self._errors)
        passed = sum(1 for e in self._errors if e.error_code.category == ErrorCategory.PASS)
        failed = sum(1 for e in self._errors if e.error_code.category == ErrorCategory.FAIL)
        errored = sum(1 for e in self._errors if e.error_code.category == ErrorCategory.ERROR)
        skipped = sum(1 for e in self._errors if e.error_code.category == ErrorCategory.SKIP)

        self.section("测试汇总")
        print()
        self.print_colored(f"  总计  : {total}  个测试", bold=True)
        self.print_colored(f"  通过  : {passed} ✅", ErrorCategory.PASS)
        self.print_colored(f"  失败  : {failed} ❌", ErrorCategory.FAIL)
        self.print_colored(f"  错误  : {errored} 💥", ErrorCategory.ERROR)
        self.print_colored(f"  跳过  : {skipped} ⏭️", ErrorCategory.SKIP)
        print()
        self.print_colored(f"  日志文件: {self.log_path}", bold=False)
        self.print_colored(f"  错误文件: {self.error_path}", bold=False)
        print()

        error_list = [e for e in self._errors if e.error_code.category != ErrorCategory.PASS]
        if error_list:
            self.print_colored("失败/错误详情:", ErrorCategory.ERROR, bold=True)
            for e in error_list:
                self.print_colored(f"    {e.brief()}", e.error_code.category)
            print()

    def get_summary(self) -> dict:
        """返回汇总数据（GUI 用）"""
        total = len(self._errors)
        return {
            "total": total,
            "passed": sum(1 for e in self._errors if e.error_code.category == ErrorCategory.PASS),
            "failed": sum(1 for e in self._errors if e.error_code.category == ErrorCategory.FAIL),
            "errored": sum(1 for e in self._errors if e.error_code.category == ErrorCategory.ERROR),
            "skipped": sum(1 for e in self._errors if e.error_code.category == ErrorCategory.SKIP),
            "log_path": str(self.log_path),
            "error_path": str(self.error_path),
            "errors": self._errors,
            "entries": self._log_entries,
        }
