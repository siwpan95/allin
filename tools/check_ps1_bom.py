#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ps1_bom.py —— PowerShell 脚本编码门禁

为什么存在
----------
`/tools/README.md` 纪律 1 写着：「`.ps1` 必须存成 UTF-8 带 BOM —— 否则 PowerShell 5.1
按 ANSI 解码中文，报一堆**假**语法错误」。

但这条纪律此前**只是文字**。2026-09-25 实测当场踩中：用编辑工具改
`/tools/fix-registry-acl.ps1` 后 **BOM 被剥掉**，而 PowerShell 5.1 下
`scan_hardcoded.ps1`（无 BOM 且含中文）确实报出假语法错误：

    Unexpected token '}' in expression or statement.
    At /tools/gate/scan_hardcoded.ps1:122 char:60

**文字纪律挡不住工具链的默认行为**，所以把它变成退出码。

判定口径
--------
对每个 `.ps1`：
  · 含非 ASCII 字符（中文注释等）→ **必须**有 UTF-8 BOM，否则阻断（PS 5.1 会乱码/假语法错）
  · 纯 ASCII → 无 BOM 也合法（不做无谓要求）
  · `-Strict` 下：任何 `.ps1` 都要求 BOM（团队统一风格时用）

同时校验：BOM 存在但文件本身不是合法 UTF-8 → 阻断（BOM 会掩盖真实编码损坏）。

用法
----
    python check_ps1_bom.py                      # 扫默认根
    python check_ps1_bom.py --root /projects/allin_push --root /projects
    python check_ps1_bom.py --fix                # 就地补 BOM（**会写文件**，默认干跑）
    python check_ps1_bom.py --selfcheck          # 注入破坏用例自证
    python check_ps1_bom.py --json out.json

退出码
------
    0 = 全部合规（或 --fix 已修好）
    1 = 有违规
    2 = 用法错误
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BOM = b"\xef\xbb\xbf"
# 去符盘（铁律 5，2026-09-26）：默认根 = 环境变量 PROJECTS_ROOT，否则脚本所在仓根（tools/ → 上级）
DEFAULT_ROOTS = [os.environ.get("PROJECTS_ROOT")
                 or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "site-packages", "dist", "build", ".deps", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "target", ".next", ".cache",
}


def has_non_ascii(data):
    try:
        data.decode("ascii")
        return False
    except UnicodeDecodeError:
        return True


def scan_file(path, strict=False):
    """返回问题描述字符串；None = 合规。"""
    try:
        data = open(path, "rb").read()
    except OSError as e:
        return "无法读取: {}".format(e)
    has_bom = data.startswith(BOM)
    body = data[len(BOM):] if has_bom else data
    if has_bom:
        # BOM 在但内容不是合法 UTF-8 —— BOM 会掩盖真实编码损坏
        try:
            body.decode("utf-8")
        except UnicodeDecodeError as e:
            return "有 BOM 但内容非合法 UTF-8（掩盖了编码损坏）: {}".format(e)
        return None
    non_ascii = has_non_ascii(body)
    if strict:
        return "缺 UTF-8 BOM（-Strict 模式要求所有 .ps1 带 BOM）"
    if non_ascii:
        return "含非 ASCII 字符但缺 UTF-8 BOM —— PowerShell 5.1 会按 ANSI 解码，报假语法错误"
    return None


def fix_file(path):
    data = open(path, "rb").read()
    if data.startswith(BOM):
        return False
    with open(path, "wb") as fh:
        fh.write(BOM + data)
    return True


def iter_ps1(roots):
    for root in roots:
        if os.path.isfile(root) and root.lower().endswith(".ps1"):
            yield root
            continue
        if not os.path.isdir(root):
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for fn in fns:
                if fn.lower().endswith(".ps1"):
                    yield os.path.join(dp, fn)


