# G:\tools 新增 6 个工具 — 交付汇总

全哥指定的 6 个工具已全部建到 `G:\tools\` 下，自包含、不引用其他工具（复制优于共享），均通过编译/导入/纯逻辑功能验证。

| 工具 | 路径 | 类型 | 功能 | 依赖 | 验证 |
|------|------|------|------|------|------|
| imgproc | `G:\tools\imgproc\` | Tkinter GUI | 批量缩放/格式转换/文字水印/灰度/缩略图/模板重命名，输出 `imgproc_out/` | Pillow | ✅ 5 单函数 + batch |
| audiotool | `G:\tools\audiotool\` | Tkinter GUI | 格式转换/裁剪/音量归一(loudnorm)/提取音轨/合并(concat) | 运行时需 ffmpeg | ✅ build cmd 断言 |
| repocheck | `G:\tools\repocheck\` | Tkinter GUI | 扫项目标记：无 git/README/测试/依赖/LICENSE + import 断裂启发式；导出 CSV/HTML | 纯 stdlib | ✅ 缺项识别 |
| subtitle | `G:\tools\subtitle\` | Tkinter GUI | 提取/编辑/保存 .srt/烧录；预留 translate_hook | 运行时需 ffmpeg | ✅ parse 往返 |
| procgen | `G:\tools\procgen\` | 库 + cli | noise/dungeon/namegen/loot/terrain 程序化生成，可 import 复用 | numpy(+Pillow 演示) | ✅ 各生成器形状/类型 |
| renamer | `G:\tools\renamer\` | Tkinter GUI | 正则批量重命名，实时预览/冲突检测/默认 dry-run | 纯 stdlib | ✅ preview + apply |

## 运行方式
```bat
:: 各 GUI 工具
python G:\tools\imgproc\main.py
python G:\tools\audiotool\main.py
python G:\tools\repocheck\main.py
python G:\tools\subtitle\main.py
python G:\tools\renamer\main.py

:: procgen 库演示
cd G:\tools\procgen
python cli.py terrain --size 64 --seed 1 --out terrain.png
python cli.py dungeon --w 48 --h 32 --rooms 8
python cli.py name --style fantasy --n 10
python cli.py loot --n 5
```

## 关键说明
- **audiotool / subtitle** 运行时需系统安装 ffmpeg 并加入 PATH（本机 `C:\ffmpeg\bin\ffmpeg.EXE` 已存在）。GUI 在无 ffmpeg 时安全提示，不静默失败。
- **procgen** 是独立包，可直接复制到任意游戏工程内 `import`（复制优于共享），所有随机带 seed 可复现。
- **踩坑已修**：Pillow 12 移除 `ImageDraw.textsize`，imgproc 水印改用 `font.getbbox`。
- imgproc、procgen 因 Agent 通道瞬时故障，由本人直接编写并测试；其余 4 个经并行工程师交付。

## 已知限制
- repocheck 的 import 断裂是静态启发式，未收录的合法第三方库可能误报。
- renamer 只重命名文件、不重命名文件夹、无撤销（执行前务必确认预览）。
- audiotool 裁剪对 mp3 等有损格式非帧级精确；合并要求各文件编码一致。
