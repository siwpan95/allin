#!/usr/bin/env bash
# CI 安装 gitleaks v8.18.4（与仓根 .pre-commit-config.yaml 同版），GitHub / Gitee 两侧共用。
#
# 为什么不再用 `go install`：
#   ubuntu-latest 已迁移到 Ubuntu 26，runner 的 Go 工具链随之升级；v8.18.4 是
#   2024 年的发行版，其依赖在新版 Go 下可能直接编译失败（2026-11-04 CI 首跑
#   「安装 gitleaks v8.18.4」步骤实测 exit 1）。改为下载官方 release 的**预编译
#   二进制**，并用同一 release 的 gitleaks_8.18.4_checksums.txt 做 SHA256 校验：
#   不依赖 runner 的 Go，版本固定，完整性由官方校验和保证（可审计、可复现）。
#
# 用法：
#   bash scripts/install-gitleaks.sh
#   GITLEAKS_INSTALL_DIR=<目录> bash scripts/install-gitleaks.sh
#   GITLEAKS_BASE_URL=<release 资产根 URL> bash scripts/install-gitleaks.sh
#
# 产物（**固定路径**，这是两侧能共用同一个脚本的关键）：
#   - 二进制始终是 <安装目录>/gitleaks（默认 /tmp/gitleaks-8.18.4/gitleaks）
#   - 若存在 $GITHUB_PATH，把安装目录写入，使后续 step 的 PATH 生效
#   - stdout 末行输出 GITLEAKS_BIN=<固定路径>，便于在同一条命令里取用
#   - Gitee Go 没有 GITHUB_PATH，靠 scripts/scan-secrets.sh 对同一固定路径的兜底发现
#
# GITLEAKS_BASE_URL 覆盖的用途：境内 runner 直连 github.com 的 release 资产可能超时
# （本机实测 45s 0 字节），允许运维指向可达的镜像；镜像必须同时提供同名 tarball 与
# checksums.txt，校验逻辑不变 —— 换源不换校验，才算可审计。
#
# 下载 / 校验 / 解压失败一律 exit 3 —— 凭据防线不允许「假装装过了」。

set -euo pipefail

V="8.18.4"
ASSET="gitleaks_${V}_linux_x64.tar.gz"
CHECKSUMS="gitleaks_${V}_checksums.txt"
BASE_URL="${GITLEAKS_BASE_URL:-https://github.com/gitleaks/gitleaks/releases/download/v${V}}"
DIR="${GITLEAKS_INSTALL_DIR:-/tmp/gitleaks-${V}}"
BIN="$DIR/gitleaks"

# 已装好且版本匹配则直接复用（避免重复下载，也让多次调用幂等）。
if [ -x "$BIN" ] && "$BIN" version 2>/dev/null | grep -q "${V}"; then
  echo "gitleaks: 复用已安装的 v${V}（$BIN）"
  printf 'GITLEAKS_BIN=%s\n' "$BIN"
  exit 0
fi
if command -v gitleaks >/dev/null 2>&1 && gitleaks version 2>/dev/null | grep -q "${V}"; then
  echo "gitleaks: 复用 PATH 中已安装的 v${V}"
  printf 'GITLEAKS_BIN=%s\n' "$(command -v gitleaks)"
  exit 0
fi

mkdir -p "$DIR"
cd "$DIR"

if ! curl -fsSL --retry 3 --connect-timeout 15 -o "$ASSET" "${BASE_URL}/${ASSET}"; then
  echo "ENV ERROR: 下载 ${BASE_URL}/${ASSET} 失败（可设 GITLEAKS_BASE_URL 指向可达镜像）。" >&2
  exit 3
fi
if ! curl -fsSL --retry 3 --connect-timeout 15 -o "$CHECKSUMS" "${BASE_URL}/${CHECKSUMS}"; then
  echo "ENV ERROR: 下载 ${BASE_URL}/${CHECKSUMS} 失败。" >&2
  exit 3
fi

# checksums.txt 里每行形如 "<64 hex>  gitleaks_8.18.4_linux_x64.tar.gz"；
# 用 -F 精确匹配资产名，避免把其它平台的同名前缀行算进来。
EXPECTED="$(grep -F "$ASSET" "$CHECKSUMS" | awk 'NR==1 {print $1}')"
if [ -z "$EXPECTED" ] || [ "${#EXPECTED}" -ne 64 ]; then
  echo "ENV ERROR: ${CHECKSUMS} 中找不到 ${ASSET} 的 64 位 SHA256 校验和。" >&2
  exit 3
fi
if ! echo "${EXPECTED}  ${ASSET}" | sha256sum -c -; then
  echo "ENV ERROR: ${ASSET} 的 SHA256 与官方 ${CHECKSUMS} 不一致。" >&2
  exit 3
fi

# 不假设 tarball 内的目录层级：解到独立子目录再定位名为 gitleaks 的可执行文件，
# 统一安置到固定路径 $BIN —— 两侧 CI 与 scan-secrets.sh 都只认这一个路径。
# 独立子目录是为了避免 tarball 里的二进制恰好叫 gitleaks、与 $BIN 重名时互相干扰。
EXTRACT="$DIR/.extract"
rm -rf "$EXTRACT"
mkdir -p "$EXTRACT"
if ! tar -xzf "$ASSET" -C "$EXTRACT"; then
  echo "ENV ERROR: 解压 ${ASSET} 失败。" >&2
  exit 3
fi
FOUND="$(find "$EXTRACT" -type f -name gitleaks -print -quit)"
if [ -z "$FOUND" ]; then
  echo "ENV ERROR: ${ASSET} 内未找到 gitleaks 可执行文件。" >&2
  exit 3
fi
cp -f "$FOUND" "$BIN"
chmod 0755 "$BIN"
if ! "$BIN" version 2>/dev/null | grep -q "${V}"; then
  echo "ENV ERROR: ${BIN} 版本不是 v${V}（二进制与 release 不匹配）。" >&2
  exit 3
fi

if [ -n "${GITHUB_PATH:-}" ]; then
  echo "$DIR" >> "$GITHUB_PATH"
fi
printf 'GITLEAKS_BIN=%s\n' "$BIN"
