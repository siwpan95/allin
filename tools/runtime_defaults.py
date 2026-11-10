#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行时超时默认值 —— 单一事实源（审计 M-10 / P2 #20）。

权威源
------
``docs/事实源/runtime_defaults.json``：``{"unit": "seconds", <key>: <正整数>, ...}``。
业务判据集中在本模块（key 须 snake_case、值须 int>0 且非 bool、必带 unit=="seconds"），
**零第三方依赖、零 import cli**（JSON 走标准库，避免污染 sys.modules["cli"]；
便携 Python 缺 PyYAML 也不会让门禁假红，Node 侧可直接 JSON.parse）。

语义（对齐 P1 #7，且比 facts 更严）
----------------------------------
* 权威源**缺席** → ConfigError(kind="missing")，**绝不静默回落默认值**：
  超时配置是运行时必需件，不是「可删可重建的派生物」，缺席必须显式报错。
* 在场但 JSON 解析失败 / 顶层非 dict / 缺 unit / unit≠seconds / key 非法 /
  值非正整数 → ConfigError（各自 kind），**绝不判绿**。
* 这与 ``tools/facts/cli.py::yaml_load``（缺席→None 允许 SKIP）**刻意相反**：
  端口/事实派生物可缺席，运行时超时默认值不可缺席。

退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错（权威源缺席/不可读）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

# 权威源相对仓根定位（治理铁律 5：从脚本位置自发现，不写死盘符）
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTH = ROOT / "docs" / "事实源" / "runtime_defaults.json"

SECONDS_UNIT = "seconds"
_ALLOWED_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_CALL_RE_TPL = r"timeout\(\s*['\"]%s['\"]\s*\)"

# 迁移映射表：每处 = (相对仓根路径, 迁移前字面量秒数, timeout key)。
# check() 逐条断言 timeout(key)==字面量（值不变证明）+ 源码确有 timeout(key) 调用（迁移落地证明）。
MIGRATIONS: tuple[tuple[str, int, str], ...] = (
    # 首批 8 处（值不变，仅把字面量换成 timeout(key)）
    ("deploy/dolt/import_from_git.py", 10, "git_probe"),          # git_commit_time  git show
    ("deploy/dolt/import_from_git.py", 10, "git_probe"),          # git_sha          git rev-parse
    ("deploy/dolt/import_from_git.py", 180, "subprocess_long"),   # run_cmd  stdin 分支
    ("deploy/dolt/import_from_git.py", 180, "subprocess_long"),   # run_cmd  无 stdin 分支
    ("deploy/graphrag/build_input.py", 60, "subprocess_default"),  # tracked  git ls-files
    ("deploy/netbox/sync_from_git.py", 10, "git_probe"),          # git_sha          git rev-parse
    ("deploy/netbox/sync_from_git.py", 15, "network_probe"),      # apply_remote    urlopen
    ("tools/build_portfolio.py", 60, "url_open"),                 # fetch_all       urlopen
    # 追加 9 处：venv_security.py 纯 subprocess 超时；60/120/300/900 四种值，
    # 120/300/900 无现成 key，新增专用 key 以保持「值不变」（详见报告）。
    ("tools/security/venv_security.py", 60, "subprocess_default"),     # standalone_uv_version  uv --version
    ("tools/security/venv_security.py", 60, "subprocess_default"),     # probe  <py> --version
    ("tools/security/venv_security.py", 120, "subprocess_pip"),        # pip_works  <py> -m pip --version
    ("tools/security/venv_security.py", 300, "subprocess_ensurepip"),  # PipBootstrap.apply 第 1 次 ensurepip
    ("tools/security/venv_security.py", 300, "subprocess_ensurepip"),  # PipBootstrap.apply 隔离后第 2 次
    ("tools/security/venv_security.py", 120, "subprocess_pip"),        # Baseline.verify  pip --version
    ("tools/security/venv_security.py", 120, "subprocess_pip"),        # Baseline.verify  <py> -c 校验 certifi
    ("tools/security/venv_security.py", 900, "subprocess_install"),    # Baseline.apply  pip install --upgrade
    ("tools/security/venv_security.py", 900, "subprocess_install"),    # CAEmSignG3.apply  pip --force-reinstall
)

# 第二阶段预留 key（权威源已定义并校验合法，但本轮不改消费方，见报告）：
#   subprocess_build=600 / subprocess_archive_push=3600
#   —— 端口 9000 联动组、/api/status port→boundPort、push_archives.py 等属行为变更/单列 PR。


class ConfigError(Exception):
    """超时权威源不可用或取值非法。``kind`` 供门禁区分判态、拒绝静默回落。"""

    def __init__(self, message: str, kind: str = "config") -> None:
        super().__init__(message)
        self.kind = kind


