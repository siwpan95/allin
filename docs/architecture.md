# allin-platform 架构地图（一个事实一个家）

> 本文是有序地图：模块职责与依赖方向。类型细节看源码，决策理由看 docs/decisions/。

## 分层

```
apps/portal/   前台 @allin/portal —— 零依赖纯 node:http；路由 + 静态资源 + API 门面。
               只做编排：启停/工坊/告警/引擎视图都委托 @allin/core。
apps/cli/      命令行 @allin/cli —— 只读命令直连 registry；启停直连 core（pid 持久化）；
               写命令走门户 HTTP（缓存与事务在门户层）。
packages/core/ 内核 @allin/core —— registry（清单加载/校验/端口查表）/ launch（子进程
               启停 + running.json + tasks.log）/ workshop（订阅=clone/更新=pull/回滚/
               退订）/ gitee（发布面查询，故障显式区分）/ probe（TCP/HTTP 探活 + 慢启动宽限）。
registry/      数据面：projects/*.yaml（一项目一份）+ ports.yaml（env 缺失时的仓内默认）。
harness/       离线黄金值门禁：manifest.json（组合即数据）→ port.mjs（JSON-lines 子进程
               端口）→ driver.mjs（适配器）→ harness.mjs（编排 + 众数共识/分歧 + 退出码绑定）。
scripts/       check.mjs（无 GUI 审计）/ build_batch.mjs（批量打包）/ ensure-mirror.ps1（本地 npm 镜像）。
data/          运行时状态（gitignored）：tasks.log / running.json / workshop.json / portal.port。
```

依赖方向：`portal / cli → core →（js-yaml 唯一三方依赖）`。core 不依赖 apps。

## 关键不变量

- 子进程隔离：`launch.command` 在 `entry.path` 下 shell 执行；pid 落 running.json，
  跨宿主（门户/CLI）可见可停；exit/error 事件双向清理（children Map + running.json）。
- 终止梯：stop.command 优雅停止（15s 封顶）→ 2s settle 窗口 → Windows taskkill 树杀 / POSIX SIGTERM。
- 校验 fail-loud：必填字段、id 形状、path 绝对（+可选存在性）、端口查表 + 服务归属核对、
  gameplay 受控枚举、重复 id。`_valid:false` 条目拒绝启动。
- 日志即事实源：tasks.log（seq/ts/type/project/action）、divergence-events.jsonl（E5 订阅链路）；
  归档/状态写一律 temp+fsync+rename（durable 语义，2026-09-24 Phase 1）。
- Host 围栏：门户全路由前置校验 Host 头（仅回环字面量），防 DNS rebinding——
  GET 读取面与写操作同受保护（2026-09-24 Phase 1）。
- harness 退出码绑定：黄金值全绿 exit 0；任何分歧/报错 exit 1（informational 用例除外，
  但超出声明预期分歧同样失败）。

## 文档税表

| 事实 | 唯一的家 |
|---|---|
| 常备命令 / 环境变量 | 根 [AGENTS.md](../AGENTS.md) |
| 模块职责 / 不变量 | 本文 |
| 持久决策理由（含后果） | docs/decisions/YYYY-MM-DD-<slug>.md（冻结，永不为现行权威） |
| harness 用例契约 | [harness/spec.md](../harness/spec.md) |
| platform.yaml 字段规范 | 《平台项目清单规范_platform.yaml.md》（外部文档枢纽） |
| 端口分配 | `PLATFORM_PORTS` 指向的外部端口分配表（仓内 ports.yaml 仅为回退默认） |
