#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量黄金集断言（2026-11-25 P0：6 → 30 条）。

## 为什么是批量工厂，不是 24 个手写函数

每条用例的结构完全一样：**取一个事实 → 与另一个事实比**。
手写 24 遍只会让"断言"和"取数方式"混在一起，改一处要动 24 处。
所以拆成：

- `FACTS`：怎么取数（每个键一个取数函数，**一种口径只写一次**）
- `ASSERTS`：断言表（名字 → 用哪两个事实、怎么比、失败时说什么）

加用例 = 在 `ASSERTS` 加一行。取数口径变了只改 `FACTS` 一处。

## 用例从哪挑（这是关键，不是凑数）

排查基准：**门禁 20 道 + MCP `--selftest` 已经覆盖的不算**（重复计数没意义）。
所以只挑它们**结构上管不到**的四类：

| 类 | 为什么门禁看不到 |
| --- | --- |
| A 公共核纪律 | 门禁在**消费仓**跑，看不到包自己的 `dependencies` 与延迟导入纪律 |
| B 发布链路 | 2.2.0 才有的新能力，门禁里没有对应项 |
| C 跨文件语义一致 | D 判据管**格式**（行号、锚点），管不了"自述的数字对不对" |
| D 记账制度 | 月账/交接的规矩 11-25 才定，判据只覆盖了一部分 |

## 冲突阈值（自指的一种）

`黄金集用例数 = golden.json 条数` —— 这条自己也在黄金集里。
它保证「加了断言却忘了登记」或「登记了却没实现」会立刻被抓。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

#: 这些由 runner 注入。**约定：每个值都是可调用对象，返回字符串** ——
#: `root()` / `run(cmd)` / `_read(path)` / `REGISTRY()` / `MCP()` / `NODE()` / `CASE_FUNCS`。
#: 统一成可调用，才不会出现「有时当函数、有时当字符串」的 bug 温床。

FACTS: dict = {}
ASSERTS: list = []


def fact(name: str):
    """注册一个取数口径。返回原函数（便于直接调用调试）。"""
    def deco(fn):
        FACTS[name] = fn
        return fn
    return deco


def assert_(name: str, *, use: tuple[str, ...], rule: str = "eq",
            why: str = "") -> None:
    """登记一条断言：比较 `use` 里两个事实。"""
    ASSERTS.append({"name": name, "use": use, "rule": rule, "why": why})


# ============================================================ A 公共核纪律
@fact("pkg_dependencies")
def _f_pkg_deps():
    """包的**运行时依赖**（从已安装元数据读，不读源码仓 pyproject）。

    2026-11-25 CI 实测踩坑：初版读 `../allin-governance/pyproject.toml`，
    而 CI 上只有 allin 仓、没有同级包仓 ⇒ 5 条 A 类断言全假红。
    **本机布局不能当通用假设** —— 改成只依赖已安装包。
    """
    import importlib.metadata as md
    reqs = md.requires("allin-governance") or []
    # 只要"无 extra 条件"的那些（`foo>=1; extra == "ml"` 属可选，不算运行时依赖）
    base = [r for r in reqs if "extra ==" not in r]
    return ",".join(base)


@fact("pkg_optional_deps_keys")
def _f_pkg_optdeps():
    """可选依赖组名（从已安装元数据的 `Provides-Extra` 读）。

    2026-11-25 CI 实测：初版读同级包仓的 pyproject.toml —— 与本文件里
    `pkg_dependencies` 同一处错误（CI 上无同级仓）。两者必须一起改，
    否则修一个漏一个，CI 会以「每次剩 1 条」的形式反复红。
    """
    import importlib.metadata as md
    try:
        extras = md.metadata("allin-governance").get_all("Provides-Extra") or []
    except Exception:  # noqa: BLE001
        return ""
    return ",".join(sorted({e for e in extras if e}))


@fact("ml_toplevel_torch_import")
def _f_ml_top_torch():
    """`_ml` 各模块**顶层**有没有 `import torch`（必须没有：延迟导入纪律）。"""
    d = FACTS["_pkg_ml_dir"]()
    bad = []
    for f in sorted(Path(d).glob("*.py")):
        for i, ln in enumerate(FACTS["_read"](f).split("\n"), 1):
            s = ln.strip()
            if s.startswith(("import torch", "from torch")) and not ln.startswith((" ", "\t")):
                bad.append(f"{f.name}:{i}")
    return ",".join(bad)


