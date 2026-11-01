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

## 安装 / 快速开始

纯 Python 标准库、**一次性脚本，没有 pip 安装步骤**，在本仓任意 Python 3.9+ 解释器下直接运行。

落点全部**环境变量化**（SPEC-001 铁律 5：不写死盘符），缺任一必填变量脚本会立即 `sys.exit` 报缺哪个，**不会拿缺省值去干活**：

| 脚本 | 必填环境变量 | 可选 |
| --- | --- | --- |
| `mk_archive_branches.py` | `TIER3_WORK` `TIER3_REPOS` `TIER3_ARCHIVE` | `TIER3_INDEX`（缺省按仓内 `docs/事实源/组合分级决策索引.md` 推导） |
| `push_archives.py` | `TIER3_WORK` `TIER3_REPOS` | — |
| `add_banners.py` | `BANNER_PLAN`（指向 `_banner_plan.json`） | — |
| `recover_banner_divergence.py` | `TIER3_REPOS` | — |

变量语义：`TIER3_WORK` = 收拢工作区（目标归档仓的克隆所在处）；`TIER3_REPOS` = 源仓发布区根（`<root>/<仓名>`）；
`TIER3_ARCHIVE` = 归档区根（`<root>/<仓名>-retired-<日期>`）。

## 用法 / 示例

```bash
# PowerShell
$env:TIER3_WORK   = 'G:\tier3-work'
$env:TIER3_REPOS  = 'G:\repos'
$env:TIER3_ARCHIVE = 'G:\archive'

# ① 建分支（幂等：已存在的 archive/<仓> 会跳过并计入「已存在」）
python tools/tier_archive/mk_archive_branches.py
# ② 推 master + 全部 archive/*，并用 ls-remote 核对远端分支数
python tools/tier_archive/push_archives.py
```

⚠ **`add_banners.py` 不要直接复用**：它有「两个必须带走的坑」第 1 条那个缺陷（读本地 README 判重 ⇒ 给远端已标注的仓又加一层横幅）。
必须先做「先 `git fetch` 再读远端 README 判重」的改造；若已发生重复横幅，用 `recover_banner_divergence.py` 补救。

## 许可

本目录是 allin 仓的子件（非独立仓），许可随**仓根 LICENSE**（MIT-0）覆盖。
