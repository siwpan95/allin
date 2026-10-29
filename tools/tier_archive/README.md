# tier_archive —— Tier③ 收敛合并的执行脚本（2026-10-29）

本目录收录 2026-10-29 落实「组合分级决策索引」时实际跑过的脚本，**目的只有一个：让执行过程可复核**。
上一轮同类工作自称「6 个脚本 77/77 全过」，但脚本一个都没入库，事后无法验证——本目录不再重犯。

| 文件 | 作用 | 实际结果 |
|---|---|---|
| `mk_archive_branches.py` | 从各源仓本地 git 取全历史，在归档仓落成 `archive/<原仓>` 分支（幂等，跳过已存在） | 68 条全部建立 |
| `push_archives.py` | 推 `master` + 全部 `archive/*`，并用 `ls-remote` 核对远端分支数 | 4 个归档仓 34/13/3/13 ✅；players-unified 4、sin-virtue-cordis-host 1 分支成功（两者 master 当时落后远端，未强推） |
| `add_banners.py` | 给 ③/④ 源仓 README 顶部加状态横幅，提交并双端推送 | **已知缺陷见下**，只应在「先 fetch 再判重」改造后复用 |
| `recover_banner_divergence.py` | 补救 `add_banners.py` 造成的镜像分叉：`reset --hard origin/<br>` 丢弃重复提交，再 `push --force-with-lease` 把 github 拉回 gitee | 21 仓三端复核一致 |

## 两个必须带走的坑

1. **判重必须看远端，不能看本地工作树。** `add_banners.py` 当时读本地 README 判断「有没有横幅」，
   而本地克隆落后远端几条提交 —— 于是给 21 个**远端早已标注**的仓又加了一层横幅。
   Gitee 侧因非快进全部拒收，GitHub 侧却推成功，**制造了镜像分叉**。
   ⇒ 批量改多仓前：`git fetch` → 读 `origin/<默认分支>` 的 README → 再决定改不改。
2. **分支名不能假定 `master`。** `pomodmer` / `novel-down` 的默认分支是 `main`，
   按 `master` 取远端会静默拿到空值（`rev-list` 无输出、`git show` 失败但不报错退出）。
   ⇒ 先 `git rev-parse --abbrev-ref HEAD` 或读 `origin/HEAD` 探测默认分支。

## 不在本目录的配套动作

- 4 个归档仓 `private → public`：Gitee API `PATCH /repos/{owner}/{repo}`，**必须带 `name` 字段**（只传 `private:false` 才生效，`public:true` 会静默失败）
- 补 `LICENSE` / `README`：手写文件 + 常规提交，无脚本
