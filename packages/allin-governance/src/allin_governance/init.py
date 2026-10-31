"""`allin-governance init` —— 生成一个可跑的最小治理骨架。

**产品逻辑**（REC-AU-21 D1.1）：把 allin 自己的治理机制装成可复制的起点。
用户不需要读 7 万行文档才能开始，只需要一条命令拿到「能跑起来的那一层」。

## 为什么是「拷一份快照」而不是「引用安装包里的门禁」

这是本文件最关键的取舍，写在这里而不是隐藏。

本仓有一条吃过亏的纪律：**派生副本手抄必漂**。所以初版设计是让目标仓引用
site-packages 里的门禁（`npm run check:governance` 调 `allin-governance gate --root .`）。
但那条路会毁掉这套系统最核心的不变量：

    **门禁脚本必须物理位于被治理的仓里。**

`g00-meta` 的第一条判据就是「注册表里的 `script` 指向的文件必须在仓内存在」，
理由写在它自己的注释里 —— *注册表不是愿望清单*。一旦门禁住在 site-packages：

* `git log` 看不到判据的变更历史，治理证据链断在安装目录里；
* `pip install -U` 会**静默改变**这个仓的裁决结果，而仓内没有任何字节记录它变过；
* 审计时你无法回答「判我红的那 30 行代码是谁、哪一版写的」。

那不叫治理，那叫调用外部服务。所以 `init` **拷快照**，并用两种手段把「漂移」
从隐患变成可查的事实：

1. `GENERATED.json` —— 记下生成器版本与**每个文件的 sha256**，
   任何一处被手改或被别的版本覆盖都能逐字节判出来；
2. `--force` 是显式动作，不是默认行为 —— 升级套装的人必须亲口说要覆盖。

换句话说：副本在这里是**交付物**（像 `cargo new` 生成的骨架），不是**镜像**。
交付物有版本、有清单、有覆盖动作；镜像才会漂。

## 为什么只出厂 14 道门禁

2026-10-31 实测（空仓库 + 全部 20 道逐个跑）：

* **通过 15 道**；其中 `g18-exceptions` 需要 PyYAML —— 装了才是绿的，不装就报
  `ledger-unusable` 假红。本包对运行时的承诺是**零第三方依赖**（治理工具要在
  什么都没装的机器上跑得起来），所以 `g18` 不进默认注册表，在生成的 `RULES.md`
  里列为「按需自行添加」。
* **不通过 5 道**：`g14` `g15` `g16` `g17` `g19` —— 它们判的是 allin 自己的
  preset 载体、文档枢纽契约、平台 registry、事实源对账，在别的仓里没有对应物。
  硬塞进来只会让新用户第一天就看到一堆与他无关的红。

留下的是 14 道**纯标准库、与具体仓无关**的门禁，覆盖「凭据 / 路径 / 卫生 /
编号 / 文档时效 / 删除留证 / 编码 / 静默失败 / 未定义名 / 对象完整性 /
docs 边界 / 机器事实」。这就是「最小可用治理」的真实边界，不是删繁就简的营销话术。

## 哪些文件永远不会被 `--force` 覆盖

`--force` 的意思是「升级套装」，不是「我同意你重写我的文档」。所以：

* `tools/gate/governance/**` —— 套装本体，`--force` 才覆盖；
* `docs/**`、`README.md`、`LICENSE` —— **用户内容**，只在缺失时创建，永不被覆盖；
* `.gitignore` / `package.json` —— 只做**追加/合并**，不动既有条目。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import _stdio

__all__ = ["main", "build_plan", "GATE_IDS", "suite_dir"]

#: 套件在目标仓里的落点。**必须与 allin 自身一致**：`run.ts` 用
#: `resolve(import.meta.dirname, '..')` 当 ROOT，注册表的 `script` 字段又是相对 ROOT 的，
#: 换布局等于让聚合器与门禁的相对定位同时失效。
SUITE_RELATIVE = Path("tools") / "gate" / "governance"

#: 随套装出厂的门禁（2026-10-31 在空仓库上逐个实测通过的那批，除去需 PyYAML 的 g18）。
#: 顺序即生成 RULES.md 的顺序；改这里等于改产品的默认治理面，要有实测背书。
GATE_IDS: tuple[str, ...] = (
    "g00-meta",
    "g01-paths",
    "g03-credentials",
    "g04-push-evidence",
    "g05-hygiene",
    "g06-numbering",
    "g07-doc-freshness",
    "g08-deletion-evidence",
    "g09-python-hygiene",
    "g10-failloud-probe",
    "g11-undef-names",
    "g12-integrity",
    "g13-docs-only",
    "g20-facts",
)

#: 每道门禁的中文一句话判据。写进生成物，因为 registry.json 的 title 是英文、
#: 且只说「判什么」不说「为什么」，而新用户第一天最需要的是后者。
GATE_SUMMARY: dict[str, str] = {
    "g00-meta": "逐条校验注册表契约、让每道门禁自证、核对 RULES.md 收录 —— 门禁的门禁",
    "g01-paths": "机器相关的绝对路径：父目录不存在的死路径、写死本机盘符或用户目录",
    "g03-credentials": "凭据泄漏：私钥块、厂商令牌形态、URL 里的 userinfo、`.git/config` 全文",
    "g04-push-evidence": "远端同步只由 `git ls-remote` 判定；分叉才阻断，本地领先只记账",
    "g05-hygiene": "根三件套、`.gitignore` 凭据面、产物/字节码入索引、超阈值大文件",
    "g06-numbering": "序号文件必须连续；中英配对文档的列表形状必须逐项相等",
    "g07-doc-freshness": "自称「事实源 / 快照」的文档必须在开头带观测时点",
    "g08-deletion-evidence": "一次提交删了文件，必须附「功能面 × 接任者」对照表",
    "g09-python-hygiene": "文本 I/O 必须显式 `encoding=`；非 raw 字符串里的盘符转义伪影",
    "g10-failloud-probe": "喂一个不存在的 root，必须非 0 退出且有报错 —— 禁止静默通过",
    "g11-undef-names": "AST 找出「读了但全文件从未定义」的名字",
    "g12-integrity": "`HEAD` 可解析，且可达对象逐个可读（`--deep` 追加连通性检查）",
    "g13-docs-only": "`docs/` 只放文档扩展名；脚本、二进制、可执行位一律阻断",
    "g20-facts": "机器事实源与实况对账（Windows 专属，其他平台记 SKIP 而非通过）",
}

#: 未随套装出厂的门禁与原因。写进生成物，避免用户以为「少发了」。
GATE_EXCLUDED: dict[str, str] = {
    "g14-preset": "判 allin 的 DSH preset 载体（`GOVERNANCE:BEGIN/END` 段与插件序列），别的仓没有对应物",
    "g15-docs-contract": "判 allin 文档枢纽的四分类与 ASCII 别名，属本仓文档契约",
    "g16-skill-preset-parity": "判 allin 的三处治理载体互相对齐，属本仓多载体一致性",
    "g17-registry": "判 allin 的发布区 registry 与分级索引，属本仓资产台账",
    "g18-exceptions": "例外台账判据，**需要 PyYAML**；本包承诺零运行时依赖，故列为按需添加",
    "g19-docs-refs": "判 allin 文档里的路径引用是否可解析，依赖本仓目录结构",
}

#: `.gitignore` 必须覆盖的凭据面（g05-hygiene 逐条校验这几个片段）。
IGNORE_FRAGMENTS: tuple[str, ...] = (".env", "*.pem", "*.key", "__pycache__/")

#: 除契约要求外一并写上的忽略项，都是「入索引即噪音」的产物。
IGNORE_EXTRA: tuple[str, ...] = ("*.pyc", "*.egg-info/", ".venv/", "build/", "dist/", "node_modules/")

BASELINE_HEADER = """# Baseline ratchet for this gate. One finding key per line.
# 棘轮只允许单向收紧：基线里的条目是**已复核并接受**的存量，
# 新增问题不在基线内 ⇒ 阻断；往基线里加行意味着「我确认这条接受」，要留理由。
# 刷新前必须先把剩余条目整体过一遍：
#   python tools/gate/governance/gates/{gate}.py --no-baseline --list-all
"""


# --------------------------------------------------------------------------- #
# 套件来源
# --------------------------------------------------------------------------- #
def suite_dir() -> Path:
    """找到随包出厂的治理套件目录。

    与 `cli._repocheck_dir()` 同一套双候选逻辑，理由相同：装机形态与源码树形态
    路径不同，但指向**同一份**文件（pyproject 的 package-dir 映射，不是复制）。

    * 装机形态 → `site-packages/allin_governance/_gatesuite`
    * 源码树形态 → `<仓根>/tools/gate/governance`
    """
    packaged = Path(__file__).resolve().parent / "_gatesuite"
    if (packaged / "run.ts").is_file():
        return packaged
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tools" / "gate" / "governance"
        if (candidate / "run.ts").is_file():
            return candidate
    return packaged


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# 生成物正文
# --------------------------------------------------------------------------- #
def rules_markdown(version: str, generated_at: str) -> str:
    """生成 `RULES.md`：把「规则 → 退出码」的映射落成可读的一张表。

    `g00-meta` 的判据只是「门禁 id 出现在本文件里」，所以内容可以极简；
    但**不该**只是极简 —— 这是新用户唯一能读懂「我的仓在被什么管着」的地方。
    """
    rows = "\n".join(f"| `{gid}` | {GATE_SUMMARY[gid]} |" for gid in GATE_IDS)
    excluded = "\n".join(f"| `{gid}` | {reason} |" for gid, reason in GATE_EXCLUDED.items())
    return f"""# 治理规则 → 机械保障（RULES.md）

