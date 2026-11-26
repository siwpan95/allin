#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器分区的**单点真相**读取器：谁是真机、谁是归档位。

## 为什么需要单独一个模块

「哪几个目录是机器」这件事，2026-11-26 之前是**各判据各自推断**的：
`facts_drift` 数目录、`golden_batch` 数覆盖、`machine_ledger` 写死常量、
`check_machine_trailer` 又写死一次。归档位（`kind: archive`）一进来，
四种推断同时变成四种错法——其中两种会把「3 台机」读成「4 台」，
而「3 台机」这个数散落在 g20、facts_parity、SPEC-204 架构图里，会一路传染。

所以：**唯一真相住在 `docs/事实源/机器分区索引.md`**（人在那里写 `kind: archive`），
本模块只做一件事——把它读成两个集合。判据不许自己再推断。

## 为什么不能写死 `PROTOTYPE-01`

写死名字等于把「哪台是归档位」变成代码里的第二份真相：换代号、加第二个归档位、
或把归档位转成真机时，代码不会跟着变，而**变化不会报错，只会让数字悄悄偏一格**。
名字写在索引里，判据读索引 —— 这才是单点。

## 用法

```python
from machine_index import archive_ids, real_machines
archive_ids(root)      # {"PROTOTYPE-01"}（从索引读，不写死）
real_machines(root)    # 目录里有分区文件、且不在归档位集合里的那些
```

退出码：import 即用，无 CLI；`python machine_index.py` 只做人类可读的自检输出。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]          # tools/gate/ → 仓根
MACHINE_DIR = Path("docs") / "事实源" / "机器"
INDEX_FILE = Path("docs") / "事实源" / "机器分区索引.md"

#: 归档位标题形如：`### 归档位（`kind: archive`，**不是第四台机**）`
_ARCHIVE_HEAD = re.compile(r"kind\s*:\s*archive", re.IGNORECASE)
_CODE = re.compile(r"`([A-Za-z0-9][A-Za-z0-9._-]{1,63})`")


def parse_archive_ids(text: str) -> set[str]:
    """从索引正文里读出归档位代号（纯函数，便于自检直接喂字符串）。

    只认**归档位小节内的表格首列**：`| \\`PROTOTYPE-01\\`（原型机） | … |`。
    不做"全文搜 kind: archive"——正文里讨论归档位时也会提到这个词，
    那会把真机名字误吸进归档集合（一次误吸 = 一台真机的月账被漏判）。
    """
    ids: set[str] = set()
    in_archive_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            # 任何标题都是小节边界；只有含 `kind: archive` 的那个才算归档位小节
            in_archive_section = bool(_ARCHIVE_HEAD.search(line))
            continue
        if not in_archive_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or cells[0] in ("代号", "---") or set(cells[0]) <= {"-", " "}:
            continue
        found = _CODE.findall(cells[0])
        if found:
            ids.add(found[0])
    return ids


def archive_ids(root: Path | str = ROOT) -> set[str]:
    """归档位代号集合。索引文件缺席 ⇒ 空集（宁可不豁免，也不凭空豁免）。"""
    path = Path(root) / INDEX_FILE
    try:
        return parse_archive_ids(path.read_text(encoding="utf-8"))
    except OSError:
        return set()


def real_machines(root: Path | str = ROOT) -> list[str]:
    """真机清单 = 有 `<名>/<名>.md` 分区文件、且**不在**归档位集合里的目录。"""
    root = Path(root)
    base = root / MACHINE_DIR
    skip = archive_ids(root)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and (p / f"{p.name}.md").is_file() and p.name not in skip)


def _main() -> int:
    print(f"索引文件：{INDEX_FILE.as_posix()}")
    print(f"归档位  ：{sorted(archive_ids()) or '（无）'}")
    print(f"真机    ：{real_machines() or '（无）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
