#!/usr/bin/env python3
"""pyinstaller (打包工具集) — 无头自检入口。

`packer_pro.py` 是 tkinter GUI，但**模块级不创建窗口**（Tk()/mainloop 在
`__main__` 里），所以本自检 import 它之后用 `object.__new__` 绕过
`PackerProGUI.__init__`（那一步才会建控件、绑事件），把 GUI 状态变量换成
最小替身，直接验证真正的逻辑：PyInstaller 命令构造、输出路径、图标转换、
工程扫描。全程不创建窗口、不调用 PyInstaller 真的打包。

验证点：
  1. build_cmd：onefile/onedir、windowed/console、--clean/--noupx、
     --name/--distpath/--workpath/--specpath、--add-data/--add-binary、
     --hidden-import，脚本路径必须落在最后；multi 模式只挂项目子目录
     （排除 __pycache__/.git/venv/env/dist/build）。
  2. get_exe_path：onefile 与 onedir 两种产物路径。
  3. 图标链路：png → ico 转换、.ico 直通、路径不存在时返回 None。
  4. 工程扫描：scan_py_files 递归且有排序、find_entry_candidates 识别
     常见入口名（大小写不敏感）、get_project_tree 过滤隐藏项与 __pycache__。

用法：python selfcheck.py   （成功退出 0，失败打印 FAIL 并退出 1）
"""

import os
import sys
import tempfile
from pathlib import Path

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

_FAILS = []


def check(name, fn):
    try:
        detail = fn()
        if detail is False:
            raise AssertionError("检查返回 False")
        print(f"  [ok] {name}" + (f" — {detail}" if isinstance(detail, str) else ""))
    except Exception as exc:  # noqa: BLE001 - 自检需要兜住一切失败
        _FAILS.append(f"{name}: {type(exc).__name__}: {exc}")
        print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")


class _Var:
    """替身：模拟 tkinter.StringVar / BooleanVar 的 .get()。"""

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _bare_packer(tmpdir, **overrides):
    """构造未初始化的 PackerProGUI：不建任何 tkinter 控件。"""
    import packer_pro

    p = object.__new__(packer_pro.PackerProGUI)
    p.output_mode = _Var("onefile")
    p.console_mode = _Var("windowed")
    p.opt_clean = _Var(False)
    p.opt_noupx = _Var(False)
    p.mode = _Var("single")
    p.pack_dir = Path(tmpdir) / "out"
    p.icon_path = _Var("")
    p.project_dir_path = None
    p.extra_data = []
    p.extra_binary = []
    p.hidden_imports = []
    p.sign_enabled = _Var(False)
    p.log_write = lambda msg: None  # GUI 日志区替身
    for key, value in overrides.items():
        setattr(p, key, value)
    return p


def _cmd_pairs(cmd):
    """把 ['--add-data', 'a;b'] 形式摊平成便于断言的字典。"""
    out = {}
    i = 0
    while i < len(cmd):
        if cmd[i].startswith("--") and i + 1 < len(cmd):
            out.setdefault(cmd[i], []).append(cmd[i + 1])
            i += 2
        else:
            i += 1
    return out


