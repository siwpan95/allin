#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词库导出 —— 把 allin 的事实源投影成「个人专名词库」，供输入法等下游消费。

## 为什么要有这个

2026-11-24 用户提法：「把随包分发的工具中的输入法改成 allin 特供版，接入扫盘，
这样就不用下字典，改用 allin 作为内容库。让随包工具都能物尽其用。」

实测支撑（〔本机〕`@SIWPAN` 2026-11-24）：

- `allin-toolkit` 包里的 `print`（拼音输入法）需要三份外部数据：
  `char_base.json`（单字）/ `word.json`（32 万词）/ `idiom.json`（5 万成语），
  来源 GitHub `mapull/chinese-dictionary`；
- 本机对它的三个下载源（jsdelivr / raw.githubusercontent / ghproxy）**全部 DNS 失败**（curl 000）；
- 本地只剩 `char_base.json`（2.8 MB / 20,902 字），词库与成语**都缺**；
- 而 `print` 的 `load_word_dict()` 对缺文件是优雅降级（未建索引、不崩）⇒ 目前能逐字打字，
  **没有词语联想**。

于是问题不是「下载不到」，而是「为什么要下」。这个仓库里有 569 条它最该认识的词：
自己的项目名、工具名、术语。本脚本把它们导出来。

## 职责边界（重要，别越界）

- **allin 只供「词 + 权重」，不生成拼音。** 拼音要靠单字表反查，而单字表在消费方那边
  （`print/dictionary/.../char_base.json`）。让 allin 去依赖某个具体输入法的数据目录，
  等于把「公共核」重新绑死在一台机器的某个安装上 —— 刚拆掉的东西不能再装回去。
- 因此产物是 **TSV**：`词<TAB>权重<TAB>来源`，中文词与英文标识符都在里面，
  消费方自己决定「英文直出」还是「反查拼音」。

## 词源与权重（权重只表相对优先级，不是频率）

| 来源 | 权重 | 为什么这个值 |
| --- | --- | --- |
| `registry-id` | 100 | 仓名是最核心的专名（`cordis-py` / `musickit`） |
| `registry-name` | 80 | 项目中文名按 `·`/`|`/括号拆段，单段 ≥2 字才收 |
| `tiering` | 70 | 分级台账里的仓名（补充 registry 未覆盖的） |
| `tools` | 70 | 工具台账 |
| `spec-term` | 40 | 规范文档反引号里的英文标识符（`repocheck` / `observed`…） |

## 用法

    python tools/lexicon.py                      # 打印 TSV 到 stdout
    python tools/lexicon.py --out facts/generated/lexicon.tsv
    python tools/lexicon.py --json               # 机读（含统计）
    python tools/lexicon.py --min-weight 70      # 只要核心专名

零第三方依赖（仅标准库）。退出码：0 成功 / 2 用法错 / 3 环境错（找不到仓根）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:  # 包内形态（allin_governance._toolkit.*）
    from .exit_codes import EXIT_ENV, EXIT_OK, EXIT_USAGE
except ImportError:  # 仓内直跑形态
    try:
        from exit_codes import EXIT_ENV, EXIT_OK, EXIT_USAGE
    except ImportError:  # 兜底：本文件可能被单独拷走
        EXIT_OK, EXIT_USAGE, EXIT_ENV = 0, 2, 3

REPO_MARKERS = ("docs", "preset", "tools")

#: registry 中文名里的分隔符：`allin · 工作区治理仓（文档枢纽 + 可执行门禁）`
NAME_SPLIT = re.compile(r"[·・|｜/（）()\s+]+")

#: 规范文档里的英文标识符（反引号包裹、小写开头、3–30 字符）
SPEC_TERM = re.compile(r"`([a-z][a-z0-9_\-]{2,30})`")

#: 词条清洗：这些字符在仓名/项目名里是**排版装饰**，进词库只会污染候选窗
#: （实测 `worldwright《造界》`、`③收敛合并落点`、`七宗罪VS七美德` 这类会被直接收进来）
DECOR = re.compile(r"[《》「」『』（）()【】\[\]·・|｜/\\*#>①②③④⑤⑥⑦⑧⑨⑩,，。.!?！？:：;；\"'`~@$%^&+=]")

CJK = re.compile(r"^[\u4e00-\u9fff]+$")
#: 允许数字开头（`3dworld` / `3dworld-demos` 是本仓真实仓名），但必须含字母 ——
#: 纯数字串当词条没有意义（打 `123` 出 `123` 是噪声）
IDENT = re.compile(r"^(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9_\-]*$")


def classify(word: str) -> str:
    """`cjk` / `ascii` / `mixed` —— 消费方据此决定「反查拼音」还是「按键直出」。"""
    if CJK.match(word):
        return "cjk"
    if IDENT.match(word):
        return "ascii"
    return "mixed"


