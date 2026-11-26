#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冲突标记判据（`check_conflict_markers.py`）—— registry 之外的编排层判据。

## 为什么需要它（事故来源）

`docs/记录/交接/2026-11.md` 里曾长期残留一行 `||||||| parent of fbb7940`——
一次合并的冲突标记没清干净就提交了。**当时没有任何一道门禁抓到它**：
`docs_index` 判的是索引契约、`relative_refs` 判链接、`g15` 判节结构与锚点，
全都不看"这一行是不是 git 留下的残骸"；而文件自己还记着「知道漏了」——
*文档承认漏了*，与*门禁能拦*，是两件事。

冲突标记是最典型的"局部看起来像正常文本"的损坏：`<<<<<<< HEAD` 在代码块里
长得跟示例一模一样，在 Markdown 里也能被当成普通段落。**只有机器能稳定判它。**

## 判什么

对 `git ls-files` 的每个文本文件逐行看**行首**：

| 形态 | 判 | 为什么 |
| --- | --- | --- |
| `<<<<<<<` | **红** | 冲突起点；git 生成的形态是 `<<<<<<< <ref>`，但截断形态同样说明"没清干净" |
| 七个竖线（diff3 的基线标记） | **红** | 只在 diff3 风格合并里出现，正常文本不会有 |
| `>>>>>>>` | **红** | 冲突终点 |
| `=======` | **仅当同文件已有上面三者之一时才算** | Markdown 的 setext 标题下划线、`---`/`===` 分隔线、ASCII 表格都用它；单独判会大面积误伤 |

**精确形态**：三个都按"行首连续 7 个该字符"判，**不要求尾随空格**
（`<<<<<<<` 与 `<<<<<<< HEAD` 都红）—— 标记被编辑器吞掉尾随空格仍是被漏清的残骸，
这时候放行等于让"被格式化过的冲突"过关。

**代码块里的冲突标记同样判红**：代码块里的 `<<<<<<<` 是**损坏**，不是示例。
真要举例，请写成 `<<<` 或加零宽字符以外的方式（本仓的取舍：宁可让写文档的人
换个写法，也不让真损坏混在"看起来像示例"里）。

## 范围与例外

- 语料：`git ls-files`（**未入索引的新文件不在扫描面里** —— 这是已知边界，
  由 `check_blind_gates.py --coverage-delta` 在编排层提示）。
- 跳过：二进制（前 8KB 含 NUL）、超过 `MAX_BYTES` 的文件（记 skipped 并计数，不冒充通过）。
- 不设白名单：没有任何目录"可以有冲突标记"。

## 用法

```bash
python tools/gate/check_conflict_markers.py            # 判本仓
python tools/gate/check_conflict_markers.py --root .   # 指定仓根
python tools/gate/check_conflict_markers.py --selfcheck
```

退出码：0 干净／1 有冲突标记／2 用法错／3 环境错（不是 git 仓）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

EXIT_OK, EXIT_FINDING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

ROOT = Path(__file__).resolve().parents[2]     # tools/gate/ → 仓根
MAX_BYTES = 2 * 1024 * 1024                    # 2MB：超过就不读（记 skipped，不冒充通过）
SNIFF_BYTES = 8192

#: 行首的三种强标记（7 个字符；**不要求**尾随空格）。
STRONG_MARKERS = {"<<<<<<<": "start", "|||||||": "base", ">>>>>>>": "end"}
#: 弱标记：只在同文件已有强标记时才算（Markdown 的 setext 下划线就是 `=======`）。
WEAK_MARKER = "======="


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=str(repo),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return proc.stdout


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """纯函数：返回 [(行号, 行首标记, 原文)]。便于自检直接喂字符串。"""
    strong_hits: list[tuple[int, str, str]] = []
    weak_hits: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        head = line[:7]
        if head in STRONG_MARKERS:
            strong_hits.append((lineno, head, line[:120]))
        elif head == WEAK_MARKER:
            weak_hits.append((lineno, head, line[:120]))
    # `=======` 只在同文件已有强标记时才算：单独出现时它是 Markdown 的 setext 下划线，
    # 也是 ASCII 分隔线 —— 单独判会把一半文档打成红。
    return strong_hits + (weak_hits if strong_hits else [])


def iter_files(repo: Path) -> list[str]:
    out = git(repo, "ls-files")
    return [line.strip() for line in out.split("\n") if line.strip()]


def scan_repo(repo: Path) -> dict:
    findings: list[dict] = []
    scanned = skipped = 0
    for rel in iter_files(repo):
        path = repo / rel
        try:
            size = path.stat().st_size
        except OSError:
            skipped += 1
            continue
        if size > MAX_BYTES:
            skipped += 1
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            skipped += 1
            continue
        if b"\x00" in raw[:SNIFF_BYTES]:
            skipped += 1          # 二进制不是本判据的对象
            continue
        scanned += 1
        text = raw.decode("utf-8", errors="replace")
        for lineno, marker, line in scan_text(text):
            findings.append({"file": rel, "line": lineno, "marker": marker,
                             "text": line.strip()[:100]})
    return {"scanned": scanned, "skipped": skipped, "findings": findings}


