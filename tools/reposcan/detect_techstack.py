#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增强扫描：提取每个仓库的技术栈信号（语言/GUI/架构/引擎依赖/关键三方库）。"""
import os, re, json, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import repos_root, data_path

ROOT = repos_root()

GUI_TOKENS = {
    "tkinter": [r"import\s+tkinter", r"from\s+tkinter", r"Tk\(\)"],
    "pygame": [r"import\s+pygame", r"import\s+pygame_ce", r"pygame-ce"],
    "pyglet": [r"import\s+pyglet"],
    "Pillow/PIL": [r"import\s+PIL", r"from\s+PIL", r"import\s+Image"],
    "VLC": [r"import\s+vlc", r"python-vlc"],
    "OpenCV": [r"import\s+cv2"],
    "Matplotlib": [r"import\s+matplotlib"],
}
ARCH_TOKENS = {
    "Cordis": [r"cordis", r"@cordisjs", r"cordis\.yml", r"ctx\."],
    "ECS": [r"\becs\b", r"EntityComponent", r"System\b.*Component"],
    "allin_engine": [r"allin_engine", r"\balloy\b"],
    "3dworld/world3d": [r"world3d", r"import\s+world3d", r"3dworld"],
    "dse-core": [r"dse_core", r"dse-core", r"dse\b", r"dict-scene"],
    "procgen/worldbuilder": [r"worldbuilder", r"procgen"],
}
KEY_LIBS = [
    "numpy","scipy","pandas","torch","tensorflow","transformers","ollama",
    "pydub","soundfile","sounddevice","demucs","librosa","pyaudio",
    "opencv-python","cv2","Pillow","pyautogui","playwright","requests",
    "beautifulsoup4","bs4","lxml","openpyxl","pyvista","pygame","pyglet",
    "pycryptodome","cryptography","ffmpeg","vlc","python-vlc","pystray",
    "asteval","pygame-ce","midi","mido","supabase","fastapi","flask",
    "express","koa","fastify","vue","react","svelte","vite","tauri",
    "electron","qrcode","reportlab","pymupdf","fitz","weasyprint",
]

def read_small(p, max_lines=30):
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            out = []
            for i, line in enumerate(fh):
                out.append(line)
                if i >= max_lines - 1:
                    break
            return "".join(out)
    except Exception:
        return ""

def read_text(p, max_chars=200000):
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(max_chars)
    except Exception:
        return ""

def scan_repo(d):
    name = os.path.basename(d)
    files = []
    for root, dirs, fnames in os.walk(d):
        depth = root[len(d):].count(os.sep)
        if depth > 2:
            dirs[:] = []
            continue
        for fn in fnames:
            files.append(os.path.join(root, fn))
    # 依赖文件
    pkg = None
    pyproject = None
    req = None
    for f in files:
        b = os.path.basename(f).lower()
        if b == "package.json":
            pkg = read_text(f, 20000)
        elif b == "pyproject.toml":
            pyproject = read_text(f, 20000)
        elif b == "requirements.txt":
            req = read_text(f, 20000)
    # 顶层 py/js/ts 的 import 信号（深度<=1）
    head_blob = ""
    manifests = []
    for f in files:
        b = os.path.basename(f)
        ext = os.path.splitext(b)[1]
        rel = os.path.relpath(f, d)
        depth = rel.count(os.sep)
        if ext in (".py", ".js", ".ts", ".mjs", ".cjs") and depth <= 1:
            head_blob += read_small(f, 25) + "\n"
        if b.lower() == "manifest.json" and depth <= 1:
            manifests.append(read_text(f, 5000))
    manifest_blob = "\n".join(manifests)

    blob = (pkg or "") + (pyproject or "") + (req or "") + head_blob + manifest_blob

    # 语言
    lang = []
    if pkg: lang.append("Node/JS")
    if pyproject or req: lang.append("Python")
    if re.search(r"\"typescript\"", pkg or "") or os.path.exists(os.path.join(d,"tsconfig.json")):
        lang.append("TypeScript")
    if os.path.exists(os.path.join(d,"Cargo.toml")): lang.append("Rust")
    if os.path.exists(os.path.join(d,"go.mod")): lang.append("Go")
    if os.path.exists(os.path.join(d,"pom.xml")) or os.path.exists(os.path.join(d,"build.gradle")): lang.append("Java")
    # fallback by extension
    if not lang:
        exts = set(os.path.splitext(f)[1] for f in files)
        if ".py" in exts: lang.append("Python")
        elif ".js" in exts or ".ts" in exts: lang.append("Node/JS")
        elif ".html" in exts: lang.append("Web/静态")

    # GUI
    gui = []
    for label, toks in GUI_TOKENS.items():
        if any(re.search(t, blob, re.I) for t in toks):
            gui.append(label)
    if re.search(r"\"manifest_version\"\s*:\s*3|\"action\"\s*:", manifest_blob):
        gui.append("浏览器扩展(MV3)")
    if re.search(r"express|koa|fastify|node:http|vite|@cordisjs/service-http|http\.createServer|FastAPI|flask", blob, re.I):
        gui.append("Web服务/HTTP")
    if re.search(r"pyautogui|pynput|keyboard|mouse|ctypes", blob, re.I) and "tkinter" not in gui:
        gui.append("系统级输入模拟")

    # 架构
    arch = []
    for label, toks in ARCH_TOKENS.items():
        if any(re.search(t, blob, re.I) for t in toks):
            arch.append(label)
    if "Cordis" in arch and "Node/JS" not in lang and "Python" in lang:
        # python 里出现 cordis 字样通常也是 cordis 宿主
        pass

    # 关键库
    deps = sorted({lib for lib in KEY_LIBS if re.search(r"(?<![\w-])"+re.escape(lib)+r"(?![\w-])", blob, re.I)})

    return {
        "name": name,
        "lang": lang or ["-"],
        "gui": gui or ["CLI/headless"],
        "arch": arch or ["-"],
        "deps": deps,
        "has_pkg": bool(pkg),
        "has_py": bool(pyproject or req),
    }

def main():
    repos = sorted([os.path.join(ROOT, d) for d in os.listdir(ROOT)
                    if os.path.isdir(os.path.join(ROOT, d))])
    out = [scan_repo(d) for d in repos]
    path = data_path("tech_meta.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"scanned {len(out)} -> {path}")

if __name__ == "__main__":
    main()
