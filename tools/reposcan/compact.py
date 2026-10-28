#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re

with open("repos_meta.json", encoding="utf-8") as fh:
    data = json.load(fh)

def title_and_desc(text):
    title = ""
    desc = []
    for l in text.splitlines():
        s = l.strip()
        if not s:
            continue
        m = re.match(r"^#+\s+(.*)", s)
        if m and not title:
            title = m.group(1).strip()
            continue
        if s.startswith(">") or s.startswith("![") or s.startswith("[!["):
            continue
        # skip badge lines
        if re.search(r"!\[.*\]\(.*\)", s) and len(s) < 200 and s.startswith("!"):
            continue
        if len(s) > 10 and not s.startswith("#") and not s.startswith("-") and not s.startswith("*"):
            desc.append(re.sub(r"[#*`\[\]\(\)]", "", s)[:160])
            if len(desc) >= 3:
                break
    return title, " | ".join(desc)

rows = []
for d in data:
    t, dd = title_and_desc(d.get("readme_text",""))
    langs = ",".join(d.get("langs",[])) or "-"
    rows.append((d["name"], langs, t, dd))

# print compact
for name, langs, title, desc in rows:
    print(f"{name}\t[{langs}]\t{title}")
    if desc:
        print(f"    ↳ {desc}")
