# -*- coding: utf-8 -*-
"""
蜂蜜挂机 RPG - 项目入口

基于 MVC 架构，逻辑与数据解耦。
运行方式：
  python main.py          # 开发模式
  python build_exe.py     # 打包为 exe

依赖：Python 3.8+, tkinter（内置）, 可选 pystray/Pillow/openpyxl
"""
import sys
import os

# ============================================================
#  路径初始化（必须在 import src.* 之前）
# ============================================================
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的环境
    sys.path.insert(0, sys._MEIPASS)
else:
    # 开发环境：将项目根目录加入 sys.path
    _PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    """游戏入口"""
    import tkinter as tk
    from src.app.controllers.game_controller import GameController

    # 捕获未处理异常，避免窗口闪退时无日志
    def _handle_exception(exc_type, exc_value, exc_tb):
        import traceback
        with open("crash.log", "w", encoding="utf-8") as f:
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle_exception

    root = tk.Tk()
    # 设置窗口图标（打包后从 exe 自身读取）
    try:
        if getattr(sys, 'frozen', False):
            root.iconbitmap(sys.executable)
        else:
            icon_path = os.path.join(_PROJECT_ROOT, "BeeIdleRPG.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
    except Exception:
        pass  # 图标加载失败不影响运行
    # 禁止调整窗口大小（Canvas 自适应）
    root.resizable(False, False)
    controller = GameController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