> 生成物，由 `allin-governance {version}` 于 {generated_at} 写出。
> **改规则改这里，改判据改 `gates/` 下的脚本与它的自检用例。**
> 两者必须一起改：`g00-meta` 会拦住「注册了但没写进本文件」的门禁。

## 一、门禁契约

`registry.json` 里登记的每个门禁，必须同时满足下面五条，否则 `g00-meta` 变红：

| 条款 | 判据 |
| --- | --- |
| 注册完整 | 条目含 `id`/`title`/`script`/`tier`/`rules`/`platforms`/`requires`/`selfcheck` 八个字段 |
| 脚本存在 | `script` 指向的文件**在仓内**（这条保证了「注册表不是愿望清单」） |
| 契约完整 | `--help` 必须列出 `--selfcheck` `--quiet` `--baseline` `--no-baseline` `--write-baseline` `--list-all` |
| 自证有效 | `--selfcheck` 退出 0，末行含 `SELFCHECK {{"caught":N,"clean":M,"misreports":K}}`，要求 `N≥1`、`M≥1`、`K==0` |
| 规则可溯 | 门禁 id 出现在本文件 |

**退出码词汇（全部门禁统一）**：`0` 干净 · `1` 基线之外的新阻断 · `2` 用法错误 ·
`3` 环境错误（缺解释器、缺 git 工作树等）。

