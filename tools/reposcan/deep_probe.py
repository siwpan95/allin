#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json

ROOT = "D:/projects/repos"
TARGETS = ["haha","media-tools","players-unified","pluginplayer","write","imgproc",
           "board-replay","captcha-demo","music-prompt-generator","novel-reader"]

def tree(d, maxdepth=2):
    lines=[]
    for root, dirs, files in os.walk(d):
        depth = root[len(d):].count(os.sep)
        if depth > maxdepth:
            dirs[:] = []
            continue
        rel = os.path.relpath(root, d)
        if rel == ".":
            prefix = ""
        else:
            prefix = "  " * depth + rel + "/\n"
        for f in sorted(files):
            lines.append(("  "*(depth+1)) + f)
    return "\n".join(lines)

def find_readme(d):
    for b in ["README.md","README.MD","readme.md","Readme.md","README.txt","README"]:
        p=os.path.join(d,b)
        if os.path.isfile(p): return p
    return None

for name in TARGETS:
    d = os.path.join(ROOT, name)
    print("="*70)
    print(f"### {name}")
    print("--- tree (depth<=2) ---")
    print(tree(d))
    rd = find_readme(d)
    if rd:
        print(f"--- README: {os.path.basename(rd)} (full) ---")
        try:
            with open(rd, encoding="utf-8", errors="ignore") as fh:
                print(fh.read()[:2500])
        except Exception as e:
            print("ERR", e)
    else:
        print("--- no README ---")
    # package.json peek
    pj = os.path.join(d, "package.json")
    if os.path.isfile(pj):
        print("--- package.json ---")
        try:
            with open(pj, encoding="utf-8", errors="ignore") as fh:
                j = json.load(fh)
            print("name:", j.get("name"), "| main:", j.get("main"), "| scripts:", j.get("scripts"))
            print("deps:", list(j.get("dependencies",{}).keys())[:20])
            print("devDeps:", list(j.get("devDependencies",{}).keys())[:20])
        except Exception as e:
            print("ERR", e)
    print()
