"""门禁规则族（id 31-50）：把 ``tools/gate/governance`` 的 20 道门禁纳入 repocheck。

为什么存在
----------
搬家前（2026-11-23 之前）这套关系是**单向**的：``tools/publish_area_gate.py`` 调
repocheck 去体检发布区，而 allin 自己的 20 道治理门禁只管本仓 —— 两条评估线互不知情，
于是有「20 道全绿、发布区却是另一种结论」的结构性盲区（REC-AU-32 实证）。
本模块把方向补全：repocheck 也能评估「这个仓的治理门禁过不过」。

判据只有一份
------------
**本模块不重写任何判据，也不 import gates 的内部函数。** 内部函数签名是私有契约，
会随重构演化；对外稳定的是每道门的 CLI 契约 —— ``--root <work tree>`` 加退出码
（0 干净 / 1 阻断 / 2 用法错 / 3 环境错）。这里只复用那一层，因此：

* repocheck 与 ``run.ts`` 跑的是**同一份判据文件**，不会出现两边结论对不上；
* 门禁改了判据，repocheck 立刻跟着变，不需要同步第二处实现；
* 代价是每条规则一次子进程（实测 20 道约 60–70 秒），所以**默认关闭**，
  只在显式 ``--gates`` 时启用 —— 体检器的日常口径（0.26 s/仓）不能被它拖垮。

什么时候适用
------------
只对**自带治理套件**的仓有意义（仓内有 ``tools/gate/governance/gates/``）。
别的仓没有门禁可跑，这一族规则会被整体跳过 —— 若按「注册后逐条 SKIP」实现，
20 条 SKIP 会把所有仓的分数上限压到 9.0，把发布区健康分从 9.5 打成 9.0，
所以这里的做法是**按项目裁剪规则集**，不是按项目跳过规则。

退出码语义映射
--------------
``0`` → 通过；``1`` → 未通过（error 级）；``2`` / ``3`` → 门禁自身跑不起来，
按**未通过**记（fail-loud：跑不动不等于没问题）；超时同理。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:  # pragma: no cover
    from scanctx import ProjectContext

#: 治理套件落点（相对项目根）。两个都要在，才认为这个仓真的自带门禁。
GATE_GATES_DIR = "tools/gate/governance/gates"
GATE_RUNTIME = "tools/gate/governance/runtime/govlib.py"

#: 单道门的超时（秒）。20 道实测总时长 60–70 s，单道留足余量。
GATE_TIMEOUT = 240

#: detail 最多回显多少字符的末行 —— 报告要能看出「哪条判据拦的」，不是整篇日志。
DETAIL_CHARS = 220


def has_gate_suite(root: Path) -> bool:
    """该仓是否自带治理门禁套件（决定这一族规则挂不挂）。"""
    return (root / GATE_GATES_DIR).is_dir() and (root / GATE_RUNTIME).is_file()


def _gate_python() -> str:
    """跑门禁用的解释器：``ALLIN_PYTHON`` 优先，否则当前解释器。

    与 ``scripts/run_all_gates.sh`` 同一口径：门禁套件里 g18 要 PyYAML，
    换解释器会让「同一次跑批」的结论不可复现，所以允许显式钉住。
    """
    return os.environ.get("ALLIN_PYTHON") or sys.executable


def _gate_registry(root: Path) -> dict[str, dict]:
    """读门禁注册表（与 ``run.ts`` 同一份 ``registry.json``）。

    读它是为了复现 ``run.ts`` 的**参数契约**，不是为了读判据。实测差异：
    ``g14-preset`` 声明了 ``profileProbe: true``，``run.ts`` 会额外传
    ``--no-profile``（否则它按宿主 profile 判，在 CI/异机上误红）。少了这一步，
    repocheck 会报一条 run.ts 同批次里并不存在的红 —— 两个入口结论不一致，
    比没有第二个入口更糟。
    """
    path = root / "tools/gate/governance/registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    gates = data.get("gates", data) if isinstance(data, dict) else data
    if not isinstance(gates, list):
        return {}
    return {g.get("id"): g for g in gates if isinstance(g, dict) and g.get("id")}


def _gate_args(meta: dict) -> list[str]:
    """按注册表声明补齐与 ``run.ts`` 等价的附加参数。"""
    return ["--no-profile"] if meta.get("profileProbe") is True else []


def _tail(text: str) -> str:
    """取输出末条非空行作为 detail。"""
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line:
            return line[:DETAIL_CHARS]
    return ""


def run_gate(root: Path, script: str, gate_id: str = "", meta: dict | None = None) -> CheckResult:
    """跑一道门，把 CLI 退出码翻译成 CheckResult。"""
    gate = root / GATE_GATES_DIR / script
    if not gate.is_file():
        # 套件在、这道门不在 ⇒ 配置与实现不一致，是真实缺陷，不许静默跳过。
        return CheckResult.bad(f"门禁脚本缺失：{GATE_GATES_DIR}/{script}")

    cmd = [_gate_python(), str(gate), "--root", str(root), "--quiet",
           *_gate_args(meta if meta is not None else {})]
    try:
        proc = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=GATE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return CheckResult.bad(f"超时 >{GATE_TIMEOUT}s（按未通过记）")
    except OSError as exc:
        return CheckResult.bad(f"无法启动门禁：{type(exc).__name__}: {exc}")

    if proc.returncode == 0:
        return CheckResult.ok()
    detail = _tail(proc.stdout) or _tail(proc.stderr) or f"exit={proc.returncode}"
    return CheckResult.bad(f"exit={proc.returncode} · {detail}")


def _gate_rule(rule_id: int, gate_id: str, script: str, label: str, criteria: str) -> Rule:
    """按统一形态造一条门禁规则（闭包捕获 script，避免 20 段重复代码）。"""

    def check(ctx: "ProjectContext") -> CheckResult:
        meta = _gate_registry(ctx.root).get(gate_id, {})
        return run_gate(ctx.root, script, gate_id, meta)

    return Rule(
        rule_id,
        f"gate.{gate_id}",
        label,
        criteria,
        Severity.ERROR,
        check,
    )


#: 20 道门禁（g02 是历史缺号，不是漏搬 —— 编号沿用 ``governance/RULES.md``）。
#: 顺序即执行顺序，与 ``run.ts`` 的 g00→g20 一致，便于两边日志对照。
_GATE_TABLE: tuple[tuple[str, str, str, str], ...] = (
    ("g00-meta", "g00_meta.py", "门禁元数据自洽", "每道门禁的 id 都在 RULES.md 收录"),
    ("g01-paths", "g01_paths.py", "死根路径", "绝对路径的父目录必须真的存在"),
    ("g03-credentials", "g03_credentials.py", "凭据形态", "跟踪面内不得有凭据本体或高熵密钥"),
    ("g04-push-evidence", "g04_push_evidence.py", "推送留痕", "推送/放行须有可核查的留痕"),
    ("g05-hygiene", "g05_hygiene.py", "仓库卫生", "根文件三件套 / gitignore 覆盖 / 无产物与超大文件"),
    ("g06-numbering", "g06_numbering.py", "编号连续", "规范与调试铁律的编号不得跳号"),
    ("g07-doc-freshness", "g07_doc_freshness.py", "文档时点", "事实类文档必须带时点"),
    ("g08-deletion-evidence", "g08_deletion_evidence.py", "删除留痕", "删除行为须有证据与理由"),
    ("g09-python-hygiene", "g09_python_hygiene.py", "Python 卫生", "无裸 except / 可变默认参等"),
    ("g10-failloud-probe", "g10_failloud_probe.py", "坏输入必响", "拿到坏输入必须响亮报错，不许假绿"),
    ("g11-undef-names", "g11_undef_names.py", "未定义名", "AST 层面无从未定义过的名字"),
    ("g12-integrity", "g12_integrity.py", "对象库完整", "HEAD 可达对象可读、仓库未损坏"),
    ("g13-docs-only", "g13_docs_only.py", "文档枢纽纯文档", "docs/ 下只放文档"),
    ("g14-preset", "g14_preset.py", "preset 可挂载", "治理 preset 与实况一致、可挂载"),
    ("g15-docs-contract", "g15_docs_contract.py", "文档契约", "登记 / 索引 / 命名 / 计数一致（D1–D17）"),
    ("g16-skill-preset-parity", "g16_skill_preset_parity.py", "载体口径一致", "各处治理载体说的是同一套事实"),
    ("g17-registry", "g17_registry.py", "注册表完备", "每个本地仓要么登记、要么声明为缺口"),
    ("g18-exceptions", "g18_exceptions.py", "例外可燃尽", "豁免须有理由与到期日"),
    ("g19-docs-refs", "g19_docs_refs.py", "文档引用可达", "文档里的路径/锚点要指向真实存在的东西"),
    ("g20-facts", "g20_facts.py", "机器事实一致", "事实源断言须与磁盘一致（路径/计数/本机自述）"),
)

RULES_GATE: tuple[Rule, ...] = tuple(
    _gate_rule(31 + i, gate_id, script, f"{gate_id} · {label}", criteria)
    for i, (gate_id, script, label, criteria) in enumerate(_GATE_TABLE)
)
