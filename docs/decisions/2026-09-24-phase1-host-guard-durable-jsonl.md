# ADR 2026-09-24 — Phase 1：Host 围栏 + durable JSONL（参照 DSH 的第二批模式移植）

> 状态：已实施并验证（npm test 39/39；harness exit 0）。冻结。
> 上篇：[2026-09-24-harness-reference-hardening.md](2026-09-24-harness-reference-hardening.md)（P0–P2）。
> 路线定性见工作区《dsh-feed-allin-可行性分析.md》：本篇属 Route A（模式移植，零新依赖）。

## Problem

可行性分析确定的两项残留缺口：
1. **Host 头围栏缺失**：portal 只绑 127.0.0.1 + 写操作 loopbackOnly，但 DNS rebinding
   （恶意页面把自有域名 A 记录指到 127.0.0.1）场景下，浏览器发来的请求 socket 仍是回环
   （loopbackOnly 放行），Host 头却是攻击域名——GET 读取面（/api/library 含全盘路径信息）
   完全裸奔。DSH 对应物：`packages/client/connection/src/api-request-trust.ts:1-13`
   （威胁模型）+ Host 头围栏、非法配置加载即抛。
2. **原子写不是 durable 语义**：P0 的 temp+rename 里 `writeFileSync` 只保证进页缓存，
   掉电/崩溃时 rename 可能指向半截 tmp；轮转 rename 前也未 fsync，存在丢一代边界的
   半截日志窗口。DSH 对应物：ADR `.agents/notes/implemented/architecture/
   2026-07-05-windows-jsonl-durable-publish.md`（POSIX fsync+link+dir fsync；
   Windows MoveFileExW WRITE_THROUGH，拒绝把目录同步失败当成功）。

## Decision

- **Host 围栏**（portal/src/index.js）：仅接受字面量回环 Host
  `127.0.0.1:* | localhost:* | [::1]:*`，其余一律 403，位于全部路由之前
  （GET 读取面同样受保护）。**不做可配置白名单**——单机形态无此需求，少一个误配面
  （与 DSH trustedHosts 可配置化的差异，此处刻意收窄）。
- **durable 原子写**（core/launch.js `writeDurable` + workshop.js `saveState`）：
  open → write → **fsync** → close → rename；running.json 轮转/归档前对源文件 fsync。
  Node 无 Windows 目录 fsync 等价物，注释明示「尽力语义」——与 DSH ADR 的差异已记录。
- **测试**：Host 围栏 4 例（回环三种形态放行 / 攻击域名 / GET 读取面 / HTTP/1.0 缺
  Host raw socket 实测——Node http.request 会自动补 Host，必须 raw socket 才能覆盖）；
  running.json 损坏回退 .bak 1 例（损坏 → 从 .bak 恢复 → 下次写以 .bak 为基底重建）。

## Alternatives considered

- **trustedHosts 可配置白名单**（DSH 同款）：单机场景 YAGNI，配置面即攻击面，收窄。
- **仅写操作加 Host 校验**：读取面泄露路径/版本清单同样可被 rebind 读取，不做半吊子。
- **引 dsh-atomic-write 包**（npm 已发布）：peer 依赖 @deepseek-ai/cordis fork，
  为一个 fsync 序列引运行时不值（Route B1 触发条件未满足）。

## 备案（不实现，写明触发条件）

- **spill 输出捕获**（dsh-spill：内存留尾 + 溢出落盘）：当前 launch `stdio:'ignore'`，
  平台侧看不到项目 stdout。触发：需要「库页日志面板」时实施——契约照抄
  dsh-subprocess 的 SubprocessCollect/CollectedOutput（truncated/spillPath）。
- **进程组强化**（waitForExit 等待全组 + 15ms 防孤儿轮询）：Windows taskkill /T 已覆盖
  主场景；触发：需要 POSIX 部署或出现孤儿进程实证时实施。

## Consequences

- DNS rebinding 对门户读取面与写面的通路被同时封死；诚实边界：本机其他用户/进程
  仍可访问（无鉴权，README 已声明）。
- 状态文件与日志归档获得掉电级 durable 语义；代价是每次写多一次 fsync——
  allin 的写频（启停事件级）完全无感。
- 测试套件 36 → 39，全部纯 Node 内置依赖，零新增三方包。
