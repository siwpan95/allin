# allin-platform —— Steam 式全项目集成平台

> **迁移记账（2026-10-26）**：本目录现属 **`siwpan/allin` 治理仓**，由原独立仓 `siwpan/allin-platform`
> 整仓迁入 `platform/`（历史按决议压缩为单个 squash 提交；远端原仓已删除）。
> 架构与清单契约已上提到 [`../docs/规范/SPEC-203-allin-platform契约.md`](../docs/规范/SPEC-203-allin-platform契约.md)；
> 历史版本锚点见本仓 tag `platform-v1.0.0`；决策理由见 [`../docs/记录/决策/`](../docs/记录/决策/)。
> 许可：MIT（见 [LICENSE](LICENSE)）。
> 常驻部署：[DEPLOY.md](DEPLOY.md)（交互式 / Windows 计划任务 / systemd，端口发现、健康检查、退出清理与一次本机验证性部署记录）。
> 注：文中 `<PATH>` 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

> 立项：<PATH>（2026-08-25 用户拍板：Node+Cordis 栈 / 新建本仓 / 单机工坊+静态目录 / 首批 8 项目）。

## 定位

**聚合不融合**：把 <PATH> 全部活跃项目集成到一个平台（类似 Steam 的库 + 创意工坊），但平台零业务代码——项目仍是独立进程、独立目录、独立更新；平台只做 **登记 / 启停 / 装配 / 审计**。

- 理论支持：三条整合纪律（每个插件独立更新 / 不盲目整合 / 统一端口）+ 三件事（注册即回滚 / 补丁即差异 / 日志即事实源）；
- 教训约束：helminth/media_engine 失败 = 代码级融合 → 本平台**绝不 import 项目代码**（子进程隔离，crawl_hub 模式）；
- 端口纪律：任何新服务端口先查 `<PATH>`（与端口分配表.md 同步的唯一事实源）。

## 结构

```
apps/portal/         平台前台（零依赖纯 Node http；DSH 同款形态的独立网页应用，按需启动）：
                     库 Library（项目卡片/启停/状态） · 工坊 Workshop（订阅/取消） · 引擎 Engine（allin_engine 装配视图） · 告警 Alerts（E5 分歧事件）
packages/core/       平台内核：registry（platform.yaml 加载+校验+端口查表）/ launch（子进程+JSONL 任务日志）/ workshop（订阅=clone 到 workshop-copies，更新=真实 git pull，回滚=checkout，退订=删除副本）/ gitee（发布面查询）/ probe
registry/projects/   全部登记项目的 platform.yaml（一项目一份，数量随 estate 增长，当前 105）
scripts/check.mjs    无 GUI 配置审计（exit 0=全通过，对齐 crawl_hub --check）
data/                运行时状态（tasks.log JSONL + workshop.json，gitignored）
```

## 快速开始

```bash
cd <PATH>
npm install --registry=https://registry.npmmirror.com
npm run check      # 注册表审计（端口查表 + path 存在性 + 必填字段 fail-loud）
npm test           # 内核 + 前台测试
npm run portal     # 手动模式（PORT 自选，缺省 9000 仅供临时调试）
```

**推荐入口（2026-08-27 起）**：双击 **`start-platform.bat`** —— 门户以 **DSH 同款形态的独立网页应用**按需启动：`PORT=0` 临时端口 + 自动打开浏览器，关闭窗口即释放端口，**不常驻任何固定端口**。手动调试可 `npm run portal`（`PORT` 自选，缺省 9000 仅供临时用，未登记常驻）。9000 已从 ports.yaml 移除常驻登记。

## 用法示例

```bash
# 列全部登记项目 / 按关键词过滤（只读命令不依赖门户在线）
node apps/cli/src/index.js list
node apps/cli/src/index.js search game

# 启停（CLI 自动读取门户启动时生成的 data/portal.token）
node apps/cli/src/index.js start bloodmusic
node apps/cli/src/index.js stop bloodmusic
```

门户页面上直接点卡片即可启停：写操作所需的令牌由服务端渲染首页时注入。
自动化调用方（website BFF、脚本）发非 GET 请求时需带 `X-Allin-Local: 1` 与
`X-Allin-Token`，令牌读 `data/portal.token` 或由 `ALLIN_PORTAL_TOKEN` 注入；
只读 GET 不需要令牌。示例见 `apps/cli/src/index.js` 与
`../website/src/services/portalProxy.js`。

## 清单规范

每个接入项目一个 `platform.yaml`（字段：id/name/category/version/path/port/launch/stop/health/publish/manual），
规范已上提到 [`../docs/规范/SPEC-203-allin-platform契约.md`](../docs/规范/SPEC-203-allin-platform契约.md) §清单规范
（原引《平台项目清单规范_platform.yaml.md》未随原仓迁移）。port 必查 ports.yaml，未登记拒绝登记。

## 环境变量

