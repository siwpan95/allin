# A 级审计报告：allin-platform vs deepseek-harness-master

> 审计范围：`G:\platform`（allin-platform，git 仓，remote=gitee.com/siwpan/allin-platform.git）对照 `G:\notpython\deepseek-harness-master`（dsh 上游源码快照，MIT © DeepSeek AI，@deepseek-ai/dsh-root 0.1.0-rc.5，无 .git）。
> 方法：逐文件 hash（SHA256）+ 双向标识符 grep + 全量 registry YAML 程序化审计 + 命令实测（check / node --test / harness）。
> 结论先行：**platform 没有从 dsh 复制任何代码**。两者唯一的交集是 "Cordis" 这一设计概念，且 platform 是通过自家 `E:\lab\chess-cordis` 间接对齐，而非 dsh。因此对 dsh **无 MIT 署名义务、无许可证侵权**。真正的风险点不在版权，而在**凭证卫生**（.git/config 明文内嵌 gitee 令牌）与少量 registry 路径失实。

---

## 1. 代码借用了什么（逐文件结论）

### 1.1 语言/构建形态根本不同，排除"代码级复制"

| 维度 | dsh（上游） | allin-platform |
|---|---|---|
| 语言 | TypeScript（.ts/.tsx） | 手写 Node ESM（.mjs/.js） |
| 构建 | tsc + tsdown（`tsconfig.host.json`/`tsdown.config.ts`） | 无构建，直接 `node` 运行 |
| 依赖 | pnpm workspace，47 个 packages，vendor 内 vendored Cordis | 仅 1 个运行时依赖 `js-yaml`（+ `argparse`） |
| 包管理 | pnpm@11.7.0（pnpm-lock.yaml 680KB） | npm（package-lock.json 1.8KB，仅 js-yaml 闭包） |

platform 是 `.mjs`/`.js` 纯 JS；dsh 是 `.ts` 源码 + 构建产物。二者**没有任何同名/同扩展名/同 hash 的文件**。

### 1.2 SHA256 指纹（platform 关键源文件）

以下为 platform 源文件 SHA256（供交叉比对用；经双向 grep 验证，这些内容在 dsh 中零出现）：

```
8C2D4942…  harness/harness.mjs
B3F9D190…  harness/registry.mjs
F3EB517A…  harness/driver.mjs
B06C2F95…  harness/port.mjs
78F5FCF2…  scripts/check.mjs
44487658…  scripts/build_batch.mjs
A1580BCE…  apps/portal/src/index.js
5E5D340D…  apps/portal/public/app.js
8723E705…  packages/core/src/index.js
CCFFECAE…  packages/core/src/registry.js
D7CE9BF7…  packages/core/src/launch.js
5F229A50…  packages/core/src/workshop.js
152DFDF9…  packages/core/src/gitee.js
55D3F864…  packages/core/src/probe.js
BF76DE9C…  allin-platform.iss
431265E7…  README.md
EEB3E084…  LICENSE
```

### 1.3 双向标识符 grep（决定性证据）

- platform → dsh：在 `G:\notpython\deepseek-harness-master` 全文检索 platform 独有标识符 `siwpan / chess-cordis / crawl_hub / crawl-hub / loadRegistry / allin-platform / workshop-copies` → **0 命中**（唯一泛匹配是 `allin` 撞上英文 `calling`/`falling`，非真实标识符）。
- dsh → platform：platform 全文检索 `cordis / deepseek / dsh-root / @deepseek` → 仅命中 README 一处 "Node+Cordis 栈"、registry.mjs/harness.mjs 注释中的 "cordis.yml 语义 / Cordis Fiber effect 栈"、以及一个**业务项目** `cordis-snake`（siwpan/cordis-snake 游戏，与 dsh 无关）。**没有任何 dsh/DeepSeek 代码、API、类名、字符串被引用。**

### 1.4 platform 代码注释声明的"真实上游"

platform 各文件在头部注释里明确写了自己"对齐"的对象，**都不是 dsh**：

| platform 文件 | 注释声明的对齐对象 |
|---|---|
| `harness/harness.mjs` | `E:\lab chess-cordis/src/harness.mjs`（GOLDEN_POSITIONS/analyzeDivergence/formatReport） |
| `harness/registry.mjs` | `E:\lab chess-cordis/src/registry.mjs` |
| `harness/port.mjs` | `E:\lab chess-cordis/src/ports/subprocess.mjs` |
| `harness/spec.md` | `E:\lab port_spec.txt` |
| `scripts/check.mjs` | `crawl_hub --check` |
| `scripts/build_batch.mjs` | 街机 `build_all` 模式 |
| `apps/portal/*` | `@relay/portal` / `private-radio-stations/apps/portal` |
| `packages/core/src/launch.js` | `WorldLog / crawl_hub tasks.log`（JSONL 同构） |

