# SPEC-205 · allin-console 契约（治理控制台 · 浏览器形态）

> **编号** SPEC-205 ｜ **效力** 准则（结构约定，可被 registry 校验与门禁引用）｜ **状态** 生效
> **生效** 2026-11-22 ｜ **最后修订** 2026-11-22 ｜ **适用面** `console/` 全部代码、`platform/registry/` 数据面、各项目 CLI 入口
> **承载体** `console/scripts/check.mjs`（契约审计）、`console/apps/shell`（Electron 主进程）、`console/packages/cli-bus`（CLI 总线）
> **引用格式** SPEC-205 §C1 / §C2 / §C3
> **上位** [SPEC-203](SPEC-203-allin-platform契约.md)（platform 契约）· [SPEC-201](SPEC-201-引擎接口契约.md)（引擎接口）· [SPEC-003](SPEC-003-治理准则.md)（治理准则）
> **决策记录** 2026-11-22 全哥拍板：定位 **开发者治理控制台**（非浏览器产品）；cordis 走 **JS 版重写**（非桥接）；项目对接一律走 **CLI**（非 HTTP）。

---

## 0. 先破题：这是什么，不是什么

**是**：把 allin 已有的 83 个项目的登记 / 启停 / 端口 / 门禁 / 工坊能力，装进一个**桌面窗口**，
让「治理」从命令行变成可看、可点、可查的操作面。窗口用 Electron（Chromium 内核）承载，
因此它长得像浏览器、有标签页、能开网页 —— 但**那只是外壳顺手带来的能力，不是目标**。

**不是**：
- 不是「自研浏览器」。不碰 Chromium 源码，不做内核分支；对外表述一律为「基于 Chromium 开源项目」。
- 不是 Chrome 替代品。不做扩展商店、不做账号同步、不做 DRM。日常上网请用你的浏览器。
- 不是 platform 的重写。`platform/packages/core` 的 registry / launch / probe 全部复用，console 只做**客户端**。

> 一句话判据：**删掉所有网页标签页，console 依然成立**；反过来则不成立。这条判据用来防止范围漂移。

## 1. 为什么现在能做

三条已经具备的前提，缺一条这个 SPEC 就不该存在：

| 前提 | 现状 | 证据 |
|---|---|---|
| 项目已机器可读地登记 | 83 份 `platform/registry/projects/*.yaml`，含 path / launch / verify / publish（2026-11-25 复测） | `platform/scripts/check.mjs` 审计通过 |
| 项目已有统一 CLI 雏形 | **31 仓**实现了 `info` 子命令且返回纯 JSON（另有 6 仓有 cli.py 但无 info） | `repos/*/cli.py` · `npm run smoke` 可复算 |
| 平台内核已是 Node | registry 加载 / 子进程启停 / 端口查表 / 探活全在 `@allin/core` | SPEC-203 |

第二条是本次最关键的地基：**CLI 是 console 与项目之间唯一的总线**，不引入第二套 RPC。

## 2. 分层与依赖方向

```
console/                          控制台（本 SPEC 管辖）
├── apps/shell/                   Electron 主进程：BaseWindow + WebContentsView[]
│                                 · 窗口/标签/生命周期 · CLI 调用唯一出口 · 日志流汇聚
├── apps/ui/                      渲染层：控制台界面（项目面板/日志/门禁/命令面板）
│                                 零 Node 权限，只经 preload 白名单通信
├── packages/cli-bus/             CLI 总线：定位项目 CLI → 调用 → 解析 JSON → 归一化错误
├── packages/cordis-js/           JS 版 cordis 插件宿主（重写，见 §C2）
├── console/scripts/check.mjs     契约审计（本节所有不变量 → exit code）
└── data/                         运行时状态（gitignored）

复用（不复制）：
  platform/registry/projects/*.yaml   ← 项目事实源（唯一）
  platform/packages/core              ← registry 加载 / 端口查表 / 子进程启停 / probe 探活
  tools/gate/                          ← 门禁留痕（只读消费）

桥接（不改动）：
  kernel/（Python + cordis-py）        ← 治理事实查询，经 `python -m kernel` CLI 调用
```

