# -*- coding: utf-8 -*-
"""`gate-runs.jsonl` 的 `tail` 字段回归（P1，2026-11-25）。

## 为什么有这一条

留痕此前只有「哪条命令挂了 + 退出码」，**失败长什么样完全丢失**（stdout 只进了
当次终端；CI 里更是只能看到通用 exit 1）。下游两件事因此都卡住：

* 「失败归因」类断言写不出来 —— 判据只能停在 ``exit != 0``；
* 任何失败分类器没有特征来源。§229 的 TextCNN 语料只有「标签 + 退出码」，
  模型只能学到类别大小（val_acc 0.302 < 基线 0.317）。

``tail`` 是这两件事的唯一前置。本测试把它的行为钉死，避免它哪天静默退化。

## 怎么测

用**真实 bash 执行抽取出来的 log_run**（不跑整份门禁 —— 那是 8 分钟），
五个用例覆盖：成功 / 失败（含引号反斜杠 CR 百分号）/ 含凭据 / 超长 / SKIP。
断言四件事：

1. exit=0 与 SKIP 行**不带** ``tail`` 字段 —— 旧行结构不变，消费方零改动；
2. 失败行的 tail 是**合法 JSON**，且引号/反斜杠/CR/百分号原样保留
   （本仓 2026-11-04 曾因反斜杠拼坏 JSON 丢掉整行、指标少算一条）；
3. 高置信度凭据被遮蔽，而真实失败特征**不被误删**（过度脱敏等于白花 IO）；
4. 尾部窗口 = 40 行，且截的是**尾部**（traceback 末段才是原因所在）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _bash_is_usable() -> tuple[bool, str]:
    """``bash 在 PATH`` ≠ ``bash 能用``。

    与 test_p2_sec_remediation.py 同一条探测（该文件记录了完整踩坑经过）：
    CI Windows runner 的 ``C:\\Windows\\System32\\bash.exe`` 是 WSL 启动器 shim，
    没装发行版时只打印提示并 exit 1。只判 ``shutil.which`` 会本机恒绿、CI 恒红。
    这里复制而非 import：tests/ 不是包，跨文件 import 需要 sys.path 手术，
    为 12 行代码动 sys.path 不值得。
    """
    if shutil.which("bash") is None:
        return False, "bash 不在 PATH"
    try:
        r = subprocess.run(["bash", "-c", 'printf "%s" POSIX_OK'],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=15)
    except Exception as exc:  # noqa: BLE001 - 环境探测，任何失败都只降级为 skip
        return False, f"bash 调用失败：{exc}"
    if r.returncode != 0 or (r.stdout or "").strip() != "POSIX_OK":
        return False, (f"PATH 上的 bash 不是可用 POSIX shell"
                       f"（rc={r.returncode}, stdout={(r.stdout or '')[:80]!r}）")
    return True, ""


_BASH_USABLE, _BASH_REASON = _bash_is_usable()

# 抽取 log_run 所依赖的两个函数定义，喂五个用例，把 JSONL 交给 Python 断言。
_HARNESS = r'''
set -uo pipefail
SRC="$1"; OUT="$2"; PYEXE="$3"
GATE_RUNS="$OUT"; RUN_ID="verify-1"; HEAD_SHA="deadbee"; PY="$PYEXE"
eval "$(sed -n '/^rotate_if_large()/,/^}/p' "$SRC")"
eval "$(sed -n '/^log_run()/,/^}/p' "$SRC")"

# 1 成功：带输出文件也不该记 tail
printf 'all good\n' > "$OUT.c1"
log_run "step:ok" 0 42 false "$OUT.c1"

# 2 失败：引号 / 反斜杠路径 / 制表符 / CR / 百分号
printf 'line1 "quoted"\r\npath C:\\Users\\x\\P\r\ntab\there\r\npct 100%%\r\nboom\r\n' > "$OUT.c2"
log_run "step:bad" 1 99 false "$OUT.c2"

# 3 失败：高置信度凭据 + 一条真实失败特征
printf 'token=sk-ABCDEFGHIJKLMNOPQRSTUV\r\naws=AKIAABCDEFGHIJKLMNOP\r\nreal failure: assertion\r\n' > "$OUT.c3"
log_run "step:secret" 1 7 false "$OUT.c3"

# 4 失败：120 行，只应留最后 40 行
seq 1 120 | sed 's/^/row-/' > "$OUT.c4"
log_run "step:long" 2 5 false "$OUT.c4"

# 5 SKIP：4 参数调用（note_skip 路径）
log_run "step:skip(missing-node-deps" 0 0 true
'''


@pytest.mark.skipif(not _BASH_USABLE, reason=_BASH_REASON or "bash 不可用")
def test_log_run_tail_field(tmp_path):
    out = tmp_path / "tail-verify.jsonl"
    r = subprocess.run(
        ["bash", "-c", _HARNESS, "_",
         str(ROOT / "scripts" / "run_all_gates.sh"),
         out.as_posix(), sys.executable],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, f"harness 失败：{r.stderr}"

    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 5, f"应有 5 条留痕，实得 {len(lines)}：{lines}"
    recs = [json.loads(ln) for ln in lines]  # 每行都必须是合法 JSON

    ok, bad, secret, long_, skip = recs

    # ① 结构不变：成功行与 SKIP 行不得多出 tail（旧消费方零改动）
    assert "tail" not in ok, "成功行不应带 tail"
    assert "tail" not in skip, "SKIP 行不应带 tail"
    # 字段口径与历史行一致
    assert ok["label"] == "step:ok" and ok["exit"] == 0 and ok["skipped"] is False
    assert skip["skipped"] is True, "SKIP 行必须显式 skipped=true（判定的唯一真相源）"
    assert bad["skipped"] is False

    # ② 任意文本安全：引号 / 反斜杠 / CR / 百分号全部原样存活
    assert '"quoted"' in bad["tail"], "双引号被吞"
    assert "C:\\Users" in bad["tail"], "反斜杠路径被吞（历史上就是这样拼坏 JSON 的）"
    assert "pct 100%" in bad["tail"], "百分号被吞"
    assert "\t" in bad["tail"], "制表符被吞"
    assert "boom" in bad["tail"], "末行丢失"
    assert "\r" not in bad["tail"], "CR 应已被 splitlines 归一，不该残留 \\r"

    # ③ 脱敏：凭据遮蔽，真实特征保留（过度脱敏等于白花 IO）
    assert "sk-ABCDEFGHIJKLMNOPQRSTUV" not in secret["tail"], "sk- 凭据未遮蔽"
    assert "AKIAABCDEFGHIJKLMNOP" not in secret["tail"], "AKIA 凭据未遮蔽"
    assert "REDACTED" in secret["tail"], "未出现遮蔽标记"
    assert "real failure" in secret["tail"], "真实失败特征被误删"

    # ④ 窗口：恰好 40 行，截尾不截头
    rows = long_["tail"].splitlines()
    assert len(rows) == 40, f"应只留 40 行，实得 {len(rows)}"
    assert rows[-1] == "row-120", f"末行应为 row-120，实得 {rows[-1]!r}"
    assert rows[0] == "row-81", f"首行应为 row-81，实得 {rows[0]!r}"


def test_tail_only_on_failure_branch_in_source():
    """静态钉住：tail 分支必须挂在 `exit != 0` 上，且 tail 走 Python 而非 printf。

    动态用例已覆盖行为，这一条防的是「有人把条件放宽成恒真」——那时动态测试
    仍绿（因为它只喂失败用例），但每次跑批都会膨胀 40 行输出。
    """
    src = (ROOT / "scripts" / "run_all_gates.sh").read_text(encoding="utf-8")
    assert '"$2" != "0"' in src, "tail 分支必须排除 exit=0"
    assert "json.dumps(rec" in src, "tail 必须经 json.dumps 落盘（printf 无法安全转义）"
    assert "TAIL_LINES = 40" in src
    assert "SENSITIVE.sub" in src, "缺脱敏"
    # 截尾不截头：负索引切片，不是 tail[:TAIL_CHARS]
    assert "tail[-TAIL_CHARS:]" in src
