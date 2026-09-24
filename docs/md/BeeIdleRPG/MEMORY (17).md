# BeeIdleRPG 项目记忆

## 项目概况
- 路径: D:/allin/bee
- 类型: Python Tkinter 文字挂机RPG (Progress Quest风格)
- 入口: main.py (唯一入口，已删除 src/main.py)

## 架构决策 (2026-06-04)
- Controller层采用 **Mixin模式** 拆分: GameRenderer + SystemTrayMixin + GameIOMixin
- 音频系统采用 **三文件分层**: audio_engine(合成) → audio_presets(预设) → audio_service(播放)
- scipy兼容性: 新版本需 `from scipy.io import wavfile` 而非 `from scipy import wavfile`
- PyInstaller spec 入口为根目录 main.py
