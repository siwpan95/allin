---
name: repo-sync-remote-to-local
description: 把 Gitee/GitHub 远端仓库对齐到本地（"本地落后"场景）的标准流程——现场勘查、fetch 后实况判定、纯落后才快进、IN_SYNC 三方核对、记账汇报。当用户说「把 <repo> 对齐到本地」「本地落后」「重新对齐」时使用。
agent_created: true
---

# 远端仓库对齐到本地（本地落后）

## 适用
用户报告某个 git 仓库「本地落后」，要求从远端（Gitee/GitHub）对齐到本地。这是**纯拉取**（本地动作），不涉及推送放行。

## 标准流程（已两次实战：G:\repos\3dworld，2026-10-08）

### 第 1 步：现场勘查（并行两条）
```bash
git -C <repo> status --porcelain=v1 -b     # 工作树必须干净（有未提交改动→先停下问用户）
git -C <repo> rev-parse HEAD               # 本地现状
git -C <repo> ls-remote origin             # 远端实况（权威）
```
- **判落后量必须以 fetch 后为准**：`status` 显示的 behind 数基于旧的 origin/master 引用，可能过期（实战教训：显示 behind 5、实际 7）。
- 本机注意：Git Bash 环境用 git 2.55.0；`refs/remotes/` 在部分仓不落盘（3dworld 正常落盘），**ls-remote 才是远端权威**。

### 第 2 步：fetch + 判分叉
```bash
git -C <repo> fetch origin master          # 凭据链可能慢，超时给足（≥300s）
git -C <repo> merge-base --is-ancestor <本地HEAD> <远端HEAD> && echo PURE_BEHIND || echo DIVERGED
git -C <repo> log --oneline <本地HEAD>..<远端HEAD>   # 列出将拉入的提交
```
- `PURE_BEHIND` → 继续；`DIVERGED`（本地有独有提交/分叉）→ **停下**，向用户报告并等决策（可能需要 rebase/merge 策略）。
- 工作树**脏**（未提交改动）→ 停下问用户（不能贸然 ff 覆盖）。

### 第 3 步：快进
```bash
git -C <repo> merge --ff-only origin/master
```
- 只用 `--ff-only`；**禁止** reset --hard / 强制操作。

### 第 4 步：IN_SYNC 三方核对（必做）
```bash
echo "LOCAL : $(git -C <repo> rev-parse HEAD)"
echo "REMOTE: $(git -C <repo> ls-remote origin refs/heads/master | cut -f1)"
git -C <repo> status --porcelain=v1 -b     # 应无 ahead/behind 标记
```
- LOCAL == REMOTE 才算完成。

### 第 5 步：记账与汇报
- 追加工作日志：对齐前后 SHA、落后提交数、变更文件数、IN_SYNC 结论。
- 向用户汇报：拉入的提交列表与内容摘要（`git show <sha> --stat`；必要时看关注文件的内容 diff）。

## 陷阱清单
- **behind 数基于过期引用**：见到 status 的 behind 先 fetch 再判定。
- **分叉别硬 ff**：`--is-ancestor` 必须为真；否则停下。
- **fetch/push 慢 ≠ 失败**：本机凭据链耗时可达数十秒~数分钟，超时给 ≥300s；别中途重试打断。
- **汇报数字要留证据**：SHA 用完整 40 位核对（短 SHA 用于展示）。
- 对齐是只读+本地动作，**不要顺手做 push**（推送需用户在场放行，铁律 3）。