def find_repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if all((parent / m).is_dir() for m in REPO_MARKERS):
            return parent
    return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def collect(root: Path) -> dict[str, tuple[int, str]]:
    """返回 {词: (权重, 来源)}。同词多源时保留**最高权重**那条（来源一并留下便于溯源）。"""
    words: dict[str, tuple[int, str]] = {}

    def put(word: str, weight: int, source: str) -> None:
        word = DECOR.sub("", word.strip()).strip()
        if not word or len(word) < 2 or len(word) > 32:
            return
        # 装饰清掉后若只剩数字/单个字符，放进去只会占候选窗
        if not any(c.isalpha() or "\u4e00" <= c <= "\u9fff" for c in word):
            return
        old = words.get(word)
        if old is None or weight > old[0]:
            words[word] = (weight, source)

    reg_dir = root / "platform" / "registry" / "projects"
    for path in sorted(reg_dir.glob("*.yaml")) if reg_dir.is_dir() else []:
        text = _read(path)
        m = re.search(r"^id:\s*(.+)$", text, re.M)
        put(m.group(1) if m else path.stem, 100, "registry-id")
        m = re.search(r"^name:\s*(.+)$", text, re.M)
        if m:
            for seg in NAME_SPLIT.split(m.group(1).strip().strip("\"'")):
                put(seg, 80, "registry-name")

    for rel, key, weight, source in (
        ("docs/事实源/tiering.yaml", "repo", 70, "tiering"),
        ("docs/事实源/tools.yaml", "tool", 70, "tools"),
    ):
        path = root / rel
        if path.is_file():
            for m in re.finditer(rf"^- {key}:\s*(.+)$", _read(path), re.M):
                put(m.group(1), weight, source)

    spec_dir = root / "docs" / "规范"
    for path in sorted(spec_dir.glob("*.md")) if spec_dir.is_dir() else []:
        for term in SPEC_TERM.findall(_read(path)):
            put(term, 40, "spec-term")

    return words


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lexicon",
        description="把 allin 事实源导出成个人专名词库（TSV: 词/权重/来源），供输入法等下游消费",
    )
    parser.add_argument("--root", help="仓根（默认按脚本位置向上探测）")
    parser.add_argument("--out", help="写入该文件（默认打印到 stdout）")
    parser.add_argument("--json", action="store_true", help="机读输出（含按来源统计）")
    parser.add_argument("--min-weight", type=int, default=0, help="只导出权重 ≥ N 的词（如 70 = 仅核心专名）")
    args = parser.parse_args(argv)

    if args.root:
        root: Path | None = Path(args.root).resolve()
        if not (root / "docs").is_dir():
            print(f"ENV ERROR: --root 指向的目录不含 docs/：{root}", file=sys.stderr)
            return EXIT_ENV
    else:
        root = find_repo_root()
        if root is None:
            print("ENV ERROR: 找不到仓根（需含 docs/ preset/ tools/）；本脚本消费的是仓内事实源，"
                  "没有仓就没有词源 —— 用 --root 指定仓根。", file=sys.stderr)
            return EXIT_ENV

    words = {w: v for w, v in collect(root).items() if v[0] >= args.min_weight}
    if not words:
        print("ENV ERROR: 一个词都没导出 —— 检查 registry/projects 与 docs/事实源/ 是否为空",
              file=sys.stderr)
        return EXIT_ENV

    stats: dict[str, int] = {}
    for _w, (_weight, source) in words.items():
        stats[source] = stats.get(source, 0) + 1

    if args.json:
        payload = {
            "total": len(words),
            "by_source": dict(sorted(stats.items(), key=lambda kv: -kv[1])),
            "min_weight": args.min_weight,
            "words": [
                {"word": w, "weight": v[0], "source": v[1]}
                for w, v in sorted(words.items(), key=lambda kv: (-kv[1][0], kv[0]))
            ],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    else:
        lines = [
            "# allin 个人专名词库 —— 词<TAB>权重<TAB>来源<TAB>kind",
            "# 生成：python tools/lexicon.py（可重建产物，勿手改）",
            "# 拼音由消费方用单字表反查生成，本文件不含读音（见脚本 docstring 的职责边界）",
            "# kind: cjk=纯汉字（需反查拼音） / ascii=英文标识符（按键直出） / mixed=混排（建议跳过）",
        ]
        for word, (weight, source) in sorted(words.items(), key=lambda kv: (-kv[1][0], kv[0])):
            lines.append(f"{word}\t{weight}\t{source}\t{classify(word)}")
        text = "\n".join(lines) + "\n"

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"written: {out}（{len(words)} 词 / {out.stat().st_size} 字节）")
    else:
        print(text, end="")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