def run(repo: Path, as_json: bool) -> int:
    if not (repo / ".git").exists():
        print(f"ENV ERROR: {repo} 不是 git 仓（本判据的语料来自 git ls-files）。",
              file=sys.stderr)
        return EXIT_ENV
    report = scan_repo(repo)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"conflict_markers: scanned {report['scanned']} file(s); "
              f"blocking {len(report['findings'])}; skipped {report['skipped']}")
        for item in report["findings"][:200]:
            print(f"  BLOCK {item['file']}:{item['line']} [{item['marker']}] {item['text']}")
        if len(report["findings"]) > 200:
            print(f"  … 另 {len(report['findings']) - 200} 处（见 --json）")
        if report["findings"]:
            print("  修法：删除冲突标记与冲突正文中不保留的一侧，"
                  "然后 `git add` 重新暂存（这不是格式问题，是内容没合并完）")
        elif report["scanned"] == 0:
            print("[SKIP] conflict_markers:skip(no-files) —— 索引里没有可扫的文本文件（not a pass）")
    return EXIT_FINDING if report["findings"] else EXIT_OK


# ---------------------------------------------------------------- 自检
def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def selfcheck() -> int:
    """6 例：四条必红/必绿的负对照 + 两条边界（=`=======` 单独 vs 与强标记同现）。"""
    cases: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(prefix="conflict-markers-") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True)
        subprocess.run(["git", "config", "user.email", "selfcheck@example.invalid"],
                       cwd=str(repo), check=True)
        subprocess.run(["git", "config", "user.name", "SelfCheck"], cwd=str(repo), check=True)

        # ① 行首 `<<<<<<< `（带尾随空格，git 的原始形态）⇒ 必红
        _write(repo, "docs/a.md", "正常一行\n<<<<<<< HEAD\n冲突内容\n=======\n其他\n>>>>>>> b\n")
        got = scan_text((repo / "docs/a.md").read_text(encoding="utf-8"))
        cases.append(("行首 `<<<<<<< ` 必红（git 原始形态）",
                      {m for _, m, _ in got} >= {"<<<<<<<", "=======", ">>>>>>>"}))

        # ② `<<<<<<<` 无尾随空格 ⇒ 也必红（被编辑器吞掉空格的残骸同样是漏清）
        _write(repo, "docs/b.md", "前言\n<<<<<<<\n正文\n")
        got = scan_text((repo / "docs/b.md").read_text(encoding="utf-8"))
        cases.append(("`<<<<<<<` 无尾随空格也红（精确到 7 字符，不靠尾随空格）",
                      [m for _, m, _ in got] == ["<<<<<<<"]))

        # ③ 正常文件 ⇒ 绿
        _write(repo, "docs/c.md", "# 标题\n\n正文段落\n\n| a | b |\n| --- | --- |\n")
        cases.append(("正常文件不误伤", scan_text(
            (repo / "docs/c.md").read_text(encoding="utf-8")) == []))

        # ④ 代码块里的冲突标记 ⇒ 同样判红（代码块里的标记也是损坏，不是示例）
        _write(repo, "docs/d.md", "示例：\n\n```text\n<<<<<<< HEAD\n```\n")
        got = scan_text((repo / "docs/d.md").read_text(encoding="utf-8"))
        cases.append(("代码块里的冲突标记同样判红（不做代码块豁免）",
                      [m for _, m, _ in got] == ["<<<<<<<"]))

        # ⑤ `=======` 单独出现 ⇒ 绿（Markdown setext 标题 / 分隔线都用它）
        _write(repo, "docs/e.md", "标题\n=======\n\n下一节\n")
        cases.append(("`=======` 单独出现不判（setext 标题误伤对照）",
                      scan_text((repo / "docs/e.md").read_text(encoding="utf-8")) == []))

        # ⑥ diff3 形态 `|||||||` 红 + 全量扫描口径（语料来自 `git ls-files`）
        _write(repo, "docs/f.md", "||||||| parent of fbb7940\n两边不同\n")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
        report = scan_repo(repo)
        files_hit = {item["file"] for item in report["findings"]}
        cases.append(("diff3 的 `||||||| parent of …` 必红（本次事故的原始形态）",
                      "docs/f.md" in files_hit and report["scanned"] >= 5
                      and {"docs/a.md", "docs/b.md", "docs/d.md"} <= files_hit
                      and not ({"docs/c.md", "docs/e.md"} & files_hit)))

    passed = 0
    for name, ok in cases:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        passed += 1 if ok else 0
    print(json.dumps({"cases": len(cases), "passed": passed}, ensure_ascii=False))
    print(f"SELFCHECK: {'PASS' if passed == len(cases) else 'FAIL'} —— "
          f"{passed}/{len(cases)}（必要红、应静、误伤三类都验过）")
    return EXIT_OK if passed == len(cases) else EXIT_FINDING


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="冲突标记判据")
    parser.add_argument("--root", default=str(ROOT), help="仓根（默认本仓）")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()
    try:
        return run(Path(args.root).resolve(), args.as_json)
    except RuntimeError as error:
        print(f"ENV ERROR: {error}", file=sys.stderr)
        return EXIT_ENV


if __name__ == "__main__":
    raise SystemExit(main())
