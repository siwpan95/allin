# 长期记忆

## 项目概况
- 用户是独立开发者，一人团队，自学为主
- 项目仓库：D:/allin — Python 桌面应用/游戏集合
- 技术栈：Python + Tkinter + pygame-ce + PyInstaller
- 代表作：carimara_py（ECS架构，8.5/10）
- 编码风格：中文变量/注释，功能驱动，快速实现创意

## 架构原则
- 不同项目用不同架构（ECS / MVC / MVVM），不强求统一
- 内容型代码（音频素材等）不共享，基础设施型代码（字体加载等）可共享
- 用户偏好独立项目结构，不强求集中化

## 共享模块
- `D:/allin/shared/font_utils.py` — 跨平台 CJK/等宽字体加载工具
