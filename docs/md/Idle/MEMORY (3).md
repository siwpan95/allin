# 探险日志 (Auto Exploration Idle RPG)

## 项目路径
D:/allin/right/log/

## 技术栈
- Python 3.13 + tkinter + Pillow + pystray + openpyxl
- PyInstaller 打包为单文件 exe（25MB）
- 三层架构：core/ → data/ → gui/

## 宣传视频
- 脚本：`promo_video_gen_v6.py`（唯一保留的版本）
- 输出：`探险日志_宣传视频.mp4`（24秒，720帧，5场景+过渡+定格）
- 帧素材：`promo_frames/`（原始帧 + `*_final.png` 场景缩略图）

## 重要约定
- 旧版本脚本已清理，视频制作只用 v6
- build/ 和 __pycache__/ 不需要保留
- dist/ 目录保留发布产物（exe + 配置 + 存档）