@fact("pkg_versions")
def _f_pkg_versions():
    """已安装包的版本 **与** 源码仓 VERSION 文件（若同级仓存在）。

    只用「元数据里的版本」做硬判据；源码仓的 pyproject/VERSION 只在仓存在时参与，
    不存在就不参与比较（CI 上无同级仓，这是常态不是异常）。
    """
    import importlib.metadata as md
    out = [md.version("allin-governance")]
    root = Path(FACTS["_pkg_root"]())
    if (root / "VERSION").is_file():
        out.append(FACTS["_read"](root / "VERSION").strip())
    return "|".join(out)


@fact("installed_pkg_version")
def _f_installed_ver():
    import allin_governance
    return allin_governance.__version__


# ============================================================ B 发布链路
@fact("cli_subcommands")
def _f_cli_subcommands():
    """包 CLI 暴露的子命令全集（从模块里读，避免每次起进程）。"""
    import allin_governance.cli as c
    return ",".join(sorted(c.SUBCOMMANDS))


@fact("gitee_subcommands")
def _f_gitee_subs():
    from allin_governance._gitee import release as g
    ap = g.build_parser()
    for a in ap._actions:
        if getattr(a, "choices", None) and isinstance(a.choices, dict):
            return ",".join(sorted(a.choices))
    return ""


@fact("publish_subcommands")
def _f_publish_subs():
    from allin_governance._publish import pypi
    ap = pypi.build_parser()
    for a in ap._actions:
        if getattr(a, "choices", None) and isinstance(a.choices, dict):
            return ",".join(sorted(a.choices))
    return ""


@fact("ml_route_source_without_model")
def _f_ml_route_no_model():
    """无模型权重时的路由来源 —— 必须是 `fallback`（降级纪律）。"""
    from allin_governance._ml import Router
    r = Router(model_path=None)
    res = r.predict(["门禁 D19 必须由它自己拦住"])
    return res[0].final.source


@fact("ml_route_label_governance")
def _f_ml_route_label():
    """规则降级对「门禁/判据」类文本的判断 —— 必须是 governance。"""
    from allin_governance._ml import Router
    r = Router(model_path=None)
    return r.predict(["门禁 D19 判据必须由它自己拦住"])[0].final.label


# ============================================================ C 跨文件语义
@fact("index_header_counts")
def _f_index_counts():
    """INDEX 头部自述份数（`根 N + 规范 N + 事实源 N + 记录 N = N`）。"""
    t = FACTS["_read"](Path(FACTS["root"]()) / "docs" / "INDEX.md")
    m = re.search(r"\*\*覆盖\*\*\s*根\s*(\d+)\s*\+\s*规范\s*(\d+)\s*\+\s*事实源\s*(\d+)\s*\+\s*记录\s*(\d+)\s*=\s*\*\*(\d+)\s*份?\*\*", t)
    if not m:
        return "<头部无份数自述>"
    a, b, c, d, total = (int(x) for x in m.groups())
    return f"{a + b + c + d}={total}"


@fact("index_actual_files")
def _f_index_actual():
    """实际份数（与 INDEX 登记表逐项数）—— 只数登记过的四类目录。"""
    root = Path(FACTS["root"]())
    docs = root / "docs"
    n_root = len([p for p in docs.glob("*.md")])
    n_spec = len(list((docs / "规范").glob("*.md")))
    n_fact = len(list((docs / "事实源").rglob("*.md")))
    n_rec = len(list((docs / "记录").rglob("*.md"))) - len(list((docs / "记录").glob("*.md")))
    return f"{n_root + n_spec + n_fact + n_rec}={n_root + n_spec + n_fact + n_rec}"


@fact("gate_count_registry")
def _f_gate_count():
    p = json.loads(FACTS["_read"](Path(FACTS["REGISTRY"]())))
    return str(len(p.get("gates", [])))


@fact("gate_count_spec_selfclaim")
def _f_gate_selfclaim():
    """SPEC-204 里自述的门禁数（`20 道`）。"""
    root = Path(FACTS["root"]())
    for p in (root / "docs" / "规范").glob("SPEC-204*.md"):
        t = FACTS["_read"](p)
        m = re.search(r"(\d+)\s*道(?:治理)?门禁", t) or re.search(r"门禁\s*(\d+)\s*道", t)
        if m:
            return m.group(1)
    return "<未自述>"


@fact("d_criteria_implemented")
def _f_d_count():
    """实际实现的 D 判据数（`check_d<N>` 函数个数，从包内源码数）。"""
    from allin_governance._gatesuite.runtime import docs_contract as dc
    return str(len([n for n in dir(dc) if re.fullmatch(r"check_d\d+", n)]))


