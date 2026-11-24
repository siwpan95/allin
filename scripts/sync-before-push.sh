#!/usr/bin/env bash
# 推送前同步：先 fetch，落后就 ff-only 拉取，再（可选）推送并核对双端。
#
# 为什么要有这个脚本（2026-11-24 事故直接产物）：
#   那天 allin 与远端**分叉**了 —— 另一条工作线推了 5 个提交，本地攒了 8 个。
#   `git push` 被拒之后的第一反应往往是 `push -f` 或 `pull`（默认 merge），
#   前者改写历史（违反 SPEC-004 铁律 70），后者在分叉时制造一个没人想要的合并提交。
#   真正的顺序只有一条：**先 fetch 看清关系，再决定拉还是报**。
#
# 纪律（已写进 SPEC-101 §7 / SPEC-004 第 71 条）：
#   1. 提交前可以先不 fetch；**推送前必须先 fetch**。
#   2. 远端只领先（本地落后）→ `git pull --ff-only`，**不产生合并提交**。
#   3. 两边都有提交（diverged）→ **停下报人**，不自动 rebase / merge / push -f。
#   4. 工作区脏 → 先提交或暂存，**不允许**带着脏改动拉取。
#   5. 推完必须用 `git ls-remote` 逐端核对 SHA，不以"命令没报错"为证据。
#
# 用法：
#   bash scripts/sync-before-push.sh                # 只报告关系（只读，安全）
#   bash scripts/sync-before-push.sh --apply        # 落后则 ff-only 拉取
#   bash scripts/sync-before-push.sh --apply --push # 拉取后推送，并核对双端
#   bash scripts/sync-before-push.sh --branch main  # 换分支（默认 master）
#
# 退出码：0 已就绪/已完成 ｜ 2 需要人工处理（分叉/脏工作区/推送被拒）｜ 3 环境错

set -u

BRANCH="master"
APPLY=0
PUSH=0
REMOTES="origin github"

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --push) PUSH=1 ;;
    --branch) BRANCH="${2:-}"; shift ;;
    --remotes) REMOTES="${2:-}"; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "USAGE: 未知参数 $1" >&2; exit 2 ;;
  esac
  shift
done

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ENV ERROR: 不在 git 仓库内" >&2
  exit 3
fi

echo "== 1/3 fetch（只更新远端跟踪引用，不动工作区）"
if ! git fetch origin --prune 2>&1 | sed 's/^/   /'; then
  echo "ENV ERROR: git fetch origin 失败（网络或凭据）" >&2
  exit 3
fi

UP="origin/$BRANCH"
if ! git rev-parse --verify --quiet "$UP" >/dev/null; then
  echo "ENV ERROR: 远端没有 $UP（分支名写错，或从未推送过）" >&2
  exit 3
fi

AHEAD=$(git rev-list --count "$UP..HEAD")
BEHIND=$(git rev-list --count "HEAD..$UP")
HEAD_SHA=$(git rev-parse HEAD)
UP_SHA=$(git rev-parse "$UP")

echo "== 2/3 关系：本地 $BRANCH = ${HEAD_SHA:0:8} ｜ $UP = ${UP_SHA:0:8}"
echo "   领先 $AHEAD ｜ 落后 $BEHIND"

DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$DIRTY" != "0" ]; then
  echo "   工作区：$DIRTY 个未提交变更"
fi

if [ "$AHEAD" = "0" ] && [ "$BEHIND" = "0" ]; then
  echo "   结论：**已同步**（无本地提交，无远端更新）"
elif [ "$AHEAD" != "0" ] && [ "$BEHIND" = "0" ]; then
  echo "   结论：**本地领先** $AHEAD 个提交 —— 可直接推送"
elif [ "$AHEAD" = "0" ] && [ "$BEHIND" != "0" ]; then
  echo "   结论：**本地落后** $BEHIND 个提交 —— 需要 ff-only 拉取"