def selfcheck():
    print("== PowerShell 编码门禁 自测 ==")
    ok = True
    tmp = tempfile.mkdtemp(prefix="bom_selfcheck_")

    # ① 合规：含中文 + BOM
    p1 = os.path.join(tmp, "good.ps1")
    open(p1, "wb").write(BOM + "# 中文注释\nWrite-Host 'ok'\n".encode("utf-8"))
    r = scan_file(p1)
    print("  含中文+BOM 判合规: {}  [{}]".format("✔" if r is None else "✘", r or "None"))
    ok &= (r is None)

    # ② 破坏用例：含中文但无 BOM（本次真实踩中的形态）
    p2 = os.path.join(tmp, "bad.ps1")
    open(p2, "wb").write("# 中文注释\nWrite-Host 'ok'\n".encode("utf-8"))
    r = scan_file(p2)
    print("  含中文无 BOM 被检出: {}  [{}]".format("✔" if r else "✘", (r or "")[:50]))
    ok &= bool(r)

    # ③ 反例：纯 ASCII 无 BOM 合法
    p3 = os.path.join(tmp, "ascii.ps1")
    open(p3, "wb").write(b"Write-Host 'ok'\n")
    r = scan_file(p3)
    print("  纯ASCII无BOM不误报: {}  [{}]".format("✔" if r is None else "✘", r or "None"))
    ok &= (r is None)

    # ④ 破坏用例：BOM 掩盖非法 UTF-8
    p4 = os.path.join(tmp, "bombom.ps1")
    open(p4, "wb").write(BOM + b"# \xff\xfe invalid\n")
    r = scan_file(p4)
    print("  BOM掩盖坏编码被检出: {}  [{}]".format("✔" if r else "✘", (r or "")[:50]))
    ok &= bool(r)

    # ⑤ fix 能修好
    fixed = fix_file(p2)
    r = scan_file(p2)
    print("  --fix 补 BOM 后可合规: {}  [fixed={} result={}]".format("✔" if fixed and r is None else "✘", fixed, r or "None"))
    ok &= fixed and r is None

    # ⑥ 真实回归：拿一个曾丢过 BOM 的真实脚本验证判据（只读；路径由环境变量给出，去符盘）
    real = os.environ.get("BOM_REGRESSION_TARGET", "")
    if os.path.isfile(real):
        r = scan_file(real)
        print("  真实脚本 {}: {}  [{}]".format(os.path.basename(real),
              "合规" if r is None else "违规", (r or "")[:50]))
        ok &= (r is None)

    shutil.rmtree(tmp, ignore_errors=True)
    print("  自测{}".format("通过" if ok else "失败"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="PowerShell .ps1 编码门禁（BOM 判定）")
    ap.add_argument("--root", action="append", default=None, help="扫描根，可多次")
    ap.add_argument("--strict", action="store_true", help="所有 .ps1 都必须带 BOM")
    ap.add_argument("--fix", action="store_true", help="就地补 BOM（默认干跑）")
    ap.add_argument("--json", help="机读输出路径")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    roots = args.root or DEFAULT_ROOTS
    files = sorted(set(iter_ps1(roots)))
    problems = []
    for f in files:
        r = scan_file(f, strict=args.strict)
        if r:
            problems.append((f, r))

    fixed = []
    if args.fix and problems:
        for f, _ in problems:
            try:
                if fix_file(f):
                    fixed.append(f)
            except OSError as e:
                if not args.quiet:
                    print("[ERR] 补 BOM 失败 {}: {}".format(f, e), file=sys.stderr)
        problems = [(f, r) for f, r in problems if scan_file(f, strict=args.strict)]

    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"scanned": len(files), "problems": len(problems),
                       "fixed": fixed,
                       "items": [{"file": f, "issue": r} for f, r in problems]},
                      fh, ensure_ascii=False, indent=2)

    if not args.quiet:
        print("== PowerShell 编码门禁 ==")
        print("  扫描 {} 个 .ps1（{} 个根）{}".format(len(files), len(roots),
                                                 " | Strict" if args.strict else ""))
        if fixed:
            print("  已补 BOM: {} 个".format(len(fixed)))
        for f, r in problems:
            print("  [VIOLATION] {} —— {}".format(f, r))
        if not files:
            print("  [WARN] 未找到任何 .ps1 —— 记为 SKIP，不当作通过")
            return 1
        print("  RESULT: {}".format("通过" if not problems else "阻断 {} 个".format(len(problems))))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