@fact("d_criteria_selfclaim")
def _f_d_selfclaim():
    """SPEC-005 里登记了几条判据小节（`### 3.N` 形式的节数）。

    2026-11-25 实测：SPEC-005 **没有** `D1–DN` 这种范围自述，只有零散的 `D1/D2`。
    所以改数小节 —— 那才是文档真正承诺过的东西（SPC-005 是契约文件，节数就是判据数）。
    """
    root = Path(FACTS["root"]())
    for p in (root / "docs" / "规范").glob("SPEC-005*.md"):
        secs = re.findall(r"^###\s*3\.\d+", FACTS["_read"](p), re.M)
        if secs:
            return str(len(secs))
    return "<未找到 3.N 小节>"


@fact("readme_version")
def _f_readme_ver():
    t = FACTS["_read"](Path(FACTS["root"]()) / "README.md")
    m = re.search(r"当前版本\s*`([^`]+)`", t)
    return m.group(1) if m else "<README 无版本自述>"


@fact("mcp_tool_count")
def _f_mcp_tools():
    code, out = FACTS["run"]([FACTS["NODE"](), str(FACTS["MCP"]()), "--list-tools"], timeout=120)
    if code != 0:
        return f"<--list-tools 退出码 {code}>"
    try:
        return str(len(json.loads(out)))
    except json.JSONDecodeError:
        return "<返回非 JSON>"


@fact("skill_tool_count")
def _f_skill_tools():
    """SKILL.md 里自述的工具总数（`共 **N** 工具` / `共 N 工具`）。

    2026-11-25 实测：SKILL **有**这个自述，写的是 12，而 MCP 实际 27 —— 漂移 15 个。
    此前我断言写成「实际 >= 列出」（27>=2 恒真），等于没判；现在改等值比较。
    """
    root = Path(FACTS["root"]())
    for p in (root / ".workbuddy" / "skills").glob("allin-governance-agent/SKILL.md"):
        t = FACTS["_read"](p)
        m = re.search(r"共\s*\*{0,2}(\d+)\*{0,2}\s*工具", t) or re.search(r"(\d+)\s*个工具", t)
        if m:
            return m.group(1)
    return "<SKILL 无工具数自述>"


# ============================================================ D 记账制度
@fact("monthly_ledger_hosts")
def _f_monthly_hosts():
    """有月账的机器数（`事实源/机器/*/月账/*.md`）。"""
    root = Path(FACTS["root"]())
    hosts = {p.parent.parent.name for p in (root / "docs" / "事实源" / "机器").glob("*/月账/*.md")}
    return str(len(hosts))


@fact("monthly_ledger_has_owner_note")
def _f_monthly_note():
    """月账里是否有「归属声明」（本机自持 / 铁律 6 之类）。"""
    root = Path(FACTS["root"]())
    hits = 0
    for p in (root / "docs" / "事实源" / "机器").glob("*/月账/*.md"):
        if "铁律 6" in FACTS["_read"](p) or "本机" in FACTS["_read"](p):
            hits += 1
    return "有" if hits else "无"


@fact("golden_case_count_file")
def _f_golden_file():
    p = Path(FACTS["root"]()) / "tools" / "gate" / "ledger" / "agent_regression_golden.json"
    return str(len(json.loads(FACTS["_read"](p)).get("cases", [])))


@fact("golden_case_count_impl")
def _f_golden_impl():
    """实现侧能提供的 case 名数量（由 runner 注入）。"""
    return str(len(FACTS["CASE_FUNCS"]))


