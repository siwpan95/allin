#!/usr/bin/env python3
"""
packer_pro.py — 强化版 PyInstaller 打包工具
支持：单文件/多文件架构、图标内嵌、数字签名
"""

import os
import sys
import subprocess
import threading
import shutil
import json
import zipfile
import tempfile
from pathlib import Path
from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog, messagebox, colorchooser
import tkinter as tk

# ─── 工具函数 ────────────────────────────────────────────────────────────────

def find_signtool():
    """查找 signtool.exe（Windows SDK）"""
    candidates = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\x86\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # 尝试从 PATH 查找
    try:
        result = subprocess.run(["where", "signtool"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return None


def png_to_ico(png_path: Path, ico_path: Path, sizes=None):
    """将 PNG 转换为多尺寸 ICO（需要 Pillow）"""
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("需要 Pillow 库来转换图片。请运行: pip install Pillow")
    
    if sizes is None:
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    img = Image.open(png_path).convert("RGBA")
    icons = []
    for size in sizes:
        icons.append(img.resize(size, Image.LANCZOS))
    
    icons[0].save(ico_path, format="ICO", sizes=[(i.width, i.height) for i in icons])
    return ico_path


def scan_py_files(project_dir: Path):
    """扫描项目目录中的所有 .py 文件"""
    return sorted(project_dir.rglob("*.py"))


def find_entry_candidates(py_files):
    """查找可能的入口文件"""
    candidates = []
    for f in py_files:
        name = f.name.lower()
        if name in ("main.py", "__main__.py", "app.py", "run.py", "start.py"):
            candidates.append(f)
    return candidates


def get_project_tree(project_dir: Path):
    """获取项目目录树（用于展示）"""
    items = []
    for p in sorted(project_dir.iterdir()):
        if p.name.startswith(".") or p.name == "__pycache__":
            continue
        items.append(p)
    return items


# ─── 主 GUI 类 ───────────────────────────────────────────────────────────────

class PackerProGUI(Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.root.title("PyInstaller 打包工具 Pro")
        self.root.geometry("900x700")
        
        # 状态变量
        self.project_dir = StringVar()
        self.entry_file = StringVar()
        self.icon_path = StringVar()
        self.mode = StringVar(value="single")  # single / multi
        self.console_mode = StringVar(value="windowed")  # windowed / console
        self.output_mode = StringVar(value="onefile")  # onefile / onedir
        self.sign_enabled = BooleanVar(value=False)
        self.cert_path = StringVar()
        self.cert_password = StringVar()
        self.timestamp_url = StringVar(value="http://timestamp.digicert.com")
        
        # 附加数据列表
        self.extra_data = []   # [(src, dst), ...]
        self.extra_binary = [] # [(src, dst), ...]
        self.hidden_imports = []
        
        self.project_dir_path = None
        self.pack_dir = Path(__file__).resolve().parent / "dist_pro"
        self.pack_dir.mkdir(exist_ok=True)
        
        self.build_ui()
        
    def build_ui(self):
        notebook = Notebook(self)
        notebook.grid(row=0, column=0, sticky=NSEW, padx=10, pady=10)
        
        # Tab 1: 项目配置
        tab1 = Frame(notebook, padding=10)
        notebook.add(tab1, text="项目配置")
        self.build_project_tab(tab1)
        
        # Tab 2: 打包选项
        tab2 = Frame(notebook, padding=10)
        notebook.add(tab2, text="打包选项")
        self.build_options_tab(tab2)
        
        # Tab 3: 图标 & 签名
        tab3 = Frame(notebook, padding=10)
        notebook.add(tab3, text="图标 & 签名")
        self.build_icon_tab(tab3)
        
        # Tab 4: 高级（附加数据等）
        tab4 = Frame(notebook, padding=10)
        notebook.add(tab4, text="高级")
        self.build_advanced_tab(tab4)
        
        # 日志区域
        log_frame = LabelFrame(self, text="构建日志", padding=5)
        log_frame.grid(row=1, column=0, sticky=NSEW, padx=10, pady=(0, 10))
        
        self.log = Text(log_frame, height=12, wrap=WORD)
        self.log.pack(fill=BOTH, expand=True)
        
        # 底部按钮
        btn_frame = Frame(self)
        btn_frame.grid(row=2, column=0, pady=(0, 10), sticky=EW)
        
        Button(btn_frame, text="开始打包", command=self.start_pack).pack(side=LEFT, padx=10)
        Button(btn_frame, text="打开输出目录", command=self.open_output).pack(side=LEFT)
        Button(btn_frame, text="清除日志", command=lambda: self.log.delete(1.0, END)).pack(side=LEFT, padx=10)
        Button(btn_frame, text="退出", command=self.root.quit).pack(side=RIGHT, padx=10)
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
    def build_project_tab(self, parent):
        # 模式选择
        mode_frame = LabelFrame(parent, text="打包模式", padding=10)
        mode_frame.pack(fill=X, pady=(0, 10))
        
        Radiobutton(mode_frame, text="单文件（一个 .py 文件）", variable=self.mode,
                     value="single", command=self.on_mode_change).pack(anchor=W)
        Radiobutton(mode_frame, text="多文件项目（整个项目目录）", variable=self.mode,
                     value="multi", command=self.on_mode_change).pack(anchor=W)
        
        # 单文件模式：选择 py 文件
        self.single_frame = Frame(parent)
        self.single_frame.pack(fill=X, pady=(0, 10))
        
        Label(self.single_frame, text="Python 文件:").grid(row=0, column=0, sticky=W, pady=5)
        Entry(self.single_frame, textvariable=self.entry_file, width=60).grid(row=0, column=1, padx=5)
        Button(self.single_frame, text="浏览...", command=self.browse_py_file).grid(row=0, column=2)
        
        # 多文件模式：选择项目目录 + 入口文件
        self.multi_frame = Frame(parent)
        
        Label(self.multi_frame, text="项目目录:").grid(row=0, column=0, sticky=W, pady=5)
        Entry(self.multi_frame, textvariable=self.project_dir, width=60).grid(row=0, column=1, padx=5)
        Button(self.multi_frame, text="选择目录...", command=self.browse_project_dir).grid(row=0, column=2)
        
        Label(self.multi_frame, text="入口文件:").grid(row=1, column=0, sticky=W, pady=5)
        self.entry_combo = Combobox(self.multi_frame, textvariable=self.entry_file, width=50)
        self.entry_combo.grid(row=1, column=1, sticky=W, padx=5, pady=5)
        Button(self.multi_frame, text="浏览...", command=self.browse_entry_file).grid(row=1, column=2, pady=5)
        
        # 项目文件预览
        Label(parent, text="项目文件:").pack(anchor=W, pady=(10, 5))
        self.file_tree = Treeview(parent, height=10)
        self.file_tree.pack(fill=BOTH, expand=True, pady=(0, 10))
        
        self.on_mode_change()
        
    def build_options_tab(self, parent):
        # 输出模式
        out_frame = LabelFrame(parent, text="输出格式", padding=10)
        out_frame.pack(fill=X, pady=(0, 10))
        
        Radiobutton(out_frame, text="单文件 exe（-F / --onefile）", variable=self.output_mode,
                     value="onefile").pack(anchor=W)
        Radiobutton(out_frame, text="目录模式（-D / --onedir）", variable=self.output_mode,
                     value="onedir").pack(anchor=W)
        
        # 窗口模式
        win_frame = LabelFrame(parent, text="窗口模式", padding=10)
        win_frame.pack(fill=X, pady=(0, 10))
        
        Radiobutton(win_frame, text="GUI 模式（无控制台窗口，-w）", variable=self.console_mode,
                     value="windowed").pack(anchor=W)
        Radiobutton(win_frame, text="控制台模式（显示控制台，-c）", variable=self.console_mode,
                     value="console").pack(anchor=W)
        
        # 其他选项
        opt_frame = LabelFrame(parent, text="其他选项", padding=10)
        opt_frame.pack(fill=X, pady=(0, 10))
        
        self.opt_clean = BooleanVar(value=True)
        self.opt_noupx = BooleanVar(value=False)
        Checkbutton(opt_frame, text="清理临时文件（--clean）", variable=self.opt_clean).pack(anchor=W)
        Checkbutton(opt_frame, text="禁用 UPX（--noupx）", variable=self.opt_noupx).pack(anchor=W)
        
    def build_icon_tab(self, parent):
        # 图标设置
        icon_frame = LabelFrame(parent, text="图标设置", padding=10)
        icon_frame.pack(fill=X, pady=(0, 10))
        
        Label(icon_frame, text="图标文件 (.ico / .png / .jpg):").grid(row=0, column=0, sticky=W, pady=5)
        Entry(icon_frame, textvariable=self.icon_path, width=50).grid(row=0, column=1, padx=5)
        Button(icon_frame, text="选择...", command=self.browse_icon).grid(row=0, column=2, padx=(5, 0))
        Button(icon_frame, text="清除", command=lambda: self.icon_path.set("")).grid(row=0, column=3, padx=(5, 0))
        
        Label(icon_frame, text="提示: PNG/JPG 会自动转换为 ICO 格式").grid(row=1, column=0, columnspan=4, sticky=W, pady=(5, 0))
        
        # 签名设置
        sign_frame = LabelFrame(parent, text="数字签名（防止 SmartScreen 拦截）", padding=10)
        sign_frame.pack(fill=X, pady=(0, 10))
        
        Checkbutton(sign_frame, text="启用数字签名", variable=self.sign_enabled,
                     command=self.on_sign_toggle).grid(row=0, column=0, columnspan=3, sticky=W, pady=(0, 5))
        
        self.sign_widgets = []
        
        Label(sign_frame, text="证书文件 (.pfx / .p12):").grid(row=1, column=0, sticky=W, pady=2)
        self.cert_entry = Entry(sign_frame, textvariable=self.cert_path, width=40, state=DISABLED)
        self.cert_entry.grid(row=1, column=1, padx=5)
        self.cert_btn = Button(sign_frame, text="选择...", command=self.browse_cert, state=DISABLED)
        self.cert_btn.grid(row=1, column=2, padx=(5, 0))
        self.sign_widgets.extend([self.cert_entry, self.cert_btn])
        
        Label(sign_frame, text="证书密码:").grid(row=2, column=0, sticky=W, pady=2)
        self.pwd_entry = Entry(sign_frame, textvariable=self.cert_password, width=40, show="*", state=DISABLED)
        self.pwd_entry.grid(row=2, column=1, padx=5, sticky=W)
        self.sign_widgets.append(self.pwd_entry)
        
        Label(sign_frame, text="时间戳服务器:").grid(row=3, column=0, sticky=W, pady=2)
        self.ts_entry = Entry(sign_frame, textvariable=self.timestamp_url, width=40, state=DISABLED)
        self.ts_entry.grid(row=3, column=1, padx=5, sticky=W)
        self.sign_widgets.append(self.ts_entry)
        
        # 检测 signtool
        self.signtool_path = find_signtool()
        status_text = f"signtool.exe: {'✅ 已找到' if self.signtool_path else '❌ 未找到（需安装 Windows SDK）'}"
        Label(sign_frame, text=status_text).grid(row=4, column=0, columnspan=3, sticky=W, pady=(5, 0))
        
    def build_advanced_tab(self, parent):
        # 附加数据
        data_frame = LabelFrame(parent, text="附加数据（--add-data）", padding=10)
        data_frame.pack(fill=X, pady=(0, 10))
        
        self.data_listbox = Listbox(data_frame, height=5)
        self.data_listbox.pack(fill=X, pady=(0, 5))
        
        data_btn_frame = Frame(data_frame)
        data_btn_frame.pack(fill=X)
        Button(data_btn_frame, text="添加文件", command=self.add_data_file).pack(side=LEFT, padx=(0, 5))
        Button(data_btn_frame, text="添加目录", command=self.add_data_dir).pack(side=LEFT, padx=5)
        Button(data_btn_frame, text="删除选中", command=self.remove_data).pack(side=LEFT, padx=5)
        
        # 附加二进制
        bin_frame = LabelFrame(parent, text="附加二进制（--add-binary）", padding=10)
        bin_frame.pack(fill=X, pady=(0, 10))
        
        self.binary_listbox = Listbox(bin_frame, height=5)
        self.binary_listbox.pack(fill=X, pady=(0, 5))
        
        bin_btn_frame = Frame(bin_frame)
        bin_btn_frame.pack(fill=X)
        Button(bin_btn_frame, text="添加文件", command=self.add_binary_file).pack(side=LEFT, padx=(0, 5))
        Button(bin_btn_frame, text="删除选中", command=self.remove_binary).pack(side=LEFT, padx=5)
        
        # 隐藏导入
        hid_frame = LabelFrame(parent, text="隐藏导入（--hidden-import）", padding=10)
        hid_frame.pack(fill=X, pady=(0, 10))
        
        self.hid_entry = Entry(hid_frame)
        self.hid_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        Button(hid_frame, text="添加", command=self.add_hidden_import).pack(side=LEFT)
        
        self.hid_listbox = Listbox(parent, height=4)
        self.hid_listbox.pack(fill=X, pady=(0, 5))
        Button(parent, text="删除选中隐藏导入", command=self.remove_hidden_import).pack(anchor=W)
        
    # ─── 事件处理 ─────────────────────────────────────────────────────────────
    
    def on_mode_change(self):
        if self.mode.get() == "single":
            self.single_frame.pack(fill=X, pady=(0, 10))
            self.multi_frame.pack_forget()
        else:
            self.single_frame.pack_forget()
            self.multi_frame.pack(fill=X, pady=(0, 10))
    
    def on_sign_toggle(self):
        state = NORMAL if self.sign_enabled.get() else DISABLED
        for w in self.sign_widgets:
            w.config(state=state)
    
    def browse_py_file(self):
        path = filedialog.askopenfilename(title="选择 Python 文件", filetypes=[("Python", "*.py")])
        if path:
            self.entry_file.set(path)
    
    def browse_project_dir(self):
        path = filedialog.askdirectory(title="选择项目目录")
        if path:
            self.project_dir.set(path)
            self.project_dir_path = Path(path)
            self.refresh_file_tree()

    def browse_entry_file(self):
        """手动选择入口文件"""
        initial_dir = self.project_dir.get() if self.project_dir.get() else None
        path = filedialog.askopenfilename(title="选择入口文件", filetypes=[("Python", "*.py")],
                                          initialdir=initial_dir)
        if path:
            # 如果在项目目录内，显示相对路径；否则显示绝对路径
            if self.project_dir_path and str(self.project_dir_path) in path:
                self.entry_file.set(str(Path(path).relative_to(self.project_dir_path)))
            else:
                self.entry_file.set(path)
    
    def refresh_file_tree(self):
        self.file_tree.delete(*self.file_tree.get_children())
        if not self.project_dir_path or not self.project_dir_path.exists():
            return
        
        py_files = scan_py_files(self.project_dir_path)
        candidates = find_entry_candidates(py_files)
        
        # 更新入口文件下拉
        candidate_strs = [str(f.relative_to(self.project_dir_path)) for f in candidates]
        all_py_strs = [str(f.relative_to(self.project_dir_path)) for f in py_files]
        
        self.entry_combo["values"] = candidate_strs if candidate_strs else all_py_strs
        if candidate_strs:
            self.entry_combo.set(candidate_strs[0])
        
        # 填充树形视图
        def add_items(parent_id, directory):
            for item in sorted(directory.iterdir()):
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                item_id = self.file_tree.insert(parent_id, END, text=item.name,
                                                values=(str(item), "📁" if item.is_dir() else "📄"))
                if item.is_dir():
                    add_items(item_id, item)
        
        add_items("", self.project_dir_path)
        self.file_tree.heading("#0", text=f"项目: {self.project_dir_path.name}")
    
    def browse_icon(self):
        path = filedialog.askopenfilename(title="选择图标文件",
            filetypes=[("ICO", "*.ico"), ("PNG", "*.png"), ("JPG", "*.jpg;*.jpeg"), ("All", "*.*")])
        if path:
            self.icon_path.set(path)
    
    def browse_cert(self):
        path = filedialog.askopenfilename(title="选择证书文件",
            filetypes=[("PFX", "*.pfx"), ("P12", "*.p12"), ("All", "*.*")])
        if path:
            self.cert_path.set(path)
    
    def add_data_file(self):
        path = filedialog.askopenfilename(title="选择要附加的文件")
        if path:
            dst = filedialog.asksaveasfilename(title="目标路径（相对于 exe 目录）", defaultextension="")
            if dst:
                rel_dst = Path(dst).name
                self.extra_data.append((path, rel_dst))
                self.data_listbox.insert(END, f"{Path(path).name} → {rel_dst}")
    
    def add_data_dir(self):
        path = filedialog.askdirectory(title="选择要附加的目录")
        if path:
            self.extra_data.append((path, Path(path).name))
            self.data_listbox.insert(END, f"{path} → {Path(path).name}")
    
    def remove_data(self):
        sel = self.data_listbox.curselection()
        if sel:
            idx = sel[0]
            self.data_listbox.delete(idx)
            self.extra_data.pop(idx)
    
    def add_binary_file(self):
        path = filedialog.askopenfilename(title="选择二进制文件")
        if path:
            self.extra_binary.append((path, Path(path).name))
            self.binary_listbox.insert(END, f"{Path(path).name}")
    
    def remove_binary(self):
        sel = self.binary_listbox.curselection()
        if sel:
            idx = sel[0]
            self.binary_listbox.delete(idx)
            self.extra_binary.pop(idx)
    
    def add_hidden_import(self):
        val = self.hid_entry.get().strip()
        if val:
            self.hidden_imports.append(val)
            self.hid_listbox.insert(END, val)
            self.hid_entry.delete(0, END)
    
    def remove_hidden_import(self):
        sel = self.hid_listbox.curselection()
        if sel:
            idx = sel[0]
            self.hid_listbox.delete(idx)
            self.hidden_imports.pop(idx)
    
    # ─── 打包逻辑 ─────────────────────────────────────────────────────────────
    
    def resolve_icon(self):
        """处理图标：如果是 png/jpg 则转换为 ico"""
        icon = self.icon_path.get().strip()
        if not icon or not os.path.exists(icon):
            return None
        
        icon_p = Path(icon)
        if icon_p.suffix.lower() == ".ico":
            return str(icon_p)
        
        # 转换为 ico
        ico_path = icon_p.with_suffix(".ico")
        try:
            png_to_ico(icon_p, ico_path)
            self.log_write(f"图标已转换: {ico_path}")
            return str(ico_path)
        except Exception as e:
            self.log_write(f"⚠ 图标转换失败: {e}，跳过图标")
            return None
    
    def build_cmd(self, script_path: Path, output_name: str):
        """构建 pyinstaller 命令"""
        cmd = [sys.executable, "-m", "PyInstaller"]
        
        # 输出模式
        if self.output_mode.get() == "onefile":
            cmd.append("-F")
        else:
            cmd.append("-D")
        
        # 窗口模式
        if self.console_mode.get() == "windowed":
            cmd.append("-w")
        else:
            cmd.append("-c")
        
        # 清理
        if self.opt_clean.get():
            cmd.append("--clean")
        
        # 禁用 UPX
        if self.opt_noupx.get():
            cmd.append("--noupx")
        
        # 输出名称
        cmd.extend(["--name", output_name])
        
        # 输出目录
        cmd.extend(["--distpath", str(self.pack_dir)])
        cmd.extend(["--workpath", str(self.pack_dir / "build")])
        cmd.extend(["--specpath", str(self.pack_dir / "spec")])
        
        # 图标
        icon = self.resolve_icon()
        if icon:
            cmd.extend(["--icon", icon])
        
        # 附加数据
        for src, dst in self.extra_data:
            cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        
        # 附加二进制
        for src, dst in self.extra_binary:
            cmd.extend(["--add-binary", f"{src}{os.pathsep}{dst}"])
        
        # 隐藏导入
        for imp in self.hidden_imports:
            cmd.extend(["--hidden-import", imp])
        
        # 如果是多文件模式，添加整个项目目录的数据
        if self.mode.get() == "multi" and self.project_dir_path:
            for item in self.project_dir_path.iterdir():
                if item.is_dir() and item.name not in ("__pycache__", ".git", "venv", "env", "dist", "build"):
                    rel = item.name
                    cmd.extend(["--add-data", f"{item}{os.pathsep}{rel}"])
        
        # 脚本路径
        cmd.append(str(script_path))
        
        return cmd
    
    def get_exe_path(self, output_name: str):
        """获取打包后的 exe 路径"""
        if self.output_mode.get() == "onefile":
            return self.pack_dir / f"{output_name}.exe"
        else:
            return self.pack_dir / output_name / f"{output_name}.exe"
    
    def sign_exe(self, exe_path: Path):
        """对 exe 进行数字签名"""
        if not self.sign_enabled.get():
            return True
        
        if not self.signtool_path:
            self.log_write("❌ signtool.exe 未找到，跳过签名")
            return False
        
        cert = self.cert_path.get().strip()
        if not cert or not os.path.exists(cert):
            self.log_write("❌ 证书文件不存在，跳过签名")
            return False
        
        cmd = [self.signtool_path, "sign"]
        cmd.extend(["/f", cert])
        
        pwd = self.cert_password.get().strip()
        if pwd:
            cmd.extend(["/p", pwd])
        
        ts = self.timestamp_url.get().strip()
        if ts:
            cmd.extend(["/tr", ts])
            cmd.extend(["/td", "SHA256"])
        
        cmd.extend(["/fd", "SHA256"])
        cmd.append(str(exe_path))
        
        self.log_write(f"签名命令: {' '.join(str(c) for c in cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            self.log_write("✅ 签名成功")
            return True
        else:
            self.log_write(f"❌ 签名失败: {result.stderr}")
            return False
    
    def start_pack(self):
        """开始打包"""
        # 验证输入
        if not self.entry_file.get().strip():
            messagebox.showerror("错误", "请选择入口文件")
            return
        
        entry = Path(self.entry_file.get())
        if not entry.exists():
            messagebox.showerror("错误", f"文件不存在: {entry}")
            return
        
        if self.sign_enabled.get():
            if not self.cert_path.get().strip():
                messagebox.showerror("错误", "已启用签名，但未选择证书文件")
                return
        
        self.log_write("=" * 60)
        self.log_write(f"开始打包: {entry.name}")
        self.log_write("=" * 60)
        
        threading.Thread(target=self.pack_thread, args=(entry,), daemon=True).start()
    
    def pack_thread(self, entry: Path):
        """打包线程"""
        output_name = entry.stem
        
        # 构建命令
        cmd = self.build_cmd(entry, output_name)
        self.log_write(f"命令: {' '.join(str(c) for c in cmd)}")
        self.log_write("")
        
        # 执行打包
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace")
            
            for line in process.stdout:
                self.log_write(line.rstrip())
            
            process.wait()
            
            if process.returncode != 0:
                self.log_write(f"❌ 打包失败 (returncode={process.returncode})")
                return
            
        except Exception as e:
            self.log_write(f"❌ 打包异常: {e}")
            return
        
        # 检查输出
        exe_path = self.get_exe_path(output_name)
        if not exe_path.exists():
            # 尝试在 dist_pro 的子目录中查找
            if self.output_mode.get() == "onedir":
                possible = list(self.pack_dir.glob(f"**/{output_name}.exe"))
                if possible:
                    exe_path = possible[0]
        
        if not exe_path or not exe_path.exists():
            self.log_write(f"❌ 未找到输出的 exe 文件")
            self.log_write(f"   期望路径: {self.get_exe_path(output_name)}")
            return
        
        self.log_write(f"✅ 打包成功: {exe_path}")
        
        # 数字签名
        if self.sign_enabled.get():
            self.log_write("")
            self.log_write("开始数字签名...")
            self.sign_exe(exe_path)
        
        self.log_write("")
        self.log_write("=" * 60)
        self.log_write("🎉 全部完成！")
        self.log_write("=" * 60)
        
        # 打开输出目录
        try:
            os.startfile(exe_path.parent)
        except Exception:
            pass
    
    def log_write(self, msg):
        """线程安全的日志写入"""
        def _write():
            self.log.insert(END, msg + "\n")
            self.log.see(END)
        self.root.after(0, _write)
    
    def open_output(self):
        """打开输出目录"""
        if self.pack_dir.exists():
            os.startfile(self.pack_dir)
        else:
            messagebox.showinfo("提示", "输出目录不存在")


# ─── 入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = Tk()
    # 设置图标（如果存在）
    icon_path = Path(__file__).resolve().parent / "1.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass
    
    app = PackerProGUI(root)
    app.pack(fill=BOTH, expand=True)
    root.mainloop()