**SKIP 不是通过。** 跑不了的判据必须打印 `SKIPPED (not a pass)` 并计数，
不得静默返回 0 —— 这是这套系统里最容易被破坏、也最值钱的一条。

## 二、已注册门禁（{len(GATE_IDS)} 道）

| 门禁 id | 判据要点 |
| --- | --- |
{rows}

## 三、未随套装出厂的门禁

不是漏发。下面这些判的是 `allin` 这个仓自己的资产，搬过来只会让你的仓第一天就红：

| 门禁 id | 为什么不随套装 |
| --- | --- |
{excluded}

要加自己的门禁：脚本放进 `gates/`，在 `registry.json` 里加一条（八个字段齐全），
再在本文件加一行。`g00-meta` 会立刻替你验一遍它是否真的能自证。
"""


def suite_readme(version: str, generated_at: str) -> str:
    """生成套装 README：怎么跑、跑不了时算什么、升级怎么走。"""
    return f"""# `tools/gate/governance/` —— 可执行门禁

> 生成物，由 `allin-governance {version}` 于 {generated_at} 写出。
> **这是快照，不是上游镜像**：它不会自动跟随 allin 的更新。
> 升级方式见本文末「升级」。

## 一、怎么跑

```bash
npm run check:governance                        # 全部门禁（= node tools/gate/governance/run.ts --no-profile）
node tools/gate/governance/run.ts --list        # 列出 id / 档位 / 覆盖规则
node tools/gate/governance/run.ts --only g01-paths,g05-hygiene
node tools/gate/governance/run.ts --tier P0     # 只跑 P0 档（适合 pre-commit）

# 单跑一道（不需要 Node；门禁本体是纯 Python）
python tools/gate/governance/gates/g05_hygiene.py
python tools/gate/governance/gates/g00_meta.py --selfcheck    # 证明它还能抓到注入的缺陷
```

