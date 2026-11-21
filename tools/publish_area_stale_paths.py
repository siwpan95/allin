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

#: 整份文件都是历史留档 —— 里面的旧路径记的是「当时发生了什么」，不是让人照着做。
#: 实测误伤（2026-11-21 本机全量）：``adventurelog/log.txt`` 的运行日志与
#: ``an-engine/CHANGELOG.md`` 的变更条目被逐行替换并追加注释，等于篡改历史；
#: ``pq-multiverse/docs/项目总结.md``、``media-effect-migration-report.md`` 同理。
#: 行级 ``_EXPLANATION_MARKERS`` 拦不住这种「整份文件都是过去时」的形态 ——
#: 日志行里既没有「已失效」也没有「原」，却每一行都是历史事实，故必须在文件层排除。
_HISTORICAL_NAME_PARTS = (
    "changelog", "change-log", "history", "news", "report", "总结", "指导", "迁移",
)
_HISTORICAL_PATH_PARTS = (
    "audit/", "/audit", "记录/", "/records/", "/adr/", "adr-",
)
_HISTORICAL_SUFFIXES = (".log",)
#: 日志类文件名：``log.txt`` / ``run.log`` 之类，内容是运行痕迹而非指南。
_HISTORICAL_NAME_EXACT = ("log.txt", "log.md")


def is_historical_file(rel: str, fn: str) -> bool:
    """该文件是否属于历史留档（整份不改）。

    ``rel`` 是仓内相对路径（正斜杠），``fn`` 是文件名。
    """
    low_rel = rel.lower()
    low_fn = fn.lower()
    if low_fn.endswith(_HISTORICAL_SUFFIXES) or low_fn in _HISTORICAL_NAME_EXACT:
        return True
    if any(p in low_fn for p in _HISTORICAL_NAME_PARTS):
        return True
    if any(p in low_rel for p in _HISTORICAL_PATH_PARTS):
        return True
    return False


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


def _norm_name(s: str) -> str:
    """仓库名归一化：``pq-multiverse`` / ``pq_multiverse`` / ``PQ.Multiverse`` 视为同名。"""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _path_exists_under(root: Path | None, parts: list[str]) -> bool:
    """该相对路径在仓内是否真实存在（parts 为空 = 仓根本身，恒真）。

    ``root is None`` 时不做校验并返回 True —— 拿不到仓根就退回旧的「只按名字剥」
    行为，宁可少改也不错改。
    """
    if root is None or not parts:
        return True
    try:
        return (root.joinpath(*parts)).exists()
    except OSError:
        return True


#: 按仓缓存 ``{仓根: {子项名: [相对路径, …]}}``，供 basename 兜底查找用。
_NAME_INDEX: dict[str, dict[str, list[str]]] = {}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".deps",
              "dist", "build", "vendor"}


def _name_index(root: Path) -> dict[str, list[str]]:
    """仓内「文件名 → 相对路径列表」索引（懒建、按仓缓存）。"""
    key = str(root)
    if key in _NAME_INDEX:
        return _NAME_INDEX[key]
    index: dict[str, list[str]] = {}
    try:
        for p in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if p.is_file() or p.is_dir():
                index.setdefault(p.name, []).append(p.relative_to(root).as_posix())
    except OSError:
        pass
    _NAME_INDEX[key] = index
    return index