`E:\lab\chess-cordis` 经 `Test-Path` 确认**真实存在**（True）。即 platform 的 harness 是从 siwpan 自己的 chess-cordis 项目派生，而非 dsh。

### 1.5 结论

- **从 dsh 复制的文件：0 个**（无代码级复制）。
- **从 dsh 受启发重写：仅 "Cordis 组合/Fiber effect" 一个概念点**，且是经 chess-cordis 间接对齐，不是读 dsh 源码改写（registry.mjs 第 3 行注释 "等价 Cordis Fiber effect 栈逆序串行回收" 是唯一的概念署名）。
- **完全原创：platform 的 registry/launch/workshop/probe/gitee/portal/build_batch/iss 全部**（业务逻辑是"Steam 式项目集成平台"，与 dsh 的 agent-harness 领域无关）。

---

## 2. 许可证 / 署名合规

- 上游：`G:\notpython\deepseek-harness-master\LICENSE` = **MIT · Copyright (c) 2026 DeepSeek**；另有 `THIRD_PARTY_NOTICES.md`（披露 vendored Cordis 及全部依赖，注明 Cordis 来自 cordiverse/cordis，MIT）。
- platform：`G:\platform\LICENSE` = **MIT · Copyright (c) 2026 siwpan**；README 第 46 行 "MIT · Copyright (c) 2026 siwpan"。
- platform **没有** `THIRD_PARTY_NOTICES.md`。但 platform 的唯一 npm 运行时依赖是 `js-yaml@4.3.1`（MIT）+ `argparse@2.0.1`（Python-2.0），均为常规 npm 依赖、非源码 vendoring，package-lock 已含 license 字段，符合 npm 惯例，不构成署名义务缺失。
- **合规结论**：因为不存在从 dsh 复制代码的事实，MIT "copyright notice 必须随副本保留" 条款**不触发**，platform 无需保留 DeepSeek AI 版权声明，`© siwpan` 的署名对 dsh 而言合规。
- **次级提示（非法律义务）**：platform 代码注释/README 明确"对齐"了 `chess-cordis`、`crawl_hub`、`private-radio-stations`、`@relay/portal` 等外部项目，但未在 LICENSE/README 中披露这些被"对齐"项目的许可证。由于目前看是**概念级/模式级仿写**（非复制，未 import 其代码），通常不触发署名；但这属于最佳实践层面的可改进点，若后续真复制了其中任一 MIT 项目的代码，则需补署名。

---

## 3. 架构对照

### 3.1 dsh 的 Cordis 组合根 / registry / launch

- 组合根：`apps/cli/src/bin.ts` + `profile-boot.ts`，读取 `cordis.yml`，经 `@deepseek-ai/cordis-plugin-loader/include/group` 装配。
- 核心框架 vendored 在 `vendor/cordis/src/`：`context.ts / fiber.ts / events.ts / registry.ts / service.ts`。
- 五要素（引自 `docs/cordis-primer.md`）：插件=实现 Service 的对象（`inject` + `apply(ctx)`）；Context=服务仓库；`inject` 声明依赖以表达加载顺序；类型化事件（emit/waterfall/parallel/serial 四种 dispatch）；注册是可逆 effect（`ctx.effect()`/`ctx.on()`，随 Fiber 逆序回收）。

### 3.2 platform 的 harness.mjs/registry.mjs/driver.mjs/port.mjs

| platform 概念 | 对应 Cordis 概念 | 关系 |
|---|---|---|
| `manifest.json` components（enabled:false=运行时下架） | `cordis.yml`（组合即数据） | **概念级仿写**（harness.mjs 注释明写"对齐 cordis.yml 语义"） |
| `registry.mjs`：模块单例 Map + `register/list/snapshot` | Context 服务仓库 | 概念级仿写（简化到 ~15 行） |
| `registry.mjs` `effects` 栈 `disposeAll` 逆序执行 | Fiber effect 栈逆序串行回收 | 概念级仿写（注释明写"等价 Cordis Fiber effect 栈"） |
| `port.mjs` JSONL 子进程端口（ready 握手/按 id 关联/逐请求超时/kill） | 无直接对应（dsh 的 `packages/subprocess` 是 PTY/进程 primitive） | platform 独创的"黄金值共识 harness"协议 |
| `harness.mjs` `analyzeDivergence` 众数共识 + 黄金值 | dsh 无对应（dsh 用 vitest 快照 + `run-gates` 门禁） | 原创（源自 chess-cordis） |

### 3.3 JSONL 子进程协议 + ready 握手（platform vs dsh）

