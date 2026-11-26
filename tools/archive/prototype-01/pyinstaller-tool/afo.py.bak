#!/usr/bin/env python3
"""
pack_gui.py — Tkinter GUI for PyInstaller Batch Builder
"""

import os
import sys
import subprocess
import threading
from pathlib import Path
from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog  # 新增导入

class PackerGUI(Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.root.title("PyInstaller 打包工具")
        self.root.geometry("720x520")

        self.project = Path(__file__).resolve().parent
        self.dist = self.project / "dist"
        self.logs = self.project / "logs"
        self.dist.mkdir(exist_ok=True)
        self.logs.mkdir(exist_ok=True)

        self.scripts = {}
        self.modes = {}

        self.build_ui()
        self.load_scripts()

    # ----------------- UI -----------------
    def build_ui(self):
        # 顶部按钮区域
        top_frame = Frame(self)
        top_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky=W+E)
        
        Label(top_frame, text="选择要打包的脚本").pack(side=LEFT, padx=(0, 10))
        Button(top_frame, text="选择py文件", command=self.select_py_file).pack(side=LEFT)
        Button(top_frame, text="刷新列表", command=self.refresh_scripts).pack(side=LEFT, padx=(10, 0))

        self.list_frame = Frame(self)
        self.list_frame.grid(row=1, column=0, columnspan=2, padx=10, sticky=NSEW)

        self.log = Text(self, height=12)
        self.log.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky=NSEW)

        self.btn = Button(self, text="开始打包", command=self.start_pack)
        self.btn.grid(row=3, column=0, pady=(0, 10))

        Button(self, text="打开 dist", command=lambda: os.startfile(self.dist)) \
            .grid(row=3, column=1, pady=(0, 10))

        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def select_py_file(self):
        """选择py文件"""
        file_path = filedialog.askopenfilename(
            title="选择Python文件",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if file_path:
            script_path = Path(file_path)
            if script_path not in self.scripts:
                self.add_script_to_list(script_path)
                self.log_write(f"已添加: {script_path.name}")
            else:
                self.log_write(f"已存在: {script_path.name}")

    def refresh_scripts(self):
        """刷新脚本列表"""
        # 清空现有列表
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.scripts.clear()
        self.modes.clear()
        
        # 重新加载项目目录下的脚本
        self.load_scripts()
        self.log_write("已刷新脚本列表")

    def add_script_to_list(self, py_path):
        """将单个脚本添加到列表"""
        var = BooleanVar(value=True)
        mode = BooleanVar(value=False)  # False = Console, True = GUI

        f = Frame(self.list_frame)
        f.pack(fill=X, pady=2)

        Checkbutton(f, variable=var, width=2).pack(side=LEFT)
        Label(f, text=py_path.name, width=30, anchor=W).pack(side=LEFT)
        
        # 显示完整路径（如果是外部文件）
        if py_path.parent != self.project:
            Label(f, text=f"({py_path.parent})", anchor=W).pack(side=LEFT, padx=(5, 0))
            
        Checkbutton(f, text="GUI", variable=mode).pack(side=RIGHT)

        self.scripts[py_path] = var
        self.modes[py_path] = mode

    def load_scripts(self):
        for py in self.project.glob("*.py"):
            if py.name == "pack_gui.py":
                continue
            self.add_script_to_list(py)

    # ----------------- Logic -----------------
    def log_write(self, msg):
        self.log.insert(END, msg + "\n")
        self.log.see(END)

    def start_pack(self):
        self.btn.config(state=DISABLED)
        self.log.delete(1.0, END)
        threading.Thread(target=self.pack_all, daemon=True).start()

    def pack_all(self):
        for script, checked in self.scripts.items():
            if not checked.get():
                continue
            self.pack_one(script)

        self.log_write("\n✅ 全部完成")
        self.btn.config(state=NORMAL)

    def pack_one(self, script: Path):
        self.log_write(f"\n📦 {script.name}")

        mode_flag = ["--windowed"] if self.modes[script].get() else []
        icon = ["--icon", str(script.with_suffix(".ico"))] \
               if script.with_suffix(".ico").exists() else []

        # 修改：检查脚本所在目录的assets文件夹
        asset_dir = script.parent / "assets" / script.stem
        assets = ["--add-data", f"{asset_dir};assets/{script.stem}"] \
                 if asset_dir.exists() else []

        log_file = self.logs / f"{script.stem}.log"

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "-F", "--clean",
            "--name", script.stem,
            *mode_flag,
            *icon,
            *assets,
            str(script)
        ]

        with open(log_file, "w", encoding="utf-8") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT
            )

        proc.wait()

        exe = self.project / "dist" / f"{script.stem}.exe"
        if exe.exists():
            exe.replace(self.dist / exe.name)
            self.log_write("✅ 成功")
        else:
            self.log_write(f"❌ 失败，查看日志: {log_file}")

        # 清理临时目录
        import shutil
        shutil.rmtree(self.project / "build", ignore_errors=True)
        shutil.rmtree(self.project / script.stem, ignore_errors=True)


if __name__ == "__main__":
    root = Tk()
    app = PackerGUI(root)
    app.pack(fill=BOTH, expand=True)
    root.mainloop()