def _resolve_in_repo(root: Path | None, parts: list[str],
                     base_dir: str = "") -> list[str] | None:
    """把「旧仓根之后的路径尾巴」解析成**当前仓内真实存在**的相对路径。

    为什么需要它：旧仓根下的目录层级与当前仓布局并不一致，光删掉
    ``<旧仓根>`` 前缀会产出新的死路径。实测三类：

    * 独立仓 —— ``<旧仓根>/stay/pq_multiverse/src`` ⇒ 仓内就是 ``src``
      （中间的 ``stay/pq_multiverse`` 全属仓外）；
    * 仓根别名 —— ``<旧仓根>/hell_below_vn/build_all.py`` ⇒ novel-reader 的仓根
      内容就是 hell_below_vn 本身，故应为 ``build_all.py``；
    * **聚合仓** —— game-prototypes 仓下有 ``pq-multiverse/`` 子目录，同一句
      ``cd <旧仓根>/stay/pq_multiverse/src`` 在这里应解析成
      ``pq-multiverse/src``（且目录名是连字符，与旧路径的下划线不同名）。

    做法：从尾巴的每个起点尝试「逐段按归一化名解析到真实子项」，最长匹配优先；
    全都解析不了时退回「按 basename 全仓唯一命中」；仍不行返回 None。
    """
    if root is None or not parts:
        return None
    if _path_exists_under(root, parts):
        return parts
    # 1) 从每个起点逐段解析，取最长成功
    best: list[str] | None = None
    for start in range(len(parts)):
        cur = root
        real: list[str] = []
        ok = True
        for seg in parts[start:]:
            cand = cur / seg
            if cand.exists():
                real.append(seg)
                cur = cand
                continue
            try:
                match = [c.name for c in cur.iterdir()
                         if _norm_name(c.name) == _norm_name(seg)]
            except OSError:
                ok = False
                break
            if len(match) == 1:
                real.append(match[0])
                cur = cur / match[0]
            else:
                ok = False
                break
        if ok and real and (best is None or len(real) > len(best)):
            best = real
    if best:
        return best
    # 2) 当前文件所在目录兜底 —— 聚合仓里同名文件在多处存在（game-prototypes 下
    #    mahjong / sandbox / fish 各有一份 allin_engine），「全仓唯一命中」因此失效；
    #    但「一份文档引用的入口脚本通常就在它自己旁边」是可靠得多的上下文。
    if base_dir and parts:
        cand = root / base_dir / parts[-1]
        if cand.exists():
            return (Path(base_dir) / parts[-1]).as_posix().split("/")
    # 3) basename 全仓唯一命中兜底
    hits = _name_index(root).get(Path(parts[-1]).name, [])
    if len(hits) == 1:
        return hits[0].split("/")
    return None


#: 形态 a 里的「工具 + 目标」对，用于把命令尾部的相对路径也校正到仓内真实位置。
_TOOL_TARGET = re.compile(r"\b(pythonw?|pytest|cd)\s+((?!-)[^\s&;|]+)")


def _fix_relative_paths(text: str, repo_root: Path | None, base_dir: str = "") -> str:
    """把命令里的相对路径校正到**仓内真实存在**的位置。

    ``cd <旧仓根> && python allin_engine/x.py`` 去掉 cd 之后，命令本身仍可能指向
    旧布局（实测 fish 仓的实际位置是 ``tools/allin_engine/``，聚合仓 game-prototypes
    下则是 ``fish/tools/allin_engine/``）—— 只删盘符等于把「盘符死路径」换成
    「层级死路径」。能唯一解析的就改对，解析不了的保持原样（宁可不改也不错改）。
    """
    if repo_root is None:
        return text

    def _repl(m: re.Match[str]) -> str:
        tool, tgt = m.group(1), m.group(2)
        if re.match(r"^[A-Za-z]:", tgt) or tgt.startswith(("<", "/", "\\", "<")):
            return m.group(0)
        parts = [p for p in tgt.replace("\\", "/").split("/") if p]
        if not parts or _path_exists_under(repo_root, parts):
            return m.group(0)
        resolved = _resolve_in_repo(repo_root, parts, base_dir)
        return f"{tool} {'/'.join(resolved)}" if resolved else m.group(0)

    return _TOOL_TARGET.sub(_repl, text)


def make_replacement(line: str, repo_name: str = "", repo_root: Path | None = None,
                     rel_file: str = "") -> str | None:
    """算出该行应改成什么；None 表示不改。

    ``rel_file`` 是**当前文件**的仓内相对路径，用于在聚合仓里按「同目录」上下文
    解析出正确层级（见 :func:`_resolve_in_repo` 第 2 条兜底）。
    """
    base_dir = str(Path(rel_file).parent.as_posix()) if rel_file else ""
    if base_dir == ".":
        base_dir = ""
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
        cmd = _fix_relative_paths(m.group(2).strip(), repo_root, base_dir)
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
        # 交给仓内真实路径解析：既剥掉仓外层级（stay/pq_multiverse），
        # 也处理聚合仓（game-prototypes 下应得 pq-multiverse/src）。
        resolved = _resolve_in_repo(repo_root, parts, base_dir)
        parts = resolved if resolved else []
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
        rest = [p for p in tail[idx + 1:] if p]
        if rest and _norm_name(rest[0]) == _norm_name(repo_name):
            rest = rest[1:]
        # 旧仓根下的目录名未必等于当前仓库名（novel-reader 的仓根内容就是
        # <旧仓根>/hell_below_vn 本身），层级也未必只有一层（stay/pq_multiverse
        # 全属仓外）。统一交给仓内真实路径解析，解析不出来才降级为 <仓库根> 占位 ——
        # 占位符至少诚实，不会像残留旧路径那样看起来能跑。
        resolved = _resolve_in_repo(repo_root, rest, base_dir)
        return "/".join(resolved) if resolved else "<仓库根>"

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
            if is_historical_file(rel, fn):
                continue
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
                    rep = make_replacement(line, repo.name, repo, rel)
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
