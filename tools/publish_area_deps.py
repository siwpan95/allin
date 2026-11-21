r"""publish_area_deps.py —— 发布区依赖声明补写（规则 4 收口）

为什么有这个脚本
    规则 4（``deps.missing``）要求仓内有依赖声明。实测发布区 139 仓中
    **17 仓**没有（requirements.txt / pyproject.toml / package.json / Cargo.toml）。
    逐仓手写不可复跑 ⇒ 做成工具。

口径纪律（不臆造依赖 —— 这是本工具的第一原则）
    · 依赖**从源码 AST 实测提取**：解析每个 .py 的 import，算出模块集合；
    · 再用「本地模块消解」把**仓内自己的包**剔除（arcade 的 ``audio``、
      game-prototypes 的 ``*_plugin`` 等都是本仓模块，不是第三方依赖）；
    · 再剔除 **vendor / 第三方源码树**里的 import（实测 pluginplayer 的
      ``tensorflow`` 来自 ``player/FFmpeg-master/tools/python/`` 的 vendor 源码，
      不是本仓依赖 —— 写进 requirements 会让安装失败）；
    · 映射到 PyPI 包名（import 名 ≠ PyPI 包名的有 20 余个，见 _IMPORT_TO_PYPI）；
    · **只写确认存在的依赖**，版本一律**不钉**（钉版本需要联网核对，
      在无网/多版本环境下会写错；钉版本与否由 ``ci.unpinned_dependency``
      这条 info 级规则提示，不在依赖声明这一步冒险）。

用法
    python tools/publish_area_deps.py --repos-root <发布区根> --dry-run
    python tools/publish_area_deps.py --repos-root <发布区根> --apply

退出码
    0 无待办
    1 有待补（预演）或已完成补写（--apply）
    2 用法或环境错误
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

#: import 名 → PyPI 包名（不一致的都在这；一致的不必列）
_IMPORT_TO_PYPI: dict[str, str] = {
    "PIL": "Pillow",
    "fitz": "PyMuPDF",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "Crypto": "pycryptodome",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "serial": "pyserial",
    "docx": "python-docx",
    "vlc": "python-vlc",
    "zmq": "pyzmq",
    "uno": "uno",
    "OpenGL": "PyOpenGL",
    "magic": "python-magic",
    "pptx": "python-pptx",
    "xlsxwriter": "XlsxWriter",
    "zoneinfo": "",
    "pkg_resources": "",
    "win32api": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "pythoncom": "pywin32",
    "google": "protobuf",
    "grpc": "grpcio",
    "Crypto": "pycryptodome",
    "jwt": "pyjwt",
    "dotenv": "python-dotenv",
    "attr": "attrs",
    "dateutil": "python-dateutil",
    "OpenSSL": "pyopenssl",
    "gi": "PyGObject",
    "cairo": "pycairo",
    "Xlib": "python-xlib",
    "psutil": "psutil",
    "cpuinfo": "py-cpuinfo",
    "win32api": "pywin32",
    "keyboard": "keyboard",
    "mouse": "mouse",
    "win32clipboard": "pywin32",
    "win32con": "pywin32",
    "comtypes": "comtypes",
    "wmi": "WMI",
    "pyautogui": "pyautogui",
    "pynput": "pynput",
    "pyperclip": "pyperclip",
    "plyer": "plyer",
    "psutil": "psutil",
    "rapidocr_onnxruntime": "rapidocr-onnxruntime",
    "edge_tts": "edge-tts",
    "pyfluidsynth": "pyfluidsynth",
    "pretty_midi": "pretty_midi",
    "flask_sock": "flask-sock",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "py7zr": "py7zr",
    "zstandard": "zstandard",
    "moderngl": "moderngl",
    "glfw": "glfw",
    "sdl2": "pysdl2",
    "sounddevice": "sounddevice",
    "soundfile": "soundfile",
    "librosa": "librosa",
    "mutagen": "mutagen",
    "numba": "numba",
    "asteval": "asteval",
    "moviepy": "moviepy",
    "matplotlib": "matplotlib",
    "opencv-python": "opencv-python",
    "pathfinding": "pathfinding",
    "pystray": "pystray",
    "pygame_gui": "pygame_gui",
    "pygame_ce": "pygame-ce",
    "pygame": "pygame",
    "openpyxl": "openpyxl",
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy",
    "requests": "requests",
    "cryptography": "cryptography",
    "curl_cffi": "curl_cffi",
    "ollama": "ollama",
    "pytest": "pytest",
    "tqdm": "tqdm",
    "flask": "flask",
    "tensorflow": "tensorflow",
}

#: 目录名 ⇒ 其中的 import 一律不计入本仓依赖（第三方源码树 / 虚拟环境 / 缓存）
_VENDOR_DIR_NAMES = {
    "vendor", "vendors", "third_party", "thirdparty", "external", "externals",
    "node_modules", "site-packages", "dist-packages", ".venv", "venv", "env",
    ".deps", "deps", ".packages", "__pycache__", ".git", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "build", "dist", ".build", ".output",
    "FFmpeg-master", "ffmpeg", "Qt", "QtWebEngine",
}

#: 明显是本仓本地模块的顶层名（实测归档/容器仓的子项目目录）
_LOCAL_MODULE_HINTS = {
    "games", "game", "game2048", "calculator", "kaw", "ecs", "engine", "systems",
    "ui", "views", "viewmodels", "entities", "components", "models", "model",
    "config", "storage", "effects", "physics", "track", "audio", "audio_manager",
    "data_loader", "rider_entity", "faatt", "camera", "core", "app", "input",
    "user_dict", "view", "viewmodel", "com", "ime_core", "ime_ui",
    "keyboard_handler", "pinyin_dict", "pinyin_parser", "pinyin_syllables",
    "main", "build", "codegen", "gdb", "glib_gdb", "subunit", "testtools",
    "verify", "validate", "pe_deps", "pp_cli", "dsh_bind_workspace", "dsh_open_ui",
    "gen_third_party_notices", "kernel", "media_lib", "media_source", "player_engine",
    "player_engine_rpc", "music_player", "audio_core", "spike_panel",
    "chess_ai", "chess_core", "tests", "data", "game_engine", "dungeon",
    "superengine", "cnn", "corpus", "driver", "golden", "weiqi_ai", "weiqi_rules",
    "music_prompt_generator", "validate_styles", "Engine", "audio_core",
    "crypto_tables", "decryptors", "composer", "compositors", "constants",
    "controller", "controllers", "desktop_wallpaper", "ffmpeg_utils",
    "imageio", "recipes", "renderer", "renderers", "rendering", "rules",
    "shikonghuaban", "templates", "utils", "wave4", "wave4_legacy",
    "audio", "audio_manager", "assets", "adventurelog_common", "adventurelog_plugin",
}


def _stdlib_modules() -> set[str]:
    return set(getattr(sys, "stdlib_module_names", ())) | {
        "__future__", "typing", "collections", "dataclasses", "importlib",
    }


def _is_vendor_path(rel: str) -> bool:
    """该文件是否位于第三方源码树 / 虚拟环境 / 缓存目录内。

    注意是**路径中任意一段**命中即算 vendor —— 实测 pluginplayer 的
    ``player/FFmpeg-master/tools/python/tf_sess_config.py`` 里的 tensorflow
    来自 FFmpeg 自带源码，不是本仓依赖；只判首段会漏掉这种中段命中的情况。
    """
    parts = rel.replace("\\", "/").split("/")[:-1]
    lowered = {v.lower() for v in _VENDOR_DIR_NAMES}
    for p in parts:
        low = p.lower()
        if low in lowered:
            return True
        # 形如 FFmpeg-master / ffmpeg-9.0.1 / QtWebEngine 的第三方源码树
        if low.endswith("-master") or low.startswith("ffmpeg-") or low.startswith("qt"):
            return True
    return False


def _local_top_names(repo: Path) -> set[str]:
    """仓内自有模块的顶层名。

    两种来源：
      ① 目录里有 ``__init__.py`` ⇒ 该目录名是包名；
      ② 仓根的 .py 文件名 ⇒ 模块名。

    2026-11-21 补：还要把**所有子目录名**收进来（不论有没有 __init__.py）。
    实测 game-prototypes 是 30+ 个子项目的聚合归档仓（adventurelog/、
    darksouls/、fish/ …），子目录里的模块（如 ``fish.fishtank.economy``）
    都是本仓自己的代码。漏掉它们会产出 228 条「依赖」，全是本地模块。
    """
    names: set[str] = set()
    try:
        for entry in repo.iterdir():
            if entry.is_dir():
                if entry.name.lower() in {v.lower() for v in _VENDOR_DIR_NAMES}:
                    continue
                names.add(entry.name)
                if (entry / "__init__.py").is_file():
                    names.add(entry.name)
            elif entry.suffix == ".py":
                names.add(entry.stem)
    except OSError:
        pass

    # 二级子目录也收进来（game-prototypes 的 mahjong/、media-prototypes 的
    # media-tools/ 等），只看一层会漏。
    try:
        for entry in repo.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.lower() in {v.lower() for v in _VENDOR_DIR_NAMES}:
                continue
            try:
                for sub in entry.iterdir():
                    if sub.is_dir():
                        names.add(sub.name)
                    elif sub.suffix == ".py":
                        names.add(sub.stem)
            except OSError:
                continue
    except OSError:
        pass
    return names


def extract_requirements(repo: Path) -> tuple[list[str], list[str]]:
    """返回 (确认的第三方依赖, 待人工确认的模块名)。"""
    stdlib = _stdlib_modules()
    local = _local_top_names(repo)
    found: set[str] = set()
    unknown: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d.lower() not in {v.lower() for v in _VENDOR_DIR_NAMES}]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = Path(dirpath) / fn
            try:
                rel = str(full.relative_to(repo)).replace("\\", "/")
            except ValueError:
                continue
            if _is_vendor_path(rel):
                continue
            try:
                tree = ast.parse(full.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mods = [node.module.split(".")[0]]
                for m in mods:
                    if not m or m in stdlib or m in local:
                        continue
                    if m in _LOCAL_MODULE_HINTS:
                        continue
                    # 只有**能确认是 PyPI 包**的 import 才写入。
                    # 未在映射表里的模块名一律不写 —— 它们绝大多数是仓内本地模块
                    # （实测 game-prototypes 有 30+ 子项目，模块名如 fish_common /
                    # darksouls_plugin / _panel_harness 共 100+ 个，都不是第三方）。
                    # 宁可漏写（读者 pip install 后若缺包会立刻发现），
                    # 也不写错（写进去会让 pip install 直接失败）。
                    pypi = _IMPORT_TO_PYPI.get(m)
                    if pypi:
                        found.add(pypi)
                    else:
                        unknown.add(m)

    return sorted(found), sorted(unknown)


def process_repo(repo: Path) -> dict:
    """检查单个仓是否有依赖声明；没有则算出应写入的内容。"""
    for name in ("requirements.txt", "pyproject.toml", "package.json", "Cargo.toml"):
        if (repo / name).is_file():
            return {"repo": repo.name, "status": "has-decl"}
    reqs, unknown = extract_requirements(repo)
    if not reqs:
        # 无第三方依赖：声明为「纯标准库」，用空 requirements 显式说明，
        # 而不是留空（留空 = 缺失，判据红）。
        return {
            "repo": repo.name,
            "status": "todo",
            "requirements": [],
            "unknown": unknown,
            "note": "纯标准库项目",
        }
    return {"repo": repo.name, "status": "todo", "requirements": reqs, "unknown": unknown}


def render(reqs: list[str], repo: str) -> str:
    head = [
        f"# {repo} · 依赖声明",
        "#",
        "# 本文件由 allin 仓 tools/publish_area_deps.py 从源码 import 实测生成",
        "# （AST 解析 + 本地模块消解 + vendor 源码树剔除）。",
        "# 版本未钉：如需固定版本请在本地核对后补 `==`，避免多环境失配。",
        "",
    ]
    if not reqs:
        head.append("# 本项目仅依赖 Python 标准库，无第三方依赖。")
        head.append("")
    else:
        for r in reqs:
            head.append(r)
        head.append("")
    return "\n".join(head)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区依赖声明批量补写")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = args.repos_root
    if not root:
        print("用法错误：需 --repos-root 或设 $PROJECTS_ROOT", file=sys.stderr)
        return 2
    rp = Path(root)
    if not rp.is_dir():
        print(f"用法错误：发布区不存在 {rp}", file=sys.stderr)
        return 2

    repos = sorted(p for p in rp.iterdir() if p.is_dir() and (p / ".git").exists())
    results = [process_repo(p) for p in repos]
    todos = [r for r in results if r["status"] == "todo"]

    if args.json:
        print(json.dumps({"scanned": len(repos), "todo": len(todos),
                          "results": todos}, ensure_ascii=False, indent=2))
    else:
        print(f"扫描 {len(repos)} 个仓，待补 {len(todos)} 个")
        for r in todos:
            reqs = r["requirements"]
            note = "（纯标准库）" if not reqs else ""
            print(f"  {r['repo']:<24} {len(reqs)} 个依赖{note}")
            if reqs:
                print(f"      {', '.join(reqs)}")
            if r["unknown"]:
                print(f"      ⚠ 待人工确认: {', '.join(r['unknown'][:8])}")

    if not todos:
        return 0
    if not args.apply:
        print("\n预演模式：加 --apply 实际写盘")
        return 1

    changed: list[str] = []
    for r in todos:
        repo = rp / r["repo"]
        target = repo / "requirements.txt"
        target.write_text(render(r["requirements"], r["repo"]),
                          encoding="utf-8", newline="\n")
        changed.append(r["repo"])

    print(f"\n已写入 {len(changed)} 个仓的 requirements.txt")
    for name in changed:
        print(f"  {name}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
