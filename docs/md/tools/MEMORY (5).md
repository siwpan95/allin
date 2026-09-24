# D:\allin\tools — 工具库项目记忆

## 项目概况
- 13 个独立工具项目（从原 17 个精简而来，全部英文命名）
- 全部配备 README.md + requirements.txt
- 以 Python + tkinter GUI 为主
- 音视频类最多（bloodmusic, wave, sfx, att, loop[已归档]）

## 核心项目
| 项目 | 定位 | 架构质量 |
|------|------|---------|
| bloodmusic | 程序化游戏音频引擎 | ★★★★★ |
| webcopier | 网页抓取 v5.3 | ★★★★☆ |
| yasuo | 加密压缩工具 | ★★★★★ |
| ollama_generator | AI文本生成库 | ★★★★★ |
| art_video_gen | 音视频生成器 | ★★★★☆ |
| py_test_runner | 测试框架 | ★★★★☆ |
| daily_player | 视频播放器 | ★★☆☆☆ |
| wav_music_gen | WAV音乐生成器 | ★★☆☆☆ |
| sfx | 音效下载器 | ★★★☆☆ |
| pyinstaller | 打包工具箱 | ★★★☆☆ |
| requirements | 依赖管理器 | ★★★☆☆ |
| auto_clicker | 鼠标连点器 | ★☆☆☆☆ |
| faatt_archived | 已归档音频工作站 | - |

## 工具链
- **打包**: pyinstaller/ 统一服务所有项目
- **依赖管理**: requirements/ 图形化管理 + requirements.txt 扫描
- **音乐**: wav_music_gen/ (纯stdlib) → faatt_archived/ (已归档) → bloodmusic (旗舰)

## 全哥的偏好
- Python + tkinter 为主要技术栈
- 喜欢把所有东西打包成 .exe
- 中文命名函数和变量
- 功能驱动，快速出活
- 早期作品多为单文件巨兽，近期作品架构意识提升（bloodmusic, yasuo, ollama_generator 分层清晰）
