"""repocheck —— Tkinter GUI 入口与命令行分发。

功能
----
* 选择根目录（默认当前工作目录，不再硬编码任何盘符）
* 递归识别「项目」并逐项体检，显示健康分、严重度计数与问题标签
* 导出 CSV / HTML 报告（复用 ``report.py``，与 CLI 输出完全同源）

设计约束
--------
* 仅在本文件 ``build_gui()`` 内实例化 ``Tk()``；无显示器环境下
  ``import main`` 不会创建 GUI，方便只测纯逻辑。
* **tkinter 是 GUI 的可选依赖**：模块级导入用 try/except 包住，
  没有 tkinter 的精简解释器（常见的 WorkBuddy 便携版）也能跑命令行模式
  —— 只有图形界面会响亮报环境错（退出码 3）。
* 纯标准库（tkinter / os / pathlib），不 import 其他工具目录
  （复制优于共享）。
"""

from __future__ import annotations

import os
import sys

try:  # tkinter 只服务 GUI —— CLI 模式必须在没有 tkinter 的精简解释器上也能跑
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError:  # 没有 tkinter 的解释器：命令行可用，图形界面不可用
    tk = filedialog = messagebox = ttk = None

import report
import scanner

#: 分数分档配色（与 HTML 报告保持一致）。
_SCORE_TAGS = (
    (8.0, "good", "#137333"),
    (6.0, "fair", "#e37400"),
    (0.0, "poor", "#d93025"),
)


def _score_tag(score: float) -> str:
    for threshold, tag, _color in _SCORE_TAGS:
        if score >= threshold:
            return tag
    return "poor"


# ---------------------------------------------------------------------------
# GUI 构建
# ---------------------------------------------------------------------------

def build_gui(initial_root: str | None = None) -> None:
    """构建并启动 repocheck 的图形界面。"""
    if tk is None:
        print("ENV ERROR: 当前解释器没有 tkinter，图形界面不可用；请用命令行模式"
              "（repocheck/main.py <根目录> [--format json]）。", file=sys.stderr)
        raise SystemExit(3)
    root = tk.Tk()
    root.title(f"repocheck · 仓库体检 v{scanner.__version__}")
    root.geometry("1040x600")

    state: dict = {"results": []}

    # ---- 顶部控制栏 ----
    frm_top = ttk.Frame(root, padding=8)
    frm_top.pack(fill="x")

    ttk.Label(frm_top, text="根目录：").pack(side="left")
    var_root = tk.StringVar(value=initial_root or os.getcwd())
    ent_root = ttk.Entry(frm_top, textvariable=var_root, width=46)
    ent_root.pack(side="left", fill="x", expand=True, padx=4)
    ttk.Button(frm_top, text="选择…", command=lambda: _choose_dir(var_root)).pack(side="left")
    ttk.Button(
        frm_top, text="开始体检",
        command=lambda: _run_scan(var_root.get(), tree, state, status, root),
    ).pack(side="left", padx=(4, 0))
    ttk.Button(frm_top, text="导出 CSV",
               command=lambda: _export_csv(state["results"])).pack(side="left", padx=(4, 0))
    ttk.Button(frm_top, text="导出 HTML",
               command=lambda: _export_html(state["results"], var_root.get())).pack(side="left")

    # ---- 结果树 ----
    columns = ("path", "score", "counts", "issues")
    tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
    tree.heading("path", text="项目路径")
    tree.heading("score", text="健康分")
    tree.heading("counts", text="E/W/I")
    tree.heading("issues", text="问题标签")
    tree.column("path", width=330, anchor="w")
    tree.column("score", width=70, anchor="center")
    tree.column("counts", width=80, anchor="center")
    tree.column("issues", width=520, anchor="w")
    for _threshold, tag, color in _SCORE_TAGS:
        tree.tag_configure(tag, foreground=color)
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
    chosen = filedialog.askdirectory(initialdir=var.get() or os.getcwd())
    if chosen:
        var.set(chosen)


def _run_scan(root_dir: str, tree: ttk.Treeview, state: dict,
              status: ttk.Label, win: tk.Tk) -> None:
    """执行扫描并刷新结果树（带进度反馈）。"""
    if not root_dir or not os.path.isdir(root_dir):
        messagebox.showerror("错误", f"根目录无效：{root_dir}")
        return

    root_dir = os.path.normpath(root_dir)
    status.config(text="扫描中…")
    win.update_idletasks()

    def on_progress(done: int, total: int, current: str) -> None:
        status.config(
            text=f"扫描中… {done}/{total}　{os.path.basename(current)}")
        win.update_idletasks()

    try:
        results = scanner.scan(root_dir, progress=on_progress)
    except Exception as exc:  # noqa: BLE001 - 兜底，避免 GUI 崩溃
        messagebox.showerror("错误", f"扫描失败：{exc}")
        status.config(text="扫描失败。")
        return

    tree.delete(*tree.get_children())
    for result in results:
        counts = result.get("severity_counts") or {}
        score = float(result.get("score", 0.0))
        labels = "；".join(result["issues"]) if result["issues"] else "✓ 无 error/warn 级问题"
        tree.insert("", "end", values=(
            result["path"],
            f"{score:.1f}",
            f"{counts.get('error', 0)}/{counts.get('warn', 0)}/{counts.get('info', 0)}",
            labels,
        ), tags=(_score_tag(score),))

    state["results"] = results
    summary = report.summarize(results)
    state["summary"] = summary
    state["root"] = root_dir

    skipped_note = f"，跳过 {summary['skipped_count']} 项" if summary["skipped_count"] else ""
    status.config(
        text=(f"完成：{summary['projects']} 个项目，平均 {summary['score_mean']} 分、"
              f"最低 {summary['score_min']} 分；error {summary['errors']} / "
              f"warn {summary['warns']} / info {summary['infos']}{skipped_note}。"))


def _export_csv(results: list[dict]) -> None:
    """导出 CSV（UTF-8 BOM，Excel 直接打开不乱码）。"""
    if not results:
        messagebox.showinfo("提示", "还没有体检结果，请先扫描。")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".csv", filetypes=[("CSV 文件", "*.csv"), ("全部", "*.*")])
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            handle.write(report.render_csv(results))
        messagebox.showinfo("完成", f"已导出 CSV：\n{path}")
    except OSError as exc:
        messagebox.showerror("错误", f"导出 CSV 失败：{exc}")


def _export_html(results: list[dict], root_dir: str) -> None:
    """导出单页 HTML 报告。"""
    if not results:
        messagebox.showinfo("提示", "还没有体检结果，请先扫描。")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".html", filetypes=[("HTML 文件", "*.html"), ("全部", "*.*")])
    if not path:
        return
    html = report.render_html(results, root=root_dir, version=scanner.__version__)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(html)
        messagebox.showinfo("完成", f"已导出 HTML：\n{path}")
    except OSError as exc:
        messagebox.showerror("错误", f"导出 HTML 失败：{exc}")


# ---------------------------------------------------------------------------
# 入口分发
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """有位置参数或 ``--dump-profile`` 走命令行，否则启动 GUI。"""
    import cli

    args = cli.parse(argv)
    if args.dump_profile or args.root is not None:
        return cli.run(args)
    build_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
