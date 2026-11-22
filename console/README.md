# allin-console —— 治理控制台（浏览器形态）

> 契约：[`../docs/规范/SPEC-205-allin-console契约.md`](../docs/规范/SPEC-205-allin-console契约.md)
> 定位：**开发者治理控制台**，不是浏览器产品。用 Electron 承载只是因为它顺手能开网页，
> 删掉所有网页标签页这个产品依然成立 —— 那是 §0 的反向判据。

## 它做什么

把 allin 已有的 148 个项目的**登记 / 启停 / 端口 / 门禁**从命令行搬到可视操作面：

- 项目面板读 `platform/registry/projects/*.yaml`（经 `@allin/core`，不另建一份）
- 点项目 → 调它的 `cli.py info` → 原样显示 JSON
- 启停走 `@allin/core`（共享 pid 表与终止梯），日志读它写的 `tasks.log`
- **治理面板常驻**：打开就看到门禁红项 / 端口占用 / registry 审计，不用点命令面板

## 本机注意（必读）

**启动前必须清掉 `ELECTRON_RUN_AS_NODE`。** 本机宿主进程注入该变量，会让 `electron.exe`
以纯 Node 模式运行 —— 表现为 `--version` 输出 `v24.22.3` 而不是 `v45.4.1`，GUI 静默退出、无任何报错。

```bash
env -u ELECTRON_RUN_AS_NODE npm start
```

Windows 上更省事的方式是双击 `start-console.bat`（脚本内已清变量）。

⚠ **清空 ≠ 未设置**：探针脚本里把 `ELECTRON_RUN_AS_NODE` 设成空字符串，Electron 仍以
纯 Node 模式跑（退出码 0、什么都没干）。必须**从 env 对象里 delete**。
这一条本轮踩了两次，写在这里。

## 快速开始

```bash
npm install                 # 若 Electron 二进制未下载：见下方「二进制缺失」
npm run check               # 契约审计（结构 / 安全 / registry / 三块治理面板）
npm run smoke               # 冒烟：列表 + info + 治理面板 + 命令面板，出两张截图
npm start                   # 打开控制台
```

### 二进制缺失

`npm install` 后若 `node_modules/electron/dist/electron.exe` 不存在：

```bash
ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/" node node_modules/electron/install.js
```

## 治理面板（P3）

顶栏下方是一条**常驻**治理带，三张卡片横排，打开即见，每 15 秒刷新（也可点「刷新」）：

| 卡片 | 数据源 | 看什么 |
|---|---|---|
| 门禁红项 | `tools/gate/audit/gate-runs.jsonl` | 最近**成熟批次**的失败门禁；批次被中断会单独标 warn |
| 端口占用 | `ports.yaml` + `netstat -ano` | 登记端口探活 + **未登记的监听端口** |
| registry 审计 | `loadRegistry()` + CLI 探测 | 无效条目、重复 id、CLI 接入率、分类分布 |

两个判据细节（都是实测踩出来的）：

1. **门禁批次不能取「最后一批」**。跑批中途 Ctrl-C 会留下残缺批次（实测 30 道 vs
   正常 48 道），它没有失败项 ⇒ 会被当成「全绿」，是**假绿**。
   也不能取「门禁数最多的一批」——门禁逐次新增，历史批次天然更多，会永远报几周前的红项。
   ⇒ 以近 12 批的**门禁数众数**为应有规模，取该规模的最新一批，并显式标注残缺批次。
2. **面板只返回结构化数据**（`{status, summary, rows}`），渲染层自建 DOM +
   `textContent`。插件可能来自用户目录，直接吐 HTML 会绕过渲染层 CSP 注入标记。
   `npm run check` 第 7 项机械检查这条。

## 打包分发（P4）

```bash
npm run dist      # 出 dist/*-setup.exe（NSIS 安装版）+ *-portable.exe（免安装）
```

镜像必需：electron-builder 的 NSIS / 7zip 二进制从 GitHub 下载，本机直连会 ETIMEDOUT。

```bash
ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/" npm run dist
```

产物在 `dist/`（gitignored，约 116 MB / 106 MB，未签名）。

### 安装后怎么找到 allin 仓

