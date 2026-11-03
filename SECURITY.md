# Security Policy · allin（仓库级）

本仓与全部子件同受根目录 `LICENSE`（MIT No Attribution，MIT-0）管辖。

## 报告安全问题

本仓承载全工作区的治理制度、文档枢纽与门禁体系，并含对外站点（`website/`）
与集成平台（`platform/`）。若发现**仓库级**安全问题（如密钥/令牌意外入库、
门禁绕过、CI 配置注入、website 加密实现缺陷），请**私密**反馈：

- 优先：在 Gitee 提 Private Issue（不公开细节）：https://gitee.com/siwpan/allin
- 或直接邮件至维护者：siwpan@users.noreply.gitee.com

**响应时限**：确认收到报告后 **72 小时**内响应，并尽快给出修复与公开披露安排。

**请勿**在公开 Issue / 评论里披露漏洞细节，待修复并发布后再公开。

## 子件安全策略

各子系统有更具体的攻击面说明与设计约束，优先查阅对应文件：

| 子件 | 策略文件 | 关注面 |
|---|---|---|
| `kernel/`（治理内核） | [kernel/SECURITY.md](kernel/SECURITY.md) | 入口白名单、路径零硬编码、凭据不进仓 |
| `platform/`（集成平台） | [platform/SECURITY.md](platform/SECURITY.md) | 门户 Host 围栏、进程启停边界 |
| `tools/repocheck/` | [tools/repocheck/SECURITY.md](tools/repocheck/SECURITY.md) | 扫描器规则与评分边界 |
| `website/`（官网） | 本文件 + `website/README.md` §6 | AES-256-GCM 信封加密、会话、上传面 |
| `packages/allin-governance`（PyPI 包） | 本文件 | 打包映射完整性、门禁出厂口径 |

## 安全相关设计约束（仓库级）

- **凭据不进仓**：令牌/密钥一律不入库（`.gitignore` + `g03-credentials` 门禁双层拦截；
  分层存储原则见 `docs/记录/专题/凭据分层与密钥隔离存储_2026-10-26.md`）。
- **门禁基线棘轮只单向收紧**：放宽门禁必须在提交信息写明理由。
- **依赖监控**：仓根 `.github/dependabot.yml` 周期盯 pip/npm/github-actions（2026-11-04 上移修复）。

> 事故响应（内部）：SEV 分级与响应流程见 `docs/规范/`（事故分级与响应约定）。
