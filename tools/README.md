# tools/ — Gitee 推送 / 发版配套脚本

本目录放与 `docs/gitee推送流程_2026-09-25.md`、`docs/gitee发版指南.md` 配套的**可执行脚本**。
所有脚本**零三方依赖**（仅用 Python 3.x 标准库），拷走即可用，不依赖本仓库其它部分。

---

## `gitee_release.py` — 建仓 / 转公开 / 发布发行版（分步、可重入）

把"发一个版本"从手工点网页变成可复现的命令。每个子命令都能单独跑，重复跑是**幂等**的
（已存在就跳过，不重复创建），所以中断了可以直接重跑。

### 子命令

```bash
python tools/gitee_release.py whoami                                  # 验证令牌可用
python tools/gitee_release.py create   --name myproj                  # 建私有仓（已存在则跳过）
python tools/gitee_release.py remote   --name myproj --repo D:/local/myproj   # 配/改 origin
python tools/gitee_release.py public   --name myproj                  # 转公开（已公开则跳过）
python tools/gitee_release.py release  --name myproj --tag v1.0.0 \
                                       --title "myproj v1.0.0" --notes-file notes.md
python tools/gitee_release.py attach   --name myproj --tag v1.0.0 --file dist.zip
python tools/gitee_release.py status   --name myproj
```

默认 `--owner siwpan`。`--repo` 默认取脚本所在目录的上两级（即仓库根），用于探测分支、打 tag、
推送 tag；也可显式指定本地仓库路径。

### 令牌来源（**绝不要写进仓库**）

按以下顺序取，命中即停：

1. `--token HEX`
2. 环境变量 `GITEE_TOKEN`
3. `--token-file <路径>` —— 从中提取**第一段** 32/64 位 hex（本机令牌由
   git credential store 管理，可传 `--token-file "$HOME/.git-credentials"`）。

### 关键实现要点（踩过的平台坑，别再踩）

- **单附件上限 100MB**（Gitee 社区版；GVP 200MB），每仓库总附件 ≤ 1GB。
  大载荷压成**一个 zip** 再 `attach`，不要传散文件（附件名不允许带路径分隔符，会丢目录结构）。
- **`PATCH /repos/{owner}/{repo}` 必须带 `name`**，否则 400 `name is missing`（转公开时会撞上）。
- `GET /releases/tags/{tag}` 在 tag 不存在时返回 **200 + null** 而非 404 —— 只判状态码会误判"已存在"。
- 建仓 `auto_init: false`：否则多一个无关首次提交，默认分支也不再是你推的那个。
- `POST /releases` **必须带 `target_commitish`**（留空时脚本自动从 git 探测当前分支）；
  否则直接 400 `target_commitish is missing`。
- `attach` 走**直连** `HTTPSConnection("gitee.com")`，路径必须带 `/api/v5` 前缀，少了就是静默 404。
- 响应的 `html_url` 可能为 null；发行版网页地址按
  `https://gitee.com/{owner}/{repo}/releases/{tag}` 构造。
- 发布页 Gitee 自动附的源码包链接（`/archive/refs/tags/*.zip`）**不是直链**（匿名取到的是 HTML 页）；
  GPL 义务要求的源码指向应写 `git clone` 地址。
- 附件上传用**流式 multipart**（1MB 分块 `send`），不把上百 MB 读进内存；网络抖动自动重试两次。

### 退出码

`0` 成功；`1` 失败。

> 该脚本亦随 `gitee-repo-and-release-flow` skill 提供（路径 `<skill>/tools/gitee_release.py`），
> 两份内容一致；本仓库内以 `tools/gitee_release.py` 为准。
