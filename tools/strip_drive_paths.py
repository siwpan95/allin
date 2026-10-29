r"""strip_drive_paths.py —— 仓内盘符路径的「扫描 / 清洗」双模式工具（铁律 5 去符盘）。

为什么有这个脚本
    铁律 5 禁止硬编码机器路径，但仓里积压了两批历史盘符路径：
      ① 治理配置（platform/registry/*.yaml）注释里的「此前 <盘符>:\repos 下有本仓」一类记账；
      ② 源码注释里指向别仓/本机落点的说明（如「对齐 <盘符>:\lab chess-cordis/src/...」）。
    它们都被 g01-paths 判为 comment 而豁免（不红），但**没红不等于没问题**：盘符一换机就是死路径。
    手工改 59 处可以，下次换机再改一遍不行 ⇒ 做成可重跑的工具。

口径（与门禁同源，不另立标准）
    · 扫描分类直接复用 g01_paths 的正则与 classify_line，避免「工具说有、门禁说没有」；
    · 清洗只动 **comment 行**（注释 / 说明），YAML 有效值、代码字符串一律不碰；
    · 去符盘写法与 tools/build_portfolio.py:51 的 de_drive 同源（只剥 `<盘符>:`），
      本脚本额外做两件事：分隔符归一为 `/`、补「盘符随机器」的落点说明，使句子仍读得通。

用法
    python tools/strip_drive_paths.py --scan                  # 全仓分组统计（不写盘）
    python tools/strip_drive_paths.py --scan --list           # 附 src:comment 明细（文件:行）
    python tools/strip_drive_paths.py --strip                 # 预演：列出将改动的行，不写盘
    python tools/strip_drive_paths.py --strip --apply         # 实际清洗
    python tools/strip_drive_paths.py --strip --apply --target registry

退出码
    0 无待办（--scan 恒为 0；--strip 预演时 0 表示已清干净）
    1 有待办（--strip 预演发现可清洗项 / --apply 已完成清洗）
    2 用法或环境错误
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # tools/strip_drive_paths.py -> 仓根
sys.path.insert(0, str(ROOT / "tools" / "gate" / "governance" / "runtime"))
sys.path.insert(0, str(ROOT / "tools" / "gate" / "governance" / "gates"))

import g01_paths as g  # noqa: E402
import govlib  # noqa: E402

#: 落点说明：去符盘后补一句，避免读者以为这是仓内相对路径。
LOCALES = {
    "repos": "repos/（仓库区，盘符随机器）",
    "assets": "assets/（资源池，盘符随机器）",
    "local": "local/（本地发布区，盘符随机器）",
    "allin": "allin/（仓根，盘符随机器）",
    "lab": "lab/（lab 仓，盘符随机器）",
    "platform": "platform/（平台根，盘符随机器）",
}

#: 先替「带子路径」的（<盘符>:\repos\fonts -> repos/fonts），再替「裸根」的。
STRIP_SUBS: list[tuple[re.Pattern[str], str]] = []
for _key in LOCALES:
    STRIP_SUBS.append((re.compile(r"[A-Za-z]:\\%s\\([A-Za-z0-9_.\-]+)" % _key), "%s/\\1" % _key))
    STRIP_SUBS.append((re.compile(r"[A-Za-z]:/%s/([A-Za-z0-9_.\-]+)" % _key), "%s/\\1" % _key))
for _key, _rep in LOCALES.items():
    STRIP_SUBS.append((re.compile(r"[A-Za-z]:\\%s(?![A-Za-z0-9_.\-])" % _key), _rep))
    STRIP_SUBS.append((re.compile(r"[A-Za-z]:/%s(?![A-Za-z0-9_.\-])" % _key), _rep))
#: 反斜杠写法归一（repos\fonts -> repos/fonts）
STRIP_SUBS.append((re.compile(r"\b(repos|assets|local|allin|lab|platform)\\([A-Za-z0-9_.\-]+)"), r"\1/\2"))


def iter_findings():
    """按 g01 口径产出 (相对路径, 行号, 是否 comment, 是否文档, 是否死路径, 候选路径)。"""
    for rel in govlib.tracked_files(ROOT):
        if rel.startswith(g.SKIP_PREFIXES) or Path(rel).suffix.lower() in g.SKIP_EXTENSIONS:
            continue
        text = govlib.read_text(ROOT / rel, limit_bytes=g.MAX_FILE_BYTES)
        if text is None:
            continue
        is_doc = Path(rel).suffix.lower() in g.DOC_EXTENSIONS
        for m in (*g.WIN_PATH.finditer(text), *g.POSIX_PATH.finditer(text)):
            kind = "windows" if m.re is g.WIN_PATH else "posix"
            cand = g.normalize(m.group(0))
            tail = m.group(2)
            if kind == "windows" and g.ESCAPE_TAIL.match(tail or ""):
                continue
            if not tail:
                continue
            col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
            if "://" in govlib.line_text(text, m.start())[:col]:
                continue
            if any(k.lower() in govlib.line_text(text, m.start()).lower() for k in g.ANNOTATION_MARKERS):
                continue
            if any(k in cand for k in g.PLACEHOLDER_MARKERS):
                continue
            if g.foreign_platform(cand, "nt") or g.in_system_prefix(cand, "nt"):
                continue
            yield (rel, govlib.line_of(text, m.start()),
                   g.classify_line(text, m.start()) == "comment",
                   is_doc, g.parent_missing(cand), cand)


def cmd_scan(args) -> int:
    buckets: dict[str, int] = {}
    for rel, _, is_comment, is_doc, dead, _cand in iter_findings():
        key = "%s:%s:%s" % ("doc" if is_doc else "src", "comment" if is_comment else "code",
                            "dead" if dead else "live")
        buckets[key] = buckets.get(key, 0) + 1
    print("=== 全仓盘符路径分布（g01 口径）===")
    for k in sorted(buckets):
        print("  %-18s %d" % (k, buckets[k]))
    src_comment = sum(v for k, v in buckets.items() if k.startswith("src:comment"))
    doc_comment = sum(v for k, v in buckets.items() if k.startswith("doc:comment"))
    print("\n  源码/配置注释（src:comment）：%d 处  ← 铁律 5 的清洗域，其中保留项是门禁自身举例" % src_comment)
    print("  文档类（doc:comment）：      %d 处  ← dated 快照，默认不清（记录说当时如此）" % doc_comment)
    if args.list:
        print("\n=== src:comment 明细 ===")
        for rel, ln, is_comment, is_doc, dead, cand in iter_findings():
            if is_comment and not is_doc:
                print("  [%s] %s:%d  %s" % ("DEAD" if dead else "LIVE", rel, ln, cand))
    return 0


def cmd_strip(args) -> int:
    targets = ["platform/registry/projects"] if args.target == "registry" else ["platform/registry/projects"]
    pending: list[tuple[Path, int, str, str]] = []
    for root in targets:
        for path in sorted((ROOT / root).glob("*.yaml")):
            raw = path.read_text(encoding="utf-8")
            lines = raw.split("\n")
            for i, line in enumerate(lines):
                if not any(p.search(line) for p, _r in STRIP_SUBS):
                    continue
                new = line
                for p, r in STRIP_SUBS:
                    new = p.sub(r, new)
                if new != line:
                    pending.append((path, i, line, new))
    if not pending:
        print("=== 预演：无待清洗项（已清干净）===" if not args.apply else "=== 无待清洗项 ===")
        return 0
    if not args.apply:
        print("=== 预演：%d 处待清洗（加 --apply 才写盘）===" % len(pending))
        for path, i, old, new in pending[:40]:
            print("  %s:%d\n    - %s\n    + %s" % (path.relative_to(ROOT).as_posix(), i + 1,
                                                   old.strip()[:110], new.strip()[:110]))
        return 1
    touched: dict[Path, list[tuple[int, str]]] = {}
    for path, i, _old, new in pending:
        touched.setdefault(path, []).append((i, new))
    for path, edits in touched.items():
        lines = path.read_text(encoding="utf-8").split("\n")
        for i, new in edits:
            lines[i] = new
        path.write_text("\n".join(lines), encoding="utf-8", newline="")
        print("  %2d 处  %s" % (len(edits), path.relative_to(ROOT).as_posix()))
    print("\n合计：%d 处 / %d 个文件" % (len(pending), len(touched)))
    return 1


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="仓内盘符路径扫描 / 清洗（铁律 5）")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scan", action="store_true", help="全仓分组统计（不写盘）")
    mode.add_argument("--strip", action="store_true", help="清洗 registry 注释里的历史盘符路径")
    p.add_argument("--list", action="store_true", help="--scan 时附 src:comment 明细")
    p.add_argument("--apply", action="store_true", help="--strip 时真正写盘（默认预演）")
    p.add_argument("--target", default="registry", choices=["registry"], help="清洗目标（默认 registry）")
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("仓根：%s" % ROOT)
    return cmd_strip(args) if args.strip else cmd_scan(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