# ═══════════════════════════════════════════════════════════════
#  1. PyInstaller 命令构造
# ═══════════════════════════════════════════════════════════════
def check_build_cmd():
    tmpdir = tempfile.mkdtemp(prefix="pyinstaller_selfcheck_")
    try:
        pack_dir = Path(tmpdir) / "out"

        # ── onefile + windowed：-F -w ──
        p = _bare_packer(tmpdir, **{
            "extra_data": [("data/a.txt", "data")],
            "extra_binary": [("bin/x.dll", "bin")],
            "hidden_imports": ["numpy", "yaml"],
        })
        script = Path("main.py")
        cmd = p.build_cmd(script, "myapp")

        if cmd[:3] != [sys.executable, "-m", "PyInstaller"]:
            raise AssertionError(f"命令行前缀错误：{cmd[:3]}")
        if "-F" not in cmd or "-D" in cmd:
            raise AssertionError(f"onefile 模式应加 -F：{cmd}")
        if "-w" not in cmd or "-c" in cmd:
            raise AssertionError(f"windowed 模式应加 -w：{cmd}")
        if "--clean" in cmd or "--noupx" in cmd:
            raise AssertionError(f"未勾选的开关不应出现：{cmd}")
        if cmd[-1] != str(script):
            raise AssertionError(f"脚本路径必须在最后，实际 {cmd[-1]!r}")

        pairs = _cmd_pairs(cmd)
        if pairs.get("--name") != ["myapp"]:
            raise AssertionError(f"--name 错误：{pairs.get('--name')}")
        if pairs.get("--distpath") != [str(pack_dir)]:
            raise AssertionError(f"--distpath 错误：{pairs.get('--distpath')}")
        if pairs.get("--workpath") != [str(pack_dir / "build")]:
            raise AssertionError(f"--workpath 错误：{pairs.get('--workpath')}")
        if pairs.get("--specpath") != [str(pack_dir / "spec")]:
            raise AssertionError(f"--specpath 错误：{pairs.get('--specpath')}")
        # 附加数据/二进制用 os.pathsep 连接（Windows 是 ';'）
        sep = os.pathsep
        if pairs.get("--add-data") != [f"data/a.txt{sep}data"]:
            raise AssertionError(f"--add-data 错误：{pairs.get('--add-data')}")
        if pairs.get("--add-binary") != [f"bin/x.dll{sep}bin"]:
            raise AssertionError(f"--add-binary 错误：{pairs.get('--add-binary')}")
        if pairs.get("--hidden-import") != ["numpy", "yaml"]:
            raise AssertionError(f"--hidden-import 错误：{pairs.get('--hidden-import')}")

        # ── onedir + console + clean + noupx：-D -c --clean --noupx ──
        p2 = _bare_packer(tmpdir, **{
            "output_mode": _Var("onedir"),
            "console_mode": _Var("console"),
            "opt_clean": _Var(True),
            "opt_noupx": _Var(True),
        })
        cmd2 = p2.build_cmd(script, "app2")
        for flag in ("-D", "-c", "--clean", "--noupx"):
            if flag not in cmd2:
                raise AssertionError(f"onedir/console/clean 模式缺少 {flag}：{cmd2}")
        if "-F" in cmd2 or "-w" in cmd2:
            raise AssertionError(f"onedir/console 模式不应出现 -F/-w：{cmd2}")

        # ── multi 模式：挂项目子目录，但排除缓存/版本库/构建产物 ──
        proj = Path(tmpdir) / "proj"
        for sub in ("assets", "templates", "__pycache__", ".git", "dist", "build", "venv", "env"):
            (proj / sub).mkdir(parents=True, exist_ok=True)
        p3 = _bare_packer(tmpdir, **{"mode": _Var("multi"), "project_dir_path": proj})
        cmd3 = p3.build_cmd(script, "app3")
        datas = _cmd_pairs(cmd3).get("--add-data") or []
        mounted = sorted(d.split(sep)[-1] for d in datas)
        if mounted != ["assets", "templates"]:
            raise AssertionError(f"multi 模式挂载目录错误：{mounted}")

        # single 模式不挂项目目录
        p4 = _bare_packer(tmpdir, **{"project_dir_path": proj})
        if _cmd_pairs(p4.build_cmd(script, "app4")).get("--add-data"):
            raise AssertionError("single 模式不应挂载项目目录")

        return "onefile/onedir、windowed/console、clean/noupx、数据/二进制/隐藏导入、multi 目录挂载全部正确"
    finally:
        _rmtree(tmpdir)


# ═══════════════════════════════════════════════════════════════
#  2. 产物路径
# ═══════════════════════════════════════════════════════════════
def check_exe_path():
    tmpdir = tempfile.mkdtemp(prefix="pyinstaller_path_")
    try:
        p = _bare_packer(tmpdir)
        pack_dir = Path(tmpdir) / "out"
        one = p.get_exe_path("myapp")
        if one != pack_dir / "myapp.exe":
            raise AssertionError(f"onefile 产物路径错误：{one}")

        p.output_mode = _Var("onedir")
        many = p.get_exe_path("myapp")
        if many != pack_dir / "myapp" / "myapp.exe":
            raise AssertionError(f"onedir 产物路径错误：{many}")

        return "onefile → dist/myapp.exe，onedir → dist/myapp/myapp.exe"
    finally:
        _rmtree(tmpdir)


# ═══════════════════════════════════════════════════════════════
#  3. 图标链路
# ═══════════════════════════════════════════════════════════════
def check_icon():
    from PIL import Image

    import packer_pro

    tmpdir = tempfile.mkdtemp(prefix="pyinstaller_icon_")
    try:
        # png → ico：转换产物必须是可读的 ICO
        png = Path(tmpdir) / "logo.png"
        Image.new("RGBA", (128, 128), (10, 20, 30, 255)).save(png)
        ico = Path(tmpdir) / "logo.ico"
        out = packer_pro.png_to_ico(png, ico)
        if Path(out) != ico or not ico.exists():
            raise AssertionError("png_to_ico 未生成目标文件")
        with Image.open(ico) as im:
            if im.format != "ICO":
                raise AssertionError(f"转换产物不是 ICO：{im.format}")
            if im.size not in [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]:
                raise AssertionError(f"ICO 尺寸不在请求列表内：{im.size}")

        # resolve_icon：png 走转换、ico 直通、缺失返回 None
        p = _bare_packer(tmpdir, **{"icon_path": _Var(str(png))})
        resolved = p.resolve_icon()
        if resolved is None or not resolved.endswith(".ico") or not os.path.exists(resolved):
            raise AssertionError(f"png 图标未转换出 ico：{resolved}")

        p.icon_path = _Var(str(ico))
        if p.resolve_icon() != str(ico):
            raise AssertionError(".ico 应原样返回")

        p.icon_path = _Var(str(Path(tmpdir) / "missing.png"))
        if p.resolve_icon() is not None:
            raise AssertionError("图标路径不存在时应返回 None")

        p.icon_path = _Var("")
        if p.resolve_icon() is not None:
            raise AssertionError("空图标路径应返回 None")

        return "png→ico 转换产物可读，.ico 直通，空/缺失路径返回 None"
    finally:
        _rmtree(tmpdir)