**依赖方向**：`ui → (preload) → shell → cli-bus → 项目 CLI`；`shell → @allin/core`。
`@allin/core` 与 `kernel` 互不依赖；console **不 import 任何项目代码**（沿用 SPEC-203 的子进程隔离铁律）。

## 3. §C1 项目 CLI 契约（本 SPEC 的核心）

### 3.1 为什么是 CLI 而不是 HTTP

| 维度 | HTTP | **CLI（选定）** |
|---|---|---|
| 覆盖率 | 仅 11 个端口服务 | 83 个项目全部适用 |
| 审计 | 需另建日志 | 每次调用天然留痕（参数/退出码/耗时） |
| 隔离 | 需管端口与鉴权 | 子进程天然隔离，无端口冲突 |
| 离线 | 依赖服务在线 | 进程起停即可 |

83 个项目里只有 11 个有 Web 面（`ports.yaml` active），HTTP 路线覆盖不到 GUI/CLI 的大多数 —— 这是选 CLI 的硬理由。

### 3.2 必须具备的子命令

每个项目在**仓根**提供 `cli.py`（Python）或 `cli.mjs`（Node），至少实现：

| 子命令 | 语义 | 输出 | 退出码 |
|---|---|---|---|
| `info` | 项目自述：name / version / entry / selfcheck / requirements / root | **纯 JSON 到 stdout**（无参数，默认即 JSON） | 0 |
| `version` | 打印版本号（单行） | 文本 | 0 |
| `selfcheck` | 无头自检（不弹窗、不需显示器） | 文本 + 可选 `--json` | 0=通过 / 1=失败 |
| `launch` | 启动项目入口；`--port N` 可指定端口 | 启动即返回或前台运行 | 0 |
| `stop`（可选） | 优雅停止 | 文本 | 0 |
| `logs --tail N`（可选） | 输出最近 N 行日志 | 文本/JSONL | 0 |

> **2026-11-22 P0 实测订正**：初版本文把 `info` 写成 `info --json`，是**凭空发明参数**——
> 既有 31 个项目的 `info` 本来就默认输出 JSON，加 `--json` 会直接触发 argparse
> `unrecognized arguments`（实测 shikonghuaban / captcha-demo）。契约必须贴着既成事实，
> 不能反过来要求 31 个仓改接口。console 侧已改为「`info` 无参数 + `expectJson` 显式选项」。

### 3.3 输出与退出码纪律（可机械判定的部分）

1. **`info` 的 stdout 必须是可 `JSON.parse` 的单个对象**，不得夹带 banner、进度、颜色码。
2. 人类可读信息一律走 **stderr**。
3. 退出码：`0` 成功 / `1` 业务失败 / `2` 用法错误。**禁止用其他码表示第三类语义**。
4. 所有子命令必须能在 `--help` 之外**无交互**运行（console 不可能应答 stdin）。
5. `selfcheck` 必须**不依赖显示器**（无头可跑）—— 否则无法在 CI 与 console 里使用。
6. **"有 cli.py" ≠ "已接入"**：console 只把实现了 `info` 子命令的项目标为可调用。
   实测 bloodmusic（`batch/preview/list/gui/pool`）与 audio-pipeline（`doctor/run/stage-*`）
   都有 cli.py 却无 `info`，属早期 CLI 形态，需在 B 批次补 `info` 后才算接入。

### 3.4 与 registry 的关系

`platform.yaml` 的 `launch.command` **改为指向 CLI**：

```yaml
# 反例（旧）：直接调入口脚本，绕过统一面
launch:
  command: python main.py

# 正例（新）：走 CLI，参数与退出码可被 console 解释
launch:
  command: python cli.py launch
verify:
  command: python cli.py selfcheck --json
```

**迁徙期规则**：`check.mjs` 对新登记项目要求 `launch.command` 出现 `cli.py` / `cli.mjs`；
存量 115 个未补 CLI 的项目登记在 `console/data/cli-gap.json`（按优先级排序），不阻断 P0。

