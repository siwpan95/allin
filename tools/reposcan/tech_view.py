#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
with open("tech_meta.json", encoding="utf-8") as fh:
    data = json.load(fh)
for d in data:
    print(f"{d['name']:<26} lang={','.join(d['lang']):<14} gui={','.join(d['gui']):<34} arch={','.join(d['arch'])}")
    if d['deps']:
        print(f"    deps: {', '.join(d['deps'])}")
