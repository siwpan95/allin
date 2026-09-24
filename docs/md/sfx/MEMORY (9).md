# sfx 项目记忆

## 项目定位
- 路径: D:/allin/t0l/sfx
- 功能: 免费音效批量下载器 + 本地试听播放器
- 架构: gui.py(新版主界面) → 从 dl_sounds.py 导入核心引擎 + sfx_utils.py(反爬) + musicplayer.py(播放器)
- dl_sounds.py 双角色: (1) CLI 兼容版 (硬编码全量源)  (2) 核心引擎 (SOURCES / _download_one 等被 gui.py import)
- 数据源: sources/ 目录下 18 个 JSON 配置文件

## 关键约定
- 只用无需注册的数据源（有需注册的 API 源已移除）
- **页面抓取统一 Playwright** (18个源全部) + stealth.js + CF 绕行
- 下载音频文件仍用 urllib（身份轮换+指数退避），不需要 Playwright
- **每个爬虫函数内部有重试**（试多个分类/页面/搜索词），不依赖外层换源
- 无限滚动站点（Pixabay/Mixkit）使用 _fetch_page_scroll 滚动 3 次触发懒加载
- 每个爬虫函数返回 (url, label, ext, referer) 元组，可 2/3/4 元
- 扩展数据源只需：创建 sources/xxx.json + 写 _xxx_scrape_one() + 注册到 SOURCES 列表

## 2026-06-11 改造 (第1轮)
- 新增抓取层重试: MAX_SCRAPE_RETRIES=3 (每槽最多试3个不同源)
- 新增源统计: _source_stats 追踪每个源的成功/失败
- 数据源 14→18: +Zapsplat, +WavSource, +Sampleswap, +99Sounds
- QuickSounds ID 范围扩大, FindSounds/Pixabay/Myinstants 关键词扩充

## 2026-06-11 改造 (第2轮 — 统一 Playwright + 内部重试)
- 5 个 urllib 源全部改为 Playwright: Myinstants, AudioMicro, FindSounds, WavSource, Sampleswap
- 18 个源全部增加源内部重试（试多个分类/页面后再放弃）
- Pixabay + Mixkit 增加滚动加载（scroll_count=3）
- sfx_utils.py 新增 enhanced_fetch_page_scroll() 支持滚动+选择器等待+最小长度验证
