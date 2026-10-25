# repocheck · 仓库体检

一个**自包含**的桌面小工具，用来对某个根目录下的多个「项目」做一轮快速体检，
自动找出那些「没版本控制 / 没文档 / 没测试 / 没依赖声明 / 没 License / import 疑似断裂」
的工程卫生问题，并支持导出 CSV / HTML 报告。

> 归属：全哥工具箱 `G:\tools\dev\repocheck\`
> 原则：**复制优于共享**——本目录独立运行，不 import 其他工具目录，也不依赖任何中心化共享核。

---

## 功能

1. **选择根目录**（默认 `G:\`），一键递归识别「项目」。
2. 对每个项目做 6 项体检，给出中文问题标签。
3. 结果用 `ttk.Treeview` 展示：项目路径 + 问题数 + 问题标签（可滚动）。
4. 一键导出 **CSV**（UTF-8 BOM，Excel 友好）或 **HTML** 报告。

### 什么是「项目」

根目录的**直接一级子目录**中，满足以下任一条件即视为项目：

- 自身含 `.git` 目录；
- 自身含 `package.json` / `Cargo.toml` / `pyproject.toml`；
- 其子树（默认向下 2 层）内存在任意 `.py` 文件。

### 体检检查项

| 标签 | 判定口径 |
| --- | --- |
| 无版本控制（缺 .git） | 项目目录内无 `.git` |
| 无 README | 目录自身无 `README*` / `readme*` 文件 |
| 无测试 | 无 `tests/` 或 `test/` 目录，且无 `test_*.py` / `*_test.py` |
| 无依赖声明 | 无 `requirements.txt` / `pyproject.toml` / `package.json` / `Cargo.toml` |
| 无 LICENSE | 目录自身无 `LICENSE*` 文件 |
| 疑似 import 断裂风险 | 静态启发式：import 的顶层模块既不在项目内部、也不在标准库、也不在常见第三方清单中 |
| 旧仓库路径残留(D:/allin) | 代码/配置/文档中出现 `D:/allin` 或 `D:\allin`（仓库自 D 盘迁至 G:\ 的残留，含 .bat 的 `cd /d` 旧路径） |
| 内联引擎副本缺 engine.patch.yaml | 项目内联 alloy/allin_engine 引擎副本（含 tools/vendor 子位）但没有 patch 记录——补丁即差异纪律 |

> **关于「import 断裂风险」**：仅用 `ast` 做静态扫描，**不实际执行代码**。
> 它是启发式，会存在误报（例如未收录进清单的合法第三方库）。标签以「疑似」前缀提醒，
> 最终以人工确认 / 实际运行 `pip install` 为准。

### 默认排除目录

扫描与识别时会自动跳过：`__pycache__`、`.git`、`.mypy_cache`、
`_cleanup_trash`、`node_modules`、`dist`、`build`。

---

## 文件结构

```
G:\tools\dev\repocheck\
├── main.py          # Tkinter GUI 入口（中文界面）；仅在 __main__ 时建窗体
├── scanner.py       # 纯逻辑：discover_projects / check_project 等
├── requirements.txt # 纯标准库，无第三方依赖（说明占位）
├── README.md        # 本文件
└── test_scanner.py  # 冒烟测试（tempfile 造数据，可离线运行）
```

---

## 运行方式

### 图形界面（需要有显示器 / Tk 可用）
```bat
REM 使用全哥指定的 Python
C:/Users/13122/.workbuddy/binaries/python/versions/3.13.12/python.exe main.py
```
启动后选择根目录（默认 `G:\`），点「开始体检」即可。

### 命令行模式（无显示器也可用）
```bat
C:/Users/13122/.workbuddy/binaries/python/versions/3.13.12/python.exe main.py G:\
```
会调用 `scanner._console_scan` 直接在终端打印每个项目的问题。

### 跑冒烟测试
```bat
C:/Users/13122/.workbuddy/binaries/python/versions/3.13.12/python.exe test_scanner.py
```

---

## 核心函数（scanner.py）

- `discover_projects(root, exclude=None, max_py_depth=2) -> list[str]`
  递归识别根目录下的一级子项目，返回项目路径列表（按名称排序）。
- `check_project(path, exclude=None) -> dict`
  对单个项目体检，返回 `{"name", "path", "issues": list[str], "metrics": dict}`。
- 辅助函数（均为私有，供测试间接验证）：
  `_is_project`、`_has_readme`、`_has_tests`、`_has_deps`、`_has_license`、
  `_scan_imports`、`_find_broken_imports`、`_internal_module_bases`。

---

## 已知限制

1. **import 断裂为启发式**：依赖一份「常见第三方库」手写清单，未收录的合法库会被误报；
   不解析虚拟环境 / `site-packages`，不追踪 `sys.path` 动态修改。
2. **项目识别限于一级子目录**：嵌套很深的仓库不会被单独列为项目（但属于某个一级项目的内部会一起被检查）。
3. **README / LICENSE 仅看目录自身**：子目录里的 `README` 不计入（符合多数仓库约定，但非绝对）。
4. **max_py_depth 默认 2**：极深的纯 Python 项目若 `.py` 都在 3 层以下，可能漏判为「项目」；
   可通过 `discover_projects(root, max_py_depth=N)` 调大。
5. **Tkinter 依赖系统 tk**：最小化服务器 Python 可能缺 tk，此时只能走命令行 / 测试模式。
6. **不读取 .gitignore**：被忽略的构建产物等仍可能参与文件计数（不影响问题判定）。
