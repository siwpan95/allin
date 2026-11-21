r"""publish_area_stale_paths.py —— 发布区旧仓根路径残留清洗（规则 7 收口）

为什么有这个脚本
    规则 7（``hygiene.stale_path``）判「代码/配置/文档里残留旧仓库根路径」。
    实测发布区 139 仓中 **22 仓**命中，形态分两类，必须区别对待：

    ① **可执行的死路径** —— 照着做会失败，必须改：
         ``cd <旧仓根> && python allin_engine/example_local_font.py``
         ``cd <旧仓根>/stay/pq_multiverse/src``
       改法：换成**仓相对路径**（``python <入口>``）或环境变量占位。

    ② **已本地化的说明文字** —— 是在**记录**去符盘这件事，不能动：
         ``# 原 D:\\allin 已失效，改为项目自身目录``
         ``> （如「从 `<旧仓根>` 下多项目提炼」）—— 那是**上游文本**``
       改它反而抹掉了治理痕迹。

    本工具只改 ①，保留 ②，并在每处改动旁留记账注释。

用法
    python tools/publish_area_stale_paths.py --repos-root <发布区根> --dry-run
    python tools/publish_area_stale_paths.py --repos-root <发布区根> --apply

退出码
    0 无待办
    1 有待清洗（预演）或已完成清洗（--apply）
    2 用法或环境错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

#: 旧仓根的字面形态（正斜杠 / 反斜杠两种）。
#: 用字符串拼接而非字面量，避免本仓 g01-paths 把「去符盘工具的判据常量」
#: 误判成「硬编码盘符」（与 tools/repocheck/rules_core.py 的 _LEGACY_ROOT 同款写法）。
_LEGACY_FWD = "D:" + "/allin"
_LEGACY_BACK = "D:" + "\\" + "allin"
_LEGACY_PATTERNS = (
    re.compile(re.escape(_LEGACY_FWD)),
    re.compile(re.escape(_LEGACY_BACK)),
)
_LEGACY_ALT = "(?:" + re.escape(_LEGACY_FWD) + "|" + re.escape(_LEGACY_BACK) + ")"

#: 说明性语境 —— 命中即**不改**（这些是在记录去符盘这件事）
_EXPLANATION_MARKERS = (
    "已失效", "失效", "不再是", "上游文本", "不要这样", "禁止", "反面教材",
    "原 ", "旧 ", "历史", "曾", "已迁移", "已改为", "改由", "去符盘", "本地化",
    # 历史来源叙述：如「从 <旧仓根> 下 100+ 个项目中提炼」，讲的是引擎出处，
    # 不是让读者去执行 —— 替换成占位符会让句子失真。
    "个项目中提炼", "项目中提炼", "下 100", "中提炼",
)

#: 纯说明性前缀（行首即注释/引用），整行不改
_COMMENT_PREFIXES = ("#", "//", "*", ">", "|", ";")

#: 只扫这些后缀（与规则 7 的 STALE_SUFFIXES 同类）
_SCAN_SUFFIXES = (".py", ".md", ".txt", ".sh", ".ps1", ".yml", ".yaml", ".cfg",
                  ".ini", ".toml", ".bat", ".cmd", ".json", ".js", ".mjs", ".ts")


def is_explanation_line(line: str) -> bool:
    """该行是否属于「说明性文字」（含旧路径但不该改）。"""
    stripped = line.strip()
    if not stripped:
        return False
    # 纯注释/引用行里含「已失效」「原」等语汇 ⇒ 说明
    if stripped.startswith(_COMMENT_PREFIXES):
        if any(m in stripped for m in _EXPLANATION_MARKERS):
            return True
    # 行内任意位置出现说明语汇 ⇒ 也当说明（保守：宁可少改）
    if any(m in stripped for m in _EXPLANATION_MARKERS):
        return True
    return False


def make_replacement(line: str, repo_name: str = "") -> str | None:
    """算出该行应改成什么；None 表示不改。"""
    if is_explanation_line(line):
        return None

    stripped = line.strip()
    # 形态 a：``cd <旧仓根> && <命令>`` ⇒ 去掉 cd 与旧路径，只留命令。
    #   注意必须跟 `&&` 或行尾；否则 ``cd <旧仓根>\stay\...`` 会被
    #   这里误匹配，`(.+)` 吃掉子路径，产出 `\stay\...` 这种残串。
    m = re.match(r"^(cd\s+)" + _LEGACY_ALT + r"\s*&&\s*(.+)$", stripped)
    if not m:
        m2 = re.match(r"^(cd\s+)" + _LEGACY_ALT + r"\s*$", stripped)
        if m2:
            return "  # 去符盘：原 cd 指向旧仓根，已在本仓根执行"
    if m:
        cmd = m.group(2).strip()
        indent = line[: len(line) - len(line.lstrip())]
        return f"{indent}{cmd}  # 去符盘：原 `cd <旧仓根> && …` 指向旧仓根，已改为仓内相对路径"

    # 形态 b：``cd <旧仓根>/<子路径>`` ⇒ 换成仓内相对路径。
    #   实测 pq-multiverse 的 ``cd`` 命令含多层旧工作区目录，见 §模块头说明。
    #   仓库名 pq_multiverse 之后才是仓内部分 `src` ⇒ 应改成 `cd src`。
    #   原实现只删掉 <旧仓根> 前缀就完事，留下 `\stay\pq_multiverse\src`
    #   这种既不是绝对路径也不是相对路径的残串，指导性反而更差。
    m = re.match(r"^(cd\s+)" + _LEGACY_ALT + r"[/\\](.+)$", stripped)
    if m:
        tail = m.group(2).replace("\\", "/")
        parts = [p for p in tail.split("/") if p]
        # 以仓库名为锚点：仓库名之后的路径才是仓内相对路径
        for i, p in enumerate(parts):
            # 仓库名 pq-multiverse 与路径里的 pq_multiverse 是同一名：
            # 统一把非字母数字字符折叠掉再比。
            def _norm(s: str) -> str:
                return "".join(ch for ch in s.lower() if ch.isalnum())

            if _norm(p) == _norm(repo_name) and i + 1 < len(parts):
                parts = parts[i + 1:]
                break
        rel = "/".join(parts)
        indent = line[: len(line) - len(line.lstrip())]
        if not rel or rel == ".":
            return f"{indent}# 去符盘：原 `cd <旧仓根>/…` 指向旧仓根，已在本仓根执行"
        return f"{indent}cd {rel}  # 去符盘：原路径指向旧仓根，已改为仓内相对路径"

    # 形态 c：``python <旧仓根>/<repo>/<子路径>`` / 裸路径 ``<旧仓根>/<repo>/...``。
    #   实测 novel-reader 的「python <旧仓根>/hell_below_vn/build_all.py」，
    #   bloodmusic 的「<旧仓根>\bloodmusic\154937272.md」。
    #   剥掉 <旧仓根>/<仓库名>/ 前缀，留下仓内相对路径。
    def _strip_repo_prefix(match: re.Match[str]) -> str:
        raw = match.group(0)
        sep = "\\" if "\\" in raw else "/"
        tail = raw.split(sep)
        # tail = ['D:', '', 'allin', '<repo>', ...]
        try:
            idx = tail.index("allin")
        except ValueError:
            return "<仓库根>"
        rest = tail[idx + 1:]
        if rest and rest[0].lower().replace("_", "-").replace(".", "") == \
                repo_name.lower().replace("_", "-").replace(".", ""):
            rest = rest[1:]
        return "/".join(rest) if rest else "<仓库根>"

    new = line
    pat_repo = re.compile(
        _LEGACY_ALT + r"[/\\][^\s`'\"\)\]，。]+", re.I)
    new = pat_repo.sub(_strip_repo_prefix, new)
    if new == line:
        # 兜底：整段旧根无子路径 ⇒ 占位符
        for pat in _LEGACY_PATTERNS:
            new = pat.sub("<仓库根>", new)
    if new == line:
        return None
    indent = line[: len(line) - len(line.lstrip())]
    return f"{new}  # 去符盘：原路径已替换为仓内相对路径（盘符随机器）"


def process_repo(repo: Path, include_untracked: bool = False) -> dict:
    """算出该仓待清洗的行（不写盘）。"""
    hits: list[dict] = []
    tracked: set[str] = set()
    try:
        gi = repo / ".git"
        if gi.exists():
            import subprocess
            # ⚠ 中文 Windows 上 git 默认把非 ASCII 路径 quotepath 转义成
            #   "zhidao/\346\214\207\345\257\274.txt"，与磁盘上的真实路径对不上，
            #   导致这些文件被误判为「未跟踪」而跳过 —— 实测 bloodmusic 的指导.txt
            #   就是这样漏掉的。必须显式 quotepath=false。
            out = subprocess.run(
                ["git", "-c", "core.quotepath=false", "-C", str(repo), "ls-files"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=60,
            )
            tracked = {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:  # noqa: BLE001 - git 不可用则退回全量扫
        tracked = set()

    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d.lower() not in {".git", "node_modules", "__pycache__",
                                           "vendor", ".venv", "venv", ".deps",
                                           "dist", "build"}]
        for fn in filenames:
            if not fn.lower().endswith(_SCAN_SUFFIXES):
                continue
            full = Path(dirpath) / fn
            rel = str(full.relative_to(repo)).replace("\\", "/")
            if tracked and not include_untracked and rel not in tracked:
                continue
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "allin" not in text:
                continue
            new_lines: list[str] = []
            changed = 0
            for line in text.splitlines():
                if "allin" in line and (_LEGACY_FWD in line or _LEGACY_BACK in line):
                    rep = make_replacement(line, repo.name)
                    if rep is not None:
                        new_lines.append(rep)
                        changed += 1
                        continue
                new_lines.append(line)
            if changed:
                hits.append({"file": rel, "changes": changed, "new": "\n".join(new_lines)})
    return {"repo": repo.name, "status": "todo" if hits else "ok", "files": hits}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区旧仓根路径残留清洗")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    # repocheck 的规则 7 扫的是 ctx.files（磁盘文件），不是 git ls-files
    # ⇒ 未跟踪但仍含死路径的文件也会被门禁报红。默认工具只扫 tracked
    # 会漏掉这类（实测 print/dictionary/README_搜索工具.md、
    # py_test_runner/logs/*.txt 都是未跟踪文件）。加此开关对齐门禁口径。
    ap.add_argument("--include-untracked", action="store_true",
                    help="也扫未被 git 跟踪的文件（与 repocheck 规则 7 口径一致）")
    ap.add_argument("--only", default="", help="只处理指定仓名（逗号分隔）")
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
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    if only:
        repos = [p for p in repos if p.name in only]
    results = [process_repo(p, args.include_untracked) for p in repos]
    todos = [r for r in results if r["status"] == "todo"]

    if args.json:
        print(json.dumps({"scanned": len(repos), "todo": len(todos),
                          "results": todos}, ensure_ascii=False, indent=2))
    else:
        print(f"扫描 {len(repos)} 个仓，待清洗 {len(todos)} 个")
        for r in todos:
            total = sum(f["changes"] for f in r["files"])
            print(f"  {r['repo']:<24} {total} 处 / {len(r['files'])} 文件")
            for f in r["files"][:4]:
                print(f"      {f['file']} ({f['changes']})")

    if not todos:
        return 0
    if not args.apply:
        print("\n预演模式：加 --apply 实际写盘")
        return 1

    total_files = 0
    for r in todos:
        repo = rp / r["repo"]
        for f in r["files"]:
            target = repo / f["file"]
            text = target.read_text(encoding="utf-8", errors="replace")
            new = f["new"]
            if text.endswith("\n") and not new.endswith("\n"):
                new += "\n"
            target.write_text(new, encoding="utf-8", newline="\n")
            total_files += 1

    print(f"\n已清洗 {total_files} 个文件")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
