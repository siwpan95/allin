#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, re, sys

ROOT = "D:/projects/repos"

LANGS = {
    "package.json": "Node/JS",
    "yarn.lock": "Node/JS",
    "pnpm-lock.yaml": "Node/JS",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "setup.py": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java",
    "build.gradle": "Java/Gradle",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
    "*.csproj": "C#/.NET",
    "CMakeLists.txt": "C/C++",
    "Makefile": "C/C++",
    "tsconfig.json": "TypeScript",
}

def find_readme(d):
    for cand in ["README.md","README.MD","readme.md","Readme.md","README.txt","README","README.rst","readme.md"]:
        p = os.path.join(d, cand)
        if os.path.isfile(p):
            return p
    # also match README* generically
    try:
        for f in os.listdir(d):
            if re.match(r"readme", f, re.I) and os.path.isfile(os.path.join(d,f)):
                return os.path.join(d,f)
    except Exception:
        pass
    return None

def lang_of(d):
    found = set()
    try:
        for f in os.listdir(d):
            fp = os.path.join(d,f)
            if os.path.isdir(fp):
                continue
            low = f.lower()
            if low in LANGS:
                found.add(LANGS[low])
            if f.endswith(".csproj"):
                found.add("C#/.NET")
            if f.endswith(".lua"):
                found.add("Lua")
            if f in ("main.py","app.py","__main__.py"):
                found.add("Python")
            if f in ("main.go",):
                found.add("Go")
    except Exception:
        pass
    return sorted(found)

def top_entries(d, n=20):
    try:
        items = sorted(os.listdir(d))
        return items[:n]
    except Exception:
        return []

def readme_summary(path, max_chars=1200):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return ""
    # first non-empty lines
    lines = [l.rstrip() for l in text.splitlines()]
    # find first heading
    out = []
    cnt = 0
    for l in lines:
        if not l.strip():
            continue
        out.append(l)
        cnt += len(l)
        if cnt > max_chars:
            break
    return "\n".join(out)[:max_chars]

def main():
    repos = sorted([d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT,d))])
    result = []
    for r in repos:
        d = os.path.join(ROOT, r)
        rd = find_readme(d)
        summary = readme_summary(rd) if rd else ""
        result.append({
            "name": r,
            "readme": os.path.basename(rd) if rd else None,
            "langs": lang_of(d),
            "top": top_entries(d),
            "readme_text": summary,
        })
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repos_meta.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print(f"scanned {len(result)} repos -> {out}")

if __name__ == "__main__":
    main()