| 变量 | 语义 | 缺省 |
|---|---|---|
| `PLATFORM_ROOT` | 运行时状态根（data/） | 仓库根 |
| `PLATFORM_PORTS` | 外部端口分配表（唯一事实源） | 仓内 `registry/ports.yaml`（重建默认） |
| `PLATFORM_REGISTRY` | registry/projects 目录 | 仓内 `registry/projects` |
| `PLATFORM_PATH_CHECK` | `exists`（默认）/ `absolute`（异机/CI 仅校验形状） | `exists` |
| `PLATFORM_ALLIN_ENGINE_CWD` | an-engine 引擎项目目录 | 未配置 → 引擎页报「未配置」 |
| `PLATFORM_PYTHON` | 引擎 CLI 用的 python | `python`（PATH） |

异机 / CI 验证：`PLATFORM_PATH_CHECK=absolute npm run check && npm test`。

> **path 存在性豁免（2026-11-01 拍板）**：`status: archived` / `retired` 的**墓碑条目**不做「path 必须本机存在」校验
> —— 这类条目按治理流程已把工作树移出 `repos/` 归入仓外归档区（远端也多已删除，如 `calculator`），
> 再要求本机存在等于逼我们删掉「撤退记录」才能绿灯。形状纪律照旧（仍须写 `path`、仍禁盘符），活性条目照旧 fail-loud。

## 文档

- [AGENTS.md](AGENTS.md) —— 常备命令 / 环境变量 / 纪律速览（agent 与新协作者入口）
- [../docs/规范/SPEC-203-allin-platform契约.md](../docs/规范/SPEC-203-allin-platform契约.md) —— 架构地图 + 文档税表 + 清单规范（2026-10-26 由原仓架构文档 `architecture.md` 上提到本仓文档枢纽）
- [../docs/记录/决策/](../docs/记录/决策/) —— 冻结的决策记录（Problem/Decision/Alternatives/Consequences）
- [../docs/记录/专题/DSH喂给allin-platform可行性分析_2026-09-24.md](../docs/记录/专题/DSH喂给allin-platform可行性分析_2026-09-24.md) —— 参照 DeepSeek Harness 的强化可行性分析与推进状态
- [harness/spec.md](harness/spec.md) —— 编排 harness 契约（用例的单一真相来源）

## 接入新项目

1. 在 `registry/projects/` 写一个 platform.yaml（先查 ports.yaml 再填 port）；
2. `npm run check` 通过；
3. 库页自动可见（子进程隔离启动）。

## 安全边界（诚实声明，借 DSH SAFETY.md 纪律）

- 门户只绑 `127.0.0.1`，写操作限回环（`loopbackOnly`），**全部请求校验 Host 头**——
  仅接受 `127.0.0.1 / localhost / [::1]`（任意端口），防 DNS rebinding 读取/写穿
  （2026-09-24 Phase 1，详见 ADR [`../docs/记录/决策/platform决策_Host围栏与持久JSONL_2026-09-24.md`](../docs/记录/决策/platform决策_Host围栏与持久JSONL_2026-09-24.md)）。
- **状态变更双闸**（2026-11-08 深度审核）：所有非 GET/HEAD 请求必须同时通过
  ① 令牌闸 `X-Allin-Token`——门户启动时随机生成并写入 `data/portal.token`（0600、不入库），
  经首页注入前端，CLI / website 代理读同一文件，也可用 `ALLIN_PORTAL_TOKEN` 显式注入；
  ② 来源闸——`X-Allin-Local: 1` 或同源 Fetch Metadata/Origin。
  此前 `X-Allin-Local: 1` 是无凭证通行证 ⇒ 同机任意进程即可 shutdown；现已收紧为
  「能读到令牌或拿到注入令牌才能写」。跨站页面既读不到该文件，伪造自定义头也会触发
  CORS 预检失败。**剩余边界**：同用户且能读 `data/portal.token` 的本地进程仍可写；
  多用户 / 存在不可信同机进程时请勿部署。
- **命令形状校验**：`registry.js` 的 `validateEntry` 与 `launch.js` 启停前均调用
  `commandProblems()`，拒绝 shell 控制符、`..` 路径穿越、首词不在受控集合的命令；
  `npm run check` 对 145 份清单零误伤。启动命令仍来自 registry yaml（`shell:true` 执行），
  **registry 依然是信任边界**，只登记自己写的清单。
- 状态文件（running.json / workshop.json）temp+fsync+rename 原子写 + .bak 回退。

## 许可

MIT · Copyright (c) 2026 siwpan（铁律 0：开源优先，公开仓）。

---

## 编排 harness（离线黄金值门禁）

`npm run harness`（= node harness/harness.mjs）——组件清单 harness/manifest.json，契约 harness/spec.md：

- registry-audit：scripts/check.mjs 注册表审计（platform.yaml 全量，数量 informational 不写死）→ 黄金值 exit 0
- registry-count：条目数（informational，随 estate 增长）
- portal-health：只读探活 http://127.0.0.1:9000/（informational——门户已改 DSH 插件版临时端口，离线不判失败；在线时 status 200 + marker「allin-platform」），不新增端口

JSON-lines 子进程协议 + ready 握手 + 逐请求超时；子进程由 port 层登记 effect，退出即 kill；全绿 exit 0，任何分歧/报错 exit 1。
