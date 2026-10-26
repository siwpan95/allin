---
name: gitee-push-from-extracted-dir
description: "Commit and push to a Gitee repo when the local working copy is NOT a git repository (a downloaded zip extract, a copied folder, or a tree whose .git was lost). Covers: cloning a scratch repo outside the source, finding the REAL changes despite CRLF/LF noise, filtering out runtime data and secrets, and pushing with a private token that never lands in the repo."
description_zh: "本地目录不是 git 仓库（zip 解包 / 复制来的）时，如何把改动提交并推送到 Gitee"
agent_created: true
---

# 从「非 git 目录」推送到 Gitee

## 何时用

- 本地目录是**源码 zip 解包**出来的（常见特征：目录里有 `xxx-master.zip`，还套着一层
  同名子目录如 `pluginplayer-main/pluginplayer-main/`），`git status` 报
  `fatal: not a git repository`。
- 目录是从别处拷来的，`.git` 丢了。
- 需要把「在这里改的代码」推到远端，但**不能**用 `git init` + 强推（会丢历史）。

先确认：`ls -d <dir>/.git`，没有就走本流程。

## 步骤 1：克隆到源目录**之外**的临时位置

```bash
mkdir -p /c/tmp/git-push
git clone --quiet https://gitee.com/<owner>/<repo>.git /c/tmp/git-push/<repo>
cd /c/tmp/git-push/<repo>
git config user.name  <name>
git config user.email <email>
git config http.version HTTP/1.1     # 见步骤 5 的坑 1
```

**不要**在源目录里 `git init` 后强推 —— 远端历史就没了。克隆的是远端的真实基线与分支。

## 步骤 2：找出「真实」改动（**关键，别被行尾骗了**）

直接 `diff -rq` 几乎必然是「每个文件都不同」：zip 解包出来的文件通常是 **LF**，
而克隆检出的工作区是 **CRLF**（`core.autocrlf=true`）。必须**忽略 CR** 再比：

```bash
python - <<'PY'
import os, io
SRC, DST = r"C:\src", r"C:\tmp\git-push\repo"
SKIP_DIRS = {".git","node_modules","__pycache__","dist","build","vendor","_deps","coverage"}
def norm(p): return io.open(p,"rb").read().replace(b"\r\n", b"\n")
changed, only_src, only_dst = [], [], []
def walk(base):
    out={}
    for root,dirs,files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            rel=os.path.relpath(os.path.join(root,f), base)
            out[rel]=os.path.join(root,f)
    return out
s, d = walk(SRC), walk(DST)
for rel,a in s.items():
    if rel not in d: only_src.append(rel)
    elif norm(a) != norm(d[rel]): changed.append(rel)
for rel in d:
    if rel not in s: only_dst.append(rel)
print("M:", *sorted(changed), sep="\n  ")
print("A(only in source):", *sorted(only_src), sep="\n  ")
print("D(only in clone):", *sorted(only_dst), sep="\n  ")
PY
```

**只按这个清单逐个 `cp`**，绝不整目录同步。

## 步骤 3：提交前先过一遍「不该入库」清单

`only_src`（源目录有、远端没有）里最容易混进来这些，**一律不提交**：

| 类型 | 例子 |
|---|---|
| 机器本地配置 | `.npmrc`、`cordis.patch.yml`（通常已被 gitignore） |
| 运行时数据 | `presets.json`、播放/频道收藏（常含**带签名的 URL**） |
| 密钥材料 | `*.key`、`*.crt`、`auto.key`、令牌文件、rpc-token |
| 二进制依赖 | `ffmpeg.exe`、`ffprobe.exe`、`mediamtx.exe` |
| zip 残留 | `xxx-master.zip`、`xxx (2).js/.md/.bat` 这类重复副本 |

判不定时用 `git check-ignore -v <file>` 看是否已被忽略；已忽略的就别手动加。

## 步骤 4：核对 diffstat 再提交

```bash
git status --short          # 应当恰好等于你打算改的文件
git diff --stat             # 小 diff = 行尾没被搞乱；整文件级 diff = 行尾被改了
```

提交时按**逻辑拆成多个 commit**（如「修路径」与「加功能」分开），远好过一个混合提交。

## 步骤 5：推送（令牌只走运行时）

**`git push` 到 Gitee 必须走 HTTP/1.1**：HTTP/2 下会被服务端断开，报
`send-pack: unexpected disconnect while reading sideband packet` 并挂到超时
（**只有 push 会，fetch/clone 正常**）。这是最耗时的坑——现象像网络慢。

令牌**绝不写进仓库文件，也不写进 `.git/config`**；放在仓库外的临时文件里，只在
命令行 URL 里用一次：

```bash
TOKEN=$(cat /c/tmp/pp-toolchain/.gitee_token)     # 仓库外
GIT_TERMINAL_PROMPT=0 git push "https://<user>:${TOKEN}@gitee.com/<owner>/<repo>.git" master 2>&1 \
  | sed -e "s/${TOKEN}/<token>/g"                  # 输出里也别把令牌打出来
```

## 步骤 6：推送后自检

```bash
# 1) 远端 HEAD 是不是刚推的那个
git ls-remote --heads https://gitee.com/<owner>/<repo>.git master | cut -c1-60
# 2) 令牌有没有残留（两处都必须为 0 / 无输出）
grep -c "$TOKEN" /c/tmp/git-push/<repo>/.git/config
grep -rl "$TOKEN" /c/tmp/git-push/<repo> 2>/dev/null | grep -v "/.git/"
```

## 顺手记下的两个约定

- **bat 文件**：Windows 下要 **CRLF**，且**尽量 ASCII-only**（仓库常见约定：中文注释在
  GBK 控制台会解析错）。zip 解包出来常是纯 LF，`goto`/标签解析会有问题，转 CRLF：
  ```python
  b=open(f,'rb').read(); open(f,'wb').write(b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
  ```
  有 autocrlf 时这不会产生行尾噪声（入库时被归一化）。
- **路径不写死盘符**：`.bat` 里用 `%~dp0`，生成器脚本里也不要注入绝对路径
  （见过仓库从 G: 搬到 D: 再搬到 C:，每次写死都静默断链）。
