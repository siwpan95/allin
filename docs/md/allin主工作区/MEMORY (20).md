# 项目长期记忆 — allin_engine / dwarf_scrolls

## 引擎与项目位置（关键）
- 真实引擎包 `allin_engine` 位于 `D:\allin\allin_engine`（其下 `__init__.py`、`core/`、`world/`、`systems/`、`render/`、`ai/`）。
- 游戏项目位于 `D:\allin\example\dwarf_scrolls`。`D:\allin\example` 是【项目根】，不是引擎。

## 引擎引导正确姿势
- 正确：`sys.path.insert(0, r"D:\allin")` 然后 `import allin_engine`（真实引擎）。
- 错误（已废弃）：用 importlib 把 `D:\allin\example` 注册成 `allin_engine` 别名。会让 `allin_engine.core` 指向项目的 core（含项目私有的 paths.get_fonts_dir），并掩盖 example/__init__.py 实为引擎 __init__ 副本的问题。
- `ensure_engine_loaded()` 返回 None（与既有 test_bootstrap 一致）。

## example/__init__.py 必须保持「项目根标记」
- 曾是被复制的引擎 __init__（import get_fonts_dir 等），导致 `import example` 失败、pytest 以 `example.dwarf_scrolls.*` 收集时 51 测试全 collection error。
- 现改为仅 docstring 项目标记。不要在 example/__init__.py 里写引擎初始化逻辑。

## 渲染 / GUI 约束
- ConsoleRenderer 缓冲 `self._buf`：`List[List[(char, fg, bg, attrs)]]`；`flush()` 读后清空缓冲 → GUI 路径须先读 `_buf` 再绘制（render_to_buffer 不 flush）。
- 引擎自带 Tkinter 层：render/gui_base.py（BaseWindow/StatusPanel/Styles）、render/widgets.py（GameLogPanel/StatusBar/QuickCommandBar/GameInputBar/GameWindow）。
- 沙箱托管 Python 3.14.4 无 tkinter、无显示器 → GUI 窗口（DwarfScrollsWindow）只能在用户 Windows 上跑；沙箱只能做无头逻辑 + py_compile 验证。

## 测试
- 测试在 `dwarf_scrolls/tests/`，conftest 把 D:\allin\example 加入 sys.path 并调 ensure_engine_loaded()。
- 跑法：在 D:\allin\example 下 `python -m pytest dwarf_scrolls/tests -q`。
- 当前基线：51 passed（针对真实引擎）。