- platform：`driver.mjs`（子进程侧）启动先吐 `{"ready":true}`，随后逐行读 stdin 的 `{id,cmd}`、逐行写 stdout `{id,ok,value,error}`；`port.mjs`（父侧）按 `id` 关联 pending 请求、逐请求 timeout、stderr 抽干防死锁、dispose 时 kill。这是**简化的行分隔 JSON-RPC 风格**。
- dsh：`packages/subprocess`（`spawnTerminal` 等）是 PTY/进程组/信号/树杀的原语，服务端-客户端用 `@remote`/RPC（`ctx.connection.rpc.call`）跨 Host/Client，远复杂。
- 异同：两者都做"子进程 + 行/JSON 消息 + 生命周期可逆回收"，但 platform 的"黄金值 + 众数共识（analyzeDivergence）"是 dsh 完全没有的机制。

### 3.4 platform 相对上游的能力缺失/简化（能力列表）

platform 完全缺失 dsh 拥有的：类型化事件系统（4 种 dispatch）、`inject` 依赖声明与自动等待、HMR、服务生命周期/作用域（scope 链）、sandbox 权限、approval 流、LLM/session/subagent/plan/goal/workflow/工具目录等 agent 领域能力、`@remote` Host↔Client RPC、快照测试门禁。这些是**领域差异**而非缺陷——platform 目标是"Steam 式项目集成平台"，根本不需要 agent-harness 能力；但从"对齐 Cordis"的角度看，platform 只借走了"组合即数据 + effect 逆序回收"两个最小概念。

---

## 4. platform 自身质量

### 4.1 `scripts/check.mjs` 是否真的校验 registry

- 实测 `node G:\platform\scripts\check.mjs` → **exit 0**，输出 `[check] 通过：95 个项目清单全部有效`。
- **但它不校验 path 是否真实存在**：`packages/core/src/registry.js` 的 `validateEntry` 对 path 只做 `path.isAbsolute()`（第 37 行），从不 `fs.existsSync`。于是全量审计发现 **2/95 个 path 指向不存在的目录却依然"通过"**：
  - `fonts.yaml` → `G:\local\fonts`（不存在）
  - `paotuan.yaml` → `G:\local\paotuan`（不存在）
- 结论：check.mjs 校验的是"必填字段 + id 形状 + 端口查表 + gameplay 枚举 + 端口归属"，**不校验磁盘真实存在性**，属"配置结构校验"而非"环境可达性校验"。

### 4.2 测试

- `packages/core/test/` 存在（registry.test.mjs、workshop.test.mjs）；`apps/portal/test/` 存在（api.test.mjs）。
- 实测 `node --test packages/core/test/*.test.mjs` → **7 pass / 0 fail，exit 0**。
- 实测 `node --test apps/portal/test/*.test.mjs` → **8 pass / 0 fail，exit 0**。
- 测试覆盖：registry 端口查表/必填字段/gameplay 枚举/端口归属、workshop 订阅=clone / 更新=git pull / 回滚=checkout / 退订=删除、portal 的 status/library/workshop/catalog/audit/404。

### 4.3 registry/projects/*.yaml 全量审计（95 个）

程序化脚本（js-yaml）全量解析结果：

- 总数：**95** 个 yaml。
- path 存在性：**93 存在 / 2 不存在**（fonts、paotuan）。
- port 重复：有 port 的条目共 **5 个**（radio:8000、video:8100、mixer:8010、audio-separator:8080、portal:9000），**0 重复**，全部唯一。
- 字段完整性：95/95 均有 `launch.command`；0 个 path 非绝对路径；必填字段（id/name/category/version）无缺失（否则 check.mjs 会 fail）。
- 15 个抽查样本（radio、audio-separator、fonts、alloy、portal、cordis-snake、video、crawl-hub、mixer、bee、darksouls、gan、math、pyinstaller、sfx）：13 存在 / 2 不存在（fonts、paotuan）。

### 4.4 harness 实测

- `node G:\platform\harness\harness.mjs` → **exit 0**，三用例 `registry-audit`(0)、`registry-count`(95)、`portal-health`(200) 全 PASS，`OVERALL: ALL GOLDEN VALUES MATCH`。（说明 portal :9000 当前在线。）

### 4.5 附带发现（bug/隐患）

- `apps/portal/src/index.js` 第 27 行 `ALLOY_CWD` 默认 `'G:\\games'`，而 `G:\games` **不存在**（Test-Path=False）——引擎装配视图在未设 `PLATFORM_ALLOY_CWD` 时必然失败。
- `harness/manifest.json` runtime.python = `F:/Python314/python.exe` 经 Test-Path **存在**（True）。

---

## 5. installer / release / build-batch

### 5.1 内容

