# -*- coding: utf-8 -*-
"""Verify every project in `platform/registry/projects/` headlessly.

One command, one report. For each entry the verifier picks the strongest
available evidence, in this order:

    1. `verify.command`   an explicit headless check committed with the entry
                          (this is where GUI projects get a `--selfcheck`)
    2. `launch.command --help`  a real command-line surface (exit 0)
    3. package import     the project's own package loads under its interpreter

Evidence tiers, from strong to weak:

    T1  explicit `verify.command` exited 0          ("ran the functionality")
    T2  launch command accepted --help / exited 0   ("command surface works")
    T3  package imports headlessly                  ("code and deps load")
    T4  none of the above                           ("needs a CLI/selfcheck")
    N/A `verify.skip` declares a non-runnable project (content corpus / asset library)

Exit codes: 0 all T1/T2/T3, 1 at least one T4 or a crash, 2 usage error,
3 environment error (no PyYAML / no registry).

Read-only: nothing is installed, no project file is written.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

try:  # optional: PyYAML gives a full parse, the built-in reader only needs four keys
    import yaml
except ImportError:  # pragma: no cover - zero-dependency path
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "platform" / "registry" / "projects"
REPOS = ROOT.parent / "repos"
# g01 铁律 5：绝不写死机器盘符解释器。优先级：ALLIN_PYTHON 环境变量 > 当前解释器。
_env_python = os.environ.get("ALLIN_PYTHON")
SYSTEM_PYTHON = Path(_env_python) if _env_python else Path(sys.executable)
DEFAULT_REPORT = ROOT / "tools" / "gate" / "audit" / "projects_verify.json"

HEADLESS_ENV = {
    "SDL_VIDEODRIVER": "dummy",
    "SDL_AUDIODRIVER": "dummy",
    "PYGLET_HEADLESS": "1",
    "QT_QPA_PLATFORM": "offscreen",
    "MPLBACKEND": "Agg",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
    "PYTHONWARNINGS": "ignore",
    # 验证过程不许在项目里留下字节码：有仓曾把 .pyc 跟踪进库，一次自检就会把工作区弄脏。
    "PYTHONDONTWRITEBYTECODE": "1",
    "GIT_TERMINAL_PROMPT": "0",
}

HELP_HINT = re.compile(r"(?i)\b(usage|options|commands|arguments)\b")
DEPS_HINT = re.compile(r"(?:No module named|Cannot find module)\s*['\"]?([A-Za-z0-9_.\-]+)")


def launch_text(entry: dict) -> str:
    launch = entry.get("launch")
    if isinstance(launch, dict):
        return str(launch.get("command") or "").strip()
    return str(launch or "").strip()


def verify_text(entry: dict) -> str:
    verify = entry.get("verify")
    if isinstance(verify, dict):
        return str(verify.get("command") or "").strip()
    return str(verify or "").strip()


def skip_reason(entry: dict) -> str:
    """A declared non-runnable project (content corpus / asset library), with its reason."""
    verify = entry.get("verify")
    if isinstance(verify, dict):
        return str(verify.get("skip") or "").strip()
    return ""


def verify_commands_list(entry: dict) -> list[str]:
    """B602 方案 A：支持 `verify.commands` 列表字段（多个显式 headless 检查）。

    与 `verify.command` 单字符串互斥（verify() 中优先用单字符串）。列表里
    每条仍是 shell=False 的 argv（经 prepare()），`&&` 由 Python 顺序短路代替，
    不再依赖 shell 解释。空列表 / 非列表 / 缺字段一律返回 []。
    """
    verify = entry.get("verify")
    if isinstance(verify, dict) and isinstance(verify.get("commands"), list):
        return [str(c).strip() for c in verify["commands"] if str(c).strip()]
    return []


def project_dir(entry: dict) -> Path | None:
    raw = str(entry.get("path") or "").replace("\\", "/").strip("/")
    if raw.startswith("repos/"):
        return REPOS / raw.split("/", 1)[1]
    if raw == "platform":
        return ROOT / "platform"
    return None


def interpreter(project: Path) -> Path:
    venv = project / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return venv
    return SYSTEM_PYTHON if SYSTEM_PYTHON.is_file() else Path(sys.executable)


def prepare(command: str, project: Path) -> list[str]:
    """B602 方案 A：把命令拆成 argv 以 shell=False 安全执行，不再 shell=True。

    - python/pythonw → [解释器, *参数]；
    - npm/node/*.bat → 显式 argv 调 cmd.exe（shell=False，保留 Windows 行为；
      cmd /c 仍解释 && 等元字符，但属显式调用而非 shell=True）；
    - 其余 → shlex.split（仓内 verify 命令统一用正斜杠，POSIX 分词安全）。
    """
    parts = command.split()
    first = parts[0].lower() if parts else ""
    if first in ("python", "pythonw"):
        rest = command[len(parts[0]):].strip()
        return [str(interpreter(project)), *shlex.split(rest)]
    if first in ("npm", "node") or first.endswith(".bat"):
        return ["cmd", "/c", command]
    return shlex.split(command)


def headless_off(entry: dict) -> bool:
    """Some smokes need a real window/pyglet context (headless drivers break them)."""
    verify = entry.get("verify")
    return isinstance(verify, dict) and verify.get("headless") is False


def _display_argv(argv: list[str]) -> str:
    """Report-safe rendering of an argv list (no dependency on shlex.join)."""
    return " ".join(shlex.quote(p) for p in argv)


def run(command: list[str], project: Path, timeout: float,
        env: dict[str, str] | None = None) -> tuple[int | None, str, float]:
    """B602 方案 A：argv 列表 + shell=False。绝不再 shell=True。

    `command` 恒为 argv 列表（由 prepare() 产出）；`cmd /c` 也走显式 argv，
    不依赖 shell=True。元字符（; | && 等）不会被解释，注入被中性化。

    注意：shell=False 下，命令的可执行体不存在会由 `Popen` 直接抛 OSError
    （`shell=True` 时由 shell 吞掉、仅返回非 0）。这里把「启动失败」降级为
    (1, 错误信息)，让 verify() 走 T4 / import_check 兜底，而不是让整个
    verifier 崩溃——与旧 shell=True 行为的失败语义保持一致。
    """
    started = time.time()
    try:
        process = subprocess.Popen(command, cwd=str(project), shell=False,
                                   env=env or {**os.environ, **HEADLESS_ENV},
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                   errors="replace")
    except OSError as e:
        return 1, f"launch failed: {type(e).__name__}: {e}", round(time.time() - started, 2)
    try:
        output, _ = process.communicate(timeout=timeout)
        code = process.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            output = process.stdout.read() if process.stdout else ""
        except Exception:  # noqa: BLE001
            output = ""
        code = None
    return code, (output or "").strip(), round(time.time() - started, 2)


def import_check(project: Path, timeout: float = 30.0) -> tuple[bool, str]:
    packages = [child.name for child in project.iterdir()
                if child.is_dir() and (child / "__init__.py").is_file() and not child.name.startswith(".")]
    if not packages:
        return False, "no package"
    python = interpreter(project)
    name = packages[0]
    script = f"import sys; sys.path.insert(0, '.'); import {name}; print('IMPORT_OK')"
    code, output, _seconds = run([str(python), "-c", script], project, timeout)
    return (code == 0 and "IMPORT_OK" in output), output.strip().splitlines()[-1][:120] if output.strip() else ""


def verify(entry: dict, timeout: float) -> dict:
    identifier = str(entry.get("id") or entry.get("file") or "?")
    project = project_dir(entry)
    record = {"id": identifier, "category": entry.get("category", ""),
              "project": str(project) if project else "", "tier": "T4",
              "evidence": "", "command": "", "seconds": 0.0, "detail": ""}
    if project is None or not project.is_dir():
        record.update(evidence="no local project", detail="path does not exist")
        return record

    declared_skip = skip_reason(entry)
    if declared_skip:
        record.update(tier="N/A", evidence="not runnable (declared)", detail=declared_skip)
        return record

    explicit = verify_text(entry)
    commands = verify_commands_list(entry)
    if explicit:
        prepared = [prepare(explicit, project)]
        kind = "explicit"
    elif commands:
        prepared = [prepare(c, project) for c in commands]
        kind = "explicit"
    else:
        launch = launch_text(entry)
        if not launch:
            record.update(evidence="no launch/verify command")
            return record
        prepared = [[*prepare(launch, project), "--help"]]
        kind = "launch"

    record["command"] = " && ".join(_display_argv(c) for c in prepared)
    env = {**os.environ, **({} if headless_off(entry) else HEADLESS_ENV)}
    # B602 方案 A：每条命令都是 shell=False 的 argv；顺序执行、任一失败即短路，
    # 等价旧 `&&` 语义，但不再交予 shell 解释元字符。
    code = 0
    output = ""
    seconds = 0.0
    for cmd in prepared:
        c, o, s = run(cmd, project, timeout, env)
        seconds += s
        if c is None or c != 0:
            code, output = c, o
            break
        output = o
    record["seconds"] = seconds
    record["detail"] = "\n".join(output.splitlines()[:4])[-400:]
    if code is None:
        crashed = bool(re.search(r"(?m)^\s*(Traceback|.*Error:)", output))
        record.update(tier="T4", evidence="CRASHED" if crashed else "TIMEOUT",
                      detail=(record["detail"] or "still running after timeout"))
        return record
    if code == 0:
        if kind == "explicit":
            record.update(tier="T1", evidence="verify.command exit 0")
        else:
            record.update(tier="T2", evidence="help/launch exit 0" if HELP_HINT.search(output) else "launch exit 0")
        return record

    missing = DEPS_HINT.search(output)
    if missing:
        record.update(tier="T4", evidence="missing dependency", detail=missing.group(1))
        return record

    ok, detail = import_check(project)
    if ok:
        record.update(tier="T3", evidence="package imports", detail=detail)
    else:
        record.update(tier="T4", evidence="entry failed", detail=record["detail"] or detail)
    return record


def load_entry(path: Path) -> dict:
    """Read one registry entry, preferring PyYAML and falling back to a line reader.

    The fallback is deliberately narrow: it extracts only the four fields this
    tool judges (`id`, `category`, `path`, `launch.command`, `verify.command`),
    so the tool stays zero-dependency like the rest of `tools/`.
    """
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            data["file"] = path.stem
            return data
    data: dict = {"file": path.stem}
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and ":" in stripped:
            key, _, value = stripped.partition(":")
            section = key.strip()
            if value.strip():
                data[section] = value.strip()
            continue
        # P4：回退读取器补 skip/headless（与 YAML 路径语义对齐）。
        # 仅捕获 launch/verify 下的已知键，避免把任意子键都吞进来。
        if section in ("launch", "verify"):
            if ":" in stripped:
                sub_key, _, sub_val = stripped.partition(":")
                sub_key = sub_key.strip()
                if sub_key == "commands":
                    # B602 方案 A：`verify.commands` 列表字段（多个 headless 检查）。
                    data.setdefault(section, {})["commands"] = []
                elif sub_key in ("command", "skip", "headless"):
                    data.setdefault(section, {})[sub_key] = sub_val.strip()
            elif stripped.startswith("- ") and isinstance(
                    data.get(section, {}).get("commands"), list):
                # 列表项：收集进已开启的 commands 列表（YAML `- item` 形态）。
                data[section]["commands"].append(stripped[2:].strip())
    return data


def selftest() -> int:
    """B602 方案 A 自检：含非法元字符的命令必须被中性化（shell=False，不交予 shell 解释）。

    不联网、不扫仓库、不改工作区。验证三件事：
      ① prepare() 返回 list[str]（不再是 shell 字符串）；
      ② 合法命令在 shell=False 下仍正常执行（exit 0）；
      ③ 含 `;` 注入的命令字符串，经 prepare()+run() 后绝不创建注入目标文件
         （证明 shell 注入被中性化，这是 B602 整改的核心可证伪点）。
    另验证 verify.commands 列表字段在 YAML 路径与回退路径下都能被正确解析。
    """
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="allin-vp-selftest-"))
    fails = 0
    py = str(SYSTEM_PYTHON)
    marker = tmp / "ALLIN_B602_PWNED"

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        if cond:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")
            fails += 1

    # ① prepare 返回 list[str]
    check("① prepare 返回 list[str]", isinstance(prepare("python -c \"print(1)\"", tmp), list))

    # ② 合法命令在 shell=False 下正常执行
    code, output, _ = run([py, "-c", "print('ok')"], tmp, 30)
    check("② 合法命令 exit 0 且输出含 ok", code == 0 and "ok" in (output or ""))

    # ③ 负向：含 `;` 注入的命令经 prepare+run 不得创建 marker（核心 B602 断言）
    malicious = "python -c 'print(1)' ; python -c 'open(%r, \"w\").close()'" % str(marker)
    code, output, _ = run(prepare(malicious, tmp), tmp, 30)
    check("③ 元字符未被 shell 解释（marker 不存在）", not marker.exists())

    # ⑤ 启动失败（可执行体不存在）必须降级为 code=1，而非让 verifier 崩溃
    code, output, _ = run(["this_executable_does_not_exist_xyz", "--help"], tmp, 30)
    check("⑤ 启动失败降级为 code=1（不崩溃）", code == 1 and "launch failed" in (output or ""))

    # ④ verify.commands 列表字段：YAML 路径 + 回退路径都能解析
    yaml_text = (
        "id: t\n"
        "verify:\n"
        "  commands:\n"
        "    - python -c \"print(1)\"\n"
        "    - python -c \"print(2)\"\n"
    )
    if yaml is not None:
        data = yaml.safe_load(yaml_text)
        cmds = verify_commands_list(data)
        check("④ yaml 路径解析 commands 列表",
              cmds == ['python -c "print(1)"', 'python -c "print(2)"'])
    p = tmp / "t.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cmds2 = verify_commands_list(load_entry(p))
    check("④ 回退路径解析 commands 列表",
          len(cmds2) == 2 and all(c.startswith("python") for c in cmds2))

    # 清理（若注入竟成功创建了 marker，也一并清掉，避免污染）
    try:
        if marker.exists():
            marker.unlink()
    except OSError:
        pass
    print()
    if fails == 0:
        print("verify_projects --selftest: 全部通过（B602 方案A 中性化验证）")
    else:
        print(f"verify_projects --selftest: {fails} 项失败", file=sys.stderr)
    return fails


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="verify every registered project headlessly")
    parser.add_argument("--only", default="", help="comma separated ids")
    parser.add_argument("--category", default="", help="only this category")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=6, help="parallel projects (GUI timeouts are the cost)")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--selftest", action="store_true",
                        help="B602 方案A 自检：非法元字符必须被中性化（不扫仓库）")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if not REGISTRY.is_dir():
        print(f"verify_projects: registry missing at {REGISTRY}", file=sys.stderr)
        return 3

    entries = []
    for path in sorted(REGISTRY.glob("*.yaml")):
        entries.append(load_entry(path))
    if args.only:
        wanted = {part.strip() for part in args.only.split(",")}
        entries = [entry for entry in entries if entry.get("id") in wanted]
    if args.category:
        entries = [entry for entry in entries if entry.get("category") == args.category]
    if args.limit:
        entries = entries[:args.limit]

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(verify, entry, args.timeout) for entry in entries]
        for future in futures:
            record = future.result()
            records.append(record)
            if not args.quiet:
                print(f"  {record['id']:<26} {record['tier']}  {record['evidence']:<28} {record['seconds']:>6}s")

    tally = {}
    for record in records:
        tally[record["tier"]] = tally.get(record["tier"], 0) + 1
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\ntiers:", dict(sorted(tally.items())), "total:", len(records))
    print("report:", args.json)
    return 0 if tally.get("T4", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
