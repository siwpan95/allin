#!/usr/bin/env bash
# allin bootstrap —— 一条命令把本仓变成「可跑门禁的工作区」。
#
# 为什么需要它（对应 docs/新人开发上手指南.md 附录 A 第 1 条）：
# 本仓**没有根级 requirements.txt**，历史上新人只能靠读代码反推该装什么
# （`pyyaml` / `watchdog` 是从 _cordis_locate.py 的报错提示里猜出来的）。
# 这个脚本把那段「猜」固化成一条可复跑的命令。
#
# 它做什么（幂等，重复跑安全）：
#   1. 建仓内 .venv（若已有则复用，不重建）
#   2. 装齐依赖：PyYAML（g18-exceptions / kernel/tree.py 必需）+
#      watchdog（cordis 的 hmr 可选增强，缺失时 cordis 退回 mtime 轮询）
#   3. 建 docs/ 下的 ASCII 别名（spec/ facts/ records/ 历史/）——
#      别名是 junction/symlink，**不入库**，换机或克隆后必须重建
#   4. 装 Node 侧依赖（platform 必装；website 用 --with-node）——
#      干净检出缺 node_modules 时 portal 会 ERR_MODULE_NOT_FOUND 启动即崩
#   5. 打印下一步命令（跑门禁 / 看门禁自检）
#
# 换机纪律（2026-11-10 整改）：本脚本**不再有静默跳过**——
#   · 无 pwsh 时改用 cmd 内建 mklink /J 建 junction（原先只 echo 警告就跳过，
#     导致 g15 的 D6 必红而用户以为环境就绪 = 假绿的第一处）；
#   · Node 依赖未装时如实说明「哪些能力会降级为 not_applicable」。
#
# 用法：
#   bash scripts/bootstrap.sh
#   bash scripts/bootstrap.sh --no-aliases   # 跳过别名（Linux/CI 上别名意义有限）
#   bash scripts/bootstrap.sh --with-node     # 连 website 依赖一并装
#
# 退出码：0 = 全部完成；非 0 = 某一步失败（说明哪一步，不静默吞错）

set -euo pipefail

# 脚本自身路径（绝对）：ROOT 由它推导。
# 用绝对路径而非相对路径，是因为脚本中段会 cd 到 ROOT —— 之后若再以相对路径
# 引用 BASH_SOURCE（比如 --help 里读本文件），会因工作目录已变而读不到自己。
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
SKIP_ALIASES=0
WITH_NODE=0
for arg in "$@"; do
  case "$arg" in
    --no-aliases) SKIP_ALIASES=1 ;;
    --with-node) WITH_NODE=1 ;;
    -h|--help)
      sed -n '2,34p' "$SELF" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数：$arg（用 --help 看用法）" >&2; exit 2 ;;
  esac
done

say() { printf '\n== %s\n' "$1"; }
die() { printf '!! %s\n' "$1" >&2; exit 1; }
# 步骤计数（2026-11-10：新增 Node 依赖步，共 5 步；此前硬编码 /4 会误导）
STEP=0
TOTAL_STEPS=5
step() { STEP=$((STEP + 1)); say "$STEP/$TOTAL_STEPS $1"; }

# ---------------------------------------------------------------- 1) 解释器
step "选定 Python 解释器"
PY_BOOTSTRAP=""
for cand in python3.13 python3.12 python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' 2>/dev/null; then
      PY_BOOTSTRAP="$cand"; break
    fi
  fi
done
[ -n "$PY_BOOTSTRAP" ] || die "找不到 Python >= 3.12（内核要求；repocheck 只要 >= 3.11）。
  装一个再跑，或用 pyenv/mise 选版本。已装的可显式指定：ALLIN_BOOTSTRAP_PYTHON=/path/to/python bash scripts/bootstrap.sh"
echo "   解释器：$PY_BOOTSTRAP（$("$PY_BOOTSTRAP" --version 2>&1)）"

# ---------------------------------------------------------------- 2) venv
step "准备仓内 .venv"
if [ -x "$VENV/bin/python" ] || [ -x "$VENV/Scripts/python.exe" ]; then
  echo "   已存在，复用：$VENV"
else
  "$PY_BOOTSTRAP" -m venv "$VENV" || die "创建 venv 失败"
  echo "   已创建：$VENV"
fi
if [ -x "$VENV/bin/python" ]; then VENV_PY="$VENV/bin/python"; else VENV_PY="$VENV/Scripts/python.exe"; fi
echo "   解释器：$VENV_PY"