**依赖**：`npm run check:governance` 需要 **Node >= 22.18**（原生 TypeScript 类型擦除，
不需要 `tsx`）与 **Python >= 3.9**。门禁本体零第三方依赖，单跑只要 Python。

## 二、第一次跑会看到 SKIP，那是正常的

`SKIPPED (not a pass)` 不等于失败，也不等于通过。新仓常见三条：

| 门禁 | 什么时候会 SKIP | 怎么让它真跑起来 |
| --- | --- | --- |
| `g04-push-evidence` | 还没配远端 | `git remote add origin <url>` 之后 |
| `g12-integrity` | `--deep` 未开（默认只验 HEAD 可达对象可读） | 加 `--deep` 追加 `git fsck --connectivity-only` |
| `g20-facts` | 没有 `docs/事实源/机器/` 台账；或当前不在 Windows 上 | 建台账 / 换 Windows 跑 |

## 三、判定口径

* 只看**被 git 跟踪**的面（`git ls-files`）。没 `git add` 的文件不参与判定。
* 退出码：`0` 干净 · `1` 基线外的新阻断 · `2` 用法错 · `3` 环境错。
* 有基线棘轮：`baseline/<gate>.txt` 里列的存量不阻断，新增即阻断。

## 四、升级

这套门禁是**快照**。升级 = 用新版 `allin-governance` 重跑 `init --force`。
覆盖前先比对 `GENERATED.json` 里的 sha256：

* 你手改过的文件会被列出来，不会静默覆盖；
* 想保留改动，就把它挪成**你自己的门禁**（新 id、新脚本、新注册条目），
  不要改在快照文件里 —— 下次覆盖就没了，而且没人知道判据变过。
"""


DOC_INDEX = """# 文档索引（INDEX）

> 本文档是文档枢纽的入口。新增文档先在这里登记，读者从这里出发。
> 登记粒度到「一行一句」，不写长篇摘要 —— 索引的价值是**可跳到**，不是可通读。

| 编号 | 文档 | 时点 | 一句话 |
| --- | --- | --- | --- |
| — | 待登记 | — | — |

## 分层

