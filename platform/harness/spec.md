# 编排 harness 契约 spec（allin-platform）

> 对齐 E:\lab port_spec.txt 思路：本文件是 harness 用例的单一真相来源；实现与 spec 冲突时以 spec 为准。

## 协议

- 行分隔 JSON（JSON-lines）：请求 {id, cmd, ...}；响应 {id, ok, value, error}；启动先回 {ready:true}。
- 逐请求超时：manifest timeout（platform-gate 150s / portal-probe 5s）。
- 生命周期：子进程由 port.mjs 登记 effect，harness 退出/dispose 时 kill（可逆效应）；stderr 抽干防死锁。

## cmd 集

| cmd | 参与者 | 语义 | 黄金值 |
|---|---|---|---|
| check | platform-gate | 跑 scripts/check.mjs（registry yaml 全量审计；数量 informational，不写死——2026-09-24 起随 estate 增长），exit 0 = 全绿 | 0 |
| count | platform-gate | 同上输出解析「通过：N 个」 | 无（informational，随 estate 增长） |
| health | portal-probe | 探活目标按「`PLATFORM_PORTAL_URL` → `data/portal.port` → manifest target 兜底」取（S2 后口径）。informational 三态：**① 无 HTTP 响应 = 门户离线** ⇒ 返回 manifest 的 `offlineValue`（`OFFLINE`），不进 errors、不计 failures；**② 有响应但非 200 / marker 缺失 = 门户不健康** ⇒ error ⇒ failures++；**③ 200 + marker** ⇒ 200 通过。门户按需临时端口启动，离线是常态，不判失败 | 无 |

## 纪律

- 无新增端口：portal-probe 只读探活既有 :9000（端口登记见 G:\allin\docs\md\allin主工作区\ports.yaml / 端口分配表.md）。
- 运行：node harness/harness.mjs；全绿 exit 0，任何分歧/报错 exit 1。
- 在线冒烟（portal 交互链路）不在 harness 黄金值内，由 portal 自身测试与手动验证负责。
- **S2（2026-11-11）离线 / 不健康分界**：唯一分界是「**有没有 HTTP 响应**」，不按错误字符串匹配（避免 `fetch failed` / `TimeoutError` 措辞变化把判据带偏）。离线值由 manifest 的 `offlineValue` 声明；改语义只改 manifest + 本 spec，不动判据结构。旧实现把「门户没起」报成 `DIVERGENCE DETECTED (1)`，与本 spec 的「离线不判失败」自相矛盾，已订正。

## E4/E5（2026-08-27 补）

- E4 eval-invariant：expectConsensus:true 的用例出现任何分歧/报错/失配 = 真失败（exit 1）；informational 用例（expected:null）可声明 expectDiverged 名单，超出预期分歧同样失败。
- E5 分歧事件订阅链路：分歧/报错事件以 JSON-lines 追加到 data/divergence-events.jsonl（可用 DIVERGENCE_EVENT_FILE 环境变量改路径），每条含 ts/case/consensus/expected/expectDiverged/diverged/errors/components（registry snapshot 健康快照），供 CI/上层订阅与告警。
