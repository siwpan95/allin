# Security Policy · platform（allin 集成平台）

本目录与整个仓库同受根目录 `LICENSE`（MIT No Attribution，MIT-0）管辖。

## 报告安全问题

platform 是 Steam 式全项目集成平台（库 Library + 创意工坊 Workshop + 引擎视图）。
若发现安全缺陷（如 Host 头绕过、子进程注入、凭据处理不当），请**私密**反馈：

- 优先：在 Gitee 提 Private Issue（不公开细节）：https://gitee.com/siwpan/allin
- 或直接邮件至维护者：siwpan@users.noreply.gitee.com

**响应时限**：我们会在确认收到报告后 **72 小时**内响应，并尽快给出修复与公开披露安排。

**请勿**在公开 Issue / 评论里披露漏洞细节，待修复并发布后再公开。

## 安全相关设计约束

- **Host 头围栏**（防 DNS rebinding）、持久 JSONL 的 fsync durable 语义（见 `docs/记录/决策/` 的 platform ADR）。
- **入口白名单 + 子进程隔离聚合**（见 `docs/规范/SPEC-203-allin-platform契约.md`）。
- **凭据不进仓**（见 `docs/规范/SPEC-101-推送流程.md` 的令牌红线）。