### 3.5 覆盖度现状与补齐优先级

| 批次 | 范围 | 判据 |
|---|---|---|
| B0（已完成） | **31 仓**（2026-11-22 实测） | 有 `cli.py` 且实现 `info` 子命令，`info` 返回纯 JSON |
| B0′（新增） | **6 仓** | 有 `cli.py` 但无 `info`（bloodmusic / audio-pipeline 等早期形态）→ 补 `info` 子命令 |
| B1 | 11 个 Web 服务（`ports.yaml` active） | console 首批真正「能开标签页」的对象 |
| B2 | 高频项目（`portfolio` 里有截图的） | 视觉演示价值高 |
| B3 | 其余 CLI/GUI 项目 | 只做「启停 + 日志」，不做页面 |

> 覆盖度实测口径：83 个登记项目中 **31 个有 `info`**（该 31 与百分比为 2026-11-22 口径，本轮未复测）。用 `npm run smoke` 可复算，
> 判据是「`info` 的 stdout 以 `{` 开头」，不是「cli.py 存在」——后者会虚高 6 个。

## 4. §C2 cordis-js 插件契约

### 4.1 为什么不桥接 Python cordis

`vendor/cordis` 是 **cordis-py 4.0.0**，与 Electron 主进程（Node 24）不同运行时。桥接方案
（`python -m kernel`）能让 console 读到治理事实，但**插件无法参与界面生命周期** —— 而「插件即扩展」
的价值恰恰在于能往 UI 里加面板、加命令、挂钩子。因此：

- **治理事实查询** → 桥接 Python kernel（只读，CLI 调用）
- **界面/命令/钩子扩展** → JS 版 cordis 宿主（本节）

两者并存，职责不重叠。

### 4.2 插件形态

`console/packages/cordis-js` 基于 **`@cordisjs/core` 3.18.1**（注意：JS 版是 3.x，
`vendor/cordis` 的 Python 版是 4.0.0，两条版本线独立演进，不要按版本号强行对齐），
插件即 npm 包或本地目录，导出：

```js
export const name = 'allin-plugin-port-health'
export function apply(ctx, config) {
  ctx.console.command({ id: 'port.health', title: '端口体检', run: async () => {...} })
  ctx.console.panel({
    id: 'port.health.panel',
    slot: 'sidebar',
    // P3 起：常驻面板用 render() 返回**结构化数据**，不用 HTML 字符串
    render: async () => ({
      status: 'ok' | 'warn' | 'bad' | 'error' | 'unknown',
      summary: '一句话结论',
      rows: [{ label: '8000 radio-panel', value: '监听中', tone: 'ok' }],
    }),
  })
  ctx.console.on('project:started', ({ id, pid }) => { /* ... */ })
}
```

> **面板为什么必须返回结构化数据而不是 HTML 字符串（P3 定案）**：
> 插件可能来自用户目录，属于**外部输入**。若插件直接吐 HTML 字符串、渲染层
> 用 `innerHTML` 塞进去，就等于给插件开了一条绕过渲染层 CSP 的注入通道
> （CSP 只挡 `script-src`，挡不住 `<img onerror>` 这类）。
> ⇒ 约定：面板只返回 `{status, summary, rows}`，**渲染层自己建 DOM**，
> 全部文本经 `textContent` 赋值。契约审计 `console/scripts/check.mjs` 第 7 项
> 就是机械检查这条（治理面板渲染函数内不得出现 `.innerHTML =`）。

> **2026-11-22 P2 实测的两个坑（都已跳过，写在这里免得重犯）**：
> 1. **不要给插件声明 `inject`**。cordis 的 `inject` 会挂起插件直到该服务被 `provide`；
>    而宿主是把能力直接挂在 `ctx` 上（非 `Service`），一旦声明就永远等不到——
>    表现为「插件加载成功但 `apply` 从不执行、注册 0 个命令」。
> 2. Windows 下 `import()` 加载插件必须传 `pathToFileURL(...).href`，直接用绝对路径
>    会报 `ERR_UNSUPPORTED_ESM_URL_SCHEME`。