def load_defaults(auth=DEFAULT_AUTH) -> dict[str, int]:
    """读 + 校验权威源，返回 ``{key: 正整数秒}``（不含 unit 元数据）。

    业务判据只此一处：

    * 文件缺席            → ConfigError(kind="missing")：超时是必需件，绝不静默回落；
    * 读失败              → ConfigError(kind="read")；
    * 在场解析失败        → ConfigError(kind="parse")；
    * 顶层非 dict         → ConfigError(kind="shape")；
    * 缺 unit / unit≠seconds → ConfigError(kind="unit")（timeout_ms 依赖秒语义）；
    * key 非法 / 值非 int>0（含 bool）→ ConfigError(kind="key" / "value")。
    """
    p = Path(auth)
    if not p.is_file():
        raise ConfigError(
            f"超时权威源缺席：{p}（运行时默认配置属必需，拒绝静默回落默认值）",
            kind="missing",
        )
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"超时权威源读取失败：{p}: {exc}", kind="read") from exc
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"超时权威源在场但 JSON 解析失败（不得判绿）：{p}: {exc}", kind="parse"
        ) from exc
    if not isinstance(doc, dict):
        raise ConfigError(
            f"超时权威源顶层非对象：{p}（{type(doc).__name__}）", kind="shape"
        )
    if "unit" not in doc:
        raise ConfigError(f"超时权威源缺 unit 字段：{p}", kind="unit")
    if doc["unit"] != SECONDS_UNIT:
        raise ConfigError(
            f"unit 必须为 {SECONDS_UNIT!r}（timeout_ms 依赖秒语义）：{p} "
            f"实为 {doc['unit']!r}",
            kind="unit",
        )
    out: dict[str, int] = {}
    for key, val in doc.items():
        if key == "unit":
            continue
        if not _ALLOWED_KEY.match(key):
            raise ConfigError(f"非法超时 key（须 snake_case）：{key!r}", kind="key")
        if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
            raise ConfigError(f"超时值须正整数（非 bool）：{key}={val!r}", kind="value")
        out[key] = val
    return out


def timeout(key: str, *, auth=DEFAULT_AUTH) -> int:
    """取单个超时秒数；key 未登记抛 ConfigError(unknown_key)，绝不回退。"""
    defaults = load_defaults(auth)
    if key not in defaults:
        raise ConfigError(f"超时 key 未登记：{key!r}", kind="unknown_key")
    return defaults[key]


def timeout_or(key: str, fallback: int, *, auth=DEFAULT_AUTH) -> int:
    """取超时秒数；仅 **key 未登记** 时返回 fallback。

    权威源缺席/在场损坏仍抛 ConfigError —— 不用 fallback 掩盖配置故障（对齐 P1 #7）。
    """
    defaults = load_defaults(auth)
    return defaults.get(key, fallback)


def timeout_ms(key: str, *, auth=DEFAULT_AUTH) -> int:
    """取超时毫秒数（unit 已由 load_defaults 校验为 seconds）。"""
    return timeout(key, auth=auth) * 1000


def migration_table(auth=DEFAULT_AUTH) -> list[tuple[str, int, str, int | None, bool]]:
    """返回 (文件, 原字面量, key, timeout(key) 实值, 值是否不变) 对照表。"""
    rows = []
    for path, literal, key in MIGRATIONS:
        try:
            actual = timeout(key, auth=auth)
            rows.append((path, literal, key, actual, actual == literal))
        except ConfigError:
            rows.append((path, literal, key, None, False))
    return rows


def check(auth=DEFAULT_AUTH) -> tuple[int, list[str]]:
    """机械门禁：① 权威源健在且合法；② 每处迁移 timeout(key)==原字面量；
    ③ 每个迁移点源码确有 timeout(key) 调用（防止「映射表写了、代码没改」）。"""
    try:
        load_defaults(auth)
    except ConfigError as exc:
        if exc.kind == "missing":
            return EXIT_ENV, [f"权威源缺席（默认配置属必需，拒绝静默回落，不假绿）：{exc}"]
        return EXIT_BLOCKING, [f"权威源在场但不可用（不得判绿）：{exc}"]

    findings: list[str] = []
    # ② 值不变：每处 timeout(key) 必须等于迁移前字面量
    for path, literal, key, actual, ok in migration_table(auth):
        if not ok:
            findings.append(
                f"{path}: timeout({key!r})={actual!r} ≠ 迁移前字面量 {literal}"
                f"（权威源缺 key 或取值被改）"
            )
    # ③ 迁移落地：按 (文件, key) 聚合，源码 timeout(key) 调用数 ≥ 预期迁移点数
    expected: dict[tuple[str, str], int] = defaultdict(int)
    for path, _literal, key in MIGRATIONS:
        expected[(path, key)] += 1
    for (path, key), n in sorted(expected.items()):
        src = ROOT / path
        if not src.is_file():
            findings.append(f"{path}: 迁移目标文件不存在")
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(f"{path}: 读取失败：{exc}")
            continue
        calls = len(re.findall(_CALL_RE_TPL % re.escape(key), text))
        if calls < n:
            findings.append(
                f"{path}: 源码 timeout({key!r}) 调用 {calls} 处 < 预期 {n} 处"
                f"（迁移未落地或仍有裸字面量）"
            )
    return (EXIT_BLOCKING if findings else EXIT_OK), findings


