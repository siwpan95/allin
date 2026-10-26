---
name: github-release-source-archive-download
description: 在本沙箱环境中下载 GitHub 仓库 release 的源码归档（自动生成的 .zip / .tar.gz），处理镜像截断、代理失效、路径校验假阴性与 rm 挂起等陷阱。当用户要求「下载某 release/某 tag 的全部附件」「拉取 GitHub release 源码包」「releases 页面附件下载到 X 目录」，且目标仓库 release 无上传二进制资产时使用。
agent_created: true
---

# GitHub release 源码归档下载（沙箱环境）

## 适用场景
GitHub release 页面的「附件」通常只有两类：
1. **上传的二进制资产**（`assets` 非空）→ 需逐个下载 `browser_download_url`。
2. **自动生成的源码归档**（`assets` 为空，绝大多数仓库，如 `deepseek-ai/deepseek-harness`）→ 每个 tag 一份 `Source code (zip)` + `Source code (tar.gz)`。

本技能针对第 2 类。

## 第一步：先核实 release 真实内容（不要猜）
```bash
# ⚠️ 坑1：tag 常带前缀。仓库 tag 可能是 dsh-v0.2.0-rc.2，
#         而 release "名字" 才是 v0.2.0-rc.2。用错前缀查 API 会 404。
curl -fsSL "https://api.github.com/repos/<owner>/<repo>/releases?per_page=5" | grep -E '"tag_name"|"name"'
curl -fsSL "https://api.github.com/repos/<owner>/<repo>/releases/tags/<带前缀的tag>" > /tmp/rel.json
# 确认 assets 数组长度：
python -c "import json;d=json.load(open('/tmp/rel.json'));print('assets:',len(d['assets']));[print(a['name'],a['size'],a['browser_download_url']) for a in d['assets']]"
```
`assets: 0` → 只需下载两份源码归档。

官方归档 URL（cag方管 undocumented 但稳定）：
- zip:     `https://codeload.github.com/<owner>/<repo>/zip/refs/tags/<TAG>`
- tar.gz:  `https://codeload.github.com/<owner>/<repo>/tar.gz/refs/tags/<TAG>`

## 核心陷阱（本技能存在的理由）

| # | 陷阱 | 规避方法 |
|---|---|---|
| 1 | **`ghproxy.net` 等代理镜像对大文件（>~15MB，尤其 >40MB）会在中途截断**（`curl: (18) transfer closed`），并间歇性 `502` / `schannel SSL(35)` | **优先 `codeload.github.com` 直连**。实测直连稳定且更快（约 70–78 KB/s）；ghproxy 仅作兜底。且这些镜像**均不支持 HTTP Range**（`-C -` 报 33，`-r` 返回 200 忽略），无法续传，只能整文件重下。 |
| 2 | **直接对目标盘路径（`G:` / `D:`）跑 `tar -tzf` / `unzip -t` 会不可靠地报假失败** | 校验铁律：**先 `cp` 到 `/tmp` 再校验**。否则会把完好的文件误判为"全部损坏"，导致大量无效返工。 |
| 3 | **`rm` / `rm -f` 清理临时文件可能被 safe-bin trash shim 挂起**，使 curl 失败后的重试链卡死 | 每次尝试用**唯一临时文件名**（`${TAG}-source.zip.a${attempt}.$$`），**完全不用 `rm`**。残留留在 `_dl` 无害。同理避免 `rm -rf <目录>`（对含多文件的目录必挂）。 |
| 4 | **并行多个 bash 后台任务易触发 `fork: Permission denied`（CreateProcessW errno 13）**，会杀死整个脚本与重试链 | 下载**串行**执行（一个后台任务内 `bash x.sh zip; bash x.sh tar.gz`）。 |
| 5 | **向目标盘直接写大文件失败**（`tar -czf` 直接写 `G:`/`D:` 会失败）；解压大量小文件到 workspace 路径（`_dl`）会卡死 | **在 `/tmp` 构建/解包**（快速可靠），再 `mv` 单文件入目标盘（`mv` 字节不变，已 md5 验证）。若需从 zip 生成 tar.gz 或反之，一律 `/tmp` 内完成再 `mv`。 |

> 补充：`mv` 从 `/tmp` 到目标盘**字节不变**（md5 前后一致已验证），可放心使用；只是 `mv` 后仍要用 `/tmp` 副本法校验。

