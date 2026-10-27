# ADR-0002 —— SBOM 只存证，不进阻断链

- 状态：**accepted**（2026-10-28 落地：`tools/sbom.py` + `tools/license_matrix.py`）
- 相关：调研线 4（Policy-as-Code）：「SBOM attest, don't gate」

## Problem

供应链治理的常规做法是「产出 SBOM + 扫描漏洞 + 卡 CI」。
本仓有 139–140 个登记项目、`platform/` 与 `kernel/` 两棵依赖树，
要不要把 SBOM 接进门禁，让依赖变化直接决定提交能否通过？

## Decision

**产出，但不阻断。** `tools/sbom.py` 生成 CycloneDX 1.5 到 `tools/gate/audit/sbom.cdx.json`，
`tools/license_matrix.py` 生成许可矩阵；两者都是**按需跑的存证工具**
（`npm run sbom` / `npm run licenses`），不出现在门禁链里。

理由是一条可靠性原则：**阻断链上每加一个环节，就等于把该环节的可用性外包给了外部世界。**
SBOM 的价值在于「出事时能立刻回答我们用了什么」——这是事后取证能力，
而它一旦进阻断链，一次上游发版、一次许可证数据库抖动、一次网络不通
就能让本仓提交全线红灯。用「随时能查」换「随时能卡」，是把证据变成了人质。

配套的两条硬边界：

- **许可识别不猜。** `license_matrix.py` 匹配不上就记 `unknown`，
  且把「有本地克隆却没有 LICENSE」单列为待补清单（首跑即抓出 `ncmturnmp3`）。
  合规矩阵里一个错的 MIT，比一个诚实的空格危害大得多。
- **密钥是唯一例外。** 与 SBOM 相反，`.pre-commit-config.yaml` 里的 gitleaks **直接阻断**。
  密钥属 day-1 block：一旦进历史就必须回滚重写，没有影子模式的余地。

## Alternatives considered

| 方案 | 为什么没选 |
| --- | --- |
| SBOM + 漏洞扫描进 CI 阻断 | 把外部数据库的可用性塞进提交路径；且本仓依赖面小、无 lockfile 解析，扫描结果信噪比低 |
| 只做许可证合规门禁（禁 GPL 依赖进 `platform/`） | 会先误伤 `vendor/`（第三方源码快照）与研究性依赖；真需要时以单独门禁 + 白名单落地，不塞进 SBOM |
| 完全不做 SBOM | 出供应链事故时无法回答「我们用了什么」，取证成本不可接受 |

## Consequences

- 正：供应链取证能力就位（`sbom.cdx.json` + `license-matrix.md`），提交路径零新增故障点。
- 正：许可盘点首跑即产出可行动项（缺 LICENSE 的清单），而不是一堆无法消化的 unknown。
- 负：**不会主动发现问题**——新增一个 GPL 依赖不会有人被拦住，只能靠定期跑一次人肉看。
  缓解：两个工具都进了 `package.json` 脚本，成本是一次命令。
- 负：`sbom.cdx.json` 只覆盖**已声明**依赖（`package.json` / `pyproject.toml`），
  不做 lockfile 解析，因此不含传递依赖——取证时须知晓这一口径，已在产物 `properties` 里写明。
