#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sha256 摘要口径的单一实现（深度审计 P3 L-4 / #25 收敛）。

背景：仓内曾有 4 处各自手写 ``sha256(...).hexdigest()``，看似重复，实则分两族、
输入类型不同。**合并必须保持既有摘要值逐字节不变**，否则 facts marker、netbox
state、包映射对账全部漂移，直接破坏 P2 已验证的「生成物逐字节 IDENTICAL」。

两族刻意分开，函数命名区分，避免「为了统一而统一」把不同语义揉成一处：

* 结构化摘要族（输出 16 位十六进制）——对**内存中的确定性字节**取摘要，
  用于内容指纹 / 幂等键 / 溯源键。输入无跨副本 EOL 差异，**不做 LF 归一**
  （归一反而会改变既有指纹值）：
  - :func:`digest_obj`  — JSON 对象；``json.dumps(ensure_ascii=False, sort_keys=True)``
    是口径的一部分，供 facts/cli.py expected_hash 与 deploy/netbox digest 共用
    （这两处原算法逐字相同）。
  - :func:`digest_text` — 纯文本（如整段 SQL），供 deploy/dolt sql_sha256。

* 文件字节对账族（输出完整 64 位）——供 check_pkg_parity.py：
  - :func:`file_sha256` 读磁盘字节、LF 归一后取完整 sha256。归一遵循铁律 12：
    Windows 上 setuptools 把 wheel 内 .py 写成 CRLF，仓内 .gitattributes 强制
    eol=lf，同一份源码只是换行形态不同，不是漂移；**不截断**以免放大碰撞面。

零第三方依赖（标准库 hashlib / json / pathlib）。
退出码：selftest 0 全过 / 1 有漂移。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def digest_obj(obj) -> str:
    """结构化对象的确定性指纹（16 位十六进制）。

    ``ensure_ascii=False, sort_keys=True`` 是**口径本身**：改动会让所有既有 facts
    marker / netbox state 失配（与 P2 #19「生成物逐字节 IDENTICAL」同一纪律）。
    """
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def digest_text(text: str) -> str:
    """内存文本的确定性指纹（16 位十六进制）；输入无跨副本 EOL 差异，不做归一。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    """磁盘文件的完整 sha256（64 位），LF 归一后计算（跨 OS 对账，铁律 12）。

    调用前提：目标目录内均为文本源码（见 check_pkg_parity.REPO_ONLY_OK 的说明）；
    二进制内容经 CRLF→LF 替换会失真，不适用本函数。
    """
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def selftest() -> int:
    """锁定两族口径，防「收敛」过程里悄然改变既有摘要值。"""
    results: list[tuple[str, bool]] = []

    # 结构化族：与收敛前 facts/cli.py expected_hash、netbox digest 逐字同算法
    sample = {"b": 2, "a": "中文", "n": None, "lst": [3, 1]}
    legacy_obj = hashlib.sha256(
        json.dumps(sample, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    results.append(("digest_obj 与旧式逐字节一致", digest_obj(sample) == legacy_obj))
    results.append(("digest_obj 输出 16 位", len(digest_obj(sample)) == 16))
    results.append(("digest_obj 键序无关", digest_obj({"x": 1, "y": 2}) == digest_obj({"y": 2, "x": 1})))
    results.append(("digest_obj 非 ASCII 保留", digest_obj({"k": "中"}) != digest_obj({"k": "\\u4e2d"})))

    # 文本族：与收敛前 dolt sql_sha256 同算法
    sql = "SELECT 1;\nSELECT 2;\n"
    legacy_text = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
    results.append(("digest_text 与旧式逐字节一致", digest_text(sql) == legacy_text))
    results.append(("digest_text ≠ digest_obj(同形 JSON 串)", digest_text('{"a":1}') != digest_obj({"a": 1})))

    # 文件族：LF 归一 + 完整 64 位
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="allin-sha256util-"))
    a = root / "a.py"
    a.write_bytes(b"line1\r\nline2\r\n")
    b = root / "b.py"
    b.write_bytes(b"line1\nline2\n")
    c = root / "c.py"
    c.write_bytes(b"line1\nline2!\n")
    results.append(("file_sha256 CRLF/LF 归一一致", file_sha256(a) == file_sha256(b)))
    results.append(("file_sha256 完整 64 位", len(file_sha256(a)) == 64))
    results.append(("file_sha256 内容不同则不同", file_sha256(a) != file_sha256(c)))

    for label, ok in results:
        print("  {} {}".format("PASS" if ok else "FAIL", label))
    failed = sum(1 for _, ok in results if not ok)
    print("SHA256UTIL SELFTEST: {} passed, {} failed".format(len(results) - failed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(selftest())
