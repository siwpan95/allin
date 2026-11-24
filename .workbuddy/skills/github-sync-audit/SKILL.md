---
name: github-sync-audit
description: >
  G:\repos 本地仓 ↔ GitHub(siwpan95) ↔ gitee 主源(origin) 三端增量巡检的唯一 SOP：
  三端差集判定、先私后公建仓、SSH 通道、shallow clone 拒推、凭据走 GCM 不入库、
  GitHub 限流退避、高风险动作默认 dry-run。触发词：GitHub 增量巡检、三端同步、
  三端对账、批量推 GitHub、GitHub 建仓、github-sync、github-release、repos 巡检、
  automation 增量巡检、待建仓、gitee 为权威的单向校准、远端已删除冻结仓清理。
agent_created: true
---

# 三端增量巡检 SOP（GitHub / gitee / 本地）

> 执行器：`allin-governance github`（建仓/转公开/推 GitHub/独立复核）
> 巡检器：`allin-governance github`（巡检子命令）（盘点/从 gitee 快进/推 GitHub/drift 只读，建仓与复核委托前者）
> 统一入口：`allin tools github-release <...>` / `allin tools github-sync <...>`
> 本技能讲**判定口径与踩坑**，脚本负责执行。参照 `venv-security-audit` 的「判据单一实现」纪律：
> **建仓逻辑只在 github_release.py 一份**，巡检器不得自带第二份。

## 一、为什么上提

原 automation「GitHub 135仓增量巡检」的 cwd 在 WorkBuddy 临时工作区
（`C:\Users\psw\WorkBuddy\2026-10-27-20-12-32`），工具无版本化、无治理、无门禁覆盖。
2026-11-24 上提到 allin，参照两次既有范式：
- `venv-audit`（automation `362347e7`）：工具 + 技能 + `allin tools` 入口 + automation 改指
- `foolproof-operation`（commit `1228432`）：上提判据工具、不搬无关资产、原仓处置先做冗余三查

## 二、三端口径（引用必须带口径，别混用）

| 口径 | 真值获取 | 注意 |
|---|---|---|
| 本地仓数 | `ls -d <发布区>/*/.git \| wc -l`，或工具 `list` | **2026-11-24 实测 75**（含本仓自身；远端 76 = 75 + `anatomy3d` remote-only）；两次清理前为 140（58 冻结 + 9 归档）。任务名「135仓」历史值 |
| GitHub 仓数 | `gh_repos()` 分页 `GET /user/repos?affiliation=owner` | **2026-11-24 实测 76**（与 gitee 一致，含 `allin`；`sin-virtue-game` 已随冻结仓清理删除） |
| gitee 仓数 | `git ls-remote` origin（逐仓） | GitHub 独有 2 中：`allin` 独立双推不在巡检范围；`sin-virtue-game` 已退役（gitee 404） |

**巡检范围**：发布区顶层含 `.git` 的目录。**2026-11-24 起本仓自身也在发布区内**
（仓根由 `<工作区>/allin` 迁至 `<工作区>/repos/allin`），因此同样纳入巡检；
它自己的 origin 已配双推（gitee + github），重复推送幂等无害。
**待建** = 本地有而 GitHub 无；**GitHub 独有** = GitHub 有而本地无（不算失败，需人工判定是否遗漏检出）。

## 三、平台差异（Gitee 与 GitHub 不能照搬）

