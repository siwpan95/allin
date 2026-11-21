# allin-console —— 治理控制台（浏览器形态）

> 契约：[`../docs/规范/SPEC-205-allin-console契约.md`](../docs/规范/SPEC-205-allin-console契约.md)
> 定位：**开发者治理控制台**，不是浏览器产品。用 Electron 承载只是因为它顺手能开网页，
> 删掉所有网页标签页这个产品依然成立 —— 那是 §0 的反向判据。

## 它做什么

把 allin 已有的 148 个项目的**登记 / 启停 / 端口 / 门禁**从命令行搬到可视操作面：

- 项目面板读 `platform/registry/projects/*.yaml`（经 `@allin/core`，不另建一份）
- 点项目 → 调它的 `cli.py info` → 原样显示 JSON
- 后续：启停（`launch`/`stop`）、日志流、端口占用、门禁红项（P1–P3）

## 本机注意（必读）

**启动前必须清掉 `ELECTRON_RUN_AS_NODE`。** 本机宿主进程注入该变量，会让 `electron.exe`
以纯 Node 模式运行 —— 表现为 `--version` 输出 `v24.22.3` 而不是 `v45.4.1`，GUI 静默退出、无任何报错。

```bash
# Git Bash / PowerShell 均可：先清变量再启动
env -u ELECTRON_RUN_AS_NODE npm start
```

Windows 上更省事的方式是双击 `start-console.bat`（脚本内已清变量）。

## 快速开始

```bash
npm install                 # 若 Electron 二进制未下载：见下方「二进制缺失」
npm run check               # 契约审计（结构 / 安全三件套 / registry 可加载）
npm run smoke               # 冒烟：列表渲染 + 调一个项目 info + 截图到 data/smoke.png
npm start                   # 打开控制台
```

### 二进制缺失

`npm install` 后若 `node_modules/electron/dist/electron.exe` 不存在：

```bash
ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/" node node_modules/electron/install.js
```

## 结构

```
apps/shell/main.js      入口：应用生命周期（薄）
apps/shell/app.js       窗口 + IPC（smoke.mjs 复用同一份，不另写一套）
apps/shell/preload.cjs  contextBridge 白名单（不暴露 ipcRenderer 本体）
apps/ui/                渲染层：列表 / 详情 / 输出（零 Node 权限）
packages/cli-bus/       CLI 总线：定位 → 调用 → 解析 → 归一化错误
scripts/check.mjs       契约审计（exit 0 才算过）
scripts/smoke.mjs       冒烟（Electron 里跑，带截图与断言）
data/                   运行时产物（gitignored）
```

## 状态（P0，2026-11-22）

| 项 | 实测 |
|---|---|
| registry 条目 | 148 |
| 实现 `info` 子命令 | **31**（另有 6 仓有 cli.py 但无 info，属早期形态） |
| 冒烟 | PASS（列表渲染 / `captcha-demo` 的 info 返回纯 JSON / 截图非空） |
| 契约审计 | PASS |

**P1 待做**：启停（`launch`/`stop` 走 `@allin/core`）、日志流、Web 服务标签页。

## 许可

MIT-0（MIT No Attribution），见 [LICENSE](LICENSE)。无署名义务。