def _safe(fn) -> object:
    try:
        return fn()
    except ConfigError:
        return None


def _kind_of(auth) -> str | None:
    try:
        load_defaults(auth)
    except ConfigError as exc:
        return exc.kind
    return None


def _kind_of_key(key: str) -> str | None:
    try:
        timeout(key)
    except ConfigError as exc:
        return exc.kind
    return None


def selftest() -> int:
    """自检：好样本全绿；坏 JSON 注入 / 缺席 / 缺 key 三类探针必须非 0 或显式判态。"""
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="allin-rtd-selftest-"))
    results: list[tuple[str, bool]] = []

    def ck(name: str, cond: bool) -> None:
        results.append((name, bool(cond)))

    # 好样本：默认权威源
    try:
        d = load_defaults()
        ck("默认权威源解析为正整数映射", isinstance(d, dict) and d.get("git_probe") == 10
           and "unit" not in d)
    except ConfigError as exc:
        ck(f"默认权威源解析（kind={exc.kind}）", False)
    ck("timeout_ms 秒→毫秒", _safe(lambda: timeout_ms("git_probe")) == 10000)

    # 坏 JSON 注入：在场但坏 → ConfigError(parse) + check 非 0（绝不判绿）
    bad = root / "bad.json"
    bad.write_text('{"unit":"seconds","git_probe":[unclosed', encoding="utf-8")
    ck("坏 JSON → ConfigError(kind=parse)", _kind_of(bad) == "parse")
    rc_bad, msgs_bad = check(bad)
    ck("坏 JSON check 非 0（不得判绿）",
       rc_bad != EXIT_OK and any("不得判绿" in m for m in msgs_bad))

    # 缺席：明确判态 EXIT_ENV，绝不静默回落
    missing = root / "no-such.json"
    ck("缺席 → ConfigError(kind=missing)", _kind_of(missing) == "missing")
    rc_miss, msgs_miss = check(missing)
    ck("缺席 check=EXIT_ENV（明确态、不假绿）",
       rc_miss == EXIT_ENV and any("缺席" in m for m in msgs_miss))

    # 缺 key / 业务判据探针
    ck("缺 key → ConfigError(unknown_key)", _kind_of_key("no_such_key") == "unknown_key")
    ck("timeout_or 仅缺 key 回退", _safe(lambda: timeout_or("no_such_key", 7)) == 7)
    for label, body, want in (
        ("缺unit", '{"git_probe":10}', "unit"),
        ("unit非秒", '{"unit":"milliseconds","git_probe":10}', "unit"),
        ("值非正int", '{"unit":"seconds","git_probe":0}', "value"),
        ("值为bool", '{"unit":"seconds","git_probe":true}', "value"),
        ("非法key", '{"unit":"seconds","Bad-Key":10}', "key"),
        ("顶层非dict", '[]', "shape"),
    ):
        p = root / (label + ".json")
        p.write_text(body, encoding="utf-8")
        ck(f"{label} → ConfigError(kind={want})", _kind_of(p) == want)

    # 正常 check 全绿（值不变 + 迁移落地）
    rc_ok, findings_ok = check()
    ck("默认源 check 全绿（值不变+迁移落地）", rc_ok == EXIT_OK and not findings_ok)

    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"SELFTEST: {passed}/{len(results)} passed"
          f" — {'PASS' if passed == len(results) else 'FAIL'}")
    return EXIT_OK if passed == len(results) else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="运行时超时默认值（单一事实源）")
    ap.add_argument("--auth", type=Path, default=DEFAULT_AUTH, help="权威源 JSON 路径")
    ap.add_argument("--check", action="store_true", help="校验权威源 + 迁移值不变/落地")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出权威源（供 Node JSON.parse）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.json:
        try:
            defaults = load_defaults(a.auth)
        except ConfigError as exc:
            print(f"ENV ERROR: {exc}", file=sys.stderr)
            return EXIT_ENV if exc.kind == "missing" else EXIT_BLOCKING
        print(json.dumps({"unit": SECONDS_UNIT, **defaults}, ensure_ascii=False, indent=2))
        return EXIT_OK

    rc, findings = check(a.auth)
    print("RUNTIME DEFAULTS CHECK")
    try:
        d = load_defaults(a.auth)
        print(f"  source = {a.auth}\n  unit = {SECONDS_UNIT} | keys = {len(d)}")
    except ConfigError:
        print(f"  source = {a.auth}")
    print("  迁移对照表（文件 · 原字面量 == timeout(key) 实值）:")
    for path, literal, key, actual, ok in migration_table(a.auth):
        print(f"    {'OK ' if ok else 'BAD'} {path:<38} {literal:>4} == timeout({key!r}) = {actual}")
    for f in findings:
        print(f"  BLOCK {f}")
    print(f"CHECK: {'PASS' if rc == EXIT_OK else 'FAIL'} (exit={rc}, findings={len(findings)})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
