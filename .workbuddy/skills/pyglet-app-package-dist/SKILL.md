---
name: pyglet-app-package-dist
description: 把 pyglet 应用打包为 Windows 独立 exe（PyInstaller）并组装发行版，含离线录制（ffmpeg）与本机环境要点。当需要「把 demo/项目打包出去」「制作发行版」「录制演示视频」，或排查「打包后运行失败/文件落点不对」时使用。
agent_created: true
---

# pyglet 应用：打包 exe + 视频化发行

源自 3dworld S3 实战（2026-10-08/09）。完整案例：`G:\repos\3dworld` 的
`docs/分发指南.md` + `scripts/build_exe.py`。

## 打包（PyInstaller）

- 环境：隔离 venv 装 pyinstaller（本机：`~/.workbuddy/binaries/python/envs/default`）
- 标准命令（项目根执行）：
  ```bat
  python -m PyInstaller --onefile --console --name <name> ^
      --paths . --distpath dist --workpath build/pyi --specpath build/pyi <入口.py>
  ```
- 要点（实测）：
  - `--paths <项目根>` 必须有（项目里 `sys.path.insert` 是运行时逻辑，打包器看不到）；
  - **pyglet + 项目内包（engine/ 等）无需 hidden-import**，PyInstaller 自动追踪；
  - 产物 ~10.9 MB/个（单文件）；`dist/`、`build/` 记入 gitignore；
  - `--paths` 打包后**主脚本 `__file__` 形态特殊**，见下。

## 冻结后路径机制（坑，必读）

- `PROJECT_ROOT = dirname(dirname(__file__))` 这类推导在 onefile 下**落点因写法而异**：
  - 入口脚本自算的 ROOT → 常解析到运行目录；
  - `_harness` 等被依赖模块的 PROJECT_ROOT → 可能解析到 `%TEMP%`（_MEIPASS 的父）。
- 结论：**不崩、跨机器可用**，但写文件落点不可控。加固惯例：
  - 写文件（截图等）包 `try/except`——**失败只告警、不打断主流程**；
  - 正式分发如需输出文件，加启动参数显式指定目录；
  - 改进项：`getattr(sys, 'frozen', False)` 时**跳过**副产物（如自动抓帧）。

## 运行验证（bash 环境）

```bash
timeout 40 ./dist/<name>.exe --smoke 3 > /tmp/exe.log 2>&1; echo "RC=$?"; cat /tmp/exe.log
```
- 判据：输出含 `EXIT_OK` 即渲染链路打通；**退出挂起属本环境现象**
  （见 `windows-gui-exit-hang-diagnose`——用 timeout + 输出标记判定）。

## 离线录制（ffmpeg）

- 本机可用 ffmpeg（**PATH 上的 `G:\Python314\Scripts\ffmpeg.exe` 是 108KB 坏壳，勿用**）：
  - `G:\repos\musickit\radio\ffmpeg\ffmpeg.exe`（7.1，87MB 单文件，推荐）
  - `G:\repos\pluginplayer\vendor\ffmpeg\bin\ffmpeg.exe`（9.0.1 shared，需同目录 DLL）
- 查找逻辑必须**逐一 `-version` 校验**（防坏壳被 which 优先命中——3dworld 的
  `record_all.ffmpeg_exe()` 已按此修复，可参考其写法）。
- 规模参考：15 个动画（总 705s 素材，30fps 逐帧离屏）**约 5-6 分钟**录完。

## 发行版组装

- 参考 `3dworld/scripts/build_exe.py`：`--list / --only / --all / --pack`；
  `--pack` = 打「精选」+ 收集到 `dist/<pack-name>/` + 生成中文 README.txt。
- 发布渠道：视频平台（MP4 合集）／网盘或 itch.io（exe）／Gitee Release（与 tag 绑定）。
