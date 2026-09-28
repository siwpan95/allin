#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""docs_index.py —— 文档枢纽「索引契约」门禁（SPEC-005 的机械保障）。

判据（D1–D7）：
  D1 登记完整 —— docs/ 下每份非历史文档都能在 INDEX.md 里找到
  D2 索引有效 —— INDEX.md 里每条指向 docs/ 的链接都指向真实存在的文件
  D3 规范头部 —— 每份 规范/SPEC-*.md 八项字段齐备（编号/效力/状态/生效/最后修订/适用面/承载体/引用格式）
  D4 命名规则 —— 规范文件名不含日期；记录文件名含日期或是按月卷 <YYYY-MM>.md
  D5 分类一致 —— 文件所在目录与 INDEX 声明的类别一致
  D6 ASCII 别名 —— 四个别名目录存在且指向正确（Windows 用 junction；非 Windows 可 ln -s）
  D7 卷号连续 —— 记录/交接/<YYYY-MM>.md 无空洞，且每卷首行声明覆盖区间

契约（与本仓其它门禁一致）：
  退出码 0 干净 / 1 基线之外的新阻断 / 2 用法错误 / 3 环境错误
  --selfcheck 必须抓到 ≥1 个真实破坏用例，且 ≥1 个干净用例不误报
  豁免与跳过一律计数打印，不静默丢弃
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

HIST_DIR = "md"                     # 历史树，冻结，不参与 D1/D4
ALIASES = {"spec": "规范", "facts": "事实源", "records": "记录", "历史": "md"}
HUB_FILES = {"README.md", "INDEX.md", "MEMORY.md"}

SPEC_HDR_FIELDS = ["编号", "效力", "状态", "生效", "最后修订", "适用面", "承载体", "引用格式"]
DATE_IN_NAME = re.compile(r"(19|20)\d{2}[-_]?\d{2}[-_]?\d{2}")
VOLUME_NAME = re.compile(r"^(\d{4})-(\d{2})\.md$")
LINK_TO_DOCS = re.compile(r"\]\(([^)\s]+?)\)")


# ---------------------------------------------------------------- 基础设施
class Report:
    def __init__(self) -> None:
        self.blocking: list[tuple[str, str]] = []
        self.reported: list[tuple[str, str]] = []   # 只报告不阻断
        self.exempted: dict[str, int] = {}
        self.skipped: list[str] = []

    def block(self, code: str, msg: str) -> None:
        self.blocking.append((code, msg))

    def note(self, code: str, msg: str) -> None:
        self.reported.append((code, msg))

    def exempt(self, kind: str, n: int = 1) -> None:
        self.exempted[kind] = self.exempted.get(kind, 0) + n

    def skip(self, what: str) -> None:
        self.skipped.append(what)


