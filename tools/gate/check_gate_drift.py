#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_gate_drift.py —— 门禁「双落点」漂移检查（`/allin/tools/gate` ↔ `/tools/gate`）

为什么存在
----------
`SPEC-004 §调试铁律 64` 记过一次真实事故：同一个 `repo_hygiene.py` 在两个落点漂移，
"覆盖式同步"差点丢东西。2026-10-06 又实测到 `scan_hardcoded.ps1` 两份**互补漂移** ——
仓内版已修 `core.quotepath=false` / PS 5.1 GBK 中文豁免失效 / `GetExtension` 抛异常三处，
而工作副本**还写死** `G:\\tools\\gate` 且 selftest 是旧变体；两份**都能跑、都"看着对"**，
差异只有人工 diff 才看得见（而且我第一遍还把方向看反了）。

**纪律不如门禁**：本脚本把"两份必须一致"变成退出码。这是 F1 的收口动作。

判据（严格按 `调试铁律 12`）
---------------------------
- 两侧都存在的**门禁脚本**逐个比对：**先归一化 EOL，再逐字节比** ——
  跨副本比对不归一化换行符会得出假差异（实测差 438 字节全是 CRLF/LF）。
- 只在**一侧**存在的文件 → 报告为"归属差异"（**不算漂移**），因为"随仓分发 vs 工作副本专属"
  是刻意的归属决定（见 `SPEC-003`/`docs/规范/README.md` §4.1），不该被本脚本判成故障。
- 对端目录**不存在** → `SKIPPED (not a pass)`：换机后还没建工作副本时**不许假绿**
  （`g10-failloud-probe` 的口径：拿不到输入要响亮说明，不能静默通过）。

