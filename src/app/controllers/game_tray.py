# -*- coding: utf-8 -*-
"""
游戏系统托盘模块 - 最小化到托盘 / 恢复 / 退出

以 Mixin 方式注入 GameController。
"""

import os
import sys
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False


class SystemTrayMixin:
    """系统托盘 Mixin — 提供 _create_tray_image / _minimize_to_tray / _restore_from_tray / _exit_from_tray"""

    def _get_ico_path(self):
        """获取项目图标的绝对路径（开发环境或打包后均适用）"""
        if getattr(sys, 'frozen', False):
            # exe 同目录
            base = os.path.dirname(sys.executable)
        else:
            # 项目根目录（从 game_controller.py 向上两级）
            base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "..")
        return os.path.normpath(os.path.join(base, "BeeIdleRPG.ico"))

    def _create_tray_image(self):
        """加载或绘制托盘图标，优先使用 .ico 文件"""
        ico_path = self._get_ico_path()
        if _TRAY_AVAILABLE and os.path.exists(ico_path):
            try:
                img = Image.open(ico_path)
                return img.resize((64, 64), Image.LANCZOS)
            except Exception:
                pass
        # 回退：程序化绘制蜜蜂图标
        img = Image.new("RGB", (64, 64), "#0d1117")
        draw = ImageDraw.Draw(img)
        # 蜜蜂身体
        draw.ellipse([16, 20, 48, 52], fill="#facc15", outline="#e6cc80", width=2)
        # 条纹
        draw.rectangle([26, 26, 38, 34], fill="#0d1117")
        draw.rectangle([26, 38, 38, 46], fill="#0d1117")
        # 触角
        draw.arc([22, 4, 34, 18], start=200, end=340, fill="#e6cc80", width=2)
        draw.arc([30, 4, 42, 18], start=200, end=340, fill="#e6cc80", width=2)
        return img

    def _minimize_to_tray(self):
        """最小化到系统托盘"""
        if self._tray_running:
            return
        self.root.withdraw()
        menu = pystray.Menu(
            pystray.MenuItem("\u663e\u793a\u7a97\u53e3", self._restore_from_tray, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("\u9000\u51fa\u6e38\u620f", self._exit_from_tray),
        )
        self.tray_icon = pystray.Icon(
            "\u8702\u871c\u6302\u673a", self._create_tray_image(), "\u8702\u871c\u6302\u673a RPG", menu
        )
        self._tray_running = True
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        # 短暂延迟确保图标创建完成
        self.root.after(100, lambda: None)

    def _restore_from_tray(self, icon=None, item=None):
        """从托盘恢复窗口"""
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
            self._tray_running = False

    def _exit_from_tray(self, icon=None, item=None):
        """从托盘退出游戏"""
        self._tray_running = False
        self.running = False
        self.audio.stop_all()
        self.save_game()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.destroy)

    @property
    def tray_available(self) -> bool:
        """系统托盘功能是否可用"""
        return _TRAY_AVAILABLE