def read_text(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def iter_docs_files(docs: str):
    """产出 docs 相对路径；显式跳过 ASCII 别名目录与历史树。

    别名既可能是 junction（Windows，落在 dirs 里），也可能是符号链接或断链
    （落在 files 里）—— 一律按名字跳过，避免把同一份内容数两遍。
    """
    for root, dirs, files in os.walk(docs, followlinks=False):
        dirs[:] = [d for d in dirs if d not in ALIASES]
        if os.path.basename(root) == HIST_DIR or os.sep + HIST_DIR + os.sep in root + os.sep:
            dirs[:] = []
            continue
        for fn in files:
            if fn in ALIASES:
                continue
            full = os.path.join(root, fn)
            if os.path.islink(full):
                continue
            rdocs = os.path.relpath(full, docs).replace("\\", "/")
            if rdocs.split("/")[0] == HIST_DIR:
                continue
            yield rdocs


# ---------------------------------------------------------------- 判据
def load_index(docs: str, rep: Report) -> dict[str, str]:
    """返回 {docs 相对路径: INDEX 声明的类别}"""
    idx = os.path.join(docs, "INDEX.md")
    if not os.path.isfile(idx):
        rep.block("D2", "INDEX.md 不存在（总目录缺失）")
        return {}
    text = read_text(idx)
    reg: dict[str, str] = {}
    for m in LINK_TO_DOCS.finditer(text):
        t = m.group(1)
        if t.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if t.startswith("../"):
            continue
        t = t.split("#")[0]
        if not t or t.startswith(".."):
            continue
        if t.endswith("/"):
            rep.exempt("D2-dir-link")      # 目录链接（分类导航）不是文档登记项
            continue
        head = t.split("/")[0]
        last = t.split("/")[-1]
        if "." not in last and t not in HUB_FILES:
            rep.exempt("D2-dir-link")
            continue
        if head in ALIASES.values() or head == HIST_DIR or t in HUB_FILES:
            reg[t] = head if head in ALIASES.values() else "枢纽"
        elif "/" not in t and t.endswith(".md"):
            reg[t] = "枢纽"
    return reg


def check_d1(files: list[str], reg: dict[str, str], rep: Report) -> None:
    for f in files:
        if f not in reg:
            rep.block("D1", "未在 INDEX.md 登记：docs/%s" % f)
        else:
            rep.exempt("D1-registered")


def check_d2(docs: str, reg: dict[str, str], rep: Report) -> None:
    for rel in sorted(reg):
        if not os.path.isfile(os.path.join(docs, rel.replace("/", os.sep))):
            rep.block("D2", "INDEX.md 登记了不存在的文件：docs/%s" % rel)
        else:
            rep.exempt("D2-resolved")


def check_d3(spec_dir: str, rep: Report) -> None:
    if not os.path.isdir(spec_dir):
        rep.block("D3", "规范/ 目录不存在")
        return
    for fn in sorted(os.listdir(spec_dir)):
        if not (fn.startswith("SPEC-") and fn.endswith(".md")):
            continue
        text = read_text(os.path.join(spec_dir, fn))
        for field in SPEC_HDR_FIELDS:
            if ("**%s**" % field) not in text:
                rep.block("D3", "%s 头部缺字段：%s" % (fn, field))
            else:
                rep.exempt("D3-field")


def check_d4(files: list[str], rep: Report) -> None:
    for f in files:
        parts = f.split("/")
        if parts[0] != "规范" and not (len(parts) > 1 and parts[0] == "事实源"):
            continue
        if DATE_IN_NAME.search(parts[-1]):
            rep.block("D4", "%s 类文件名不得含日期：%s" % (parts[0], f))
        else:
            rep.exempt("D4-nodate")
    for f in files:
        parts = f.split("/")
        if parts[0] != "记录":
            continue
        fn = parts[-1]
        if fn == "README.md":
            rep.exempt("D4-record-readme")
            continue
        base = os.path.splitext(fn)[0]
        if DATE_IN_NAME.search(fn) or VOLUME_NAME.match(fn):
            rep.exempt("D4-dated")
        else:
            rep.block("D4", "记录类文件名必须带日期或是按月卷：%s" % f)


def check_d5(files: list[str], reg: dict[str, str], rep: Report) -> None:
    for f in files:
        if f not in reg:
            continue
        declared = reg[f]
        actual = f.split("/")[0] if "/" in f else "枢纽"
        if declared == "枢纽":
            if "/" in f:
                rep.block("D5", "INDEX 把 %s 记为枢纽件，但它在分类目录下" % f)
            continue
        if declared != actual:
            rep.block("D5", "分类不一致：%s 在 %s/ 下，INDEX 记为 %s" % (f, actual, declared))
        else:
            rep.exempt("D5-match")


def check_d6(docs: str, rep: Report, enabled: bool) -> None:
    if not enabled:
        rep.skip("D6 ASCII 别名（--no-aliases）")
        return
    for alias, real in ALIASES.items():
        ap = os.path.join(docs, alias)
        rp = os.path.join(docs, real)
        if not os.path.exists(rp):
            rep.block("D6", "真身目录缺失：docs/%s" % real)
            continue
        if not os.path.exists(ap):
            rep.block("D6", "别名缺失：docs/%s -> docs/%s（跑 make_doc_aliases.ps1 重建）" % (alias, real))
            continue
        try:
            same = os.path.samefile(ap, rp)
        except OSError:
            same = False
        if not same:
            rep.block("D6", "别名指向错误：docs/%s 未指向 docs/%s" % (alias, real))
        else:
            rep.exempt("D6-ok")


def check_d7(docs: str, rep: Report) -> None:
    d = os.path.join(docs, "记录", "交接")
    if not os.path.isdir(d):
        rep.block("D7", "记录/交接/ 不存在")
        return
    vols = sorted(fn for fn in os.listdir(d) if VOLUME_NAME.match(fn))
    if not vols:
        rep.block("D7", "记录/交接/ 下没有按月卷（<YYYY-MM>.md）")
        return
    keys = [tuple(int(x) for x in VOLUME_NAME.match(v).groups()) for v in vols]
    y, m = keys[0]
    for (yy, mm) in keys:
        if (yy, mm) != (y, m):
            rep.block("D7", "交接卷号不连续：期望 %04d-%02d，实到 %04d-%02d" % (y, m, yy, mm))
            return
        m += 1
        if m == 13:
            y, m = y + 1, 1
    for v in vols:
        head = "\n".join(read_text(os.path.join(d, v)).splitlines()[:6])
        if "卷" not in head or "~" not in head:
            rep.block("D7", "交接卷 %s 首行未声明覆盖区间（形如 `<YYYY-MM> 卷（<起> ~ <止>）`）" % v)
        else:
            rep.exempt("D7-range")


# ---------------------------------------------------------------- 主流程
def run(root: str, args) -> Report:
    rep = Report()
    docs = os.path.join(root, "docs")
    if not os.path.isdir(docs):
        raise SystemExit("ENV ERROR: 找不到 docs/：%s" % docs)
    files = sorted(iter_docs_files(docs))
    reg = load_index(docs, rep)
    check_d1(files, reg, rep)
    check_d2(docs, reg, rep)
    check_d3(os.path.join(docs, "规范"), rep)
    check_d4(files, rep)
    check_d5(files, reg, rep)
    check_d6(docs, rep, enabled=not args.no_aliases)
    check_d7(docs, rep)
    return rep


def baseline_path(root: str) -> str:
    return os.path.join(root, "tools", "gate", "audit", "docs_index_baseline.txt")


def load_baseline(root: str) -> set[str]:
    p = baseline_path(root)
    if not os.path.isfile(p):
        return set()
    return {ln.strip() for ln in read_text(p).splitlines() if ln.strip() and not ln.startswith("#")}


def emit(rep: Report, args, baseline: set[str]) -> int:
    new_block = [(c, m) for (c, m) in rep.blocking if ("%s|%s" % (c, m)) not in baseline]
    known = len(rep.blocking) - len(new_block)

    if not args.quiet:
        for c, m in rep.blocking:
            tag = "BASELINE" if ("%s|%s" % (c, m)) in baseline else "BLOCK   "
            print("%s [%s] %s" % (tag, c, m))
        for c, m in rep.reported:
            print("REPORT   [%s] %s" % (c, m))
        for s in rep.skipped:
            print("SKIPPED (not a pass): %s" % s)
        if rep.exempted:
            print("exempted: " + " ".join("%s=%d" % kv for kv in sorted(rep.exempted.items())))
        print("blocking=%d baseline=%d new=%d reported=%d skipped=%d"
              % (len(rep.blocking), known, len(new_block), len(rep.reported), len(rep.skipped)))

    if args.list_all and not args.quiet:
        print("--list-all: 已打印全部 %d 条阻断" % len(rep.blocking))

    if args.write_baseline:
        p = baseline_path(args.root)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("# docs_index 基线（存量一次性固化；清完后应重写为空）\n")
            for c, m in sorted(set(rep.blocking)):
                f.write("%s|%s\n" % (c, m))
        print("已写入基线：%s（%d 条）" % (p, len(set(rep.blocking))))
        return EXIT_OK

    return EXIT_FAIL if new_block else EXIT_OK


# ---------------------------------------------------------------- selfcheck
SELFCHECK_CASES = [
    ("clean", "全部合规的迷你枢纽", True),
    ("missing-registration", "文件存在但未登记 INDEX", False),
    ("dangling-index", "INDEX 登记了不存在的文件", False),
    ("spec-no-header", "规范缺头部字段", False),
    ("spec-dated-name", "规范文件名带日期", False),
    ("record-undated", "记录文件名无日期", False),
    ("category-mismatch", "分类与所在目录不一致", False),
    ("volume-gap", "交接卷号有空洞", False),
    ("volume-no-range", "交接卷缺覆盖区间", False),
]


def build_fixture(kind: str, base: str) -> str:
    docs = os.path.join(base, "docs")
    for sub in ("规范", "事实源", "记录/交接", "记录/审计"):
        os.makedirs(os.path.join(docs, sub), exist_ok=True)

    spec = "# SPEC-001 · 测试\n\n" + "\n".join(
        "> **%s** 值" % f for f in SPEC_HDR_FIELDS) + "\n\n正文\n"
    spec_name = "SPEC-001-铁律.md"
    if kind == "spec-no-header":
        spec = "# SPEC-001 · 测试\n\n> **编号** SPEC-001\n\n正文\n"
    if kind == "spec-dated-name":
        spec_name = "SPEC-001-铁律_2026-09-28.md"
    with io.open(os.path.join(docs, "规范", spec_name), "w", encoding="utf-8") as f:
        f.write(spec)

    with io.open(os.path.join(docs, "事实源", "本机事实.md"), "w", encoding="utf-8") as f:
        f.write("# 本机事实\n\n> **时点** 2026-09-28\n")

    vol1 = "2026-08.md"
    vol2 = "2026-09.md"
    rec = "盘点_2026-09-23.md"
    if kind == "record-undated":
        rec = "盘点.md"
    if kind == "volume-gap":
        vol1, vol2 = "2026-08.md", "2026-10.md"
    for v in (vol1, vol2):
        head = "# 会话交接 · %s 卷（起 ~ 止）\n" % v[:-3]
        if kind == "volume-no-range" and v == vol2:
            head = "# 会话交接 · %s\n" % v[:-3]
        with io.open(os.path.join(docs, "记录", "交接", v), "w", encoding="utf-8") as f:
            f.write(head)
    with io.open(os.path.join(docs, "记录", "审计", rec), "w", encoding="utf-8") as f:
        f.write("# 盘点\n\n> **本文是 2026-09-23 的一次性记录，不作为约束。**\n")

    for hub in ("README.md", "INDEX.md"):
        with io.open(os.path.join(docs, hub), "w", encoding="utf-8") as f:
            f.write("# 门面\n")
    os.makedirs(os.path.join(docs, "md"), exist_ok=True)   # 历史树真身（D6 需要）

    lines = ["# INDEX", "", "| 编号 | 文件 |", "| --- | --- |",
             "| HUB-01 | [README.md](README.md) |",
             "| HUB-02 | [INDEX.md](INDEX.md) |",
             "| SPEC-001 | [铁律](规范/%s) |" % spec_name,
             "| FACT-01 | [本机事实](事实源/本机事实.md) |",
             "| REC-AU-01 | [盘点](记录/审计/%s) |" % rec,
             "| REC-HO-01 | [2026-08](记录/交接/%s) |" % vol1,
             "| REC-HO-02 | [%s](记录/交接/%s) |" % (vol2[:-3], vol2)]
    if kind == "missing-registration":
        lines = [ln for ln in lines if "本机事实" not in ln]
    if kind == "dangling-index":
        lines.append("| REC-XX-99 | [不存在](记录/审计/根本不存在_2026-01-01.md) |")
    if kind == "category-mismatch":
        lines = [ln.replace("(事实源/本机事实.md)", "(规范/本机事实.md)") for ln in lines]
    with io.open(os.path.join(docs, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    for alias, real in ALIASES.items():
        ap, rp = os.path.join(docs, alias), os.path.join(docs, real)
        if os.path.exists(ap):
            continue
        try:
            os.symlink(rp, ap, target_is_directory=True)
        except OSError:
            pass
    return docs


def selfcheck() -> int:
    caught = clean = misreports = 0
    for kind, desc, expect_clean in SELFCHECK_CASES:
        tmp = tempfile.mkdtemp(prefix="docsidx_")
        try:
            build_fixture(kind, tmp)
            args = argparse.Namespace(root=tmp, quiet=True, no_aliases=False,
                                      list_all=False, write_baseline=False)
            rep = run(tmp, args)
            ok = not rep.blocking
            if expect_clean:
                if ok:
                    clean += 1
                else:
                    misreports += 1
                    print("MISREPORT clean-case failed: %s -- %s" % (kind, [m for _, m in rep.blocking][:3]))
            else:
                if not ok:
                    caught += 1
                else:
                    print("MISSED case not caught: %s" % kind)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print('SELFCHECK {"caught":%d,"clean":%d,"misreports":%d}' % (caught, clean, misreports))
    return EXIT_OK if (caught >= 1 and clean >= 1 and misreports == 0) else EXIT_FAIL


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="文档枢纽索引契约门禁（SPEC-005）")
    ap.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
                    help="仓根（默认由脚本位置反推）")
    ap.add_argument("--selfcheck", action="store_true", help="跑真实破坏/干净用例自证")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--baseline", action="store_true", help="启用基线棘轮（默认启用）")
    ap.add_argument("--no-baseline", action="store_true", help="忽略基线，看全部存量")
    ap.add_argument("--write-baseline", action="store_true", help="把当前全部阻断写入基线")
    ap.add_argument("--list-all", action="store_true")
    ap.add_argument("--no-aliases", action="store_true", help="跳过 D6 别名校验（非 Windows CI 用）")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        print("ENV ERROR: root 不存在：%s" % args.root)
        return EXIT_ENV
    args.root = os.path.abspath(args.root)

    if args.selfcheck:
        return selfcheck()

    try:
        rep = run(args.root, args)
    except SystemExit as e:
        print(e)
        return EXIT_ENV
    except Exception as e:  # noqa: BLE001
        print("ENV ERROR: %s" % e)
        return EXIT_ENV

    baseline = set() if args.no_baseline else load_baseline(args.root)
    return emit(rep, args, baseline)


if __name__ == "__main__":
    sys.exit(main())