宿主通过 `ctx.deps` 注入**受控依赖**（`core` / `runCli` / `readGateRuns`），
插件拿不到 `electron` / `fs` / `child_process`。

宿主暴露三个扩展点（**只此三个，不扩**）：

| 扩展点 | 能力 | 例子 |
|---|---|---|
| `console.command` | 命令面板里的可执行项 | 「全部项目 selfcheck」「清理孤儿进程」 |
| `console.panel` | UI 插槽（sidebar / tab / statusbar） | 端口占用看板、门禁红项列表 |
| `ctx.console.on(...)` | 生命周期钩子 | `project:started` / `project:stopped` / `project:exited` / `cli:error` |

### 4.3 约束

1. 插件**只能**通过宿主暴露的 API 访问能力，不得直接 `require('electron')` 或读文件系统。
2. 插件的 CLI 调用一律经 `cli-bus`，不得自行 `child_process.spawn`。
3. 插件加载失败**不得阻断** console 启动（降级为「插件不可用」条目）。
4. 插件清单声明 `permissions`（`read:logs` / `exec:cli` / `ui:panel`），未声明即拒绝。

## 5. §C3 进程与安全边界

| 边界 | 规则 | 理由 |
|---|---|---|
| 渲染进程 | `nodeIntegration: false` · `contextIsolation: true` · `sandbox: true` | 控制台 UI 会加载项目页面，不可信 |
| 主进程 | **唯一**能 `spawn` CLI 的地方 | 防渲染层注入任意命令 |
| preload | 只暴露白名单方法（`listProjects` / `runCommand` / `startProject` / `onLog`） | 最小面 |
| 项目网页 | 独立 session partition（`persist:allin-web`），与 UI（`persist:allin-ui`）隔离 | 沿用 Lunar Browser 的成熟做法 |
| 本地服务 | console 打开的 `127.0.0.1:*` 页面**不带** portal token；写操作只经 CLI | 关闭 DNS rebinding 面 |

## 6. 数据流：点一下卡片会发生什么

```
UI 点击「启动 bloodmusic」
  → preload.startProject('bloodmusic')
  → shell：读 platform/registry/projects/bloodmusic.yaml（经 @allin/core）
  → shell：cli-bus.run('bloodmusic', ['launch'])
        · 定位 <path>/cli.py
        · spawn，捕获 stdout/stderr，超时 30s
        · 解析退出码；失败则把 stderr 末 20 行回传 UI
  → 成功后：pid 落 running.json（@allin/core 既有能力）
  → 若 info.web === true：开一个 WebContentsView 指向 127.0.0.1:<port>
  → 事件总线广播 project:started → 插件可挂钩
```

**关键不变量**：console 自己**不维护** pid 表、端口表、项目清单 —— 全部读 `@allin/core` 的既有事实源。
console 重启后状态自动恢复，不存在「两边各记一份」的分裂。

## 7. 分期与验收

| 阶段 | 内容 | 机械验收判据 | 估时 |
|---|---|---|---|
| **P0 壳可跑** ✅ 2026-11-22 | BaseWindow + WebContentsView + 项目面板（读 registry）+ 命令面板骨架 | 启动后列出 **148** 个 id；点击任一项目执行 `cli.py info` 并原样显示 JSON | 1.5 周 |
| **P1 CLI 总线** ✅ 2026-11-22 | cli-bus + 启停 + 日志流 + 失败回传 | 启停走 `@allin/core`（共享 pid 表）；`tasks.log` 落 launch+exit 两行；`info` 输出以 `{` 开头 | 2 周 |
| **P2 插件宿主** ✅ 2026-11-22 | cordis-js + 三个扩展点 + 首批 2 个插件（端口体检 / 门禁红项） | 命令面板列出命令并执行返回结果；删掉插件目录后 console 正常启动 | 2 周 |
| **P3 治理面板** ✅ 2026-11-22 | 侧栏**常驻**三面板：门禁红项 / 端口占用 / registry 审计；`console.panel` 升级为 `render()` 结构化数据 | 启动即见 3 张卡片且每张有数据行（空壳不算）；数值与 `gate-runs.jsonl` / `ports.yaml` / registry 一致 | 2 周 |
| **P4 分发** ✅ 2026-11-22 | electron-builder 打包 + 自用安装包（暂不做自动更新） | NSIS 安装版 + portable 均出包；装好后探针断言 `registry=148 problems=0`；不配仓时降级为快照模式且明示 | 1 周 |