else
  echo "   结论：**已分叉**（本地多 $AHEAD / 远端多 $BEHIND）—— 停下报人"
  echo "   处置：先看远端改了什么（git log --oneline HEAD..$UP），再决定 rebase 还是合并；"
  echo "         禁止 push -f，禁止在没看清前拉取。"
  exit 2
fi

if [ "$BEHIND" != "0" ]; then
  if [ "$APPLY" = "0" ]; then
    echo "   （未加 --apply：只报告，不拉取）"
    exit 0
  fi
  if [ "$DIRTY" != "0" ]; then
    echo "   拒绝拉取：工作区有未提交变更。先提交或 stash，再重跑。" >&2
    exit 2
  fi
  echo "== 拉取（--ff-only，不产生合并提交）"
  if ! git pull --ff-only origin "$BRANCH" 2>&1 | sed 's/^/   /'; then
    echo "   拉取失败：远端可能刚又被推进。重跑本脚本即可（幂等）。" >&2
    exit 2
  fi
  HEAD_SHA=$(git rev-parse HEAD)
  echo "   拉取后 HEAD = ${HEAD_SHA:0:8}"
fi

if [ "$PUSH" = "0" ]; then
  echo "== 3/3 未加 --push：仍逐端核对（只读）"
  mismatched=0
  for remote in $REMOTES; do
    got=$(git ls-remote "$remote" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)
    if [ "$got" = "$HEAD_SHA" ]; then
      printf '   [ok]   %-8s %s\n' "$remote" "${got:0:8}"
    else
      printf '   [FAIL] %-8s 远端 %s ≠ 本地 %s\n' "$remote" "${got:0:8}" "${HEAD_SHA:0:8}"
      mismatched=1
    fi
  done
  [ "$mismatched" = "0" ] && exit 0
  echo "   有远端未同步（本地已提交但没推上去）—— 加 --push 重跑。" >&2
  exit 2
fi

if [ "$DIRTY" != "0" ]; then
  echo "   拒绝推送：工作区有未提交变更（推送只发已提交内容，别让改动悄悄落队）。" >&2
  exit 2
fi

AHEAD=$(git rev-list --count "$UP..HEAD")
if [ "$AHEAD" = "0" ]; then
  echo "== 3/3 本端无待推提交（远端可能仍有未同步的另一端，下面逐端核对）"
else
  echo "== 3/3 推送 $AHEAD 个提交到 origin"
  if ! git push origin "$BRANCH" 2>&1 | sed 's/^/   /'; then
    echo "   推送被拒。**不要** push -f：重跑本脚本，按提示处理。" >&2
    exit 2
  fi
fi

# 逐端核对。⚠ `origin` 可以配多个 pushurl（本仓 = Gitee + GitHub），但那**只对
# `origin` 一个名字生效**；本仓另有独立 `github` remote，`push origin` 不会碰它。
# 2026-11-24 实测：只核 origin 时脚本报「已同步」，而 GitHub 落后 4 个提交。
for remote in $REMOTES; do
  got=$(git ls-remote "$remote" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)
  if [ "$got" = "$HEAD_SHA" ]; then
    printf '   [ok]   %-8s %s\n' "$remote" "${got:0:8}"
    continue
  fi
  echo "   [warn] $remote 落后（远端 ${got:0:8}）→ 单独补推"
  if ! git push "$remote" "$BRANCH" 2>&1 | sed 's/^/      /'; then
    echo "   [FAIL] $remote 推送失败（可能被远端策略拦下，如 push protection）" >&2
    exit 2
  fi
  got=$(git ls-remote "$remote" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)
  if [ "$got" != "$HEAD_SHA" ]; then
    printf '   [FAIL] %-8s 补推后仍不一致 %s\n' "$remote" "${got:0:8}" >&2
    exit 2
  fi
  printf '   [ok]   %-8s %s（补推）\n' "$remote" "${got:0:8}"
done

echo "== 完成：本地与远端 SHA 逐端一致"
exit 0
