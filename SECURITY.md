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
| `website/`（官网） | 本文件 + `website/README.md` §6（尤其 §6.6 备份纪律） | AES-256-GCM 信封加密、会话、上传面、密钥与密文分离 |
| `packages/allin-governance`（PyPI 包） | 本文件 | 打包映射完整性、门禁出厂口径 |
| CI 凭据防线 | `scripts/secret-scan-allowlist.txt` | 增量扫描与全树门禁共用的注解白名单 |

## 安全相关设计约束（仓库级）

- **凭据不进仓**：令牌/密钥一律不入库（`.gitignore` + `g03-credentials` 门禁双层拦截；
  分层存储原则见 `docs/记录/专题/凭据分层与密钥隔离存储_2026-10-26.md`）。
- **内联豁免注解不是提交内容的权力**（2026-11-07 加固）：`...: allow` 这类注解只在
  `scripts/secret-scan-allowlist.txt` 登记的仓库自有夹具文件内生效。该文件是**受评审的
  仓库配置**；`scripts/scan-secrets.sh` 与 `g03_credentials.py` 共用同一份，出现在其它
  文件一律不再豁免且 CI 直接判失败。新增夹具请先改白名单，不要写在提交内容里。
- **密钥与密文分离**：`website/data/` 禁止整目录复制备份（会同时带走主密钥与密文库）；
  用 `npm run backup:data` + `npm run backup-key` 分两处存放，`npm run check:data-hygiene` 只读体检。
- **门禁基线棘轮只单向收紧**：放宽门禁必须在提交信息写明理由。
- **CI 最小权限 + 有界运行**：`permissions: contents: read`、第三方 action 全部 SHA 钉版、
  每个 job 带 `timeout-minutes`，不设无限等待。
- **依赖监控**：仓根 `.github/dependabot.yml` 周期盯 pip/npm/github-actions（2026-11-04 上移修复）。

> 事故响应（内部）：SEV 分级与响应流程见 `docs/规范/`（事故分级与响应约定）。