P0 结束即可验证「这条路成不成」；**P0 不通过则不进入 P1**。

### 7.1 P3 治理面板的三条设计约定（2026-11-22 定案）

1. **常驻，不是「点命令面板才看」**。三个面板放在项目列表**上方**的一条横向带里，
   打开 console 即见 —— 否则「治理」就退化成了「又多点一次」。
   刷新：首次加载 + 每 15 秒一次 + 手动「刷新」按钮。
2. **面板只返回结构化数据**（`{status, summary, rows}`），渲染层自建 DOM、
   文本走 `textContent`。理由见 §4.2 的说明：这是防插件注入的唯一办法。
3. **门禁红项必须处理「残缺批次」**。门禁留痕按 `batch` 分组，跑批中途被打断会
   留下一个门禁数偏少的批次（实测 30 道 vs 正常 48 道）。若直接取「最后一批」，
   残缺批次没有失败项 ⇒ 被判成「全绿」，是**假绿**。
   ⇒ 取批次规则：以近 12 批的**门禁数众数**为「应有规模」，取该规模的最新一批；
   同时把最新批次若不足规模这件事**显式标出来**（`warn`）。
   ⚠ 不可用「门禁数最多的批次」——门禁是逐次新增的，历史批次天然更多，
   会永远选到最老的一批，报出几周前的红项（这个错我犯过一次）。

### 7.2 P4 安装态路径契约（2026-11-22 定案）

