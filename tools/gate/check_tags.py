#!/usr/bin/env python3
"""Tag 纪律的「硬件」—— 把散在四份文档里的规矩变成一个退出码。

## 这条纪律原本只在文档里

- `docs/规范/SPEC-004-调试铁律.md` 第 70 条：发布点不可变，**禁止 force push 改写已发布 tag**，
  也禁止删 tag 后同名重建；修正一律递增新 tag。
- `docs/规范/SPEC-102-发版指南.md`：tag 必须指向**全量回归通过**的 commit；release 基于已推送的 tag。
- `docs/规范/SPEC-103-社区协作规范.md`：每个发布版本必须打 tag，release 必须基于已推送 tag。
- `docs/新人开发上手指南.md` §3.2：命名 `<项目>-v<版本>`，**禁止裸 `v1.0.0`**（本仓是 monorepo，会撞车）。

四份文档说的是同一件事，但**没有任何一条能被机器判**：写错了 tag 名、拿轻量 tag 冒充发布、
tag 指向一个没推上去的本地提交、tag 版本与 `pyproject` 对不上、已推的 tag 被悄悄移动 ——
这些在门禁里全都看不出来。本脚本补的就是这一面（2026-11-24 全检的残留项）。

## 判据（每条对应一条已记录的纪律或事故）

1. **命名**：`<包名>-v<MAJOR.MINOR.PATCH>`；裸 `vX.Y.Z` 直接阻断（monorepo 里必撞）。
2. **必须 annotated**：轻量 tag 没有 tag 对象，带不了发布说明，也无法被签名/审计。
3. **版本对账**：tag 名里的版本必须等于**该 commit 上**对应清单的版本（不是 HEAD 的）。
4. **指向已推送的主线**：tag 指向的 commit 必须是 `origin/master` 的祖先；
   否则就是「在本地临时提交上打了 tag，然后忘了推」——发布页会指向一个远端不存在的 commit。
5. **不可变（`--remote`）**：与 `git ls-remote --tags` 的 tag 对象 SHA 比对。
   本地与远端不一致 = 该 tag 被移动/重建过（铁律 70 禁止）；本地有、远端无 = 没推。

## 退出码

`0` 通过 ｜ `1` 阻断 ｜ `3` 环境错（不在 git 仓、git 不可用）。
`exempt`（历史遗留）与 `skip`（判不了）都**不计入通过数**，逐条打印理由。

用法：

    python tools/gate/check_tags.py              # 本地判据（离线）
    python tools/gate/check_tags.py --remote     # 追加远端比对（需要网络，CI 用）
    python tools/gate/check_tags.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_ENV = 3

ROOT = Path(__file__).resolve().parents[2]

#: 历史遗留 tag：保留不删（铁律 70 禁止改写/删后重建），逐条给出理由。
LEGACY_TAGS = {
    "nothing": "2026-08-27 把 misc 分支转成 tag 的历史产物，非发布 tag，保留不删",
}

#: 迟于这个日期的 tag，其指向的 commit 必须在 origin/master 上。
#: 为什么要有这条线：`platform-v1.0.0` / `repocheck-v1.0.0` / `repocheck-v2.0.0`
#: 打于 2026-10-26 —— 那时 platform 与 repocheck 还是**独立仓**，历史没有并入
#: allin 的 master，它们的 commit 天然不在主线上。用日期切分而不是把它们塞进
#: 白名单：新 tag 一律受「必须在主线」约束，历史 tag 不冒充通过、也不拦着不放。
MONOREPO_CUTOFF = "2026-11-01"

#: tag 前缀 → 该包的版本清单。对不上号的前缀按「无可对账清单」豁免（打印理由）。
VERSION_MANIFESTS = {
    "allin-governance": "packages/allin-governance/pyproject.toml",
    "repocheck": "tools/repocheck/pyproject.toml",
    "platform": "platform/package.json",
}

TAG_NAME = re.compile(r"^(?P<name>[a-z0-9][a-z0-9._-]*)-v(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")
BARE_VERSION = re.compile(r"^v\d+\.\d+\.\d+")
REMOTE = "origin"


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=check,
    )


def tag_objects() -> dict[str, str]:
    """{tag 名: 对象 SHA}。"""
    out = git("for-each-ref", "refs/tags", "--format=%(refname:short) %(objectname)").stdout
    result = {}
    for line in out.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            result[parts[0]] = parts[1]
    return result


def peeled_commit(tag: str) -> str:
    out = git("rev-list", "-n1", tag).stdout.strip()
    return out


def manifest_version(commit: str, path: str) -> str | None:
    proc = git("show", f"{commit}:{path}")
    if proc.returncode != 0:
        return None
    text = proc.stdout
    if path.endswith(".toml"):
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        return match.group(1) if match else None
    if path.endswith(".json"):
        try:
            return str(json.loads(text).get("version") or "") or None
        except json.JSONDecodeError:
            return None
    return None


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def ok(self, tag: str, detail: str) -> None:
        self.rows.append(("ok", tag, detail))

    def bad(self, tag: str, detail: str) -> None:
        self.rows.append(("fail", tag, detail))

    def exempt(self, tag: str, detail: str) -> None:
        self.rows.append(("exempt", tag, detail))

    def skip(self, tag: str, detail: str) -> None:
        self.rows.append(("skip", tag, detail))

    def report(self, as_json: bool) -> int:
        order = {"fail": 0, "skip": 1, "exempt": 2, "ok": 3}
        for status, tag, detail in sorted(self.rows, key=lambda r: (order[r[0]], r[1])):
            print(f"[{status}] {tag}: {detail}")
        failed = sum(1 for r in self.rows if r[0] == "fail")
        skipped = sum(1 for r in self.rows if r[0] == "skip")
        exempted = sum(1 for r in self.rows if r[0] == "exempt")
        print(f"tag-check: ok={len(self.rows) - failed - skipped - exempted} "
              f"fail={failed} skip={skipped} exempt={exempted}")
        if as_json:
            print(json.dumps({"rows": self.rows, "fail": failed, "skip": skipped}, ensure_ascii=False))
        return EXIT_BLOCKING if failed else EXIT_OK


def check(remote: bool, as_json: bool) -> int:
    if git("rev-parse", "--git-dir").returncode != 0:
        print("ENV ERROR: 不在 git 仓库内", file=sys.stderr)
        return EXIT_ENV

    tags = tag_objects()
    if not tags:
        print("tag-check: SKIPPED (not a pass) 本仓没有任何 tag —— 判不了，不是通过")
        return EXIT_OK

    # 判「已推送主线」的基准：origin/master 优先（权威），没有就退到本地 master。
    base_ref = f"{REMOTE}/master"
    base = git("rev-parse", "--verify", "--quiet", base_ref).stdout.strip()
    base_label = base_ref
    if not base:
        base = git("rev-parse", "--verify", "--quiet", "master").stdout.strip()
        base_label = "master（无 origin/master 可判，降级为本地基准）"

    result = Result()
    for tag in sorted(tags):
        if tag in LEGACY_TAGS:
            result.exempt(tag, LEGACY_TAGS[tag])
            continue

        match = TAG_NAME.match(tag)
        if not match:
            if BARE_VERSION.match(tag) and "-v" not in tag:
                result.bad(tag, "裸 `vX.Y.Z` —— 本仓是 monorepo，会与并入仓的 tag 撞名（指南 §3.2）")
            else:
                result.bad(tag, "命名不符合 `<包名>-v<MAJOR.MINOR.PATCH>`（SPEC-102 / 指南 §3.2）")
            continue

        package = match.group("name")
        version = match.group("version")

        kind = git("cat-file", "-t", tag).stdout.strip()
        if kind != "tag":
            result.bad(tag, f"是轻量 tag（对象类型 {kind or 'unknown'}）—— 发布 tag 必须 annotated")
            continue

        commit = peeled_commit(tag)
        if not commit:
            result.bad(tag, "解析不出指向的 commit")
            continue

        tagged_at = git("for-each-ref", f"refs/tags/{tag}", "--format=%(taggerdate:short)").stdout.strip()
        if base:
            ancestor = git("merge-base", "--is-ancestor", commit, base)
            if ancestor.returncode != 0:
                if tagged_at and tagged_at < MONOREPO_CUTOFF:
                    result.exempt(
                        tag,
                        f"打于 {tagged_at}（早于 {MONOREPO_CUTOFF}）—— 并仓前的独立仓历史 tag，"
                        f"其 commit {commit[:8]} 未并入 master，属历史遗留不阻断",
                    )
                    continue
                result.bad(tag, f"指向 {commit[:8]} 不在 {base_label} 上 —— 打了 tag 却没推那条提交")
                continue

        manifest = VERSION_MANIFESTS.get(package)
        if manifest is None:
            result.exempt(tag, f"前缀 `{package}` 无版本清单可对账（不是已登记的发布包）")
            continue

        declared = manifest_version(commit, manifest)
        if declared is None:
            result.bad(tag, f"读不到 {commit[:8]}:{manifest} 的版本 —— 无法对账")
            continue
        if declared != version:
            result.bad(
                tag,
                f"tag 版本 {version} ≠ 该 commit 的 {manifest} 版本 {declared}"
                "（发版意味着两处必须相等；不等就是拿别的版本号打了这个 tag）",
            )
            continue

        result.ok(tag, f"annotated → {commit[:8]}，版本 {version} 与 {manifest} 一致")

    if remote:
        proc = git("ls-remote", "--tags", REMOTE)
        if proc.returncode != 0:
            result.skip("--remote", f"ls-remote {REMOTE} 失败（网络或远端不可达）：{proc.stderr.strip()[:120]}")
        else:
            remote_sha: dict[str, str] = {}
            for line in proc.stdout.splitlines():
                sha, _, ref = line.partition("\t")
                name = ref.removeprefix("refs/tags/").removesuffix("^{}")
                if ref.endswith("^{}"):
                    continue  # peeled 行，取 tag 对象本身那一行
                remote_sha[name] = sha
            for tag, local in sorted(tags.items()):
                if tag in LEGACY_TAGS:
                    continue
                if tag not in remote_sha:
                    result.bad(tag, "本地有、远端无 —— tag 没推上去（发布页会指向不存在的引用）")
                elif remote_sha[tag] != local:
                    result.bad(
                        tag,
                        f"远端 tag 对象 {remote_sha[tag][:8]} ≠ 本地 {local[:8]} "
                        "—— 该 tag 被移动/重建过（铁律 70 禁止；修正应递增新 tag）",
                    )

    return result.report(as_json)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_tags",
        description="Tag 纪律机器判据：命名 / annotated / 版本对账 / 指向已推送主线 / 不可变",
    )
    parser.add_argument("--remote", action="store_true",
                        help="追加远端比对（ls-remote 检测移动/未推送；需要网络）")
    parser.add_argument("--json", action="store_true", help="追加机器可读输出")
    args = parser.parse_args(argv)
    return check(args.remote, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