# ---------------------------------------------------------------- 3) 依赖
step "安装依赖"
# PyYAML 是硬依赖：g18-exceptions 要解析 exceptions.yml，kernel/tree.py 要读 cordis 配置树。
# watchdog 是 cordis 的 hmr 可选增强（cordis[hmr]）；缺它 cordis 退回 mtime 轮询，不崩。
# 两者都装，是为了让「换台机器跑出同样结论」成立，而不是让新人踩 g18 假红。
if "$VENV_PY" -c 'import yaml' >/dev/null 2>&1 && "$VENV_PY" -c 'import watchdog' >/dev/null 2>&1; then
  echo "   PyYAML 与 watchdog 均已就位，跳过安装"
else
  "$VENV_PY" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "$VENV_PY" -m pip install -r "$ROOT/requirements-dev.txt" || die "依赖安装失败（检查网络，或用国内镜像：-i https://pypi.tuna.tsinghua.edu.cn/simple）"
  echo "   已安装 requirements-dev.txt"
fi
"$VENV_PY" -c 'import yaml; print("   PyYAML", yaml.__version__)'

# ---------------------------------------------------------------- 4) ASCII 别名
step "建 docs/ ASCII 别名"
# 别名是 junction（Windows）/ symlink（POSIX），**不入库**（.gitignore 已屏蔽），
# 换机或克隆后必须重建。不建的话门禁 g15 的 D6 会报「别名缺失」。
#
# 两条路径：
#   Windows：走权威实现 tools/gate/make_doc_aliases.ps1（junction，不需要管理员）
#   POSIX  ：直接 ln -s（原生支持，不需要 pwsh）—— 这条是 2026-10-31 补的：
#            此前脚本只在有 pwsh 时才建别名，导致 Linux CI 上 D6 必然红，
#            而 D6 本来在 Linux 上是**能真正判**的（symlink 天然支持）。跳过它
#            等于用 --no-aliases 把一个能判的判据关掉，属于「假绿」的另一种形态。
# 判定宿主是 Windows（Git Bash/MSYS/Cygwin）还是 POSIX（Linux/macOS 原生）
IS_WINDOWS=0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) IS_WINDOWS=1 ;;
esac

if [ "$SKIP_ALIASES" = "1" ]; then
  echo "   已按参数跳过（--no-aliases）"
elif [ "$IS_WINDOWS" = "0" ]; then
  # POSIX：docs/<别名> -> docs/<真身>，已存在且指向正确的跳过（幂等）
  created=0; kept=0; failed=0
  for pair in "spec:规范" "facts:事实源" "records:记录" "历史:md"; do
    alias_name="${pair%%:*}"; real_name="${pair##*:}"
    ap="$ROOT/docs/$alias_name"; rp="$ROOT/docs/$real_name"
    if [ ! -d "$rp" ]; then
      echo "   !! 真身目录缺失：docs/$real_name"; failed=$((failed+1)); continue
    fi
    if [ -L "$ap" ] && [ "$(readlink "$ap" 2>/dev/null)" = "$rp" ]; then
      kept=$((kept+1)); continue
    fi
    rm -rf "$ap" 2>/dev/null || true
    if ln -s "$rp" "$ap" 2>/dev/null; then created=$((created+1)); else echo "   !! 建别名失败：docs/$alias_name"; failed=$((failed+1)); fi
  done
  echo "   已建 $created 个、已存在 $kept 个、失败 $failed 个（POSIX symlink）"
  [ "$failed" = "0" ] || die "别名重建有失败项（见上）"
elif command -v pwsh >/dev/null 2>&1; then
  # 权威实现：tools/gate/make_doc_aliases.ps1（Windows 用 junction，管理员不需要）
  pwsh -File "$ROOT/tools/gate/make_doc_aliases.ps1" || die "别名重建失败（Windows 上若因权限失败，看 FAQ 第 6 条）"
  echo "   已用 make_doc_aliases.ps1 重建"