# ═══════════════════════════════════════════════════════════════
#  4. 工程扫描
# ═══════════════════════════════════════════════════════════════
def check_project_scan():
    import packer_pro

    tmpdir = tempfile.mkdtemp(prefix="pyinstaller_scan_")
    try:
        proj = Path(tmpdir) / "proj"
        (proj / "sub" / "deep").mkdir(parents=True)
        (proj / "main.py").write_text("", encoding="utf-8")
        (proj / "helper.py").write_text("", encoding="utf-8")
        (proj / "App.py").write_text("", encoding="utf-8")
        (proj / "sub" / "x.py").write_text("", encoding="utf-8")
        (proj / "sub" / "deep" / "y.py").write_text("", encoding="utf-8")
        (proj / "readme.txt").write_text("", encoding="utf-8")
        (proj / "__pycache__").mkdir(exist_ok=True)
        (proj / "__pycache__" / "cached.py").write_text("", encoding="utf-8")
        (proj / ".hidden_dir").mkdir(exist_ok=True)
        (proj / ".hidden_dir" / "h.py").write_text("", encoding="utf-8")

        files = packer_pro.scan_py_files(proj)
        names = [f.name for f in files]
        # 排序口径是 Path 全路径（Windows 下大小写不敏感），不是文件名
        if files != sorted(files):
            raise AssertionError(f"scan_py_files 未按路径排序：{[str(f) for f in files]}")
        # rglob 会递归进隐藏目录与 __pycache__（既有行为），这里只锁“全都扫到 + 排序”
        for expected in ("main.py", "helper.py", "App.py", "x.py", "y.py", "cached.py", "h.py"):
            if expected not in names:
                raise AssertionError(f"scan_py_files 漏扫 {expected}：{names}")
        if any(f.suffix != ".py" for f in files):
            raise AssertionError("scan_py_files 混入了非 .py 文件")
        if len(files) != 7:
            raise AssertionError(f"scan_py_files 结果数应为 7，实际 {len(files)}：{names}")

        # 入口候选：常见入口名，大小写不敏感（故 App.py 也算 app.py）
        cands = [f.name for f in packer_pro.find_entry_candidates(files)]
        if set(cands) != {"main.py", "App.py"}:
            raise AssertionError(f"find_entry_candidates 判定错误：{cands}")
        if "helper.py" in cands or "x.py" in cands:
            raise AssertionError(f"非入口文件被误判为入口：{cands}")
        for entry_name in ("main.py", "__main__.py", "app.py", "run.py", "start.py"):
            got = packer_pro.find_entry_candidates([Path(entry_name)])
            if len(got) != 1:
                raise AssertionError(f"{entry_name} 应被识别为入口候选")
        if packer_pro.find_entry_candidates([Path("helper.py")]):
            raise AssertionError("helper.py 不应被识别为入口候选")

        # 目录树：过滤隐藏项与 __pycache__，其余按名排序
        tree = [p.name for p in packer_pro.get_project_tree(proj)]
        if "__pycache__" in tree or ".hidden_dir" in tree:
            raise AssertionError(f"目录树未过滤隐藏项/缓存：{tree}")
        if tree != sorted(tree):
            raise AssertionError(f"目录树未排序：{tree}")
        if set(tree) != {"main.py", "helper.py", "App.py", "sub", "readme.txt"}:
            raise AssertionError(f"目录树内容错误：{tree}")

        # signtool 查找：要么给出现存路径，要么 None（不能抛异常）
        signtool = packer_pro.find_signtool()
        if signtool is not None and not os.path.exists(signtool):
            raise AssertionError(f"find_signtool 返回了不存在的路径：{signtool}")

        return "递归扫描/排序、入口候选判定、目录树过滤、signtool 查找均符合预期"
    finally:
        _rmtree(tmpdir)


def _rmtree(path):
    """清理临时目录（不借助 shutil.rmtree 也能删干净）。"""
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def main():
    print("pyinstaller (打包工具集) 无头自检（不建窗口、不真的打包）")
    check("PyInstaller 命令构造", check_build_cmd)
    check("产物路径", check_exe_path)
    check("图标链路（png→ico）", check_icon)
    check("工程扫描与入口判定", check_project_scan)

    if _FAILS:
        print(f"FAIL: {len(_FAILS)} 项检查未通过")
        for f in _FAILS:
            print(f"  - {f}")
        return 1

    print(
        "selfcheck ok: build_cmd 的 onefile/onedir/console/clean/数据/隐藏导入/multi 挂载 + "
        "产物路径 + png→ico 图标链路 + 递归扫描与入口候选判定"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
