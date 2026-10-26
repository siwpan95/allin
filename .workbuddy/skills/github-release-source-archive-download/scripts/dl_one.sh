#!/usr/bin/env bash
# Download one GitHub release source archive (.zip or .tar.gz) reliably in this sandbox.
#
# Usage:
#   bash dl_one.sh <owner>/<repo> <TAG> <DEST_DIR> <zip|tar.gz>
#
# Notes baked in from hard-won experience:
#   - codeload.github.com FIRST: ghproxy-style mirrors truncate large files mid-transfer.
#   - unique temp filename per attempt: `rm` can hang via the safe-bin trash shim.
#   - validate via /tmp copy: checking tar/unzip directly on G:/D: gives FALSE negatives.
#   - single file `mv` into DEST is byte-preserving (md5-verified).
#   - idempotent: skips if a valid file already exists.
set -u

REPO="$1"        # e.g. deepseek-ai/deepseek-harness
TAG="$2"         # e.g. dsh-v0.2.0-rc.2  (mind repo-specific prefixes!)
DST="$3"         # e.g. D:/deepseek harness GitHub
EXT="$4"         # zip | tar.gz
DLDIR="${TMPDIR:-/tmp}/_ghd"
LOG="$DLDIR/dl_${TAG}_${EXT}.log"
mkdir -p "$DST" "$DLDIR"
: > "$LOG"
RUN="$$"

final="$DST/${TAG}-source.$EXT"

echo "downloading $TAG source.$EXT -> $DST" >> "$LOG"

if [ -s "$final" ]; then
  cp "$final" "/tmp/_pre.$EXT"
  if   [ "$EXT" = "zip" ]    && unzip -tq "/tmp/_pre.zip"    >/dev/null 2>&1; then echo "SKIP already valid" >> "$LOG"; echo "DONE" >> "$LOG"; exit 0
  elif [ "$EXT" = "tar.gz" ] && tar -tzf "/tmp/_pre.tar.gz"  >/dev/null 2>&1; then echo "SKIP already valid" >> "$LOG"; echo "DONE" >> "$LOG"; exit 0
  fi
fi

if [ "$EXT" = "zip" ]; then
  urls=(
    "https://codeload.github.com/${REPO}/zip/refs/tags/${TAG}"
    "https://ghproxy.net/https://github.com/${REPO}/archive/refs/tags/${TAG}.zip"
    "https://mirror.ghproxy.com/https://github.com/${REPO}/archive/refs/tags/${TAG}.zip"
    "https://github.moeyy.xyz/https://github.com/${REPO}/archive/refs/tags/${TAG}.zip"
  )
else
  urls=(
    "https://codeload.github.com/${REPO}/tar.gz/refs/tags/${TAG}"
    "https://ghproxy.net/https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"
    "https://mirror.ghproxy.com/https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"
    "https://github.moeyy.xyz/https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"
  )
fi

for attempt in $(seq 1 5); do
  for url in "${urls[@]}"; do
    tmp="$DLDIR/${TAG}-source.$EXT.a${attempt}.$RUN"
    echo "attempt $attempt via ${url:0:52}" >> "$LOG"
    if curl -fsSL --connect-timeout 25 --max-time 3300 --speed-limit 1200 --speed-time 35 \
         -o "$tmp" "$url" && [ -s "$tmp" ]; then
      sz=$(wc -c <"$tmp")
      echo "  got $sz bytes, validating..." >> "$LOG"
      cp "$tmp" "/tmp/_ck.$EXT"
      if   [ "$EXT" = "zip" ]    && unzip -tq "/tmp/_ck.zip"   >/dev/null 2>&1; then ok=1
      elif [ "$EXT" = "tar.gz" ] && tar -tzf "/tmp/_ck.tar.gz" >/dev/null 2>&1; then ok=1
      else ok=0; fi
      if [ "$ok" = 1 ]; then
        mv -f "$tmp" "$final"
        echo "OK ${EXT} -> ${final} ($sz bytes)" >> "$LOG"; echo "DONE" >> "$LOG"; exit 0
      else
        echo "  INVALID (truncated) size=$sz" >> "$LOG"
      fi
    else
      echo "  curl FAIL $(wc -c <"$tmp" 2>/dev/null)" >> "$LOG"
    fi
  done
done

echo "GIVEUP $EXT" >> "$LOG"
echo "DONE" >> "$LOG"
exit 1
