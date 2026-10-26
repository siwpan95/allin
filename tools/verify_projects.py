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
SYSTEM_PYTHON = Path(r"G:\Python314\python.exe")
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


def prepare(command: str, project: Path) -> str:
    first = command.split()[0].lower() if command.split() else ""
    if first in ("python", "pythonw"):
        rest = command[len(first):].strip()
        return f'"{interpreter(project)}" {rest}'.strip()
    if first in ("npm", "node") or first.endswith(".bat"):
        return f"cmd /c {command}"
    return command


def headless_off(entry: dict) -> bool:
    """Some smokes need a real window/pyglet context (headless drivers break them)."""
    verify = entry.get("verify")
    return isinstance(verify, dict) and verify.get("headless") is False


def run(command: str, project: Path, timeout: float,
        env: dict[str, str] | None = None) -> tuple[int | None, str, float]:
    started = time.time()
    process = subprocess.Popen(command, cwd=str(project), shell=True,
                               env=env or {**os.environ, **HEADLESS_ENV},
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                               errors="replace")
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
    code, output, _seconds = run(f'"{python}" -c "{script}"', project, timeout)
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
    if explicit:
        command = prepare(explicit, project)
    else:
        launch = launch_text(entry)
        if not launch:
            record.update(evidence="no launch/verify command")
            return record
        command = prepare(launch, project) + " --help"
    record["command"] = command
    env = {**os.environ, **({} if headless_off(entry) else HEADLESS_ENV)}
    code, output, seconds = run(command, project, timeout, env)
    record["seconds"] = seconds
    record["detail"] = "\n".join(output.splitlines()[:4])[-400:]
    if code is None:
        crashed = bool(re.search(r"(?m)^\s*(Traceback|.*Error:)", output))
        record.update(tier="T4", evidence="CRASHED" if crashed else "TIMEOUT",
                      detail=(record["detail"] or "still running after timeout"))
        return record
    if code == 0:
        if explicit:
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
        if section in ("launch", "verify") and stripped.startswith("command:"):
            data.setdefault(section, {})["command"] = stripped.split(":", 1)[1].strip()
    return data


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="verify every registered project headlessly")
    parser.add_argument("--only", default="", help="comma separated ids")
    parser.add_argument("--category", default="", help="only this category")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=6, help="parallel projects (GUI timeouts are the cost)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

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
