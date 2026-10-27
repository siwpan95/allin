# ADR-0001 —— 治理内核留在 Python，不迁 Node Cordis

- 状态：**accepted**（2026-10-28 落地，无代码改动）
- 相关：`docs/记录/审计/allin增强方案调研_2026-10-28.md`（调研线 2：Cordis 4.x）

## Problem

2026-10-28 调研 Cordis 4.x（官方包 `@cordisjs/core` 4.0.x，ESM-first、Node ≥ 22）后，
摆着一个诱人的选项：Cordis 的「一切皆插件 + Context 依赖注入 + Fiber 可逆副作用」
与本仓治理内核的诉求高度同构，而本仓现在的治理内核是**自研 Python 运行时**
（`tools/gate/governance/runtime/govlib.py`）。
要不要把治理内核迁到 Node + Cordis，换取官方维护的插件生命周期与热重载？

## Decision

**不迁。** 三条理由，按权重排序：

1. **门禁的第一性是「能跑」，不是「优雅」。** 门禁要在每台机器、每次 pre-commit、
   每个 CI 上跑通。Python 侧已有 19 条门禁、自检框架（`SELFCHECK`）、基线棘轮、
   退出码词汇表，且与仓内 `tools/repocheck/`、`tools/verify_projects.py` 同栈。
   换栈等于把这套已验证的东西连同 Node 运行时可用性一起赌进去——
   本机已出现过托管 Node/Python 缺件（tkinter 缺失）导致门禁跑不起来的事故。
2. **Cordis 的价值在理念，不在运行时。** 真正被借鉴并已落地的是它的方法：
   声明式配置（`preset/allin/allin.patch.yml` 对应 Cordis 的 `cordis.yml` 思路）、
   插件序列有序且可比对（`g14-preset` 逐项相等校验）、
   热重载对应的「事实变更即重挂」由 `g16-skill-preset-parity` 的双载体比对替代。
   这些都用 Python 侧已有机制达成了。
3. **成本不对等。** 迁移的收益是「官方维护的插件生命周期」，而治理门禁的插件集合
   是**封闭且稳定**的（19 条，季度级变化）；为它引入一整套 Node 运行时与依赖，
   是把稳定物绑到活跃物上。

**借鉴照做，运行时不动**——Cordis 的能力矩阵作为对照表保留在调研记录里，
若将来治理内核需要真正的运行时热插拔（而非文本注入），再回来重开本决策。

## Alternatives considered

| 方案 | 为什么没选 |
| --- | --- |
| 内核迁 Node + Cordis 4.x，Python 门禁改为子进程调用 | 门禁从「同栈直调」变成「跨进程 RPC」，失败模式翻倍；本机 Node 运行时可用性已证明是风险点 |
| 双栈并存：新门禁用 Node 写，老的留 Python | 两条自检框架、两套基线格式、两个退出码来源——`g00-meta` 的元校验会被迫重写，且「哪条门禁归谁」成为新的认知负担 |
| 迁 Python 版 Cordis（`vendor/` 下的 vendored cordis）为唯一内核 | 本仓已在 `kernel/` 侧用 vendored cordis 做内核 CLI；治理面与内核面耦合会让一次内核升级牵动全部门禁 |

## Consequences

- 正：门禁继续与 `tools/` 同栈，`scripts/run_all_gates.sh` 无需引入 Node 依赖即可跑治理门禁；
  新增门禁的成本不变（一个 Python 文件 + 注册表一行 + `RULES.md` 一行）。
- 负：**放弃了官方插件生态与运行时热重载**。治理 preset 仍是「文本注入」而非「运行时装载」，
  因此 `g16` 只能比对两个载体的事实一致性，无法验证运行时行为。
- 负：Cordis 侧的改进（如 Fiber 的副作用自动回收）不会自动惠及本仓，需人工搬运理念。
- 复核触发条件：出现「治理规则需要在不停机的前提下增删」这一真实需求时，重开本决策。