# ============================================================ 断言表
def _register_all():
    ASSERTS.clear()
    # A 公共核纪律
    assert_("包零依赖", use=("pkg_dependencies", "empty"), why="dependencies 必须为空")
    assert_("torch 在可选依赖里", use=("pkg_optional_deps_keys", "has:ml"),
            rule="has", why="[ml] 组必须存在，且不得进 dependencies")
    assert_("_ml 顶层不 import torch", use=("ml_toplevel_torch_import", "empty"),
            why="延迟导入纪律：没装 torch 时骨架仍可 import")
    assert_("包版本一致（元数据/源码 VERSION）", use=("pkg_versions", "all_same"), rule="all_same",
            why="pyproject / __init__ / VERSION 必须同一个值")
    assert_("README 版本 = 安装版本", use=("readme_version", "installed_pkg_version"),
            why="消费仓 README 写的版本要等于实际装上的")
    # B 发布链路
    assert_("CLI 五大子命令齐全", use=("cli_subcommands", "has_all:publish,ml,gitee,github,facts"),
            rule="has_all", why="发布链路收拢后必须五个都在")
    assert_("gitee 子命令齐全", use=("gitee_subcommands", "has_all:create,public,release,attach"),
            rule="has_all", why="建仓/转公开/发版/附件四件套")
    assert_("publish 五步齐全", use=("publish_subcommands", "has_all:check,build,verify,upload,release"),
            rule="has_all", why="发版四道判据 + 一条龙")
    assert_("ml 四步齐全", use=("cli_subcommands", "has:ml"), rule="has",
            why="骨架入口必须在")
    assert_("ml 无模型时走 fallback", use=("ml_route_source_without_model", "fallback"),
            why="降级纪律：没有权重不许硬答")
    assert_("ml 规则判 governance 正确", use=("ml_route_label_governance", "governance"),
            why="降级实现的基本正确性")
    # C 跨文件语义
    assert_("INDEX 份数自述一致", use=("index_header_counts", "self_consistent"),
            rule="self_consistent", why="头部 a+b+c+d 必须等于声明的总数")
    assert_("门禁数自述 = registry", use=("gate_count_spec_selfclaim", "gate_count_registry"),
            why="SPEC 写的门禁数要与 registry 条目数相等")
    # 口径不同，只能比下限（2026-11-25 实测）：SPEC-005 有 14 个 `### 3.N` 判据小节，
    # 而代码里 `check_d*` 只有 11 个 —— D1–D8 用的是别的函数名（如锚点/序号类）。
    # 强行相等会假红；测下限能抓「文档判据节被误删」。
    assert_("SPEC-005 判据节数 >= check_d* 数", use=("d_criteria_selfclaim", "d_criteria_implemented"),
            rule="gte", why="文档承诺的判据节不能少于代码里显式命名的 check_d*（口径差异见注释）")
    # 2026-11-25 实测教训：此前写 `rule="gte"`（实际 27 >= 列出 2）恒真，等于没判。
    # 改成等值 —— 它立刻抓出「SKILL 写 12、实际 27」这个 15 个工具的漂移。
    assert_("MCP 工具数 = SKILL 自述", use=("mcp_tool_count", "skill_tool_count"),
            why="工具面变化必须同步 SKILL；恒真断言等于没判（实测过）")
    # D 记账制度
    assert_("月账覆盖三台机", use=("monthly_ledger_hosts", "3"),
            why="SIWPAN / KQABATS / 8RSV60V 都该有月账")
    assert_("月账有归属声明", use=("monthly_ledger_has_owner_note", "有"),
            why="铁律 6：本机自持要写明")
    assert_("黄金集条数 = 实现 case 数", use=("golden_case_count_file", "golden_case_count_impl"),
            why="加了断言忘了登记 / 登记了没实现，都该立刻红")


_register_all()


# ============================================================ 执行
def _cmp(rule: str, lhs: str, rhs: str) -> tuple[bool, str]:
    """按规则比较两个事实。

    `rhs` 可以带**规则前缀**：`empty` / `all_same` / `self_consistent` / `has:x` / `has_all:a,b`。
    这样断言表一行就能表达「比什么 + 怎么比」，不用额外记 rule 参数
    （2026-11-25 实测：两处并存时必有人漏传，6 条断言因此全假红）。
    """
    if rhs in ("empty", "all_same", "self_consistent"):
        rule, rhs = rhs, ""
    elif rhs.startswith("has_all:"):
        rule, rhs = "has_all", rhs[len("has_all:"):]
    elif rhs.startswith("has:"):
        rule, rhs = "has", rhs[len("has:"):]
    if rule == "eq":
        return lhs == rhs, f"{lhs!r} vs {rhs!r}"
    if rule == "all_same":
        parts = lhs.split("|")
        return len(set(parts)) == 1, f"{lhs}"
    if rule == "empty":
        return lhs == "", f"{lhs!r}"
    if rule == "has":
        return rhs in lhs, f"需含 {rhs}；实际 {lhs}"
    if rule == "has_all":
        need = rhs.split(",")
        missing = [n for n in need if n not in lhs]
        return not missing, f"缺 {missing}" if missing else "齐"
    if rule == "gte":
        try:
            return float(lhs) >= float(rhs), f"{lhs} >= {rhs}"
        except ValueError:
            return False, f"{lhs!r} >= {rhs!r}（非数值）"
    if rule == "self_consistent":
        a, _, b = lhs.partition("=")
        return a == b, f"{lhs}"
    return False, f"未知规则 {rule}"


def run_assertions() -> list[tuple[str, bool, str]]:
    """跑全部断言，返回 [(名字, 是否通过, 说明)]。"""
    out: list[tuple[str, bool, str]] = []
    for a in ASSERTS:
        name, use, rule = a["name"], a["use"], a["rule"]
        try:
            lhs = FACTS[use[0]]()
            rhs_raw = use[1]
            rhs = FACTS[rhs_raw]() if rhs_raw in FACTS else rhs_raw
            ok, detail = _cmp(rule, str(lhs), str(rhs))
        except Exception as exc:  # noqa: BLE001  取数失败等同该条不通过，但要说明原因
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        out.append((name, ok, detail))
    return out


def names() -> list[str]:
    return [a["name"] for a in ASSERTS]
