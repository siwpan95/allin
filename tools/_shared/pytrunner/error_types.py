"""
错误类型定义 — 明确分类测试中可能出现的所有错误。

设计原则：
    每种错误类型都有唯一的 name/code/emoji，方便日志筛选和 GUI 渲染。
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class ErrorCategory(Enum):
    """错误大类"""
    PASS = "通过"
    FAIL = "失败"
    ERROR = "错误"
    SKIP = "跳过"


class ErrorCode(Enum):
    """错误细类 — 每种错误有唯一标识码"""

    # ── 通过 ──
    TEST_PASS = ("PASS-000", "测试通过", ErrorCategory.PASS, "✅")

    # ── 断言失败 ──
    ASSERT_EQUAL = ("FAIL-001", "断言相等失败：期望值与实际值不符", ErrorCategory.FAIL, "❌")
    ASSERT_TRUE = ("FAIL-002", "断言为真失败：表达式求值为 False", ErrorCategory.FAIL, "❌")
    ASSERT_FALSE = ("FAIL-003", "断言为假失败：表达式求值为 True", ErrorCategory.FAIL, "❌")
    ASSERT_IN = ("FAIL-004", "断言包含失败：值不在集合中", ErrorCategory.FAIL, "❌")
    ASSERT_RAISES = ("FAIL-005", "断言异常失败：未抛出预期异常", ErrorCategory.FAIL, "❌")
    UNEXPECTED_RESULT = ("FAIL-006", "意外结果：返回值与预期不符", ErrorCategory.FAIL, "❌")

    # ── 运行时错误 ──
    RUNTIME_ERROR = ("ERR-001", "运行时错误", ErrorCategory.ERROR, "💥")
    ATTRIBUTE_ERROR = ("ERR-002", "属性错误：对象没有该属性或方法", ErrorCategory.ERROR, "💥")
    TYPE_ERROR = ("ERR-003", "类型错误：操作数类型不匹配", ErrorCategory.ERROR, "💥")
    VALUE_ERROR = ("ERR-004", "值错误：参数值不合法", ErrorCategory.ERROR, "💥")
    KEY_ERROR = ("ERR-005", "键错误：字典中不存在该键", ErrorCategory.ERROR, "💥")
    INDEX_ERROR = ("ERR-006", "索引错误：序列索引越界", ErrorCategory.ERROR, "💥")
    ZERO_DIVISION = ("ERR-007", "零除错误：除数为零", ErrorCategory.ERROR, "💥")
    NAME_ERROR = ("ERR-008", "名称错误：变量未定义", ErrorCategory.ERROR, "💥")
    OS_ERROR = ("ERR-009", "系统错误：操作系统相关异常", ErrorCategory.ERROR, "💥")
    IO_ERROR = ("ERR-010", "IO 错误：文件读写失败", ErrorCategory.ERROR, "💥")
    RECURSION_ERROR = ("ERR-011", "递归错误：递归深度超限", ErrorCategory.ERROR, "💥")
    MEMORY_ERROR = ("ERR-012", "内存错误：内存不足", ErrorCategory.ERROR, "💥")

    # ── 语法/导入错误 ──
    SYNTAX_ERROR = ("ERR-101", "语法错误：代码无法解析", ErrorCategory.ERROR, "📝")
    IMPORT_ERROR = ("ERR-102", "导入错误：模块不存在或无法加载", ErrorCategory.ERROR, "📝")
    INDENTATION_ERROR = ("ERR-103", "缩进错误：代码缩进不正确", ErrorCategory.ERROR, "📝")
    MODULE_NOT_FOUND = ("ERR-104", "模块未找到：依赖缺失", ErrorCategory.ERROR, "📝")

    # ── 超时错误 ──
    TIMEOUT_ERROR = ("ERR-201", "超时错误：执行超过时间限制", ErrorCategory.ERROR, "⏱️")

    # ── 测试框架错误 ──
    SETUP_ERROR = ("ERR-301", "准备阶段错误：setUp 方法异常", ErrorCategory.ERROR, "🔧")
    TEARDOWN_ERROR = ("ERR-302", "清理阶段错误：tearDown 方法异常", ErrorCategory.ERROR, "🔧")
    FIXTURE_ERROR = ("ERR-303", "夹具错误：测试数据准备失败", ErrorCategory.ERROR, "🔧")

    # ── 跳过 ──
    TEST_SKIP = ("SKIP-000", "测试跳过", ErrorCategory.SKIP, "⏭️")
    SKIP_CONDITION = ("SKIP-001", "条件跳过：前置条件不满足", ErrorCategory.SKIP, "⏭️")
    SKIP_PLATFORM = ("SKIP-002", "平台跳过：当前平台不支持", ErrorCategory.SKIP, "⏭️")

    # ── 测试探针 ──（快速冒烟检测）
    PROBE_PASS = ("PROBE-PASS", "探针通过：检测点正常", ErrorCategory.PASS, "📍")
    PROBE_FAIL = ("PROBE-FAIL", "探针失败：检测点异常", ErrorCategory.FAIL, "📍")
    PROBE_SKIP = ("PROBE-SKIP", "探针跳过：条件不满足", ErrorCategory.SKIP, "📍")

    # ── 未知 ──
    UNKNOWN_ERROR = ("ERR-999", "未知错误：无法归类的异常", ErrorCategory.ERROR, "❓")

    @classmethod
    def from_exception(cls, exc: Exception) -> "ErrorCode":
        """根据异常类型自动匹配 ErrorCode"""
        mapping = {
            AssertionError: cls.ASSERT_EQUAL,
            AttributeError: cls.ATTRIBUTE_ERROR,
            TypeError: cls.TYPE_ERROR,
            ValueError: cls.VALUE_ERROR,
            KeyError: cls.KEY_ERROR,
            IndexError: cls.INDEX_ERROR,
            ZeroDivisionError: cls.ZERO_DIVISION,
            NameError: cls.NAME_ERROR,
            OSError: cls.OS_ERROR,
            IOError: cls.IO_ERROR,
            RecursionError: cls.RECURSION_ERROR,
            MemoryError: cls.MEMORY_ERROR,
            SyntaxError: cls.SYNTAX_ERROR,
            ImportError: cls.IMPORT_ERROR,
            IndentationError: cls.INDENTATION_ERROR,
            ModuleNotFoundError: cls.MODULE_NOT_FOUND,
            TimeoutError: cls.TIMEOUT_ERROR,
        }
        return mapping.get(type(exc), cls.UNKNOWN_ERROR)

    @property
    def code(self) -> str:
        return self.value[0]

    @property
    def description(self) -> str:
        return self.value[1]

    @property
    def category(self) -> ErrorCategory:
        return self.value[2]

    @property
    def emoji(self) -> str:
        return self.value[3]


@dataclass
class TestError:
    """单条测试错误记录"""
    error_code: ErrorCode
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    traceback: Optional[str] = None
    test_name: str = ""
    file_path: str = ""
    line_number: int = 0

    def brief(self) -> str:
        """一行摘要"""
        loc = f"{self.file_path}:{self.line_number}" if self.file_path else ""
        return f"[{self.error_code.code}] {self.error_code.emoji} {self.message}  {loc}"

    def detail(self) -> str:
        """完整详情"""
        lines = [
            f"{'='*60}",
            f"  错误码 : {self.error_code.code}",
            f"  类型   : {self.error_code.description}",
            f"  时间   : {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"  测试   : {self.test_name}",
        ]
        if self.file_path:
            lines.append(f"  位置   : {self.file_path}:{self.line_number}")
        lines.append(f"  消息   : {self.message}")
        if self.traceback:
            lines.append(f"  堆栈   :\n{self.traceback}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)