源码态 console 位于 `<allin>/console/`，`core` 能靠 `__dirname` 推导出仓根；**安装后不行**。
按以下顺序定位：

1. 环境变量 `ALLIN_HOME=<allin 仓根>`
2. `%APPDATA%\allin-console\config.json`：`{"allinHome": "<ALLIN_ROOT>"}`
   （本机示例：`D:/projects/allin`；他机按实际仓根替换）
3. 包内随附的 registry 快照（**自动降级**）

快照模式下能浏览 148 条清单、看治理面板、跑只读命令，但**启停与路径解析不可用** ——
日志里会明说，不会假装完整可用。要完整功能就配上面任一项。

`console` 为此需要 core 的三个 env 钩子（都在模块顶层求值，**必须先设再 import**）：
`PLATFORM_ROOT` / `PLATFORM_PORTS` / `PLATFORM_REPOS_ROOT`，外加本轮给 core 新增的
`ALLIN_ROOT`（解析 `platform` 这类仓内相对路径用；不设会解析到 `app.asar` 里的假路径）。

## 结构

```
apps/shell/main.js      入口：生命周期 + 定位配置 + 打包探针（薄）
apps/shell/app.js       窗口 + IPC（smoke.mjs 复用同一份，不另写一套）
apps/shell/config.js    安装态配置解析（ALLIN_HOME / config.json / 包内快照兜底）
apps/shell/preload.cjs  contextBridge 白名单（不暴露 ipcRenderer 本体）
apps/ui/                渲染层：列表 / 详情 / 治理面板 / 命令面板（零 Node 权限）
packages/cli-bus/       CLI 总线：定位 → 调用 → 解析 → 归一化错误
packages/cordis-js/     JS 插件宿主（command / panel / 钩子三个扩展点）
plugins/                3 个内置插件：gate-reds / port-health / registry-audit
scripts/check.mjs       契约审计（含三块治理面板 + 注入防护）
scripts/smoke.mjs       冒烟（Electron 里跑，带截图与断言）
scripts/verify-*.mjs    插件 / 启停 / 产物完整性 / 打包产物运行验证
build/                  图标源与生成脚本（构建时自动生成，gitignored）
data/                   运行时产物（gitignored）
```

## 状态

| 阶段 | 内容 | 实测 |
|---|---|---|
| P0 | 148 项目列表 / 搜索 / 调 `info` 看 JSON | PASS |
| P1 | 启停（走 `@allin/core`，共享 pid 表与终止梯）/ 运行态轮询 / 任务日志 | PASS |
| P2 | cordis-js 插件宿主（command / panel / 钩子）+ 命令面板 | PASS |
| P3 | 治理面板常驻视图（3 插件 / 3 卡片）+ 注入防护 | PASS |
| P4 | electron-builder 打包（NSIS 安装版 + portable）+ 产物运行验证 | PASS |

**接入覆盖**：registry 148 条；实现 `info` 子命令 **31** 个；有 `cli.py` 但无 `info`
6 个（B0′ 批次待补）。

**内置插件**（`plugins/*.mjs`，改完重启即生效，无热加载）：
- `gate-reds` —— 门禁留痕 + 残缺批次识别（命令 `gate.reds` / 面板 `governance.gates`）
- `port-health` —— 端口探活 + 未登记监听端口（命令 `port.health` / 面板 `governance.ports`）
- `registry-audit` —— 登记质量审计（命令 `registry.audit` / 面板 `governance.registry`）

## 验证命令

```bash
npm run check               # 契约审计：结构 / 安全 / registry / 治理面板 / 注入防护
npm run smoke               # 冒烟：渲染 + info + 治理面板 + 命令面板（无副作用）
npm run verify:plugins      # 插件宿主：3 命令 + 3 面板，逐条执行
npm run verify:lifecycle    # 真启停一次（会真的执行项目 launch 命令）
npm run verify:package      # 打包产物完整性（asar 依赖 / registry 资源）
npm run verify:packaged     # 打包产物运行探针（断言 registry=148、problems=0）
```

`verify:lifecycle` 会往 `platform/data/tasks.log` 写记录并真实拉起进程 —— 只在需要
核对启停链路时手动跑。

## 许可

MIT-0（MIT No Attribution），见 [LICENSE](LICENSE)。无署名义务。