| 目录 | 放什么 | 是否约束 |
| --- | --- | --- |
| `docs/规范/` | 约束性规范，带稳定编号 | **是** |
| `docs/事实源/` | 活台账：会被实测反复改写的现值 | **是**（必须带观测时点） |
| `docs/记录/` | 证据流水：审计、研究、事故复盘 | 否（只作证据，不作约束） |
"""

DOC_CATEGORY: dict[str, tuple[str, str]] = {
    "规范": (
        "约束性规范",
        "放「必须遵守什么」。每条规范应有稳定编号（如 `SPEC-001`），"
        "引用时用编号而不是标题 —— 标题会改，编号不会。\n\n"
        "写规范的门槛：**能被一条门禁或一次复核变成退出码**。写不成判据的，"
        "那是愿望，不是规范。\n",
    ),
    "事实源": (
        "活台账",
        "放「现在是什么」。会被实测反复改写的内容都归这里：盘位、仓数、版本、"
        "端口、外部服务的现值。\n\n"
        "两条硬约束：① 每份台账开头写**观测时点**与**观测工具**，"
        "否则读者无法判断它是否还成立（`g07-doc-freshness` 会拦）；"
        "② 台账是证据不是结论 —— 结论写进规范或记录，并引用台账。\n",
    ),
    "记录": (
        "证据流水",
        "放「发生过什么」：审计、研究、事故复盘、决策留痕。\n\n"
        "**只增不改。** 结论错了就再写一份订正并互相引用，不要回改历史记录 —— "
        "记录一旦可改，它就不再是证据，而只是一份说法。\n",
    ),
}


# --------------------------------------------------------------------------- #
# 生成器
# --------------------------------------------------------------------------- #
@dataclass
class Plan:
    """一次 init 的完整意图：先算清楚再落盘（`--dry-run` 就是只算不落）。"""

    target: Path
    dry_run: bool = False
    created: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)

    def write(self, relative: str, text: str, *, force: bool) -> None:
        path = self.target / relative
        existed = path.exists()
        if existed and not force:
            self.kept.append(relative)
            return
        payload = text.encode("utf-8")
        if existed and path.read_bytes() == payload:
            # 内容一字不差就不写：`--force` 的语义是「升级」，不是「重写一遍」。
            # 没有这一条，二次 `init --force` 会刷掉全部 mtime 并在 git 里制造
            # 一堆零 diff 的「已修改」，把真正需要复核的覆盖淹掉。
            self.kept.append(relative)
            self.hashes[relative] = hashlib.sha256(payload).hexdigest()
            return
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        (self.overwritten if existed else self.created).append(relative)
        self.hashes[relative] = hashlib.sha256(payload).hexdigest()

    def copy(self, relative: str, source: Path, *, force: bool) -> None:
        path = self.target / relative
        existed = path.exists()
        digest = _sha256(source)
        if existed and not force:
            self.kept.append(relative)
            return
        if existed and _sha256(path) == digest:
            # 内容一致就不动它：`--force` 的目的是「升级到新版」，
            # 不是「制造一堆 mtime 变更」—— 零 diff 的覆盖只会污染 git 历史。
            self.kept.append(relative)
            self.hashes[relative] = digest
            return
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
        (self.overwritten if existed else self.created).append(relative)
        self.hashes[relative] = digest


def _gate_script_name(gate_id: str) -> str:
    return gate_id.replace("-", "_") + ".py"


def _registry_subset(source: Path) -> dict:
    """从套件自带注册表里裁出出厂子集。

    不从零手写注册表：字段约束（八个必填、`requires` 的词法、`tier` 的取值）
    都写在 `g00-meta` 里，手写一份等于把同一套约束再实现一次，迟早对不上。
    """
    raw = json.loads((source / "registry.json").read_text(encoding="utf-8"))
    gates = [entry for entry in raw.get("gates", []) if entry.get("id") in GATE_IDS]
    found = {entry.get("id") for entry in gates}
    missing = [gid for gid in GATE_IDS if gid not in found]
    if missing:
        raise SystemExit(
            "ENV ERROR: 套装注册表缺少门禁 " + ", ".join(missing)
            + "\n  说明安装包与 init 的期望不一致，请重装或升级 allin-governance。"
        )
    order = {gid: index for index, gid in enumerate(GATE_IDS)}
    gates.sort(key=lambda entry: order[str(entry["id"])])
    return {
        "version": raw.get("version", 1),
        "comment": (
            "Registry of the governance gates shipped by allin-governance. "
            "g00-meta reads this file and refuses to pass when an entry is incomplete, "
            "when a gate cannot prove itself, or when a gate is missing from RULES.md."
        ),
        "gates": gates,
    }


def _merge_gitignore(target: Path, plan: Plan) -> None:
    """补齐 `.gitignore` 的凭据面。

    `g05-hygiene` 逐条校验 `.env` / `*.pem` / `*.key` / `__pycache__/`。
    已有文件就**追加**缺失片段，绝不整体覆盖 —— 覆盖别人的 `.gitignore`
    等于替别人决定什么该入库，那是越权。
    """
    path = target / ".gitignore"
    if not path.exists():
        plan.write(".gitignore",
                   "# 凭据面（g05-hygiene 会逐条校验）\n" + "\n".join(IGNORE_FRAGMENTS)
                   + "\n\n# 产物\n" + "\n".join(IGNORE_EXTRA) + "\n",
                   force=False)
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [fragment for fragment in IGNORE_FRAGMENTS if fragment not in text]
    if not missing:
        plan.kept.append(".gitignore")
        return
    merged = (
        text.rstrip("\n") + "\n"
        + "\n# --- allin-governance：凭据面（g05-hygiene 校验这几条，勿删）---\n"
        + "\n".join(missing) + "\n"
    )
    plan.write(".gitignore", merged, force=True)
    plan.notes.append(f".gitignore 追加了 {len(missing)} 条凭据面片段（原有内容未动）")


def _merge_package_json(target: Path, plan: Plan, *, force: bool) -> None:
    """把 `check:governance` 挂进 npm scripts，保留其余字段。"""
    path = target / "package.json"
    script = "node tools/gate/governance/run.ts --no-profile"
    if not path.exists():
        payload = {
            "name": target.name.lower().replace(" ", "-") or "governance",
            "private": True,
            "scripts": {"check:governance": script},
        }
        plan.write("package.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n", force=False)
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        plan.notes.append(f"package.json 解析失败（{error}），已跳过命令挂载；请手动加 scripts.check:governance")
        return
    if not isinstance(payload, dict):
        plan.notes.append("package.json 顶层不是对象，已跳过命令挂载")
        return
    scripts = payload.setdefault("scripts", {})
    if not isinstance(scripts, dict):
        plan.notes.append("package.json 的 scripts 不是对象，已跳过命令挂载")
        return
    current = scripts.get("check:governance")
    if current == script:
        plan.kept.append("package.json")
        return
    if current is not None and not force:
        plan.notes.append(
            f"package.json 已有 check:governance（值为 {current!r}），未覆盖；确需替换请加 --force"
        )
        return
    scripts["check:governance"] = script
    plan.write("package.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n", force=True)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
    )


def _ensure_repo(target: Path, plan: Plan) -> bool:
    """确保目标是**独立**的 git 工作树。

    为什么必须有 `.git`：`govlib.repo_root()` 从门禁自身位置向上找 `.git`，
    找不到就抛 `GateError`（exit 3）。所以「不是 git 仓」= 一套跑不了的门禁。

    为什么必须独立：若目标落在别人的工作树里又没有自己的 `.git`，
    `repo_root()` 会一路向上找到**外层仓**，于是门禁去判一个不相干的仓 ——
    这比报错更糟，因为它会给出一个看似正常、实则答错题的结论。
    """
    probe = _git(["rev-parse", "--show-toplevel"], target)
    if probe.returncode == 0:
        toplevel = Path(probe.stdout.strip()).resolve()
        if toplevel == target.resolve():
            return True
        plan.notes.append(
            f"目标位于已有工作树 {toplevel} 内且自己没有 .git ⇒ 将初始化独立仓"
            "（否则门禁会以那个外层仓为根，判错对象）"
        )
    created = _git(["init"], target)
    if created.returncode != 0:
        plan.notes.append(f"git init 失败：{created.stderr.strip()[:200]}")
        return False
    return True


def _commit_if_empty(target: Path, plan: Plan) -> None:
    """仓库还没有任何提交时补一个。

    为什么必须补：`g12-integrity` 要解析 `HEAD^{commit}`，`g00-meta` 要求索引里有文件。
    零提交的仓库上这两条必然红（实测：g00 exit 3 / g12 exit 1 / g08 exit 3），
    于是「刚 init 完就是一屏红」—— 那不是用户的问题，是 init 没做完。
    """
    staged = _git(["add", "-A"], target)
    if staged.returncode != 0:
        plan.notes.append(f"git add 失败：{staged.stderr.strip()[:200]}")
        return
    if _git(["rev-parse", "--verify", "HEAD"], target).returncode == 0:
        plan.notes.append("仓库已有历史：只暂存、不提交（提交信息由你定）")
        return
    identity: list[str] = []
    if not _git(["config", "user.email"], target).stdout.strip():
        identity = ["-c", "user.email=allin@localhost", "-c", "user.name=allin init"]
        plan.notes.append("git 未配置 user.email，首个提交暂用 allin@localhost 身份（可随时改）")
    commit = _git([*identity, "commit", "-m", "chore: 初始化治理骨架（allin-governance init）"], target)
    if commit.returncode != 0:
        plan.notes.append(f"首个提交失败：{commit.stderr.strip()[:200]}；门禁需要可解析的 HEAD")
        return
    plan.notes.append("已建立首个提交（门禁需要可解析的 HEAD 与已跟踪文件）")


def _generation_stamp(manifest_path: Path, version: str) -> str:
    """本次生成的时间戳；同一版本重跑时沿用上次那个。

    为什么不能每次都取 `now()`：`GENERATED.json`、`RULES.md`、套件 README 里都写着
    这个时点。若每次都刷新，`init --force` 会把这三份文件的内容改掉 —— 于是
    「升级套装」和「什么都没变」在 git 里长成同一个样子，而真正需要复核的覆盖
    被淹在噪音里。版本没变 ⇒ 内容没变 ⇒ 时点也不该变。
    """
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    if previous.get("version") == version and isinstance(previous.get("generated_at"), str):
        return str(previous["generated_at"])
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def build_plan(target: Path, *, force: bool, with_git: bool, license_id: str | None,
               dry_run: bool = False) -> Plan:
    plan = Plan(target=target, dry_run=dry_run)
    suite = suite_dir()
    if not (suite / "run.ts").is_file():
        raise SystemExit(
            f"ENV ERROR: 找不到治理套件目录：{suite}\n"
            "  这通常意味着安装包没被打全。请重装 allin-governance，或从源码目录运行。"
        )

    version = _package_version()
    root = SUITE_RELATIVE.as_posix()
    generated_at = _generation_stamp(target / root / "GENERATED.json", version)

    # 1) 套件本体：run.ts / govlib / 门禁脚本 / ESM 标记 / 基线
    plan.copy(f"{root}/run.ts", suite / "run.ts", force=force)
    esm = suite / "package.json"
    if esm.is_file():
        plan.copy(f"{root}/package.json", esm, force=force)
    plan.copy(f"{root}/runtime/govlib.py", suite / "runtime" / "govlib.py", force=force)
    for gate_id in GATE_IDS:
        name = _gate_script_name(gate_id)
        plan.copy(f"{root}/gates/{name}", suite / "gates" / name, force=force)
        plan.write(f"{root}/baseline/{gate_id}.txt",
                   BASELINE_HEADER.format(gate=gate_id.replace("-", "_")), force=force)

    # 2) 注册表与规则映射
    registry = _registry_subset(suite)
    plan.write(f"{root}/registry.json",
               json.dumps(registry, ensure_ascii=False, indent=2) + "\n", force=force)
    plan.write(f"{root}/RULES.md", rules_markdown(version, generated_at), force=force)
    plan.write(f"{root}/README.md", suite_readme(version, generated_at), force=force)

    # 3) 生成清单：把「快照 vs 上游」的差异变成可逐字节判的事实
    manifest = {
        "generator": "allin-governance",
        "version": version,
        "generated_at": generated_at,
        "note": "快照清单。sha256 对不上 = 该文件被手改或被别的版本覆盖过。升级用 init --force。",
        "gates": list(GATE_IDS),
        "files": {relative: f"sha256:{digest}" for relative, digest in sorted(plan.hashes.items())},
    }
    plan.write(f"{root}/GENERATED.json",
               json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", force=force)

    # 4) 文档枢纽四分类 —— 用户内容，永不被 --force 覆盖
    plan.write("docs/INDEX.md", DOC_INDEX, force=False)
    for name, (title, body) in DOC_CATEGORY.items():
        plan.write(f"docs/{name}/README.md", f"# {title}\n\n{body}", force=False)

    # 5) 根面
    if (target / "README.md").exists():
        plan.kept.append("README.md")
    else:
        plan.write("README.md", _root_readme(target.name, version, root), force=False)
    if (target / "LICENSE").exists():
        plan.kept.append("LICENSE")
    elif license_id:
        plan.write("LICENSE", _license_text(license_id), force=False)
        plan.notes.append(f"已按 {license_id} 生成 LICENSE（默认值，按需替换）")
    _merge_gitignore(target, plan)
    _merge_package_json(target, plan, force=force)

    # 6) git
    if not with_git:
        plan.notes.append("已按 --no-git 跳过 git；门禁需要 git 工作树，否则会 exit 3")
    elif dry_run:
        plan.notes.append("（--dry-run）不执行 git init / add / commit")
    elif _ensure_repo(target, plan):
        _commit_if_empty(target, plan)

    return plan


def _root_readme(name: str, version: str, suite_root: str) -> str:
    return f"""# {name}

