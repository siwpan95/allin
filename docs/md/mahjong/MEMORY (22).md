# 项目长期记忆 - mahjong (麻将连连看)

## 项目位置
`D:\allin\right\mahjong`

## 架构
- 2026-07-12 由旧版单文件 `chess.py` (634 行 God Class) 重构为 MVVM 四层
- 入口：`main.py`
- 分层：`models/` (数据) · `services/` (算法) · `viewmodel/` (状态机) · `views/` (渲染)
- 旧版 `chess.py` 保留作对比，不再维护

## 运行
- `python main.py` (需 Pillow + tkinter)
- 本地 Python：`C:/Users/13122/AppData/Local/Programs/Python/Python314/python.exe` (有 tkinter + PIL，能跑 GUI)

## 核心规则
- 标准 144 张牌，乌龟布局 86+40+14+4 交叉堆叠
- 自由牌 = 上方无压 + 左右至少一侧露边
- 季/花组内任意互配

## 设计约束
- ViewModel 不依赖 tkinter (纯逻辑+回调)，可独立单测
- 渲染按 `tile.short` 缓存 ImageTk.PhotoImage (42 种唯一牌面)
- 布局支撑合法性由冒烟测试保证 (每张上层牌下方 4 张下层牌必须存在)