源码态 console 在 `<allin>/console/`，`@allin/core` 靠 `__dirname` 往上推导即可；
**安装态**（`C:\Program Files\allin console\`）没有 allin 仓，必须显式定位：

| 顺序 | 来源 | 效果 |
|---|---|---|
| ① | env `ALLIN_HOME` | 完整模式 |
| ② | `%APPDATA%\allin-console\config.json` 的 `allinHome` | 完整模式 |
| ③ | 包内 `resources/registry` 快照（extraResources） | **快照模式**：只看清单 + 治理面板，启停/路径解析不可用 |

快照模式必须**明示降级**（日志写明「启停不可用」），不得伪装成完整可用。

实现上的三条硬约束（都是实测踩出来的）：

1. **env 必须先设再 import core**。core 在模块顶层把 `PORTS_YAML`/`REPOS_ROOT`/
   `ALLIN_ROOT` 求值成 const，`console/apps/shell/app.js` 因此**必须动态 import**
   `@allin/core`；静态 import 会被提升，env 还没设就锁死成 `app.asar` 里的假路径。
2. **`ALLIN_ROOT` 需要 env 钩子**。core 原本只有 `PLATFORM_ROOT` 有钩子，`ALLIN_ROOT`
   硬推导导致打包后 `resolvePath('platform')` 解析到 `app.asar/platform`，registry 报
   「path 不存在」。已在 `platform/packages/core/src/registry.js` 补 `ALLIN_ROOT` env
   （未设时行为逐字节不变）。
3. **打包成功 ≠ 产物可用**。`file:` 依赖的传递依赖收集有盲区（`@allin/core` 声明的
   `js-yaml` 没进 asar，打包只报一行 warning 不阻断，运行时必崩）。
   ⇒ `console/scripts/verify-package.mjs` 检查 asar 依赖完整性；
   `verify-packaged.mjs` 真启动 exe 并断言 `registry=148 problems=0`。
   ⚠ Windows GUI 进程不继承 stdout，探针结果**必须写文件**。

环境坑（本轮出现两次）：`ELECTRON_RUN_AS_NODE` 必须**从 env 对象 delete**，
设成空字符串仍会被 Electron 当作已设置 ⇒ 以纯 Node 模式跑、退出码 0 但什么都没做。

## 8. 明确不做的事（防止范围漂移）

| 不做 | 理由 |
|---|---|
| Chromium 源码分支 / 内核定制 | 12～18 人平台团队的活，1 人不可持续（调研结论） |
| Chrome 扩展商店对接 | Electron 官方明确「完整兼容是 non-goal」，做了也是残的 |
| DRM / Widevine | 需 Castlabs 分支，与控制台定位无关 |
| 账号同步 / 云书签 | 单人项目无多端诉求 |
| 自建搜索引擎 | 用现成 URL 模板即可 |
| 把 GUI 项目 Web 化 | 成本按项目算，收益不明；只做启停与日志 |

## 9. 风险台账

| 风险 | 触发条件 | 对策 |
|---|---|---|
| 115 个项目补 CLI 工作量失控 | B3 批次铺开 | 只要求 `launch` + `selfcheck` 两个，`info` 由 registry 兜底生成 |
| project CLI 行为不一致（卡死/占前台） | 项目 `launch` 阻塞不返回 | cli-bus 统一 30s 超时 + 转后台运行（`detached`） |
| 插件破坏主进程 | 插件抛未捕获异常 | 每个插件在独立 `vm` 上下文加载，异常降级不崩溃 |
| console 与 portal 状态分裂 | 两边同时启停同一项目 | 写操作统一走 `@allin/core`，禁用 console 自建 pid 表 |
| Electron 升级破坏 API | 大版本升级 | 锁小版本；`WebContentsView` 已是稳定 API（Electron 30+） |

## 10. 记账

- 2026-11-22 立项。技术调研见 [REC-TO-16](../记录/专题/自研浏览器_开源内核二次开发_桌面端深度调研_2026-11-22.md)（同名桌面稿已于同日收录进枢纽；原 Downloads 外部指针作废）。该报告只作「不做内核分支」决策的技术对照，不是本契约的实施要求。
- 同日核实：Electron 45.3.3 = Chromium 156 + Node 24.22.3；`WebContentsView` 为 BrowserView 的正式替代（Electron 30 起弃用）。
- 同日核实：`vendor/cordis` = cordis-py 4.0.0；JS 宿主需另引 `@cordisjs/core`。
- 同日核实：83 个登记项目中 33 个已有 `cli.py` 统一入口（2026-11-22 口径），11 个有活跃 Web 端口。
- 定位纠偏记账：初版讨论曾按「自研浏览器」框定，全哥 2026-11-22 明确「不是奔着浏览器去，repos 管理治理才是大头」，
  据此把产品定位收为**治理控制台**，并写入 §0 的反向判据。
- 2026-11-22 P0 落地并实测纠偏三处（都是「写的时候想当然」）：
  1. `info --json` → **`info`**：既有 31 仓的 `info` 默认输出 JSON，不接受 `--json`；本 SPEC 初版凭空发明了参数。
  2. 「有 cli.py」→ **「有 info 子命令」**：bloodmusic / audio-pipeline 等 6 仓有 cli.py 但接口不同，
     只按文件存在统计会把覆盖率虚报 6 个（37 vs 真实 31）。
  3. 冒烟的 JSON 判据从「包含 `{`」收紧为「**以 `{` 开头**」：宽松判据会把「stdout 空、信息全在 stderr」
     的失败项目误判为合规。
- 2026-11-22 环境故障记账：本机宿主进程注入 `ELECTRON_RUN_AS_NODE=1`，导致 `electron.exe` 以纯 Node
  模式启动（`--version` 输出 `v24.22.3` 而非 `v45.4.1`，GUI 静默退出）。启动 console 前必须清除该变量；
  已写入 `console/README.md` 的「本机注意」。
