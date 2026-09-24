# 项目长期记忆（D:\allin\tools 评估相关）

## 各工具关键事实（避免误判）
- **fonts**：v1 `font_downloader.py`=**本地**字体复制（读本地 fonts_data.json，run.bat 启动）；v2 `font_downloader2.py`(2054 行)=**网络**字体爬虫（curl_cffi 爬公版字体站）。二者是本地/网络**互补双路径，应整合而非删**。缺 requirements.txt（依赖 requests/curl_cffi/playwright）。
- **yasuo**：`yasuo/` 为包（python -m yasuo），顶层 `yasuo.py` 是被包遮蔽的旧脚本——已移入隔离区 `_cleanup_trash_20260711\`。
- **ollama_generator**：`ollama_generator/` 为包（相对导入），顶层 `ollama_generator.py` 是被包遮蔽的旧入口——已移入隔离区。包 __init__ 用 `from .core`/`from .cleaner` 相对导入。
- **bilibili-helper-py**：`playwright_engine.py` 已不存在（早前合并进 `engine/bilibili_engine.py` 删除），仅 README/注释留痕。
- **art_video_gen**：`integrated_video_audio_generator_backup.py` 为纯遗留备份——已移入隔离区。

## 隔离区
- 已移除的冗余文件统一放 `D:\allin\tools\_cleanup_trash_20260711\`（保留相对结构，非永久删，可恢复）。