| 维度 | Gitee（`gitee_release.py`） | GitHub（`github_release.py`） |
|---|---|---|
| 建仓可见性 | `public` 整数 0/1/2 与 `private` 互斥；**空仓不能设公开**，先私后公再 PATCH `{"name":...,"private":false}` | `private` 布尔；建仓给 `private=True`，推完 PATCH `private=False`；无 Gitee 那套空仓坑 |
| 令牌 | `GITEE_TOKEN` → GCM `host=gitee.com` | `GITHUB_TOKEN` → GCM `host=github.com`（classic 需 `repo` scope；fine-grained 需 Administration(write)/Repository creation(write)） |
| 推送通道 | HTTPS 直推 | **本环境 443 被封**，必须 SSH `git@github.com:siwpan95/<name>.git`；REST 建仓仍走 api.github.com |
| shallow clone | 可推 | **拒收**（`did not receive expected object` / `remote unpack failed`）→ 推前 `git fetch --unshallow origin` |
| 限流 | 新建项目配额极紧（用户 20/h、IP 40/h、attempt 100/h），撞限后按小时间隔重试**无效**，退避 1 次即收工 | 主限流 5000/h（`x-ratelimit-*` 权威）；次级内容创建 80/min、500/h（POST 计 5 points）；超限 403/429 + `Retry-After` 或 `x-ratelimit-reset`，按头退避即可 |

## 四、安全边界（写死，不提供绕过开关）

按原 automation 提示词逐字保留，且脚本内置：

1. **工作区脏**（`git status --porcelain -uno`，只看已跟踪改动）→ 只报告，不自动处理
2. **detached HEAD** → 只报告
3. **与远端分叉或本地领先** → 只报告，**绝不自动 rebase/merge**
4. **权威关系（2026-11-24 全哥明确）**：**gitee 远端 = 唯一权威源**，本地与 GitHub 都是下游。方向严格单向 gitee → 本地 → GitHub。**绝不向 gitee 推送**（原 `pushorigin` 语义已废止，改为只读 `drift` 报告）。本地领先/分叉 → 只报告；若该提交确有价值，须人工决定是否提升到 gitee 成为新权威
5. **默认 dry-run**：`allin tools github-sync sync` 不带 `--apply` 只报告；建仓/推送属高风险，须人在场放行
6. `sin-virtue-game` gitee 已 404，GitHub 侧保留归档副本，不为其建 gitee 仓
7. 令牌绝不入库、不回显；`--token-file` 仅供显式外部文件

## 五、完成判据（硬性）

沿用 venv-audit 的教训：**后台任务不跨轮存活**，所以「任务报告成功」不算完成。必须：

```bash
cd /g/allin
ALLIN_REPOS_ROOT=/g/repos allin-governance github verify
```

以独立前台命令输出的 `VERIFY_SUMMARY total=75 ok=75 bad=0` 为准（2026-11-24 清理后的基线；
`skip` 只应出现在 GitHub 无对应仓的仓上）。
**看不到这一行就不算完成**，不允许用脚本自称成功替代。

## 六、已知坑（脚本已内置，了解即可）

- 部分仓是 shallow clone：GitHub 拒收 shallow push → 自动 `git fetch --unshallow origin`（超时给 1200s）
- GitHub 内容创建二级限流：撞 403/429 按 `Retry-After` 退避；不可用 Gitee 的「退避 1 次即收工」套用
- 响应头大小写：Python `dict(resp.headers)` 的键是 `X-OAuth-Scopes`（首字母大写）；曾因取 `x-oauth-scopes` 小写键误判「fine-grained」，实际是 classic PAT 含全 scope。**取头先看原始大小写**
- `pushed_done.txt` 历史上被并发写重复过，**不作为完成判据**；只以 `verify` 独立复核为准
- `--repos-root` 必给或设 `ALLIN_REPOS_ROOT`；工具不写死盘符（铁律 5）

## 七、与既有技能的分工

| 技能 | 管什么 |
|---|---|
| `repo-sync-remote-to-local` | **单仓**「本地落后」场景：现场勘查 → fetch → PURE_BEHIND 才快进 → 三方核对 |
| 本技能 | **批量全发布区**三端巡检：差集盘点 + 建仓 + 推送 + 只读偏离 + 独立复核 |
| `github-release-source-archive-download` | GitHub release 源码包下载归档（different 场景） |
| `gitee-push-from-extracted-dir` | Gitee 从解压目录推送（different 场景） |
