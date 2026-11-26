#!/usr/bin/env bash
# 一次性把本仓的 git 钩子装好（每台机器 / 每个 clone 各跑一次）
#
# 为什么需要"装"这一步：`core.hooksPath` 是**仓库本地配置**，不入库；
# `.git/hooks/` 也不入库。所以钩子文件在仓库里，但"让 git 真的调用它"这件事
# 必须每台机器各做一次 —— 忘了做，钩子文件就是纯装饰（本仓老坑：装了但没人装）。
#
# 两条互斥路径，本脚本只选一条（同时开会互相看不见，见下方"互斥"）：
#   A. hooksPath（默认，零依赖）：`git config core.hooksPath tools/gate/hooks`
#      ⇒ git 直接调用 `tools/gate/hooks/{pre-commit,commit-msg}`。
#      本仓 README §11 的既有机制，只需 git 本身。
#   B. pre-commit（需已安装 `pre-commit`）：`.pre-commit-config.yaml` 里挂了
#      gitleaks + 基础钩子 + local 的 commit-msg；由 pre-commit 生成 `.git/hooks/*`。
#
# 互斥：设了 `core.hooksPath` 之后 git **只**看那个目录，`.git/hooks/` 一律不调用。
# 所以切到 B 必须先 `git config --unset core.hooksPath`，否则你以为在跑 gitleaks，
# 其实什么都没跑（这是最坏的一种状态：装了两套，一套生效、一套纯装饰）。
#
# 装好之后仍然**不完整**：Gitee / GitHub 网页端提交与合并**根本不经过本地钩子**。
# 那类提交由 `tools/gate/check_machine_trailer.py` 在跑批时判（并把
# "技术上无法带 trailer" 的 merge / squash 单独列出，不与"忘了写"混为一谈）。
set -u

mode="hooks-path"
for arg in "$@"; do
  case "$arg" in
    --pre-commit) mode="pre-commit" ;;
    --check) mode="check" ;;
    -h|--help)
      sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数：$arg（可用：--pre-commit / --check）" >&2; exit 2 ;;
  esac
done

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "ENV ERROR: 当前目录不是 git 仓。" >&2; exit 3
}
cd "$root" || exit 3

current=$(git config --get core.hooksPath || true)
hook_files="$(ls -1 tools/gate/hooks 2>/dev/null | tr '\n' ' ')"
generated=""
if [ -f .git/hooks/commit-msg ] || [ -f .git/hooks/pre-commit ]; then
  generated=".git/hooks 下有已生成的钩子"
fi

if [ "$mode" = "check" ]; then
  echo "core.hooksPath = ${current:-<未设置>}"
  echo "仓内钩子文件   = ${hook_files:-<无>}"
  echo "pre-commit     = $(command -v pre-commit || echo '<未安装>')"
  echo ".git/hooks     = ${generated:-<无已生成钩子>}"
  if [ -n "$current" ] && [ -n "$generated" ]; then
    echo "⚠ 两套同时存在：生效的是 hooksPath（$current），.git/hooks 下那份不会被调用。"
  fi
  [ -n "$current" ] || echo "⚠ 未设 core.hooksPath：仓内钩子当前**一个都不会被执行**。"
  exit 0
fi

if [ "$mode" = "pre-commit" ]; then
  if ! command -v pre-commit >/dev/null 2>&1; then
    echo "ENV ERROR: 未安装 pre-commit（pipx install pre-commit 或 pip install pre-commit）。" >&2
    echo "           零依赖路线：bash scripts/install_git_hooks.sh（走 core.hooksPath）。" >&2
    exit 3
  fi
  if [ -n "$current" ]; then
    echo "解除 core.hooksPath=$current（否则 .git/hooks 下的 pre-commit 钩子是死的）"
    git config --unset core.hooksPath
  fi
  pre-commit install --hook-type pre-commit --hook-type commit-msg
  echo "已装：pre-commit + commit-msg（生成在 .git/hooks/）"
else
  if [ -z "$hook_files" ]; then
    echo "ENV ERROR: tools/gate/hooks/ 下没有钩子文件。" >&2; exit 3
  fi
  git config core.hooksPath tools/gate/hooks
  echo "已设 core.hooksPath=tools/gate/hooks（生效：$hook_files）"
  if [ -n "$generated" ]; then
    echo "⚠ .git/hooks 下仍有已生成的钩子，它们现在不会被调用（若那是 gitleaks，改用 --pre-commit）"
  fi
fi

git config --get core.hooksPath >/dev/null && echo "复核：git config core.hooksPath = $(git config --get core.hooksPath)"
echo "验证：git commit --allow-empty -m 'chore: 验钩子' 后看 git log -1 --format=%B 是否含 'Machine:'"
echo "提醒：网页端提交 / 合并（Gitee PR、GitHub PR）**绕过本地钩子**，那类提交由"
echo "      'python tools/gate/check_machine_trailer.py' 在跑批时判（merge / squash 单列）。"
