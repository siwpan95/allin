# Security Policy · kernel（allin 治理内核）

本目录与整个仓库同受根目录 `LICENSE`（MIT No Attribution，MIT-0）管辖。

## 报告安全问题

治理内核承载「制度 + 文档枢纽 + 执行器」三合一，直接决定全工作区的门禁与推送纪律。
若发现安全缺陷（如入口白名单绕过、凭据处理不当、路径注入），请**私密**反馈：

- 优先：在 Gitee 提 Private Issue（不公开细节）：https://gitee.com/siwpan/allin
- 或直接邮件至维护者：siwpan@users.noreply.gitee.com

**响应时限**：我们会在确认收到报告后 **72 小时**内响应，并尽快给出修复与公开披露安排。

**请勿**在公开 Issue / 评论里披露漏洞细节，待修复并发布后再公开。

## 安全相关设计约束

- **入口白名单**：未在 `kernel/registry.py` 的 `SERVICES` 与 `kernel/configs/cordis.allin.yml`
  登记的入口一律不加载（杜绝「配置即代码」任意 import 的评审绕过风险）。
- **路径零硬编码**：任何机器相关绝对路径不得写入源码（`g01_paths` 门禁扫描并阻断）。
- **凭据不进仓**：令牌、密钥从不入库（见 `docs/规范/SPEC-101-推送流程.md` 的令牌红线）。