> 本文档由 `allin-governance {version}` 生成。

## 一条命令检查

```bash
npm run check:governance
```

需要 Node >= 22.18 与 Python >= 3.9。门禁本体是纯 Python、零第三方依赖，
所以没有 Node 时也能逐道单跑：

```bash
python {suite_root}/gates/g05_hygiene.py
```

## 这套东西在管什么

`{suite_root}/` 里是**可执行的门禁** —— 把「什么算合格」从文字变成退出码。
当前 {len(GATE_IDS)} 道，逐条判据见 [`{suite_root}/RULES.md`]({suite_root}/RULES.md)。

## 文档放哪

四分类，见 [`docs/INDEX.md`](docs/INDEX.md)：`规范/`（约束）· `事实源/`（活台账）·
`记录/`（证据流水，只增不改）。

## 加你自己的门禁

脚本放进 `{suite_root}/gates/`，在 `registry.json` 加一条八个字段齐全的条目，
再在 `RULES.md` 加一行。`g00-meta` 会立刻替你验一遍它是否真能自证
（`--selfcheck` 必须抓到注入的缺陷，只打印不算）。
"""


def _license_text(license_id: str) -> str:
    if license_id.upper().replace("_", "-") in {"MIT-0", "MIT0"}:
        return (
            "MIT No Attribution\n\n"
            "Copyright <YEAR> <COPYRIGHT HOLDER>\n\n"
            'Permission is hereby granted, free of charge, to any person obtaining a copy of this\n'
            'software and associated documentation files (the "Software"), to deal in the Software\n'
            "without restriction, including without limitation the rights to use, copy, modify,\n"
            "merge, publish, distribute, sublicense, and/or sell copies of the Software, and to\n"
            "permit persons to whom the Software is furnished to do so.\n\n"
            'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,\n'
            "INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A\n"
            "PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT\n"
            "HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF\n"
            "CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE\n"
            "OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n"
        )
    return f"{license_id}\n\n(占位：请替换为你选定的许可证全文)\n"


def _package_version() -> str:
    from . import __version__  # 延迟导入：避免与包初始化形成环
    return __version__


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    # 直接调用本模块（测试、或 `python -m allin_governance.init`）时没有经过
    # `cli.main`，这里要自己兜一次编码 —— 本函数每一行都在打中文。
    _stdio.configure()
    parser = argparse.ArgumentParser(
        prog="allin-governance init",
        description="在一个目录里生成可跑的最小治理骨架（门禁 + 文档四分类 + registry）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "生成后立刻可验：\n"
            "  cd <目标目录> && npm run check:governance\n"
            "需要 Node >= 22.18 与 Python >= 3.9；门禁本体零第三方依赖。"
        ),
    )
    parser.add_argument("target", nargs="?", default=".", help="目标目录（默认当前目录）")
    parser.add_argument("--force", action="store_true",
                        help="覆盖已存在的套装文件（升级用）；docs/README/LICENSE 永不被覆盖")
    parser.add_argument("--no-git", action="store_true",
                        help="不初始化 git、不建首个提交（门禁需要工作树，之后要自己补）")
    parser.add_argument("--license", default="MIT-0", metavar="ID",
                        help="目标缺 LICENSE 时生成的许可证标识（默认 MIT-0；传 none 则不生成）")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不落盘")
    args = parser.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if target.exists() and not target.is_dir():
        print(f"USAGE ERROR: {target} 不是目录", file=sys.stderr)
        return 2
    license_id = None if str(args.license).lower() in {"none", "no", ""} else args.license

    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)

    plan = build_plan(target, force=args.force, with_git=not args.no_git,
                      license_id=license_id, dry_run=args.dry_run)

    print(f"allin-governance init -> {target}")
    if args.dry_run:
        print("  （--dry-run：只算不落盘，以下为计划）")
    print(f"  新建 {len(plan.created)}；保留 {len(plan.kept)}；覆盖 {len(plan.overwritten)}")
    for label, items in (("新建", plan.created), ("覆盖", plan.overwritten)):
        for item in items:
            print(f"    {label}  {item}")
    if plan.kept:
        preview = ", ".join(plan.kept[:6]) + (" …" if len(plan.kept) > 6 else "")
        print(f"    保留  {preview}")
    for note in plan.notes:
        print(f"  · {note}")

    print("\n下一步：")
    print(f"  cd {target}")
    print("  npm run check:governance                                      # 需要 Node >= 22.18")
    print(f"  python {SUITE_RELATIVE.as_posix()}/gates/g00_meta.py --selfcheck   # 单道自证，不需要 Node")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