## 推荐流程（脚本化）
使用同目录 `scripts/dl_one.sh`（已实战验证），用法：

```bash
# 串行下载某 tag 的两份归档到目标盘
bash scripts/dl_one.sh <owner>/<repo> <TAG> <目标目录> zip
bash scripts/dl_one.sh <owner>/<repo> <TAG> <目标目录> tar.gz
```
脚本要点：codeload 优先 → ghproxy 兜底 → 唯一临时名免 `rm` → `/tmp` 副本校验 → `mv` 落盘 → 已存在且有效则 SKIP（幂等）。

参数经验值：
- `--max-time 3300`（42MB @ ~26KB/s 理论需 27 分钟，实测 9 分钟，留足余量）
- `--speed-limit 1200 --speed-time 35`（卡死即放弃换源）
- `--connect-timeout 25`

## 缺失归档的离线补救
若某 tag 的 zip 损坏但其 tar.gz 完好（或反之），可**从完好的那一份重建**：
```bash
# zip 缺失 → 由 tar.gz 重建（注意：源必须完整！）
tar -xzf /tmp/x.tgz -C /tmp/rx        # 务必先 cp 到 /tmp 再解
python - <<'PY'
import sys,os,zipfile
src,out='/tmp/rx/<topdir>','/tmp/out.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for root,dirs,files in os.walk(src):
        for f in files:
            fp=os.path.join(root,f); z.write(fp,os.path.relpath(fp,os.path.dirname(src)))
PY
# 校验后再 mv
```
⚠️ **重要教训**：重建前必须确认"完好"那份本身是**完整**的。曾因用不完整的 tar.gz 重建 zip，导致丢失 7 个文件却「校验通过」——`unzip -t` / `tar -tzf` 只验证结构完整性，**不证明内容完整**。判断是否完整应与官方/original 存档做逐文件 sha256 比对，而非只看格式校验。

## 最终校验清单
```bash
for f in <目标目录>/<TAG>-source.zip <目标目录>/<TAG>-source.tar.gz; do
  case "$f" in
    *.zip)    cp "$f" /tmp/_v.zip && unzip -tq /tmp/_v.zip  >/dev/null 2>&1 && echo "OK  $f" || echo "BAD $f" ;;
    *.tar.gz) cp "$f" /tmp/_v.tgz && tar -tzf /tmp/_v.tgz   >/dev/null 2>&1 && echo "OK  $f" || echo "BAD $f" ;;
  esac
done
```

## 交付前必做
- 输出文件清单（文件名 + 字节数），并明确说明哪些是官方原版、哪些是本地重建（内容是否等价、是否字节一致）。

## 解压后的完整性复核（高频踩坑）
若把 zip 解压到磁盘后要核对是否解全，**不能只看普通文件数**：

```bash
reg=$(find <解压目录> -type f | wc -l)
lnk=$(find <解压目录> -type l | wc -l)
echo $((reg+lnk))   # 应精确等于 zip 内的文件条目数
```

**坑**：仓库里常含符号链接（本例 14 个，如 `.claude/skills -> ../.agents/skills`、各类 `SKILL.md`/`CLAUDE.md`/snapshot 快照）。
- `find -type f` 不会把指向目录的 symlink 算作文件；
- Python `os.walk` 同样会把指向目录的 symlink 归入 `dirnames` 而非 `files`。

因此只统计普通文件会误报"缺了 N 个文件"（本例先是误报缺 14、后又误报缺 1）。**正则文件 + 符号链接 合并计数**才对得上 zip 条目数。

实操结论：Windows Git Bash 的 `unzip` 是会建出这些 symlink 的（实测 14/14、7/7 均成功），不要误以为被跳过而去做多余的"补链"操作；用 `ls <链接路径>/` 验证其可解析即可。

### 两个附带坑
- **`unzip` 可能出现 `symlink error: File exists`（stderr）但结果正确**。判定成败只看两条硬指标：① 普通文件数 + 软链数 == zip 非目录条目数；② 失效链接（目标不存在）数为 0。不要因 stderr 报错就判定解压失败。
- **Windows 版 Python 不认 Git Bash 的 `/tmp` 别名**：Python 脚本里写 `/tmp/x.json` 会 `FileNotFoundError`（被解析为 `C:\tmp\...`）。→ 给 Python 的路径一律用 Windows 可见形式（工作区绝对路径，或 `C:/Users/<u>/AppData/Local/Temp/...`）。校验脚本、重建脚本都受此约束。
