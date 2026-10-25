# ADR 2026-09-24 — 参照 DeepSeek Harness 的 P0–P2 强化

> **本文是 2026-09-24 的一次性记录，不作为约束。**
> **迁移记账** 本文原名 `allin-platform/docs/decisions/2026-09-24-harness-reference-hardening.md`；
> 2026-10-26 三仓整合后迁入本仓 `docs/记录/决策/`，内容除本记账块与交叉引用修正外未作改动。
> 原仓远端已删除。

> 状态：已实施并验证（npm test 37/37；check/harness exit 0；portal 冒烟通过）。冻结。

## Problem

全库评估发现三类结构性弱点：
1. **规模脱节**：registry 实有 105 个 platform.yaml，README/spec 写 95、api.test 硬断言 95 → `npm test` 红灯；收编新项目忘同步测试与文档。
2. **强绑定本机**：`G:\platform`（launch/bat/iss）、`G:\allin\...\ports.yaml`（registry）、`G:\repos\an-engine`（portal）、`F:\Python314`（harness/ensure-mirror）——环境变量预留（PLATFORM_ROOT 等）只覆盖一半，任何新机器 `npm run check` 必挂。
3. **并发/可靠性隐患**：running.json 非原子读写（崩溃可清空整表）；stopEntry 用 spawnSync+Atomics.wait 阻塞门户事件循环最长 17s；gitee 网络故障被静默当成「无更新」；tasks.log / divergence-events.jsonl 无限增长；浅克隆下回滚旧提交可能不在对象库。

## Decision

参照 deepseek-ai/deepseek-harness（MIT）的工程实践，按同栈可移植原则逐项落地：

| DSH 模式 | 本仓落地 |
|---|---|
| Windows durable publish（temp→原子替换→备份） | running.json / workshop.json 原子写（temp+rename）+ .bak 回退 |
| 终止梯（TERM→grace→KILL，spec 全显式） | stopEntry 异步化：stop.command await（15s 封顶）→ 2s settle → taskkill 树杀 |
| fail-loud：不静默吞缺失引用 | gitee fetchBranchCommitStatus：`{ok:false,error}` 显式上工坊页「检查失败」徽章 |
| 日志世代轮转 | tasks.log / divergence-events.jsonl 超 5MB 归档 .1；workshop history 上限 50 |
| 具名门禁 + 数量 informational | 数量断言跟随 estate（与 yaml 文件数一致），spec 不再写死 95 |
| 组合即数据 + env 优先 | PLATFORM_PORTS/PLATFORM_ROOT/PLATFORM_ALLIN_ENGINE_CWD/PLATFORM_PYTHON env 优先 + 仓内回退；PLATFORM_PATH_CHECK=absolute 支持异机 CI |
| 文档税表 + 冻结 ADR | 新增 AGENTS.md + docs/architecture.md + 本决策记录 |

## Alternatives considered

- ** Cordis 真依赖化**（apps 挂到 cordis 内核）：改动面过大，且本仓 harness 已自实现对齐语义的 effect 栈；暂不引入运行时依赖，仅保持语义对齐。
- ** ports.yaml 随仓唯一化**（废弃外部表）：违反「端口分配表.md 是唯一事实源」的既有纪律；采用 env 优先 + 仓内重建默认的折中。
- ** 鉴权 token 加固门户**：本机单用户场景 + 只绑 127.0.0.1，写操作已有 loopbackOnly；收益低于体验成本，暂缓（已知边界，见 README）。

## Consequences

- 收编新项目只需加 yaml；`npm test` 数量断言自动跟随，不再需要同步测试。
- 仓库克隆到任意机器：`PLATFORM_PATH_CHECK=absolute npm run check && npm test` 即可全绿；作者机器保持 path 存在性 fail-loud 默认。
- 停止慢服务期间门户不再卡死；gitee 断网时工坊页显式提示而非显示「无更新」。
- 代价：stopEntry/检查更新路径变为异步，调用方必须 await（已全部适配并有测试兜底）。

> **命名订正（2026-09-24）**：本文原写 `PLATFORM_ALLOY_CWD`，现为 **`PLATFORM_ALLIN_ENGINE_CWD`**。
> `alloy` 是引擎被放弃的旧名（PyPI 上该名属他人 Sam Gammon @ Elide，不可用）；
> 分发名 `allin-engine`、导入名 `allin_engine`，**以 PyPI 为准**。
> 引擎目录已由 `alloy/` 改为 `allin_engine/`（commit `72c1d63`），全文其余 alloy 字样均按此读。