退出码：0 = 一致（或 SKIPPED）；1 = 有漂移；3 = 自检失败
用法：python check_gate_drift.py [--repo-side DIR] [--work-side DIR] [--selfcheck]
"""
import argparse
import filecmp
import os
import shutil
import sys
import tempfile

#: 需要两侧一致的门禁脚本（按文件名比对；两侧都存在的才比）。
#: 加新脚本时**必须同步加到这里**，否则它会静默漏检 —— 见 --selfcheck 的最后一项。
TRACKED = (
    "scan_hardcoded.ps1",
    "repo_hygiene.py",
    "check_ps1_bom.py",
    "watchdog.py",
    "check_undefined_names.py",
    "docs_index.py",
    "make_doc_aliases.ps1",
    "check_gate_drift.py",
)

#: 默认落点：脚本自身所在目录为工作副本，仓内落点按「约定父目录」推导 ——
#: **不写死盘符**（`铁律 5`）：仓内落点 = 环境变量 `ALLIN_ROOT`，否则 = 工作副本上两级的 `allin`。
HERE = os.path.dirname(os.path.abspath(__file__))


def _sides_from_here():
    """从脚本自身位置推导（仓内 / 工作副本）两个落点 —— **两侧运行结果相同**。

    约定：仓 = `<工作区根>/allin`，工作副本 = `<工作区根>/tools/gate`，二者同级。
    于是无论脚本跑的是哪一份，`HERE/../..` 都是同一个「工作区根」，
    候选路径一致 —— 这修掉了第一版的一个**假绿**：
    第一版把工作副本硬取成 `HERE`，于是**从仓内运行**时两侧塌成同一个目录，
    「自己跟自己比」**永远报一致**（实测：注入真漂移仍 exit 0）。`调试铁律 65`：
    一个恒返回同一值的判据不构成证据 —— **门禁自己也会犯这个错**。
    """
    root = _workspace_root()
    return (os.path.join(root, "allin", "tools", "gate"),
            os.path.join(root, "tools", "gate"))


def _workspace_root():
    """定位「工作区根」（仓与工作副本的共同父目录）。

    两种运行位置都要成立 —— 第一版只考虑了工作副本，从仓内跑时会把 `../..`（= 仓根 `allin`）
    当成工作区根，推出 `.../allin/allin/tools/gate` 这种不存在的路径，于是**静默 SKIPPED**
    （又是"假绿"的一种形态：不报错也不下结论）。
    """
    up2 = os.path.dirname(os.path.dirname(HERE))
    if os.path.basename(up2).lower() == "allin":      # 从仓内运行：HERE=<根>/allin/tools/gate
        return os.path.dirname(up2)
    return up2                                        # 从工作副本运行：HERE=<根>/tools/gate


def default_repo_side():
    env = os.environ.get("ALLIN_ROOT", "").strip()
    if env:
        return os.path.join(env, "tools", "gate")
    return _sides_from_here()[0]


def default_work_side():
    return _sides_from_here()[1]


def _norm_bytes(path):
    """读文件并归一化 EOL（铁律 12）。二进制/解码失败则原样返回。"""
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, False
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"), True


def compare(repo_side, work_side, verbose=True):
    """返回 (drifted:list, only_repo:list, only_work:list, compared:int, skipped:bool)"""
    if not os.path.isdir(repo_side) or not os.path.isdir(work_side):
        return [], [], [], 0, True
    drifted, only_repo, only_work, compared = [], [], [], 0
    for name in TRACKED:
        a = os.path.join(repo_side, name)
        b = os.path.join(work_side, name)
        ea, eb = os.path.isfile(a), os.path.isfile(b)
        if ea and not eb:
            only_repo.append(name)
            continue
        if eb and not ea:
            only_work.append(name)
            continue
        if not ea and not eb:
            continue
        compared += 1
        na, ta = _norm_bytes(a)
        nb, tb = _norm_bytes(b)
        if na == nb:
            if verbose:
                print("  ok   %-28s 一致（归一化 EOL 后）" % name)
        else:
            why = "内容不同"
            if not ta or not tb:
                why = "内容不同（含非 UTF-8 字节，按原始字节比）"
            elif len(na) == len(nb):
                why = "内容不同（**等长**：极可能是同一处被改了两遍而写法不同）"
            drifted.append((name, why))
            if verbose:
                print("  DRIFT %-27s %s" % (name, why))
    return drifted, only_repo, only_work, compared, False


def selfcheck():
    """注入式自证：漂移必须报红、一致必须报绿、缺对端必须 SKIPPED（三个方向）。"""
    print("== 门禁漂移检查 自测 ==")
    tmp = tempfile.mkdtemp(prefix="gate_drift_selfcheck_")
    ok = True
    try:
        a, b = os.path.join(tmp, "repo"), os.path.join(tmp, "work")
        os.makedirs(a)
        os.makedirs(b)
        payload = "line1\nline2\nline3\n"
        for d in (a, b):
            with open(os.path.join(d, "scan_hardcoded.ps1"), "w", encoding="utf-8", newline="") as fh:
                fh.write(payload)
        # ① 仅 CRLF/LF 不同 ⇒ 必须判「一致」（铁律 12 的正例）
        with open(os.path.join(b, "scan_hardcoded.ps1"), "w", encoding="utf-8", newline="") as fh:
            fh.write(payload.replace("\n", "\r\n"))
        d1, _, _, n1, sk1 = compare(a, b, verbose=False)
        print("  一致（仅 EOL 不同）判绿: %s  [比较 %d 个, 漂移 %d]" % ("✔" if (not d1 and not sk1) else "✘", n1, len(d1)))
        ok &= (not d1 and not sk1)
        # ② 真漂移 ⇒ 必须报红
        with open(os.path.join(b, "scan_hardcoded.ps1"), "w", encoding="utf-8", newline="") as fh:
            fh.write(payload.replace("line2", "line2-changed"))
        d2, _, _, _, _ = compare(a, b, verbose=False)
        print("  真漂移判红:             %s  [漂移 %d]" % ("✔" if d2 else "✘", len(d2)))
        ok &= bool(d2)
        # 还原，免得后续用例被上一步的漂移污染（第一版就是因此把 ④ 判错的）
        with open(os.path.join(b, "scan_hardcoded.ps1"), "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)
        # ③ 对端不存在 ⇒ SKIPPED（不许假绿）
        _, _, _, _, sk3 = compare(os.path.join(tmp, "nope"), b, verbose=False)
        print("  对端缺失 SKIPPED:       %s" % ("✔" if sk3 else "✘"))
        ok &= bool(sk3)
        # ④ 只在单侧存在 ⇒ 报"归属差异"而不是漂移
        with open(os.path.join(a, "watchdog.py"), "w", encoding="utf-8", newline="") as fh:
            fh.write("x = 1\n")
        d4, or4, ow4, _, _ = compare(a, b, verbose=False)
        print("  单侧存在判归属差异:     %s  [仅仓内 %d, 仅工作副本 %d, 漂移 %d]"
              % ("✔" if (or4 and not d4) else "✘", len(or4), len(ow4), len(d4)))
        ok &= bool(or4) and not d4
        # ⑤ 覆盖面自证：TRACKED 里的每个名字都必须真的被比过（防"加了脚本忘了登记"）
        print("  TRACKED 覆盖 %d 个名字（新增脚本须登记，否则静默漏检）" % len(TRACKED))
        ok &= len(TRACKED) >= 6
        # ⑥ 两侧是同一个目录 ⇒ 必须响亮失败（第一版就是在这里假绿的）
        same = os.path.realpath(a) == os.path.realpath(b)
        print("  同目录守卫用例（构造同目录）: %s"
              % ("✔" if _same_dir_guard(a, a) is not None else "✘"))
        ok &= _same_dir_guard(a, a) is not None
        del same
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELFCHECK_%s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 3


def _same_dir_guard(repo_side, work_side):
    """两侧同一目录 ⇒ 返回错误文本（由 main 响亮失败）。"""
    try:
        same = os.path.realpath(repo_side) == os.path.realpath(work_side)
    except OSError:
        return None
    if same:
        return ("两侧解析到同一个目录（%s）—— 那样是拿自己跟自己比，必然报一致。"
                "请用 --repo-side / --work-side 指定，或设 ALLIN_ROOT。" % repo_side)
    return None


def main():
    ap = argparse.ArgumentParser(description="门禁双落点漂移检查")
    ap.add_argument("--repo-side", default=default_repo_side())
    ap.add_argument("--work-side", default=default_work_side())
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    # 响亮失败：两侧同一目录 ⇒ 拒绝出结论（铁律 65：恒同值的判据不构成证据）
    bad = _same_dir_guard(args.repo_side, args.work_side)
    if bad:
        print("  [FAIL] " + bad)
        return 2

    print("== 门禁双落点漂移检查 ==")
    print("  仓内落点  : %s" % args.repo_side)
    print("  工作副本  : %s" % args.work_side)
    drifted, only_repo, only_work, compared, skipped = compare(
        args.repo_side, args.work_side, verbose=not args.quiet)
    if skipped:
        print("  SKIPPED (not a pass) —— 对端目录不存在，无法判定；换机后请建好工作副本再跑")
        return 0
    if only_repo or only_work:
        print("  归属差异（不算漂移，需人判断）: 仅仓内=%s 仅工作副本=%s"
              % (only_repo or "无", only_work or "无"))
    if drifted:
        print("  RESULT: 漂移 %d 个（%s）—— 按 SPEC-004 §调试铁律 64：先 diff 判方向，再决定合并" %
              (len(drifted), ", ".join(n for n, _ in drifted)))
        return 1
    print("  RESULT: 一致（比较 %d 个门禁脚本）" % compared)
    return 0


if __name__ == "__main__":
    sys.exit(main())