- `G:\platform\allin-platform.iss`：**Inno Setup** 脚本（AppId C4E1D2B0…，AppName "allin-platform 集成平台"，发布者 siwpan）。打包源 `_installer-src\stage\*`（**当前不存在**，需先手动备好）。打包清单（.iss 第 5-10 行注释）明确为：便携 Node v26.7.0 + apps/packages/registry/scripts/node_modules + package.json/package-lock.json/LICENSE/README.md + data/ 空目录；**不含 .git**。输出 `installer\allin-platform-setup-1.0.0.exe`（29.4 MB，已存在）。
- `G:\platform\release\`：`exe\` 28 个 PyInstaller onefile exe（art-video-gen/audio-separator/…/zhuangtaiji，第三方工具打包）+ `zip\` 5 个便携 zip（fonts-portable.zip **1.0 GB**、procgen、wave4、ollama-generator、audio-pipeline）。
- `G:\platform\build-batch\`：29 个 `.spec` + 各 PyInstaller work 目录（`.toc/.pyz/.exe/.pkg/base_library.zip` 等构建中间产物）。

### 5.2 令牌/私人文件风险

- **发现的真实令牌**：`git -C G:\platform remote -v` 显示 remote URL 为 `https://siwpan:<token>@gitee.com/siwpan/allin-platform.git`，即 **gitee 访问令牌以明文内嵌在 `.git/config` 的 push URL 中**。
- 核实该令牌的扩散范围（全程不打印令牌明文，仅报告布尔结论）：
  - 不在 git 历史 blob（`git grep 'siwpan:' $(git rev-list --all)` → 无命中）；
  - 不在 tracked 文件（`git ls-files` 无 node_modules/.git/config 等）；
  - 不在源码（对 packages/apps/scripts/harness 全 grep `token|password|secret|authorization|bearer|@gitee|siwpan:` → 0 命中）。
- 打进安装包/发布物的风险：
  - `.iss` 打包源是手工备好的 `stage\`，清单不含 `.git`，且 `.gitignore` 排除 `node_modules/ data/ workshop-copies/ release/ build-batch/ installer/`。
  - `scripts/build_batch.mjs` 的便携 zip 打包在 `os.walk` 排除列表里**明确排除了 `.git`**（第 120 行）；PyInstaller spec 的 `datas` 只取 entry.path 顶层非 .py 文件，不递归 .git。
  - fonts-portable.zip 抽查：487 项，全部是字体文件（etc/*.zip）+ 少量 .py/.bat/README，无 .git、无凭据。
- **结论**：未发现把含令牌的 `.git` 或私人文件打进安装包/发布物的**实际证据**；但 `.git/config` 明文 gitee 令牌本身是**独立高危项**——该 remote 是公开仓，令牌一旦随 .git 目录或环境被复制/共享即泄露，建议**立即轮换令牌并改用 credential helper**，从 remote URL 中移除明文 userinfo。

---

## 6. 对比清单表（platform 顶层 vs 参考仓库）

| platform 顶层 | dsh 对应物 | 判定 |
|---|---|---|
| `.git/` | 无（快照无 .git） | 无关（platform 有历史/remote） |
| `.gitignore` | `.gitignore` | 原创（内容完全不同） |
| `allin-platform.iss` | 无（dsh 用 `@yao-pkg/pkg` 单 exe + `scripts/build-exe-for-python-sdk.ts`） | **原创/无关** |
| `LICENSE` | `LICENSE`（MIT © DeepSeek） | 独立原创（MIT © siwpan，版权人不同） |
| `README.md` | `README.md` | 原创 |
| `package.json` | `package.json`（@deepseek-ai/dsh-root） | 原创（独立 manifest） |
| `package-lock.json` | `pnpm-lock.yaml` | 原创（npm vs pnpm） |
| `apps/portal/` | `apps/web`（React/Vite）+ `apps/cli` | **原创**（纯 Node http，领域/技术栈全异） |
| `build-batch/` | 无 | 无关（PyInstaller 批量产物） |
| `harness/` | 无直接对应（概念近 `vendor/cordis` + `cordis.yml`） | **仿写**（对齐 chess-cordis/Cordis 概念，非 dsh） |
| `installer/` | 无 | 无关（Inno Setup exe） |
| `node_modules/` | `vendor/` + node_modules | 无关（仅 js-yaml，无 vendored 源码） |
| `packages/core/` | `packages/core`（dsh 的 agent 核心服务） | **原创**（同名不同义：registry/launch/workshop） |
| `registry/` | 无（dsh 用 `cordis.yml` 组合配置） | 原创（platform.yaml 登记概念 dsh 无） |
| `release/` | 无 | 无关 |
| `scripts/check.mjs` | `scripts/run-gates.ts`（门禁概念近似） | **仿写**（对齐 crawl_hub --check，非 dsh） |
| `scripts/build_batch.mjs` | 无 | 无关 |

**总判定**：platform 与 dsh 在代码层面零交集；唯一的概念亲缘（Cordis 组合/effect）经 siwpan 自己的 chess-cordis 中转，且高度简化。许可证上对 dsh 无任何义务。