elif command -v cmd.exe >/dev/null 2>&1 && command -v cygpath >/dev/null 2>&1; then
  # 2026-11-10 换机可移植整改：无 pwsh 时**不再静默跳过**（那会让 g15 的 D6 必红，
  # 而用户以为环境就绪 —— 假绿的第一处）。改用 cmd 内建的 mklink /J 建 junction：
  # 不依赖 PowerShell 7，权限要求与 pwsh 路径相同（junction 不需要管理员）。
  created=0; kept=0; failed=0
  for pair in "spec:规范" "facts:事实源" "records:记录" "历史:md"; do
    alias_name="${pair%%:*}"; real_name="${pair##*:}"
    ap="$ROOT/docs/$alias_name"; rp="$ROOT/docs/$real_name"
    if [ ! -d "$rp" ]; then
      echo "   !! 真身目录缺失：docs/$real_name"; failed=$((failed+1)); continue
    fi
    ap_win="$(cygpath -w "$ap" 2>/dev/null || printf '%s' "$ap")"
    rp_win="$(cygpath -w "$rp" 2>/dev/null || printf '%s' "$rp")"
    if [ -e "$ap" ] || [ -L "$ap" ]; then
      # rmdir 只删链接本身（非空目录会失败），比 rm -rf 安全（不会误删真身内容）
      cmd.exe //c "rmdir \"$ap_win\"" >/dev/null 2>&1 || rm -rf "$ap" 2>/dev/null || true
    fi
    if cmd.exe //c "mklink /J \"$ap_win\" \"$rp_win\"" >/dev/null 2>&1; then
      created=$((created+1))
    else
      echo "   !! 建别名失败：docs/$alias_name"; failed=$((failed+1))
    fi
  done
  echo "   已建 $created 个、失败 $failed 个（cmd mklink /J，无 pwsh 路径）"
  [ "$failed" = "0" ] || die "别名重建有失败项（见上）—— g15 的 D6 会红，必须先解决"
else
  echo "   !! 无法重建别名：既无 pwsh，也无 cmd.exe+cygpath。"
  echo "     别名是 junction/symlink、不入库；缺了 g15 的 D6 必红。"
  die "请装 PowerShell 7（pwsh），或在 Git Bash/WSL 下重跑本脚本"
fi

# ---------------------------------------------------------------- 5) Node 侧依赖
step "安装 Node 侧依赖（platform / website）"
# 2026-11-10 换机可移植整改：干净检出里 platform/node_modules 与 website/node_modules
# 不存在 ⇒ portal 的 ESM 首行 import '@allin/core' 直接 ERR_MODULE_NOT_FOUND，
# 「按 bootstrap 走完仍起不来」。这里默认装 platform（门户启动的硬前提）；
# website 体量较大，用 --with-node 一并装。不装的后果在下方如实标注。
install_node() {
  local dir="$1"
  if [ ! -f "$ROOT/$dir/package-lock.json" ]; then
    echo "   -- $dir 无 package-lock.json，跳过"
    return 0
  fi
  if [ -d "$ROOT/$dir/node_modules" ]; then
    echo "   -- $dir 依赖已存在，跳过"
    return 0
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "   !! 找不到 npm —— $dir 依赖未安装（该目录相关能力将降级为 not_applicable）"
    return 1
  fi
  echo "   -- 安装 $dir 依赖（npm ci，需网络或已配置的镜像）..."
  npm ci --prefix "$ROOT/$dir" --no-audit --no-fund || return 1
  echo "   -- $dir 依赖已就位"
  return 0
}

node_ok=1
install_node platform || node_ok=0
if [ "$WITH_NODE" = "1" ]; then
  install_node website || node_ok=0
fi
if [ "$node_ok" != "1" ]; then
  echo "   ⚠ 部分 Node 依赖未就位：platform 门户与 smoke:e2e 会记为 not_applicable"
  echo "     （跑批汇总会如实列出，不再是「什么都没检查却全绿」）。"
  echo "     修复：npm ci --prefix platform --prefix website  （或配好 npm 镜像）"
fi

# ---------------------------------------------------------------- 下一步
cat <<'EOF'

== 完成。门禁基线已就绪，下一步：

  # 跑全部门禁（期望：末尾「全部门禁通过。」、退出码 0）
  bash scripts/run_all_gates.sh

  # 治理门禁（npm 入口，含自检）
  npm run check:governance

  # 文档索引契约（期望：存量应为 0）
  python tools/gate/docs_index.py --no-baseline --list-all

  # 如需集成平台（Node 侧）：platform 依赖通常已由本脚本装好
  cd platform && npm test

  # 若上面报「依赖未就位」，手工补装（国内网络可加 --registry=https://registry.npmmirror.com）：
  #   npm ci --prefix platform && npm ci --prefix website

EOF
echo "   （Windows 上若中文输出乱码：用 allin.bat，或设 PYTHONIOENCODING=utf-8）"
