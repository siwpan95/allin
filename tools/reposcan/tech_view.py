#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import read_json

data = read_json("tech_meta.json")
for d in data:
    print(f"{d['name']:<26} lang={','.join(d['lang']):<14} gui={','.join(d['gui']):<34} arch={','.join(d['arch'])}")
    if d['deps']:
        print(f"    deps: {', '.join(d['deps'])}")
