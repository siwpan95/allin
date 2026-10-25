"""repocheck —— Tkinter GUI 入口（中文界面）。

功能：
    * 选择根目录（默认 G:\\）
    * 递归识别“项目”并逐项体检
    * 用 ttk.Treeview 展示「项目路径 + 问题数 + 问题标签」
    * 导出 CSV / HTML 报告

设计约束：
    * 仅在本文件 ``if __name__ == "__main__":`` 内实例化 Tk()，
      无显示器环境下 import 本模块不会创建 GUI，方便只测纯逻辑。
    * 纯标准库（tkinter / os / csv / pathlib），不 import 其他工具目录，
      不依赖中心化共享核（复制优于共享）。

运行：
    python main.py            # 启动 GUI
    python main.py G:\\       # 命令行模式（走 scanner 的 console 入口）
"""

from __future__ import annotations

import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from scanner import DEFAULT_EXCLUDE, check_project, discover_projects


# ---------------------------------------------------------------------------
# GUI 构建
# ---------------------------------------------------------------------------

def build_gui() -> None:
    """构建并启动 repocheck 的图形界面。"""
    root = tk.Tk()
    root.title("repocheck · 仓库体检")
    root.geometry("960x580")

    state: dict = {"results": []}

    # ---- 顶部控制栏 ----
    frm_top = ttk.Frame(root, padding=8)
    frm_top.pack(fill="x")

    ttk.Label(frm_top, text="根目录：").pack(side="left")
    var_root = tk.StringVar(value="G:\\")
    ent_root = ttk.Entry(frm_top, textvariable=var_root, width=48)
    ent_root.pack(side="left", fill="x", expand=True, padx=4)
    ttk.Button(frm_top, text="选择…", command=lambda: _choose_dir(var_root)).pack(side="left")
    ttk.Button(
        frm_top, text="开始体检",
        command=lambda: _run_scan(var_root.get(), tree, state, status),
    ).pack(side="left", padx=(4, 0))
    ttk.Button(frm_top, text="导出 CSV", command=lambda: _export_csv(state["results"])).pack(side="left", padx=(4, 0))
    ttk.Button(frm_top, text="导出 HTML", command=lambda: _export_html(state["results"])).pack(side="left")

    # ---- 结果树 ----
    cols = ("path", "count", "issues")
    tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="browse")
    tree.heading("path", text="项目路径")
    tree.heading("count", text="问题数")
    tree.heading("issues", text="问题标签")
    tree.column("path", width=340, anchor="w")
    tree.column("count", width=60, anchor="center")
    tree.column("issues", width=520, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    vsb = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")

    # ---- 状态栏 ----
    status = ttk.Label(
        root, text="就绪。选择根目录后点击「开始体检」。", relief="sunken", anchor="w"
    )
    status.pack(fill="x", side="bottom")

    root.mainloop()


# ---------------------------------------------------------------------------
# 事件处理
# ---------------------------------------------------------------------------

def _choose_dir(var: tk.StringVar) -> None:
    """打开目录选择对话框并更新变量。"""
    chosen = filedialog.askdirectory(initialdir=var.get() or "G:\\")
    if chosen:
        var.set(chosen)


def _run_scan(root_dir: str, tree: ttk.Treeview, state: dict, status: ttk.Label) -> None:
    """执行扫描并刷新结果树。"""
    if not root_dir or not os.path.isdir(root_dir):
        messagebox.showerror("错误", f"根目录无效：{root_dir}")
        return

    status.config(text="扫描中…")
    root_dir = os.path.normpath(root_dir)
    try:
        projects = discover_projects(root_dir)
    except Exception as exc:  # noqa: BLE001 - 兜底，避免 GUI 崩溃
        messagebox.showerror("错误", f"发现项目失败：{exc}")
        status.config(text="扫描失败。")
        return

    tree.delete(*tree.get_children())
    results: list[dict] = []
    for proj in projects:
        try:
            report = check_project(proj)
        except Exception as exc:  # noqa: BLE001 - 单个项目出错不应中断整体
            report = {
                "name": os.path.basename(proj),
                "path": proj,
                "issues": [f"检查出错：{exc}"],
                "metrics": {},
            }
        results.append(report)
        issues_text = "；".join(report["issues"]) if report["issues"] else "✓ 无明显问题"
        tree.insert("", "end", values=(report["path"], len(report["issues"]), issues_text))

    state["results"] = results
    total_issues = sum(len(r["issues"]) for r in results)
    status.config(text=f"完成：发现 {len(projects)} 个项目，共 {total_issues} 个问题。")


def _export_csv(results: list[dict]) -> None:
    """将结果导出为 CSV（UTF-8 with BOM，Excel 友好）。"""
    if not results:
        messagebox.showinfo("提示", "还没有体检结果，请先扫描。")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".csv", filetypes=[("CSV 文件", "*.csv"), ("全部", "*.*")]
    )
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["项目路径", "问题数", "问题标签"])
            for r in results:
                writer.writerow([r["path"], len(r["issues"]), "；".join(r["issues"])])
        messagebox.showinfo("完成", f"已导出 CSV：\n{path}")
    except OSError as exc:
        messagebox.showerror("错误", f"导出 CSV 失败：{exc}")


def _export_html(results: list[dict]) -> None:
    """将结果导出为简单 HTML 表格报告。"""
    if not results:
        messagebox.showinfo("提示", "还没有体检结果，请先扫描。")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".html", filetypes=[("HTML 文件", "*.html"), ("全部", "*.*")]
    )
    if not path:
        return
    rows: list[str] = []
    for r in results:
        issues = "；".join(r["issues"]) if r["issues"] else "✓ 无明显问题"
        rows.append(
            f"<tr><td>{_esc(r['path'])}</td><td>{len(r['issues'])}</td>"
            f"<td>{_esc(issues)}</td></tr>"
        )
    html = (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<title>repocheck 仓库体检报告</title>"
        "<style>body{font-family:sans-serif}table{border-collapse:collapse;"
        "width:100%}td,th{border:1px solid #ccc;padding:6px 10px;text-align:left}"
        "th{background:#f0f0f0}</style></head><body>"
        "<h1>repocheck 仓库体检报告</h1>"
        f"<p>项目数：{len(results)}</p>"
        "<table><tr><th>项目路径</th><th>问题数</th><th>问题标签</th></tr>"
        f"{''.join(rows)}</table></body></html>"
    )
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        messagebox.showinfo("完成", f"已导出 HTML：\n{path}")
    except OSError as exc:
        messagebox.showerror("错误", f"导出 HTML 失败：{exc}")


def _esc(text: str) -> str:
    """对 HTML 特殊字符做转义，避免报告注入/错位。"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# 入口守卫：仅在直接运行时构建 GUI（无显示器环境 import 本模块不会实例化 Tk）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # 装配自省（agent 审计入口）：python main.py --dump-profile [--json]
    if "--dump-profile" in sys.argv:
        from scanner import dump_profile
        import json as _json
        profile = dump_profile()
        if "--json" in sys.argv:
            print(_json.dumps(profile, ensure_ascii=False, indent=2))
        else:
            print("repocheck 装配自省（规则即数据）")
            for _r in profile["rules"]:
                print(f"  [{_r['id']}] {_r['label']} —— {_r['criteria']}")
            print(f"  排除目录: {', '.join(profile['exclude_dirs'])}")
            print(f"  项目标记: {', '.join(profile['project_markers'])}")
    elif len(sys.argv) > 1:
        # 若带位置参数（如 python main.py G:\），走命令行模式，不启动 GUI
        from scanner import _console_scan

        _console_scan(sys.argv[1])
    else:
        build_gui()
