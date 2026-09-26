# 项目约定

## 铁律 0：开源优先（用户拍板，2026-08-25）
- gitee 仓库一律**公开（public）+ MIT 许可证**，与用户的 MIT 开源理念一致；私有仓视为违规，发现即转公开并补 LICENSE。
- 推送新仓库默认流程：建仓即 public → 根 LICENSE（Copyright (c) 2026 siwpan）→ 大文件资产本地保留不进库（>100MB 会导致推送挂起）。

## 铁律 1：README 优先（最高优先级）
- 动任何项目（梳理/评估/改动/写文档）之前，**第一步先读该项目的 README**；读不到才允许看结构扫描。
- 即使 README 是落后版本，也比 agent 自己审核/推断内容更可靠——先把 README 当作基准事实，再与实测对照修正。
- 目前每个项目基本都有 README；写进 SKILL/路线图/报告的内容必须以 README 为准绳，实测与 README 冲突时两边都要核实并注明。

## 铁律 2：协作工作流程（2026-08-28 用户拍板）

**先问 → 再计划 → 再 review → 后执行 → 复盘**。核心句（用户原话）：
**共识越充分，执行越不容易跑偏**。

- **分档触发**：大任务（结构性/多仓/架构/规则改造）= 走全流程；中任务（单仓功能级、多文件）= 问一句确认目标 + 简计划 + 执行 + 汇报；小任务（记账/清理/单点修复）= 直接执行 + 汇报。
- **先问纪律**：一批 ≤4 问，只问影响执行的必问项（目标/边界/约束/验收口径），不做盘问式问卷；问题必须给推荐项（Recommended）。
- **review 放行**：计划呈交后须用户明确放行（如「开始执行/按计划」）才动手；用户拒绝或修改 → 回到计划重摆，不得强行推进。
- **高风险动作不分档**：推送、建仓、删除、密钥操作、仓库结构变更——无论任务大小，逐项确认后才做。
- **执行中变数**：遇计划外重大事实（如勘察发现与计划假设冲突）→ 回头补问；小偏差 → 记入复盘。
- **复盘（第五步）**：大/中任务执行完对照计划复盘（结果 / 偏差 / 教训），教训与新坑入 MEMORY 与会话交接（现有 §三十五~四十 即复盘产物）。
- 详版模板（阶段产物、退出条件、分档表）见《协作工作流程约定_2026-08-28.md》。

## 铁律 3：推送的在场前提（2026-09-24 用户拍板）

> **由来（用户原话要点）**：AI 在用户不在电脑前时自动推送，"长时间挂起，根本没必要"。
> 核实后的准确边界：设了 `GIT_TERMINAL_PROMPT=0` 时**不会卡等输入**（凭据缺失立即失败），
> 网络不可达实测 **21.2s 自行失败**（不是无限挂起）。
> **"长时间挂起"这一条未能复现**：前台那次失败的真因是**本 agent 前台工具 120s 超时把 git 杀了**；
> 同一条 `git push` 放后台**即刻成功**（`849cccdb..cda0614c`）。
> ⇒ **规则成立的真实理由是"没必要"，不是"会挂死"** —— 加多少检查都改变不了"不需要的动作不需要"。

- **默认口径**：**本地提交即时做；推送不在无人值守时自动执行。**
  - 会话进行中、用户在（当轮有来有往）→ **可以推**；
  - 跨轮自动推进 / 用户明确离开 → **只本地提交，攒着等在场再推**。
- **推送前必须报「推什么」并等一句放行**：仓 · 分支 · 笔数 · 逐笔标题。不放行就攒着。
  （与铁律 2「高风险动作逐项确认」一致；本条是它在**推送**上的可执行化。）
- **技术前提（无论何时推，缺一不可）**：
  1. `GIT_TERMINAL_PROMPT=0` + `GCM_INTERACTIVE=never` —— 从两层封死"等待输入"；
  2. **推送放后台执行**（实测：前台推送会把一个回合吃满 120s 并被工具超时杀掉；同一条命令放后台即刻成功）；
  3. **推后一律 `git ls-remote` 核对 IN_SYNC** —— `push` 的输出不算证据（与「只信 ls-remote」同源）。
- **不以"省事"为由跳过**：一次错误的公开推送是永久历史，改不回来。
- **反模式**：为了让"无人值守也能推"而层层加固检查 —— 方向错了；不需要的动作，加多少检查都不需要。
- **总口径在《协作工作流程约定_2026-08-28》§零「协作模式两态」**：在场 / 自主的权限矩阵、自主模式三条纪律（选推荐项并记账 / 攒着不推 / 不可逆不做）、升级触发。**本条是它在推送上的具体化。**
- **`git push` 会因仓库里的大文件历史而挂起**（2026-09-25 实证，`G:\allin`）：`.git` 达 **10.7 GB** 时 push
  **挂起 17 分钟不动**（无临时包、无 443 连接、CPU 0.1s、pack 目录零变化），调大 `http.postBuffer` 亦无效。
  **判据**：`git rev-list --objects --all` + `git cat-file --batch-check` 算「原始 blob 总量」，
  按扩展名排序即可定位元凶（本例 `.txt` 18 个文件占 546.5 MB / 全仓 550.5 MB = **99.3%**）。
  **根治**：从历史剔除该文件 → `git for-each-ref refs/original/ | xargs -n1 git update-ref -d`
  → `git reflog expire --expire=now --all` → `git gc --prune=now`（本例 10.7 GB → **14 MB**）。
  **完整执行链 + 两个坑 + 反直觉认知**写在先例脚本 `G:\tools\filter-drop-dir-index.sh` 头部注释里；
  本次全过程见 `G:\allin\docs\冗余清理与盘位归位_2026-09-24.md` §十二。
- **凡按中文路径过滤 git 输出，必须带 `-c core.quotepath=false`**（2026-09-25 沉淀，**已犯两次**）：
  git 默认把非 ASCII 文件名转义成 `"\347\233\256\345\275\225…"` 并加引号，于是
  `git ls-tree … | Where-Object { $_ -eq '目录索引.txt' }` **恒假** → 会误判「文件不在仓库里」。
  两次实证：① 排查 `radio-stations-source.js` 时误判"git 历史里从未存在"；
  ② 剔除 `目录索引.txt` 前误判"它不在 HEAD"（实际在，只差这个参数）。**同类**：
  `git status`/`git diff --stat` 的中文路径同样会被转义，按名字过滤一律加此参数。

## 铁律 4：建仓三件套（README + LICENSE + .gitignore）（2026-09-24 用户拍板）

**强烈建议所有 git 仓库都带这三个文件**，建仓时一次备齐，不用事后补：

| 文件 | 作用 | 缺了会怎样 |
| --- | --- | --- |
| `README.md` | 门面：是什么、怎么跑、依赖、门禁怎么跑 | 违反铁律 1（README 优先）；接手者只能靠结构扫描猜 |
| `LICENSE` | 开源身份与授权边界 | 违反铁律 0；「公开」但无授权 = 法律上默认保留所有权利，别人不能用 |
| `.gitignore` | 挡住生成物、依赖、本地产物、**凭据** | 生成物与 `node_modules` 混进库；**凭据泄露风险**（见「敏感信息检查」节） |

- **实测覆盖率（2026-09-24，`G:\repos` 逐仓扫）**：**108 仓 = README 108/108 ✅、`.gitignore` 108/108 ✅、LICENSE 108/108 ✅**
  —— 原唯一缺口 **`cordis-text-game`（缺 LICENSE）已于同日补齐**（见下）。
- **与铁律 0/1 的关系**：本条是它们的**可执行化** —— 铁律 0 说「公开 + MIT」，落到仓上就是「根 `LICENSE` 存在」；
  铁律 1 说「先读 README」，落到仓上就是「`README` 存在且是最新的」。
- **`cordis-text-game` 三处缺口已于 2026-09-24 全部闭合**（发现 → 补齐 → 建仓 → 推送）：

  | 缺口 | 处置 |
  | --- | --- |
  | 缺 `LICENSE` | ✅ 补 MIT（正文照抄 `dict-scene-engine` 模板，仅版权行不同，逐字符核对通过）；`package.json` 同步补 `"license": "MIT"` |
  | `package.json` 的 `private: true` | ✅ **删除** —— 它是 npm「禁止发布」标记，与公开项目语义冲突；现有 5 个 Node 仓均无该字段 |
  | 无 `remote` | ✅ 建仓 `siwpan/cordis-text-game`（公开 + MIT）并推送，`ls-remote` 核实 IN_SYNC |
  | 未登记 platform | ✅ 新增 `registry/projects/cordis-text-game.yaml`（`manual: true`、**不设 `port`**：它无常驻服务，`npm run web` 的 8080 是临时静态服务且该端口已登记给 audio-separator） |

  建仓后验证：**匿名克隆** 33 文件 / 0.092 MB，三件套齐备，`dist/` 与 `node_modules/` 均未入库。
- **建仓流程与纪律（2026-09-24，Gitee API 实测）**：
  **令牌建仓的结果必然私有，需手动转公开**（这是 Gitee 的既定行为 —— 建仓请求里写 `private: false` **不会生效**，
  不是"字段被静默忽略"，也不是缺陷）。因此**建仓是两步**：
  1. `POST /user/repos` 建仓（可带 `license_template: MIT` 一并设许可）；
  2. `PATCH /repos/{owner}/{repo}` 显式转公开 —— **坑：PATCH 的 body 必须带 `name`，否则报 `name is missing` 400**。
  **纪律**：建仓后**不能只看创建响应**，必须用**匿名视角**复验（`Invoke-WebRequest https://gitee.com/<owner>/<repo>` 应 200；
  `git ls-remote` 匿名应 exit 0；`GET /repos` 看 `private`/`public` 两个字段）。
  另一条：`license_template: MIT` **会**让 Gitee 自动生成一个 `Initial commit`（含 LICENSE），因此建仓后远端非空，
  首次推送会遇到 unrelated histories —— 用 `git merge --allow-unrelated-histories` 而非 `force push`（后者会抹掉远端提交）。
  > **我这次的判断失误（留档）**：观察到"请求写了 `private: false` 而响应是 `private: true`"，我**直接判定为 API 缺陷/事故**
  > 并写进了本文档，**没有考虑"这是平台设计约定"这一可能**。用户指出后才纠正。**教训**：行为与预期不符时，
  > 先问「这是不是该平台的既定语义」，再下"缺陷"结论。
- **仓数订正**：`G:\repos` 现为 **108 仓 / 108 含 `.git`**；本文件另三处（许可分布、全域同步、新机挂载事实）原写 **107**，
  均因 `cordis-text-game` 当时未被计入 —— 以本节为准。
- **引用消歧（重要）**：本文件有**两套「铁律」编号**，引用时必须带限定词 ——
  **`铁律 N`（0–5）= 本节的命名铁律**；**`调试铁律 N`（1–45）= `## 调试铁律` 标题下的编号列表**。
  裸写「铁律 4」在本文件里同时匹配两者，**禁止**这样引用。

## 铁律 5：去符盘（路径不写死盘符）（2026-09-26 用户拍板）

- 代码、配置、文档、脚本里的**文件路径一律不写死盘符**（`C:\`/`D:\`/`E:\`/`G:\` 等）。本机是 D:、新机可能是 G:、换台电脑又会是别的盘——**盘符不是稳定事实**，写死就会在换机 / 克隆时误导或失效。
- **写法约定**：
  - 仓内文件用**仓根相对路径**（如 `preset/allin/allin.patch.yml`、`docs/MEMORY.md`）；
  - 跨仓 / 外部依赖用**约定变量或环境变量**（如 `$DSH_HOME`、`$PROJECTS_ROOT`），不要把绝对盘符路径烤进源码；
  - 文档里若必须举例绝对路径，用**去符盘形式**（`D:/allin` → `/allin`、`D:\projects\allin_push` → `/projects/allin_push`）表示「仓根 / 约定父目录」，明确它不是本机真实路径。
- **门禁**：新增的盘符绝对路径应被 `tools/gate/scan_hardcoded.ps1`（死根路径门禁）拦截；若该脚本尚未覆盖盘符模式，补一条规则（正则 `[A-Za-z]:[\\/]`）。
- **本机已部署内容先搁置**：`allin.patch.yml` 治理段内的「开卷必读四事实源」路径（`D:\projects\allin_push\docs\...`）是 agent 运行时**实际读取**的路径，属功能性，本次**不改动**；待换机 / 重部署时按本铁律刷新为仓根相对或约定变量。
- **反模式**：在脚本 / 配置里硬编码 `D:\...`；把「本机当前盘符」当事实写进提交；文档里留 `G:\allin` 这类本机专属绝对路径。

## 治理准则：创新三原则（2026-08-27 深度审核固化，铁律级）

> **创新 = 借鉴 + 调整 + 同步 + 记账；「推倒重来」只允许发生在结构层，资产与历史永远保全。**
> 依据：`G:\allin\docs\深度审核报告_20260827.md`（对照 deepseek-harness-master 与 gitee.com/siwpan 全量审核）。

1. **借鉴必记账**：复制/借鉴任何外部代码、配置、概念前，记录「来源 + 许可证 + 借用范围」。借鉴对象可以是上游项目（dsh/Cordis），也可以是自己的样板（spec+iss+CHANGELOG+冒烟协议）——自己复制自己也要记账（副本清单/同步方式）。本地参考源码（notpython 等）保持来源标注，发布前先补 LICENSE。
2. **调整必同步**：任何「灵活更新」之后必须完成三步回写——① 推远端（活跃分支，git ls-remote 验证）；② 更新引用（platform.yaml path、ports.yaml、目录索引.txt、SKILL/README 路径）；③ 跑黄金值（`npm run check` / harness exit 0）。禁止「调整完留在本地」——这是 2026-08-27 审核发现的 14 个落后仓、56 个无 .git 目录的根因。
3. **推倒重来只用于结构层**：合并优于双仓并存（重复仓拍板后退役一个，如 requirements/foolproof-operation）；补优于删（缺 LICENSE 补而不是删仓）；还原优于分支（上游修复后弃用自维护补丁，如 dsh junction 补丁）。历史与资产（legacy 仓、tag、release、归档区）永远保全——08-27 集合仓拆 91 仓就是结构层重建、资产全保全的正确示范。

### 冗余/退役判定三查（2026-09-02 落实，musickit radio 直播端误删为前车之鉴）

判定「A 已并入/迁移到 B，A 可删/归档」前，**必须逐功能面核对接任者**，禁止按同名事物整体判冗余：

1. **列功能面**：把 A 拆成独立功能面清单（例：radio = 转播 + 直播(渲染推流) + 控制面板 + 排程 + PWA）；
2. **逐面找接任者**：每个功能面在 B 中找**实证**接任者——git grep / 代码引用 / README 明载为准，不得凭「B 也叫电台」的印象；
3. **无接任者不可删**：任一面无接任者 → A 的该面不可删（保留该面，或先在 B 实现接任再删）。

删除/归档动作的**提交信息与交接文档必须附「功能面 × 接任者」对照表**。2026-09-02 事故：93db08f 只验证了转播面（Node 转播版确已接任），直播面（musickit 渲染→推流）无接任者却被一并删除，管线输出端真空（详见交接 §六十一）。

### 敏感信息检查（借鉴/调整/打包前必过）
- API Key / 令牌 / cookie：真实值绝不进代码、配置、仓库——一律 example 化 + .gitignore（2026-08-27 事故：活跃 DeepSeek Key 明文提交公开仓，见 R0）。
- 复制/打包目录前：排除 .git、node_modules、.venv、__pycache__、build/dist、日志；打安装包前复核 .iss 清单不含 .git 与凭据。
- **remote URL 明文凭据面（2026-09-22 实测记账，用户拍板维持现状）**：4 个 `.git/config` 的 origin 内含 `siwpan:<token>@gitee.com` —— `G:\platform`、`G:\repos\bee`、`G:\repos\particle`、`G:\archive\arcade2-collection-model-retired-20260827`（R1 时记为 16 处，09-22 实测 4 处）。凭据源 = `G:\私人令牌.txt`，属已知现状，**只记账不清理**；日后若轮换令牌，这 4 处需同步更新。
- **`G:\私人令牌.txt` 凭据清单（2026-09-22 盘点，只记种类不记值）**：① gitee token（32-hex）② DeepSeek key（`sk-…`）③ Tavily（`tvly-dev-…` + MCP URL）④ TestPyPI / PyPI 令牌各 1（`pypi-AgE…`）⑤ **unsplash**（Application ID / Access Key / Secret key，2026-09-22 从 `C:\Users\13122\Downloads\key.txt` 并入）⑥ **pexels** API Key（同上并入）。
  - **取用方式（image-scraper）**：`CLI/GUI 参数 → 环境变量 <NAME>_KEY（UNSPLASH_KEY / PEXELS_KEY） → config.json 的 keys`；**该仓 `config.json` 是已跟踪文件，密钥绝不写进去**（key 位保持空串占位）。
  - 令牌文件位于 `G:\` 根，而 `G:\` 根**不是任何 git 仓**（allin 仓根已迁 `G:\allin`，其 `.gitignore` 仍声明 `私人令牌.txt`）——即不入库；每次改动前先备份到 `G:\archive\私人令牌-bak-<时间戳>.txt`。

### 插件化选型（2026-08-27 用户拍板）
- **爬虫类适合插件化**（crawl-hub 模式：多站点 worker = 多插件、频繁增删、子进程隔离）；**单机 GUI 小游戏不适合**（D20 的 E:\D20 整体插件化/网页插件版实验已证明不划算，勿再尝试）。
- 判定标准：宿主是否天然「多能力组合 + 频繁增删 + 生命周期可逆」——是 → 插件化；否 → 单体优先。

### 外部机器完成的项目（2026-09-22 用户澄清）
- 已知**整个项目主要在别的机器上完成、本机是镜像/运行副本**的仓：`private-radio-stations`（siwpan/private-radio-stations）、`santi-teleprompter`（siwpan/santi-teleprompter）。
- **口径：本地一律对齐 gitee**（`git fetch` + `git pull --ff-only`）——**「远端领先本地」是正常状态**，不是异常、不是丢数据。
- 判据（避免再当事故查）：某仓出现「本地零领先 + 远端持续领先 + 本机 memory 无对应记录」→ **先按「外部机器完成」核对**，再考虑其他解释。
- ⚠ **2026-09-23 用户纠正**：「外部机器完成」**只解释"远端为什么领先"，不代表本机不能改**——本地照常可以修改、提交、推送（推送仍按高风险逐项确认）。此前把这条引申成「不以本机作为改动源」属**我方的过度引申**，已作废。

## 审核遗留处置顺序（2026-08-27 深度审核 R0–R11，按序执行）

> 证据与细节见 `G:\allin\docs\深度审核报告_20260827.md`；新会话接手按此推进并更新勾选状态。

### 立即（安全线）
- [x] **R0 DeepSeek Key（仓侧已完成；轮换用户拍板风险自担）**：两仓已清除密钥并推送（moba_battle_platform c474743 / ollama_generator 114b1c6，均 example 化 + .gitignore + CHANGELOG）；本地 `repos\moba_battle_platform\私人令牌.txt` 副本已删。**遗留（用户拍板：公开仓无访客、暂不轮换）**：**Temp 密钥副本面已清（2026-08-28：Temp\rebuild、Temp\tc_* 随 G:\Temp 全量清理删除，释放 31.85GB）**；日后若轮换 → 更新 `C:\Users\13122\.dsh\.env` 重启 dsh，并清理剩余副本：`G:\私人令牌.txt`、`local\tavern-rogue\third_party\ollama_generator`。
- [x] **R1 gitee 令牌（用户拍板维持现状）**：08-25「公开有意为之」决策延续，不轮换；可清理面已删（6 个硬编码脚本 + 1 个日志 + 2 个含令牌 clone，并入 R7）。16 处 remote userinfo 保持不变。
- [x] **R2 同步治理（完成）**：12 个落后/错位仓已 ff 对齐；65 个无 .git 目录已安全挂接（84/84 有 .git，本地文件零删除）；`_job\_arcade2` 已归档（街机合集模型退役，10 游戏已全部在 repos/arcade → archive/arcade2-collection-model-retired-20260827）。后续有差异的仓（git status 可见）按「远端为唯一真相、本地为工作副本」逐仓处置。

### 短期（同步与合规线）
- [x] **R3 LICENSE 补漏**：ai-collection-legacy 4 分支已补 MIT 并推送，全 gitee LICENSE 91/91。
- [x] **R4 platform 修复**：f0d79b1——registry.js path 存在性校验（fail-loud）+ fonts/paotuan path 修复 + ALLOY_CWD 默认 G:\repos\an-engine；check 95/95、测试 15/15、harness exit 0。
- [x] **R5 索引更新**：allin README 更新（repos 84、ai/ 移除）+ 目录索引.txt 按现盘重生成（排除 .git/node_modules/.venv/__pycache__）。

### 中期（治理决策线）
- [x] **R6 重复仓处置（完成，教训永久保留）**：requirements 与 foolproof-operation **实为同一项目**（原名「傻瓜式操作」；早期未读 README 靠扫盘误判成两个——违反铁律 1 的代价）。已归并：requirements 更新内容并入 siwpan/foolproof-operation；requirements → requirements-legacy、literary-legend → literary-legend-legacy（远端改名保全历史）；本地 requirements 目录归档。**今后判定「重复项目」必须先读双方 README 再下结论。**
- [x] **R7 Temp 清理**：2,487 个 tmp* 目录 + lic_km1787td/tc3 + 6 个硬编码令牌脚本 + 1 个含令牌日志已删，释放 3.54GB（清单 audit-fragments/R7_cleanup_log.txt）。
- [x] **R8 dsh 版本漂移**：已记入 DEPLOY.md（快照 rc.5 / 运行 rc.6 / 上游 0.1.1-rc.2；升级必重放补丁核对 SHAPE；上游修复后还原优于分支）。

### 长期（卫生线）
- [x] **R9 来源许可表**：`G:\notpython\来源与许可表.md`（43 目录全覆盖；GPL/AGPL 系 7 个单列）。
- [x] **R10 非 MIT 资产隔离**：`G:\allin\docs\非MIT资产标注.md` + `G:\web\非MIT资产标注.md`。
- [x] **R11 allin 收尾**：本地 tag「游戏」已删；3 个未跟踪文件移 archive/归类三件套-20260827；工作树干净。

## 统一引擎（2026-08-23 起改名 alloy）
> ⚠ **2026-09-22 现盘核对：包名已由 alloy 再次改名 `allin_engine`** —— 提交 `72c1d63`（2026-09-19，`refactor!: 引擎改名 alloy -> allin_engine`）；本机实测为 `G:\repos\an-engine\allin_engine\`（根层 `core/ world/ systems/ trpg/ …` 为双写镜像），入口现为 **`from allin_engine import GameEngine`**，PyPI 包名 **allin-engine 1.0.0**。
> **本段下方所有 `alloy.*`、`from alloy import`、`pip install -e …\alloy`、`python -m alloy …` 的写法，一律按 `allin_engine` 读**（内联副本 `dwarf-scrolls`/`sandbox` 亦已是 `allin_engine/`）。详见《会话交接_2026-08-27.md》§六十二与《文档与现盘核对报告_2026-09-22.md》。
- 本体路径: G:\repos\an-engine\（旧名 allin_engine → alloy；过渡 shim 已归档 G:\archive\allin-engine-shim-2026-08-27；远程仓 siwpan/an-engine）
- 入口: `from alloy import GameEngine`
- 新项目应优先复用 alloy 的模块, 而非从其他项目复制代码
- 示例文件: G:\repos\an-engine\example_quickstart.py
- 装配: `engine.add_core()/add_world()/add_systems()/add_combat()/add_audio()/add_ai_brain()`，新增 `mount(plugin)/unload(key)`；服务注册表在 `engine.ctx`（Context：注册即回滚）
- **fork 双作用域（2026-08-27 落地）**: `ctx.fork(name)` 命名子作用域（销毁自动摘除、同名重复抛 DuplicateScopeError）；`ctx.fork_install(plugin)` = outer 钩子父作用域只执行一次 + apply 每次独立 fork（多实例玩法复用）；引擎级 `engine.mount_scoped(plugin, config, name=)` / `engine.unmount(name)`，WorldLog 记 plugin.mount/plugin.unmount；依赖方向唯一（fork 可见引擎服务，反向不可见，实例服务走 fork 句柄）
- **TRPG 规则内核（R2，2026-08-27 晚并入；阶段 1/2 已完成）**: D20（D&D-GURPS 角色构建器）的 14 Service + 数据中枢并入 `alloy/trpg/`；入口 `from alloy.trpg import Character, preset_trpg`——`preset_trpg(ctx)` 已注册 `STANDARD_PRESETS["trpg"]`（幂等），`Character(..., ctx=)` 支持注入宿主 Context；多角色 = `ctx.fork(name)` + preset（每角色独立作用域）。适配层 `TrpgContext`（alloy/trpg/context.py）：容器复用 alloy Context、事件骑宿主共享 EventBus、注册即回滚、dispose 逆序退订；D20 的 mini-Cordis/YAML loader/condition 子系统不进引擎。套件 484/484 全绿（`python -m alloy.test.run_all`）。**阶段 1（2026-08-27 深夜完成，已建仓）**：D20 已 shim 化并独立建仓 siwpan/d20（公开+MIT，本地 G:\repos\d20；d20/ 只剩 5 个转发文件 → alloy.trpg，老 API 100% 兼容；.venv/tests/内核 16 文件/composition.yml 已删；黄金样例 盗贼.txt 12 字段命中）。**阶段 2（深夜完成，5787a9f）**：running-group-simulator 接入 alloy.trpg.dice（core/dice.py 接入层 + success_chance + roll_info 直通；546/546 全绿）。**阶段 3（深夜完成，六仓全推送）**：地城簇六仓（random-dungeon-/dungeon/tavern-rogue/sandbox/text-adventure/hell-below）逐仓勘查结论=**均无 D&D/GURPS 同构骰系**（区间随机/Savage Worlds 骰系/百分比判定/谜题引擎/卡牌驱动）→ 按铁律原则全部「不接入 + README 记账」（各仓 README「规则内核接入判定（R2）」节）；dungeon 恢复标准 MIT、hell-below 修 5 个旧桌面路径探针（_test_all_games 被 s→y 污染已重写）。**阶段 4 + moba 补盘点 + sandbox 同步（2026-08-28 完成）**：dwarf-scrolls/project-root/novel-reader 三仓同样无同构骰系 → 记账不接入（dwarf-scrolls 顺带修复迁仓拍平致应用损坏——包名桥 dwarf_scrolls.py）；**moba_battle_platform（用户补盘点）为 D&D 5e 同构需求方**——内核反向增强（rng 注入 + 通用 NdS roll_dice，an-engine 8b5713a/446ee86）后 moba 接入（cc9b32f），并恢复其被局部回退的 R0 密钥修复；**sandbox 内联 alloy 经 engine.patch.yaml patch 重放升级到当前版（含 trpg，5de8e0b）**——sync 流程：`git archive HEAD alloy` 提取旧版基线作 --reference → `python -m alloy sync <项目> --reference <基线> --dry-run/--apply`；**dwarf-scrolls 同流程升级完成（ae3b342，2026-08-28）**，至此两个内联副本均为当前版。project-root 既有断言失败已修（dd69acb：E1 材料门禁上线后 gui_advanced_flow 未同步，先 _do_gather_materials 再晋升；45/45 全绿）。**反向重构原则（阶段 2 沉淀，铁律级）**：只接真正同构的规则原语（骰子/成功率表等纯函数），模型与专有规则保留仓内——alloy.trpg 是 D&D 六属性口径，与 GURPS 4e 四属性模型异构，绝不为了「接入」破坏行为契约与数据模型；勘查后「无同构原语→记账声明不接入」是合法结论，不是偷懒（阶段 3/4 九仓即此）。**推仓纪律（2026-08-28 沉淀）**：推任何仓前先 `git ls-remote` 查默认分支（moba 是 main 不是 master，曾误推垃圾分支）；`git add -A` 前核对 .gitignore 覆盖 build/dist/egg-info；文档治理后必须实跑一次应用/测试（dwarf-scrolls 损坏被 README 治理遗漏）。
- **an-engine 双写不变量**: 仓库根层（__init__.py/core/test/...）是 alloy/ 规范目录的**镜像，两者都跟踪、必须同步**（fork 提交 6b3dbe7 为双写先例；R2 曾漏改根镜像，3a5afea 补齐）。改 alloy/ 后逐个 Copy-Item 到根并哈希核对。
- **alloy 安装**: `pip install -e G:\repos\an-engine`（**仓根**，不是 ...\alloy——后者 packages.find 找不到包会装空）；装后 import alloy 全局可用（指向 alloy/ 规范目录，含 trpg）。
- 自省: `python -m alloy dump-profile [--json]`；审计: `python -m alloy dump-log <path>`；副本同步: `python -m alloy sync <项目> --dry-run|--apply`
- 项目内联副本的升级用 patch 重放（engine.patch.yaml + sync --reference/--take-base），定制保留、冲突可见
- 世界事件日志 WorldLog（engine.log）是事实源：存档=快照+日志增量（SaveLoadManager.save_with_log/load_with_log）
- GameState 的玩家状态通过 `gs.player` 访问 (PlayerState), 不是 `gs.state.player_state`
- MapData 创建空地图用 `MapData.empty(cols, rows)`, 不是 `MapData(cols=, rows=)`

## foolproof-operation：Cordis 内核 + USN 索引（2026-09-23，阶段 0~6 完成并**已推送发布**）

- **本仓现状（接手先看这行）**：`G:\repos\foolproof-operation`（siwpan，master，
  本地=远端=`41b320a`，tag `v1.1.0`，gitee release id `1162143`（附件 3255007 = 便携 zip 14MB）；
  2026-09-23 完成「Cordis 式可逆插件内核 + 自研 NTFS USN/MFT 索引」重构，三个提交
  `e8f1086`（内核+索引）/ `e0dd51b`（插件接线）/ `41b320a`（运维+打包+文档）已推送，工作区干净。
  规划与阶段表见 `G:\allin\docs\md\allin主工作区\USN索引与Cordis内核规划_2026-09-23.md`（**其阶段勾选即事实源**）。
- **结构**：`core/`（Context/effect 逆序回滚/fork/isolate/事务化清单装配 + runtime/tasklog/audit）、
  `index/`（只读 USN 客户端 / FRN 路径还原 / SQLite 按卷分库 / 索引服务 / 基准探针）、
  `plugins/`（categories·pip·reqtxt·installer·search·scanner）、`foolproof.composition.json`（10 行清单）、
  `tests/`（271 例）、`docs/usn-indexer.md`（原理/实测/踩坑）。
- **黄金值（不设环境变量）**：`python -m unittest discover` 271/271；`ResourceWarning=error` 亦全绿；
  CLI 子命令 list/scan/envs/doctor/tasks/check/es 全 exit 0；`smoke_test.py` GUI 冒烟无 Traceback；
  便携 exe（`requirements.spec`）`list/doctor/envs` exit 0。
- **关键实测**：全盘 479 万条记录建库 ≈50s；查询 0.02~1.46ms；环境发现 **4 → 208 候选**。
- **两条口径纪律（本仓特有）**：① 索引只读——**绝不调用** `FSCTL_CREATE_USN_JOURNAL`（改卷状态的写操作）；
  ② 全量枚举必须 `LowUsn=0`（用 journal 的 `FirstUsn` 只能拿窗口内记录且不报错）。
- 相关铁律见本文档调试铁律 20~23（`$args` 形参、SQLite `IN COLLATE` 全表扫描、
  `ResourceWarning=error` 抓资源泄漏、测试断言禁子串启发式）。

## 调试铁律（2026-08-24 自 Cordis 贪吃蛇实验沉淀）
1. **inject 守卫**：Cordis Service/plugin 在事件回调里访问 `ctx.xxx`（哪怕是别的 service）必须在 `static inject` 声明，否则运行时抛 "without inject"。
2. **同帧抢占**：手动 set 状态但运行时无效，先查是否有同事件的其他监听器在同帧抢占（如 AI 驱动在 tick 时覆盖手动方向），不要直觉甩锅给输入校验。
3. **HMR 正确姿势**：Fiber.dispose/update + provider 级联重载 + fs.watch；core rc.8 不自带文件监听器（@cordis/loader 才带）。
4. **重开叠加泄漏**：reset 类路径重应用前必须先回收上一轮监听器/定时器（时间可组合逆操作）。
5. **工具可靠性铁律（agent 协作层）**：命令工具通道持续报错时，立即停止重试同一招；改用 Write/Read/Edit 完成能离线做的事，并诚实告知用户"请本地验收"，不假装再试。
6. **大文件文本处理（2026-08-28 沉淀）**：PowerShell 5.1 对 50 万行级文件用数组 `+=` 逐行过滤是 O(n²)（120s 超时被杀）——一律 [IO.File]::ReadAllText + [regex]::Replace；git 的 stderr 信息输出在 `2>&1` 下会被 `$ErrorActionPreference='Stop'` 误判为异常，逐条 git 调用要包 Continue。
7. **未跟踪文件审计口径（2026-08-28 沉淀）**：git status 里的未跟踪文件不全是构建产物——G:\ 曾发现 18 个「从未入过任何仓库」的真源码（README 已描述它们为入口/主程序）。.gitignore 治理前必须先分类核验：非产物未跟踪 = 潜在资产，逐件判「入库 / 忽略 / 归档」后再动手，判据看 README 与代码引用。gitignore 无前导斜杠的 `build/` 可全深度匹配嵌套产物；git status 对非 ASCII 目录输出 core.quotepath 转义（`?? "\346\234\254\345\234\260/"`），匹配前先去引号/反转义。
8. **PowerShell 变量大小写不敏感（2026-08-28 沉淀）**：`$R` 与 `$r` 是同一个变量——`$R='G:\repos'` 后 foreach 用 `$r` 会静默覆盖它（整批 git 路径错乱成「仓名\仓名」）。变量命名必须超大小写区分；批处理脚本先跑 1 个样本验证路径再全量。
9. **隐藏目录搜不到 ≠ 没有（2026-09-22 沉淀）**：ripgrep 系搜索默认跳过隐藏目录——`.workbuddy` / `.codebuddy` / `.git` 里的内容搜不到，「No matches」是**假阴性**。搜 memory、隐藏工作区、`.git` 配置必须用 PowerShell 显式遍历（`Get-ChildItem -Force -Recurse`）。
10. **PowerShell 条件表达式不能直接塞进参数位（2026-09-22 沉淀）**：`("... {0}" -f (if($x){'A'}else{'B'}))` 会让**整条语句失效**；叠加 `$ErrorActionPreference='SilentlyContinue'` 时连报错都被吞，只表现为「那一行没输出」。必须先赋值到变量，或用 `$(...)` 子表达式。
11. **TrimEnd 字符陷阱 + 全树扫描超时（2026-09-22 沉淀）**：① `'\\'` 在单引号里是**两个字符**，`.TrimEnd('\\')` 抛 `String must be exactly one character long` —— 用 `[char[]]@('\')`；② 递归 `Select-String` 扫 `G:\repos` 全树（11 万+ 文件）会超 120s 被杀，定向搜索一律用 ripgrep（grep 工具），别用 Select-String 全树。
12. **跨副本比对必须先归一化换行符（2026-09-22 第二次踩到，与 09-19 同源，已固化为动作）**：`santi-teleprompter` 本地副本初判「25 个文件内容不同」，归一化 CRLF/LF 后**真差异仅 2 个**（package.json / package-lock.json）。动作固化：**字节哈希只用于「发现候选」，下结论前必须做 EOL/BOM 归一化文本比对**。
13. **对比脚本的主键必须是 origin 仓名，不是目录名（2026-09-22 沉淀）**：本地目录名可与远端仓名不同（`G:\platform` ↔ 远端 `allin-platform`），以目录名为主键会漏配、导致总账不平（本次曾复现「116 ≠ 117」）。凡做「本地 ↔ 远端」对账，先由 `git config remote.origin.url` 解析出仓名再匹配。
14. **DSH 会话内验证 Electron 会被 `ELECTRON_RUN_AS_NODE` 污染（2026-09-22 沉淀）**：本 harness 给子进程注入 `ELECTRON_RUN_AS_NODE=1`（**仅 Process 作用域，User/Machine 未设**），此时 `electron.exe --version` 打印的是内嵌 **Node** 版本（Electron 30 → `v20.16.0`）而非 Electron 版本，极易误判「装错版本」。验证 electron 必须 `Remove-Item Env:ELECTRON_RUN_AS_NODE` 或直接读 `dist/version`；同理，**在 DSH 会话里启动任何 Electron 应用前都要清掉该变量**，否则应用会以 Node 模式运行。
15. **npm 重装大依赖会挂起（2026-09-22 复现）**：`npm uninstall electron` 在本机跑 13 分钟零输出（同「Node undici 大 tarball 不可靠」根因）。**外科式替代**：保留 `node_modules/<pkg>` 与声明，直接跑该包的 `install.js`（electron 从其 `%LOCALAPPDATA%\electron\Cache` 解包），10s 完成且不用动依赖树。
16. **仓内 pre-commit/pre-push 门禁在 DSH 沙箱里会「假红」（2026-09-22 沉淀并已实证，private-radio-stations）**：钩子形如 `#!/bin/sh` → `node scripts/check.mjs --fast`，而 check 内部对每个文件再 `spawn('node')` 做语法检查——**沙箱禁止管道 stdio 的子进程**，于是逐文件报 `x syntax: …（node 无法执行：node；EBUSY）`、整体 `check FAILED: 60`，**极像「代码全坏」**（该仓 pre-commit 与 pre-push 各拦一次）。处置动作：① 用 PowerShell 逐文件 `node --check` 独立复核（本次 78/78 全绿）；② 据实以 `git commit --no-verify` / `git push --no-verify` 完成，并在**提交信息与交接文档里写明理由与证据**；③ 请用户在正常终端复跑门禁。**实证**：用户复跑 `npm run check` → **`check PASSED`**（syntax/cordis.yml/package.json/whitespace/unit tests 全绿），确认是环境边界而非代码缺陷。**结论：不要把沙箱边界当成代码缺陷去改代码。**
17. **PowerShell 变量名含 `?` 的静默 URL 陷阱（2026-09-22 沉淀，gitee API 实测）**：`"$repo?access_token=$tok"` 里 `?` 是**合法变量名字符**，PowerShell 会把 `repo?access_token` 当成**一个变量名**（未定义→空串），URL 静默变成 `…/repos/siwpan/<token>`，接口返回 **403 Forbidden**——报错完全指不到真因（看着像 token 失效或接口被封）。**规则：字符串里变量后紧跟 `?` `-` `:` `=` `.` 等字符时一律写 `${var}`**。本次 85 仓社区指标采集因此 100% 失败，加 `${}` 后同一端点立即正常。附带：**别用 `powershell`(5.1) 去跑 pwsh 写的无 BOM UTF-8 脚本**（中文路径会烤成乱码、报「Cannot find path」）——用 UTF-8 存脚本、并统一用 pwsh 执行。
18. **批量正则改文档必须先 dry-run（2026-09-23 沉淀，85 仓 README 去本地化实测）**：把 `X:\…` 批量替换成占位符时，字符类的**排除集漏一个字符就吞掉正文**——本次两处实证：① 未排除全角 `（` → `G:\allin\docs\x.md（2026-08-25 用户拍板…` 被吃成 `<PATH> 用户拍板…`；② 未排除反引号 → `` `G:\allin\docs\x\ports.yaml` `` 的**收尾反引号被一并吃掉**，行内代码块破掉。另：尾部加 `(?<![\\/])` 防尾随斜杠反而让单独的 `G:\` 漏替换 → 改为替换后再清理 `<PATH>\`。**铁律：批量文本改写一律先 `-DryRun` 打印 before→after 样本，且排除集必须含 `（）「」《》【】、，。；：？！—=*` 与反引号/引号/尖括号/竖线**；改完必须回扫残留数 = 0 才算过。
19. **改多仓时只 `git add <指定文件>`，绝不用 `git add -A`（2026-09-23 实证价值）**：批量改 85 仓 README 时，`foolproof-operation` 当时正有另一路会话在做 Cordis 架构重构（工作区里 `core/ plugins/ index/ tests/ docs/` 均为未提交在建内容）。因为脚本只 `git add README.md`，84 个提交**逐一核验均只含 README.md**，零卷入他人在建工作。**凡在多仓并发环境下操作，逐文件 add 是硬纪律**；提交后再用 `git show --name-only HEAD` 回扫确认提交面。
    - **状态订正（2026-09-23 晚，避免后期会话误判）**：上条括注描述的是**当时那一刻的工作区状态，不是长期并行常态**。该 Cordis 重构按阶段推进，**阶段 0~5 已于 2026-09-23 当日完成**（阶段 6 文档/推送待做）；工作树**仍未提交、未推送**。后期会话读此条时**不要假设还有另一路会话在改该仓**——如需接手，先 `git status` 看实际工作区，再按 `G:\allin\docs\md\allin主工作区\USN索引与Cordis内核规划_2026-09-23.md` 的阶段表核对真实进度（该规划文档的阶段勾选即事实源）。

20. **PowerShell 函数禁用 `$args` 当参数名（2026-09-23 沉淀，代价一次 600s 超时 + 一次误判）**：`function Run($label, $args)` 里 `$args` 是**自动变量**（未绑定参数数组），声明为形参后 `& python script.py @args` 会 splat **空数组** → 实际执行 `python script.py`（无参数）→ **启动了 tkinter GUI**，进程永不退出，批处理被 600s 杀掉且**零输出**。当时误判为「`cli envs --backend walk` 全盘遍历挂死」，实测证明 walk 与该超时无关（无根时 0.00s 返回空），**结论已回头更正**。**纪律**：① 形参禁用 `$args`/`$input`/`$PSBoundParameters`，改 `$cmdArgs`；② 批处理每条命令都要有超时与回声，出现「零输出 + 超时」先怀疑脚手架本身；③ 误判必须回头纠正结论，不得让错因留在文档里。
21. **SQLite 的 `IN (…) COLLATE X` 用不上 `COLLATE X` 索引（2026-09-23 沉淀，foolproof-operation）**：批量等值查询写成 `WHERE name IN (?,?,?) COLLATE NOCASE` 会退化为**全表扫描**（实测 251 万行 **355ms**），改成逐项 `name = ? COLLATE NOCASE OR …` 才命中索引（**2.0ms，快 177 倍**）。**纪律**：有索引 ≠ 用了索引——关键查询必须实测 `EXPLAIN QUERY PLAN`，并把「不出现 `SCAN <表>`」**锁进测试**，防止日后被「简化」回去而性能静默劣化。
22. **把 `PYTHONWARNINGS=error::ResourceWarning` 当作黄金值跑一次（2026-09-23 沉淀，foolproof-operation）**：它能抓出「功能正确但资源泄漏」的静默缺陷——本次抓到 ① `IndexStore.open()` 自建连接却按「外部传入」判所有权，导致 `close()` **从未真正关闭连接**（被 WAL + 每批 commit 掩盖，长跑持续泄漏句柄）；② 测试代码里 `open(...).write(...)` 的句柄泄漏；③ 打开失败路径不回收连接。**纪律**：资源所有权必须显式声明；泄漏类缺陷靠「告警升级为错误」暴露，不要指望读代码看出来。
23. **PowerShell 做批量文本改写有两个会「写坏文件」的陷阱（2026-09-23 沉淀，各踩一次）**：① **单元素嵌套数组会被展平**——`@{ pairs = @( @('A','B') ) }` 取到的是 `@('A','B')` 两个**字符串**，于是 `$pair[0]` 变成字符串首字符、`$pair[1]` 变成第二个字符：本次把 `'plugin="plugins.installer:…"'` 的 `$pair[0]/[1]` 取成 `'p'/'l'`，**全文件 p→l**（"pip" 变 "lil"，410 处），文件损坏；**多元素数组不会展平**，所以同样的写法在另一处正常——这种「时对时错」最容易骗过人。② **`[IO.File]::ReadAllText/WriteAllText` 用的是 `Environment.CurrentDirectory`，不随 PowerShell `Set-Location`/`cd` 变**——相对路径会落到启动目录（本次落到工作区 `G:\job`，报「找不到路径」而替换计数显示 0，看着像「没匹配」实为「读的不是那个文件」）。**纪律**：批量改写一律 **Python 脚本 + 绝对路径**（Python 无展平、无 CWD 歧义），并坚持 dry-run 报计数 + 改后立即 `py_compile`/跑测试（本次正是靠 `py_compile` 与测试数量从 271 掉到 241 才发现）；**改文件前后用 `git checkout -- <file>` 兜底恢复**。
24. **`.Replace` 计数放大的信号**（2026-09-23 同上）：批量替换后若「处数」远超文件里该字符串的合理出现次数（本次 410 处），**立刻停下看现场**，不要继续往后续文件跑——这是类型/展平错误的典型指纹。

> 理论面见同目录《Cordis 理论笔记.md》；最小可运行样例见 G:\notpython\cordis-snake-example（selftest 41/41）。

25. **PowerShell splat 单个字符串会按「字符」展开（2026-09-23 沉淀，代价 5 仓提交静默失败）**：`[string]$files = (git status --porcelain ...)` 在**只有一行**输出时是标量字符串，`& git add @files` 会把它按字符拆成 `s` `c` `r` `i` `p` `t` `s` `/` … 逐个当参数（git 报 `fatal: /: '/' is outside repository`）；`$files[0]` 同样只取到首**字符** `'s'`。多行输出时是数组，所以「时对时错」。**纪律**：一律写 `[string[]]$files = @(...)`；取元素前先看 `$files.GetType().FullName`。**同一族的第二个坑（本轮同时踩到）**：循环里 `& git commit ... | Out-String` 会把 exit code 与失败输出一起吞掉，只打印「On branch master」——**判定提交/推送成功不能看有没有报错，必须核对 `git log -1` 或 `@{u}..HEAD` 是否真的变化**。
26. **判「路径是否已失效」的扫描器有三个必须堵的漏（2026-09-23 沉淀，硬编码去本地化实测）**：① **只对 MUST_FIX 行判死会漏掉赋值型行**（`MUSIC_ROOT = Path(r"G:/radio/music")` 被判 LIKELY_FIX，从未进 T1 清单，audio-separator 一仓就漏 25 处）；② **转义双反斜杠写法判活**——源码里 `"D:\\allin\\not\\OK"` 取「前两段」得到 `D:\`，而 `D:\` 存在，于是**死路径被判成活的**（py_test_runner/fish 共 19 处）；③ 死根清单若取自①的产物，则清单外的死根（`G:\csmusic*`）永远查不出。**固化口径**：对**全量命中**判死 + 分隔符容错 `[\\/]{1,2}` + 系统路径白名单 + 命中按「CODE 有效行 / CODE 注释行 / DOC·CFG」三分，只有 CODE 有效行算阻断项。
27. **多行字面量替换必须先归一化 EOL，且 here-string 的闭合符不能与其他 token 同行书写（2026-09-23 沉淀）**：CRLF 文件里用 LF 拼的搜索串 `.Contains()` 恒假（静默「未命中」）；`@'...'@.TrimEnd()` 这种「闭合符 + 方法调用同行」写法会让解析器把后续行吞进字符串。**纪律**：批量替换统一走「先测文件 EOL → 把搜索/替换串的 `\n` 换成该 EOL」，here-string 一律先赋值给变量再使用；替换后**必须** `py_compile` / 跑测试，且核对「替换处数」是否与预期一致（计数异常 = 有东西被吃掉）。

28. **发布链路三个坑（2026-09-23 沉淀，foolproof-operation 首发 PyPI 实测）**：① **第三方 CLI 的富文本进度条在 GBK 控制台直接崩** —— `twine upload` 的 rich 进度条输出 `•`（U+2022），默认 936 代码页抛 `UnicodeEncodeError` 且**上传中断**（与本地 CLI 的 emoji 崩溃同源）。动作：跑 twine/pip 等带富文本输出的工具一律 `PYTHONIOENCODING=utf-8` 并加 `--disable-progress-bar`。② **验证「安装后的包」必须在源码目录之外运行** —— 在仓库根执行 `python -c "import foolproof_operation"` 命中的是**本地源码树**而非刚装进 venv 的副本，读出正确版本是**假绿**（当时安装其实失败了）。动作：先 `cd` 到源码目录之外，并打印 `模块.__file__` 作为证据。③ **刚上传后索引有 CDN 滞后**：TestPyPI/PyPI 的 `/simple/` 页面可能仍列旧版本（本次 2 分钟内 pip 只看到 1.1.0，而 JSON API 已列出 1.1.1）。动作：以 `https://<index>/pypi/<pkg>/json` 判断上传成功，并**按上传产物的直链 URL 安装验证**；**索引未刷新时绝不重复上传同一版本**（同名版本不可重传）。
29. **PowerShell 通配符不展开给原生命令（2026-09-23 第二次踩到）**：`python -m py_compile core/*.py` 把**字面量** `core/*.py` 传给 Python → `py_compile exit 1`，看起来像「代码编译失败」。动作：用 `Get-ChildItem ... -Recurse | ForEach-Object { $_.FullName }` 收集绝对路径再 splat（与第 11、23 条同族：PowerShell 的参数传递语义必须按「它实际传了什么」验证，而不是按意图推断）。

> **本轮事实补充（2026-09-23，硬编码去本地化第 1 批）**：
> - **MIDI 素材库**：原 `G:\midi` 已不存在；4 个 `*_130406` 现存 `G:\notpython\MusicStudioPro\Data\MIDI`，2026-09-23 已**复制**回 `G:\repos\midi\pro4\MusicStudioPro\Data\MIDI`（`pro4/` 在 `.gitignore`，不进库）。合并后 `scan_midi_assets(G:\repos\midi)` = 6 素材齐，audio-generation 的 bridge 测试由「永远跳过」变为 **55 passed / 0 skipped**。
> - **`bloodmusic` 是 junction**：`F:\Python314\Lib\site-packages\bloodmusic` → `G:\repos\audio-generation`，仓内改动对全局解释器立即生效（无需 pip 重装），改坏即污染所有调用方。
> - **素材归位地在 `G:\assets\`**（2026-09-23 实测）：`radio_music_stems`、`csmusic_stems`、`csmusic`、`yasuobao`、`musicdown`、`fonts`、`musickit_transcode`、`radio_special_instruments`、`transcode_work`。原 `G:\music\*`（radio_music_stems / csmusic_stems / yasuobao）、`G:\midi` 等顶层分类目录均已不存在；musickit 与 audio-separator 的 stem/归档默认值现指向这里（可被 `STEMS_ROOT` / `CSMUSIC_STEMS_ROOT` / `YASUOBAO_SRC` 覆盖）。
> - **编译工具链其实在盘上（补正旧记录）**：`g++/clang++` 虽不在 PATH，但存在 `F:\VS2022\VC\Tools\Llvm\x64\bin\clang++.exe`（另有 Android NDK 与 `.workbuddy\binaries\llvm` 下的副本），`cl.exe` 在 `F:\VS2022\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe`。**C/C++ 改动可以真编译验证**（本次 fish `golden_runner.cpp` 即用 clang++ 编译并实跑通过）。
> - **`G:\notpython` 是资产/项目再分布区**：`merged_gui`、`kontakt_transcode`、`MusicStudioPro` 等原 `D:\allin\*`、`G:\tools\*` 的内容落到这里，跨盘引用时先 `es.exe` 全盘定位再写死。
> - **明文凭据 remote 已清理（2026-09-23）**：`bee`、`particle` 的 origin URL 原有内嵌令牌（形如 `https://siwpan:<TOKEN>@gitee.com/...`），已 `remote set-url` 改为无令牌 URL 并验证推送正常（系统级 `credential.helper=manager` 供凭据）；令牌真值只在 `G:\私人令牌.txt`。**`G:\` 旧目录侧另 2 处待盘点**。

30. **门禁必须「现在就能绿」，否则等于没有门禁（2026-09-23 沉淀，硬编码路径门禁 G:\tools\gate\scan_hardcoded.ps1）**：一次普查扫出 323 条存量阻断项（45 仓）——若门禁直接 `有命中即 exit 1`，任何仓都无法提交，团队第一反应是绕过它。**正确形态 = 基线棘轮**：`-WriteBaseline` 固化存量，日常只对**基线之外的新增命中**返回 1（存量清理后用 `-WriteBaseline` 刷新）。同时**门禁自身必须有测试**：`-SelfTest` 要同时验证「能抓」（临时仓放死路径 → 检出）与「不误报」（系统路径 / URL / 测试夹具 / `e:\n` 转义伪影 / 占位符），并验证「写入基线后新增 = 0」；再加一条端到端负例（新增死路径 → 只报那 1 条 → exit 1）。**只验证「能抓」的门禁会退化成噪声，只验证「不误报」的门禁会退化成摆设。**
31. **「拼接式替换对」已第三次丢行，必须改用 here-string 变量（2026-09-23 第三次复发，教训升级）**：在 `@( , @($old, '注释' + "`n" + '代码') )` 这种「参数位拼接」写法里，PowerShell 会**静默丢掉拼接出来的那一行**——只留下注释，代码行消失。三次实证：① musickit `_dedupe_all_pools.py` 丢了 `with open(...)`（触发 IndentationError，被编译抓到）；② musickit `ingest_csmusic.py` 丢了 `CS = ...`、`make_archive_manifest.py` 丢了 `YASUOBAO = ...`（**编译查不出**，是运行时探针才抓到 NameError）；③ musickit `build_framework.py` 丢了一整行 `r = subprocess.run(...)`（SyntaxError）。**纪律**：替换对一律**先赋值给变量**（here-string 或 `$new = "a`nb"` 单独一行），绝不在 `@(...)` 里做 `+` 拼接；改完除了 `py_compile` 还必须跑**运行时探针**（把该文件 import 一遍并打印你本次新增/改动的那几个名字，确认都真的定义了、路径也存在）。
32. **`py_compile` 只查语法，查不出「用了没导入」「str/Path 做除法」；用 AST 检查器兜底（2026-09-23 沉淀）**：第 1 批去本地化里有 6 个文件 `py_compile` 全绿，实际是 ① `build_framework.py` 用了 `tempfile` 没 import、且 `tempfile.gettempdir()`（str）与 Path 做 `/`；② 三处「替换丢行」导致的未定义名；③ 三处**历史遗留**未定义名（`audio-pipeline/cli.py` 阶段B 的 `make_source` 没导入、`audio-separator/_inspect_run.py` 用了 `time` 没 import、`py_test_runner/main.py` 注解用了没导入的 `DynamicTestResult`）。**固化工具**：`G:\tools\gate\check_undefined_names.py`（AST 收集 Load 名 vs import/赋值/def，报告全文件从未定义过的名字；支持 `--repo <仓>` 自动取「paths) 提交」改过的 .py）。**纪律**：改代码的收尾动作 = `py_compile` + `check_undefined_names.py` + 一次真实运行（哪怕只是 import 或 `--help`）。
33. **门禁类脚本的参数绑定要兼容 `-File` 调用（2026-09-23 沉淀）**：`pwsh -File scan_hardcoded.ps1 -Repos a,b,c` 里 `a,b,c` 是**一个字符串**（`-File` 走的是字符串绑定，不做 PowerShell 语言层的数组解析），于是报「仓不存在：G:\repos\a,b,c」并 exit 2。**纪律**：凡给 CLI 门禁做 `-Xxx` 列表参数，脚本内部都要 `-split ','` 展开一次，并让报错提示写明「多个值用英文逗号分隔」。

> **存量清零事实（2026-09-23 收盘）**：硬编码路径门禁存量 **99 条 → 0**（31 仓 36 个提交，未推送）；基线文件 `hardcoded_gate_baseline.csv` 已刷新为**空**，此后任何新增死路径都会被拦。配套工具两个：`G:\tools\gate\scan_hardcoded.ps1`（死根门禁，自带 `-SelfTest`）与 `G:\tools\gate\check_undefined_names.py`（AST 未定义名检查，弥补 py_compile 盲区）。本轮还顺带修掉 7 处静默缺陷（第 1 批遗留 3 处 + 历史遗留 4 处）与 25 处日期笔误。
> **推送凭据小坑（2026-09-23 实证）**：个别仓 `git push` 会稳定报 `could not read Username for 'https://gitee.com'`（且 `--dry-run` 也报），同机其它仓正常、两仓 `credential.*` 配置逐项一致 → 属 GCM 侧该仓凭据缺失/损坏，不是仓库配置问题。救急办法：用 `G:\私人令牌.txt` 的 gitee 令牌做**一次性 URL 推送**（`git -c credential.helper= push "https://siwpan:<tok>@gitee.com/siwpan/<repo>.git" <br>:<br>`），不落盘、不打印令牌；事后确认 `remote.origin.url` 仍为无令牌 URL。

34. **判「路径是否已失效」不能只看前几段（2026-09-23 沉淀，门禁口径实证）**：把路径前 1~3 段当「根」判存在性会漏掉一整类死路径——实证 `C:\Users\13122\Desktop\allin\aup\play.py` 的根 `C:\Users\13122` 存在，于是被判「活」，实际 `Desktop\allin` 早已不在（同类还有 `Desktop\{stay,santi,bofang,txt,waper}\…`、`WorkBuddy\<时间戳>\…`）。**正确口径 = 由浅到深检查「该路径的父目录是否存在」**；本工作区已把「代码行深层缺失」升级为门禁阻断项（文档类需 `-Deep`）。**同族坑**：路径里含 `spec/`、`tests/` 等字样会被「测试夹具」豁免整片漏检（`weor/legacy/spec/*.spec` 实证）——豁免规则必须限定文件类型与目录层级，不能只看片段子串。

35. **中文 Windows 上 `json.load(open(path))` / `json.dump(..., open(p,"w"))` 必须显式 `encoding="utf-8"`（2026-09-23 沉淀，musickit 实证）**：默认编码是 **GBK**，读写 UTF-8 的 JSON 会直接崩或**写出 GBK 文件**（后者更隐蔽：文件仍能生成，内容却被写坏）。实测 `index.json` / `styles_manifest.json` / `manifest_index.json` 三个文件在默认编码下加载**全部** `UnicodeDecodeError`；此前有人靠 `PYTHONUTF8=1` 绕过——**绕过的是症状，不是缺陷**。纪律：JSON/文本读写一律显式 `encoding="utf-8"`（写侧同样），修完**不设 `PYTHONUTF8`** 复跑一次才算修好。
36. **陈旧生成物要「重跑生成器」，不要手改产物（2026-09-23 沉淀，musickit 专辑流水线）**：`burbidge_album/index.json`（被跟踪、4.79 MB、26,978 条）里写着已失效的采样库根；正确处置＝先修生成器（含编码缺陷）→ **就地重跑** → 用 `git diff --numstat` 确认差异只落在预期字段（本例 1 增 1 删，只是 base+path 前缀）→ 再提交。**手改生成物会把「生成器与产物不一致」这个真问题掩盖成「看起来对了」。**

37. **git 配置里的「空值」不是「未设置」——`credential.helper=` 空值会清空 helper 链（2026-09-23 沉淀，players-unified 实证）**：该仓 `.git/config` 有一条空值 `credential.helper=`，于是系统级 `manager` 与 gitee 专用 `store` **全部失效**，每次 push 都报 `fatal: could not read Username for 'https://gitee.com'`（`--dry-run` 同样报）。**排查要点**：`git config --get credential.helper` 对「空值」和「未设置」都返回空，光看它查不出来——必须用 `git config --list --show-origin | Select-String credential` 看**有没有那一行**（或直接 grep `.git/config` 里的 `helper\s*=\s*$`）。**修复**：`git config --unset credential.helper`（可逆，且不动系统/全局配置）。**教训**：连续三次用「一次性令牌 URL」绕过报错属对症不对因，遇到重复出现的认证类故障，先做**配置差异比对**（同机正常的仓 vs 出问题的仓）。

38. **中文 Windows 控制台 GBK 会让带 `✓`/emoji 的输出直接崩，且「重定向输出时不复现」（2026-09-23 沉淀，wav_music_gen 实证）**：`python demo_vocal.py` 在 cmd 里 `exit 1`，报 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`；把输出重定向到文件或在管道里跑就**正常**——所以「跑过一次通过」可能是假象（本次即因为这个假象被漏掉）。**纪律**：① 入口脚本统一 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（本工作区 `build_framework.py` 已有先例）；② GUI/CLI 冒烟**必须在默认控制台直跑一次**，不能只看重定向输出；③ 同类已发现多处（sandbox `run.py`、mc-clone `launcher.py --probes`）。

39. **区分「链接期依赖目录」与「运行时目录」——别把脚本找错目录当成依赖坏了（2026-09-23 沉淀，pluginplayer/libass 实证并回头更正）**：libass 体检脚本原指向 `vendor/libass/bin`（32 个 DLL，**链接期**：include/lib + 部分 DLL，缺 MinGW 运行时三件套 libgcc/libstdc++/libwinpthread），报 `libass-9.dll` 加载失败 err=126；我当时判为「依赖链本身的既有问题」——**判断错误**。实测（新进程只加一个目录）：`pluginplayer/dist`（41 个 DLL，**运行时闭包**）单独可加载且 `ass_library_init` 成功；`build.py` 注释本就写明「运行时由 Windows 加载器从 dist/ 解析 libass-9.dll 及其闭包」。**纪律**：① 报「依赖缺失」前，先用「新进程 + 只加一个候选目录」逐个验证，并确认自己指的是**运行时**目录；② 修复方向应是**让脚本去对目录**（本次改为 `PP_LIBASS_BIN` → `dist/` → vendor 兜底 → fail-loud），而不是往链接期目录里塞运行时 DLL（`vendor/`、`dist/` 都不入库，塞了也不可复现）；③ 禁止为了「让它能跑」去依赖 mpv 之类跨盘外部目录——那是换机即坏类。

> **libass 运行时闭包已纳入依赖准备（2026-09-23）**：`tools/fetch_deps.py` 现在会补齐 `vendor/libass/bin` 缺的 MinGW 运行时三件套（libgcc_s_seh-1/libstdc++-6/libwinpthread-1），取件优先级 `PP_LIBASS_RUNTIME_SRC`/`PP_MINGW_BIN` → `PP_GXX` 目录 → `F:/mingw64/mingw64/bin` → 本仓 `dist/`；新增 `--libass-only`（秒级补齐+加载体检）与 `--skip-libass`。至此**构建前**用 vendor 目录也能跑通 libass 体检（17/17），不必等 `build.py` 产出 dist。

40. **批量改写的收尾动作必须「编译通过才允许提交」，不能只看日志里打印了什么（2026-09-23 沉淀，本轮真实事故）**：改写 `fetch_libass.py` 的提示语时把换行插进了 **f-string 字面量内部** → 该文件变成语法错误（`py_compile` exit 1）；而我的提交脚本**把 exit=1 打印出来后仍继续 `git commit` + `git push`**，于是坏文件进了远端，得再补一个修复提交。**纪律**：① 提交前对**本仓全部跟踪 .py**（不只改动文件）跑一次 `py_compile` 并**断言**全绿，不通过就中止；② f-string / 单行字符串里绝不能插换行（需要多行用三引号或先拼变量）；③ 日志里的 `exit=1` 必须被脚本判为失败——「打印了就继续」等于没有门禁。

41. **自检/验证脚本的退出码必须如实，禁止「打印提示就返回 0」的假绿（2026-09-23 沉淀，`_verify_libass_load.py` 实证）**：`players-unified/pluginplayer/_verify_libass_load.py` 原来任何分支都以 `exit 0` 结束——DLL 只加载成功 12/20 时只打印一行提示就正常退出，只有全绿才打印 `[PASS]`。我用它做「拿走运行时三件套」的阴性对照时，输出明明是失败，`$LASTEXITCODE` 却是 **0**。**纪律**：① 验证/自检脚本的退出码 = 判定结果（数量不齐、`ass_library_init` 返回 NULL 等一律非 0），提示语只是补充；② 新增或改动任何「体检脚本」时，**同时跑阳性与阴性对照**（本例：全量 20/20 → exit 0；人工移除三件套 → loaded 12/20、exit 1），只跑阳性等于没验证；③ 阴性对照要拿**真实产物**做（本例直接删三件套），不要用「注释掉判断」的方式模拟。

> **libass 运行时三件套改为默认随上游闭包抓取（2026-09-23；本段更新前一条 blockquote 里「刻意不抓」的口径）**：`tools/fetch_libass.py`（pluginplayer 与 players-unified/pluginplayer 两副本字节一致）里 `EXCLUDE_RUNTIME` → `RUNTIME_DLLS`，默认从上游 MSYS2 抓 `libgcc_s_seh-1.dll`/`libstdc++-6.dll`（同属 `mingw-w64-x86_64-gcc-libs`）与 `libwinpthread-1.dll`（`mingw-w64-x86_64-libwinpthread`），使得 `vendor/libass/bin` **在还没跑 build.py（无 dist/）时**即为完整可加载集（呼应 `build.py:328` 的「bin/ 下即完整可加载集」声明）；`--skip-runtime` 退回旧行为（三件套交 `fetch_deps.py --libass-only` 从本机工具链/dist 补齐，离线可用）。同时给传递依赖抓取阶段补上 `DOWNLOADS_SHA256` 钉死校验，并钉死 gcc-libs-16.2.0-3 / libwinpthread-14.0.0.r375 的实测哈希。**实测**：真实联网跑通（第 1 轮抓 gcc-libs → 第 2 轮抓 libwinpthread → 第 3 轮闭合），libass 闭包 17 → **20** 个 DLL；空 vendor + 空 tmp（无解包树、无 TOFU）从归档纯净重放后加载校验 **20/20 PASS**；`--skip-runtime` 路径 32 个 DLL、闭包完整、exit 0 且显式列出被跳过的两项；**篡改 gcc-libs 归档一字节 → 钉死校验硬失败 exit 1**。上游抓到的三件套与本机 MinGW 工具链版本**并非同一份二进制**（体积/哈希均不同：如 libgcc_s_seh-1 上游 150,998 B vs 工具链 142,336 B），两条来源路径都可用、不必互斥。提交：pluginplayer `dc8d6c3`（main）、players-unified `9ed3c93`（master），均已推送。

42. **「把文件搬到别处」是一类会静默弄坏门禁与链接的结构变更；副本仓的门禁必须单独跑（2026-09-23 沉淀，players-unified/pluginplayer 副本实证）**：该副本导入时（`2f146bb`）把 `AGENTS.md`/`CLAUDE.md`/`DEPLOY.md`/`ENHANCEMENT_PLAN.md`/`THIRD_PARTY_NOTICES.md` 放进了 `docs/`，引用却没跟着改，于是**三条门禁长期红**（`third-party-notices` 永远「文件不存在」、`doc-links` 17 处断链、`docs-index` 缺 2 篇），而**源仓 `pluginplayer` 同三条全绿**——只看源仓会得出「一切正常」的错误结论。**纪律**：① 搬动/移动文件后必须同时核三处：**相对链接**（含 README 内链）、**生成器与门禁里写死的路径**（本例 `gen_third_party_notices.py` 的 `OUT=ROOT/…` 与 `verify.py`）、**索引文件**（如 `docs/README.md`）；② **副本/镜像仓要单独跑该仓自己的门禁**，源仓绿 ≠ 副本绿；③ 判断「是不是我改坏的」用 `git status`（本次只有 5 条 `R100` 改名，门禁输入没变 → 失败必属既有漂移）。**同族发现**：门禁若把环境依赖（如 `host-js/node_modules`）当作事实来源，**没装依赖的检出会判红**——这类红先做环境补齐（`npm install`）再看，别急着改文档或改代码。

> **许可分布事实（2026-09-24 全域收尾逐仓核对）**：`G:\repos` **108 仓**（原记 107，见铁律 4 的仓数订正）= **107 个 MIT + 1 个 GPL**，唯一的非 MIT 是 **`pluginplayer`（`GPL-3.0-or-later`）**——它随包分发 gyan.dev 的 FFmpeg `full_build-shared`（该构建是 **GPL v3**）与 MinGW-w64 GCC 运行时，**属于必须随上游走 GPL、不能改 MIT** 的情形；仓库自己已把理由与合规义务写清（README「开源与合规」L216-233 + `THIRD_PARTY_NOTICES.md` 逐条证据与复核命令）。gitee API 复核两仓均 `public=true`（pluginplayer license=GPL-3.0 默认分支 main；players-unified license=MIT 默认分支 master）。**据此读铁律 0 的正确姿势**：默认「公开 + MIT」；但当发布物**链接/随包 GPL/AGPL 上游**时，许可必须随上游（改 MIT 反而是违规）。此处只记事实，未改铁律 0 文本与预设 persona（用户 2026-09-24 选择「只记事实」）。

> **全域同步事实（2026-09-24 收尾扫描 116 仓）**：`G:\repos` **108 仓**（原记 107，见铁律 4 的仓数订正）+ `G:\allin`、`G:\platform`、`G:\local\{markdown,novel-run}`、`G:\archive\`4 个归档、`G:\tmp\santi-remote` = **116 个仓，0 未提交、0 未推送**。扫描一度报 `calculator`（2 条）、`mathematical-formula-renderer`（1 条）「未推送」，`git ls-remote` 核实**远端 HEAD 与本地完全一致**——是本地 remote-tracking ref 陈旧（该仓此前用 URL 直推、后续没 fetch）导致的**假阳性**；`git fetch origin` 后差异归零。**教训**：判「未推送」只信 `git ls-remote`（对远端实际值），`origin/BR..BR` 只能当线索——同一坑已在 MEMORY 里出现过一次（推送凭据/ref 陈旧同族）。

43. **批量改写路径这类字符串时，Python 非 raw 字符串里的 `\a`/`\b`/`\f`/`\t`/`\v` 会被解释成控制字符（2026-09-24 沉淀，crawl-hub 实证）**：文档枢纽从 `G:\docs` 迁到 `G:\allin\docs` 后，`crawler_registry.py` 里那句提示文案 `f"...先查 G:\allin\docs\md\allin主工作区\端口分配表.md"` 运行时打印成 `G:\x07llin\docs\md\x07llin主工作区\端口分配表.md`——`\a` 变成 **BEL(0x07)**（旧路径 `G:\docs\md\allin主工作区\...` 就已经中过一次，改名只是又叠加一个）；`\d`/`\m` 是非法转义，只发 `SyntaxWarning`（**不报错，最容易被忽略**）。**纪律**：① 路径字面量一律用 **raw 字符串**（`r"..."` / `rf"..."`）或双反斜杠——Windows 路径里 `\a`（`\allin`/`\assets`）、`\t`（`\tmp`/`\tools`）、`\n`（`\new`）、`\b`（`\bin`）、`\v`、`\f` 全是高危；② 改写后必须**真实运行一次看输出**（`repr()` 或触发该分支），只看源码字符串看不出来；③ 验证时用 `python -W error::SyntaxWarning -m py_compile` 把非法转义升级成错误，能顺带抓出 `\d` 这类隐患。**同族**：PowerShell 单/双引号对 `\` 语义不同、JS 模板串里 `\` 仍需转义——跨语言批量改路径要逐语言确认转义规则。**第二次实证（同日，audio-generation）**：我在 **docstring** 里写了「与 G:\repos\zhuangtaiji 的 web/server.py 保持同一口径」，`\z` 立即被判非法转义；默认 `py_compile` 只发警告、代码照跑，是 `-W error::SyntaxWarning` 把它拦下的——**文档字符串同样属于字符串字面量，别忘了它**。

> **共享仓并发写入纪律的由来（2026-09-24 实证）**：文档枢纽迁入 `G:\allin` 并推送的过程中，**另一条会话/进程也在同一仓提交并推送**（我这边看到 `16688120` 出现在我推完之后；对方看到 `10929df6`；两条提交线性、互不覆盖、`is-ancestor` 均为 0）。值得记的教训是我这边的动作：当时 `git status` 报「有改动」，我按换行噪音处理跑了 **`git checkout -- .`**——跑之前 `git diff --ignore-cr-at-eol --numstat` 为空、事后 `git fsck` 今日无 dangling commit，所以没吞掉对方东西，但在**别人可能正在写的共享仓**里这就是危险动作。**纪律（见铁律 43）**：共享仓动任何写操作前后都要 `git fetch` + 看 `ls-remote`；禁止 `checkout -- .` / `reset --hard` / 强制推送；发现并发就停下来对齐分工。

> **目录索引.txt 的口径（2026-09-24 二次裁定：形态换代 —— 全盘快照 → 项目目录文档化索引）**：
> **旧形态已作废**：原 `目录索引.txt` 是 2026-08-28 15:12 的**全盘文件快照**（48.53 MB / 555,220 行，
> 逐条列每个文件；行构成 `repos` 44% + `Temp` 21.9% + `notpython` 19.1% + `assets` 8.5%，
> 其中大量是 `node_modules`/`dist` 里的第三方文件与临时区内容）。**它过于臃肿、无维护** ——
> 快照自带 08-28 时点，之后一切增删改名都不在其中。**用户裁定换形态**。
> **新形态**：**118 个项目 / 153 行 / 32.55 KB**，每个项目一条 = 标题 + 首段摘要(≤120字) +
> README 相对链接 + 体量。**以各项目自己的 README 为唯一事实源，本文件不复制正文**（要详情点进 README）。
> 覆盖 `repos`(108) + `local`(7，排除归档/构建输出) + `platform` + `tools` + `allin`。
> **生成器**：`G:\tools\build_dir_index.py`（干跑默认，`--apply` 落盘；带跨次运行的体量缓存
> `G:\tools\.dirsize-cache.json`，按 mtime 失效 —— 命中缓存时整轮 **0.1 s**）。
> **纪律**：① **改项目请改它的 README**，不要手改索引（手改会造成「生成器与产物不一致」，见调试铁律 36）；
> ② 新增项目**必须带 README**，否则生成器把它列入「缺 README」节（该节为空才是健康态）；
> ③ 索引**可以逐次提交**了 —— 32 KB 而非 50 MB，重生成的成本已可忽略。
> **旧快照已归档**：`G:\archive\目录索引-全盘快照-20260828\`（含 `MANIFEST.md`，
> SHA256 `1877C3D9ADB23A90F3F297D07867FB373307603BAA0682411E86B4DCA92D3475`）——
> 它是 08-28 那一刻现盘的**唯一证据**，保留以备追溯「当时某文件是否存在」。
> 历史脚本 `G:\logs\_gen_index_final.ps1` 等随之作废（不再适配）。

> **文档枢纽事实（2026-09-24 建设完成并公开）**：文档枢纽从 `G:\docs` 汇总整理（933 文件 / 122.1 MB → **253 文件 / 1.62 MB，只有 .md/.txt/.yaml**）后整体迁入 **`G:\allin\docs`**，随公开仓 `siwpan/allin` 发布（开发过程透明化、可供他处续做）。**现盘布局**：`G:\allin\docs\`（活文档在根：`MEMORY.md`、`会话交接_2026-08-27.md`、`协作工作流程约定_2026-08-28.md`、`ports.yaml`、`端口分配表.md`、`README.md` 文档地图、`allin治理模式_建设指南.md`；历史树在 `md/`）；非文档内容 → `G:\archive\docs-nondoc-20260924\`（audit-fragments 含 token 扫描产物、XJ380 SDK、GURPS 第三方规则，**永不入库**）；门禁工具 → `G:\tools\gate\`（`scan_hardcoded.ps1`，基线在 `audit\`；`check_undefined_names.py`；`README.md`）。**约定**：① 枢纽**只放文档**，脚本/产物/二进制/第三方资料一律不放；② `MEMORY.md` 是**唯一事实源**，禁止复制第二份；③ 新增文档入库前过敏感串扫描（11 类模式）。**引用同步**：枢纽内 100 处 + platform 2 处（含 `registry.js` 的 `PORTS_YAML` 默认值）+ 5 个仓 + 预设 persona，全部改净并推送（platform `8164b19`、crawl-hub `8378c38`/`526eb20`、foolproof-operation `b387e5e`、pluginplayer `15db038`、players-unified `f7a303a`、private-radio-stations `206db91`）。详见交接 §74。

44. **共享仓（尤其是多人/多会话在写的仓）禁止破坏性工作区操作，写前先同步（2026-09-24 沉淀，`G:\allin` 并发写入实证）**：同一时段有两条会话/进程在 `G:\allin` 提交并推送（提交图线性、无覆盖），而我在其中一次 `git status` 报「有改动」时跑了 `git checkout -- .`（事后核对无内容差异、无丢失，但**差点就是数据损失**）。**纪律**：① 在共享仓写之前先 `git fetch` + `git ls-remote` 看远端是否已被推进，提交后**推之前再看一次**，被拒就 `pull --rebase` 而不是强推；② **禁止** `git checkout -- .`、`git reset --hard`、`git clean -fd`、`push --force`——工作区「看起来脏」时先 `git diff --ignore-cr-at-eol --numstat` 判断是不是换行噪音，是就放着别动或只对**自己改的文件**做 checkout；③ 发现并发写入时，先对齐分工（谁改哪个文件/目录），必要时停下等对方提交完再动；④ 推完必须核对 `ls-remote` 与本地一致，并检查是否有别人的新提交被自己漏看（`git log --oneline HEAD..origin/BR`）。

45. **铁律编号必须唯一且连续；续编前先扫全表取最大号（2026-09-24 沉淀，本表自身「缺 23 + 29/30 各两次」实证）**：本表曾有 44 个条目却只有 42 个唯一号——**「23」缺号、「29」「30」各出现两次**（四件不同的事共用两个号）。后果不是排版难看，而是**编号引用直接失效**：`会话交接` 引用「调试铁律 24/25/29/30」时无法判断指的是哪两条；`建设指南` 的事故表更是**整体错位**（其引用的编号在 40–43 立完之后没有随编号更新，8 行里 6 行指错，直到本次才按内容重定号）。**根因**：`建设指南` S4 立了「编号稳定（永不重排）」的规矩，却**没有任何机制保证编号唯一**——规矩只说了「不许改」，没说「不许重」。⇒ 冲突说明 S4 未落到实处，故本次按用户拍板**重排为 1..44 连续唯一**并同步全部引用（`会话交接` 9 处、`建设指南` 8 处 + 2 处正文）。**纪律**：① 往任何编号列表追加条目前，先扫描该表取**最大号 + 1**，禁止凭记忆续编；② 追加后立刻校验「编号 == 1..N 连续唯一」，不通过不得提交；③ 编号列表是**引用契约**，改号必须同步全部引用点（`grep 铁律\s*\d+` 全量核），并以「引用指向的条目内容是否与上下文语义相符」为验收标准——只看编号存在与否不够（本次正是靠内容比对才发现 6 行错位）。④ 编号唯一性的同类约束适用于所有带编号的事实源（铁律、端口、条目索引）。


---

## 新机（DESKTOP-8RSV60V）挂载事实 —— 旧工作区换硬件，非迁移（2026-09-24 实测）

> **本节是本机（第二台物理机）的事实源。** 上面各节写于旧机 SIWPAN；**路径全部照旧成立**，因为外置盘已原样插到新机上。

- **旧机的 F: / G: 是两块外置盘，已原样接到新机**（两块 WD Game Drive 3,726.0 GB，**NTFS**）：
  - **`G:` 卷标 `allin`** = 项目盘：`repos`(**108 目录 / 108 含 .git**；原记 107，见铁律 4 的仓数订正)、`allin`、`platform`、`tools`、`archive`、`assets`、`venvs`、`notpython`、`workbuddy`、`job`、`logs`、`local`、`tmp`、`Temp`、`web`、`_job`、`shurufa` —— **目录契约一项不缺**；
  - **`F:` 卷标 `trash`** = 大依赖盘：`Python314`(3.14.7)、`node`、`PowerShell`、`mingw64`、`VS2022`、`ldyun`(ffmpeg)、`calibre`、`models`、`venvs`、`Godot-4.7.1`、`UE_5.8` …；
  - **⇒ 所以「换机要复制 108 仓 / 1.2 TB」这个前提不成立** —— 数据从来没离开过这两块盘。
- **新机硬件**：`i5-12600KF`(10C/16T, 3686 MHz) · 内存 **15.9 GB**（旧机 32 GB，此项倒退）· 内置 `C:` 465.8 GB **NTFS** · `D:` 7,451.9 GB **exFAT**（卷标 `save`，个人数据盘，**不是工作区**）。
- **没能一起过来的**：旧机内置 `C:` —— 因此 `C:\Users\13122\.workbuddy`、`.agent-presets`、`.dsh` 都不在；旧机的会话/服务状态也随之不存在（不迁，重建）。
- **⚠ exFAT（仅 D:）不支持硬链接与目录联接**（实测：`Hard links are not supported` / `Incorrect function`）。
  后果：① 文件写入工具在 D: 上报 `EISDIR`（其落盘用硬链接）；② 目录联接（原型的 junction 类方案）在 D: 上不可用。
  **C:/F:/G: 均为 NTFS，能力完整** —— 工作区与仓应留在 NTFS 卷上。
- **本次纠错（代价：一轮重复建设）**：我曾误判「本机是从零重建、旧资产未迁移」，于是在 `D:\local` 建了重复的 `docs` 与 `tools` 仓。
  已按「合并优于双仓并存」归并回权威副本：三处回写 → `G:\allin` 提交 `e51ba964`；
  冗余副本整体归档 **`G:\archive\local-d-rebuild-20260924\`**（docs 69 / tools 51 / allin 310 文件，逐项校验一致，**零删除**）。
- **教训**：**盘符枚举不要只看 `DriveType=3`** —— 外置 NTFS 盘同样报 `DriveType=3`，但会因筛选条件被漏掉；
  枚举卷一律用 `Get-Volume` / `Win32_DiskDrive` 全量对照，**先确认"盘到底有几块"再下"缺什么"的结论**。

---

## 借用外部文档的落点纪律（2026-09-25 沉淀，源自 gitee 三篇文档）

> gitee 三篇文档（`gitee推送流程_2026-09-25.md` / `gitee发版指南.md` / `gitee协作规范.md`）是**从外部整理借鉴**进来的，
> 内容（9 手段绕过确认、三层验收、平台坑表、发版门禁）全部有效且有价值，**但落点表写的是原型机**。
> 本次逐条实测核出三处不符，且**都不是文档笔误**，而是「换机后没做落点复核」的必然结果。

**实测核出的不符（2026-09-25，本机 `DESKTOP-8RSV60V` / 用户 `psw`）**：

| 文档所写（原型机） | 本机实测 | 后果 |
|---|---|---|
| Python = `E:\Python314\python.exe` | **`E:\` 卷不存在**；实际 `F:\Python314\python.exe`（已在 PATH，含 openpyxl 3.1.5） | 照抄即「找不到文件」 |
| 凭据 `~/.git-credentials`（`C:\Users\13122\…`） | `C:\Users\13122` **不存在**；`~/.git-credentials` **也不存在**；`credential.https://gitee.com.helper=store` **未配** | 照抄取令牌必失败 |
| 全局已配 `user.name` / `user.email` | **全局为空**；各仓靠**仓库级**配置（`siwpan` / `siwpan@users.noreply.gitee.com`） | 新 clone 的仓 `commit` 报 `Author identity unknown` |
| 「F/G 盘已移除，仅 C/D/E 三卷」 | F:/G: **都在**（原型机的外置盘已接到新机） | 结论方向相反 |

**两条纪律（本次实证）**：

46. **借用外部文档必须做落点本地化，且落点属于"某台机器"而非"事实"（2026-09-25 沉淀）**：文档里的**绝对路径、用户名、盘符、设备名、卷标**都是**某台机器**的快照，不是通用事实。把它拷进工作区时，**必须先逐条实测核对本机**，再落库；核不上的就地改成本机事实，并在文档内标注**为何**改（否则下次又被人"照原样"抄回去）。**判据**：文档能不能在一台陌生机器上照着跑通，是它唯一的质量标准——文采与信息量都不算。本节的教训不是「文档写错了」，而是**同一工作区换硬件后，事实源（`新机挂载事实` 一节）已经更正，但被借鉴进来的外部文档没跟着同步** —— 这类「事实源已更新、派生文档未同步」的缺口，是记账时**最该主动去找**的一类。
    - 附：同一批文档里还有一类**同源不同机**的规律可复用 —— `G:\platform` 的远端是 **`siwpan/allin-platform`**（不是 `platform`）；匿名查 `siwpan/platform` 会 404。**仓名与本地目录名可以不一致，核远端一律以 `git config --get remote.origin.url` 为准，不要靠目录名猜。**
    - 附：`siwpan/*` 公开仓 **≥100 个**（API 单页上限 100，实际更多），抽样 5 仓 `private=False` —— 铁律 0「默认公开」在存量仓上成立，可作为后续建仓的现状基线。

47. **鉴权验收必须贯通"整条链"，不许拿链上任一单点的成功去代表链成功（2026-09-25 沉淀）**：本次实测 `gitee_release.py whoami` **失败**（本机无 store 文件可读，脚本要求显式令牌），但**同一时刻 `git push` 却成功**（凭据在 **Windows 凭据管理器**内，GCM 自动取用，文件式检查根本看不到：`~/.gcm/credentials` 等路径均不存在）。
    - **⇒ 「某条命令能推」不等于「脚本能取令牌」**，二者是**两条独立链路**（git 凭据管理器 vs API 令牌），必须**分别**取得证据。
    - **反方向的坑同样存在**：开始我依据「无 store 文件 + GCM 无存储 + selector=`<no helper>`」推断**推送会失败** —— 这个推断是**错的**，只是我当时的检查手段（文件式枚举）看不见凭据管理器。**"我查不到" ≠ "不存在"**：凭据类事实必须以**实推探针**为准。
    - **纪律**：① 鉴权结论一律用**实推探针**（文档 §3.8 分支探针：建临时分支 → push → 删 → `ls-remote` 复核）取证据，不用文件存在性推断；② 探针必须**自清理**（本次 `__probe_cred` 推送后即刻删除，复核远端只剩 `main`）；③ 报「能用/不能用」时，明说**验的是哪条链**。
    - **补充（2026-09-25 当日二次实测）**：**GCM 凭据缓存会「先成功后失败」** —— 同一次批量推送里，前 4 个仓 `git push` 成功，后 5 个立刻报 `fatal: could not read Username for 'https://gitee.com': terminal prompts disabled`（各仓 `credential.helper` 配置**完全相同**，非配置差异）。重试仍失败。**处置**：改用**一次性 URL**（`git -c credential.helper= push "https://siwpan:<TOKEN>@gitee.com/..."`，令牌取自 `G:\私人令牌.txt`），实测 5 仓全部推送成功且 `.git/config` 无凭据残留。⇒ **批量推送不要假设"第一个成功就都能成功"**，要么逐仓验证，要么直接走一次性 URL。

---

## Python 运行环境事实源（2026-09-25 实测，含一个 CPython 缺陷）

> 本节是本机**唯一**的 Python 选型事实源。核心结论：**不要用 `F:\Python314`（3.14.7）**，它有会导致进程崩溃的 CPython 缺陷。

48. **CPython 3.14.7 存在「包内失败的相对导入直接崩进程」缺陷，必须避开（2026-09-25 实测定位）**：
    - **症状**：`import` 某个包时进程**直接消失**，`exit=-1073741819`（`0xC0000005` 访问违规），**无 traceback、无 stderr、连 `print` 都不输出**（崩在模块加载/编译期）。
    - **最小复现**（20 行，与任何第三方包无关）：
      ```python
      # pkg/__init__.py
      from .reader import go
      # pkg/reader.py
      try:
          from ..missing import X        # 包内失败的相对导入（目标不存在）
      except ImportError:
          X = False
      def go(): return X
      ```
      `python -c "import pkg"` → **崩**。把 `from ..missing` 换成**绝对**导入（`import definitely_missing_xyz`）→ **exit 0**。
      ⇒ 触发条件 = **包内失败的相对导入（`from ..x import y`）**，与 try/except 无关。
    - **已排除**：文件损坏（与 PyPI 官方 wheel 逐字节比对，190 文件 0 差异）、`.pyc` 缓存（移走全部 `__pycache__` 仍崩）、重装（stdlib 手工覆盖 195 文件仍崩）、site-packages 污染（`-S`/`-E` 无效）、numpy+lxml 组合（任意顺序均 OK）、磁盘（`Get-PhysicalDisk` 报 Healthy）、调试器（有无 `-X faulthandler` 均崩）。
    - **官方对应**：gh-134100「use-after-free in `PyImport_ImportModuleLevelObject`」（[PR #134117](https://github.com/python/cpython/pull/134117)）。**3.14.8 预计 2026-10-06 才发布**（[Ubuntu FFe #2168150](https://bugs.launchpad.net/ubuntu/+source/python3.14/+bug/2168150)），Windows 当前最新即 3.14.7。
    - **受害者实例**：`openpyxl/reader/excel.py:16` 的 `from ..tests import KEEP_VBA`（tests 目录不随 wheel 分发，**必走失败路径**）⇒ 本机所有 3.14.7 环境下 `import openpyxl` 必崩。
    - **处置（按优先级）**：
      1. **用 Python 3.13.14**（本机已有，见 49），**不要用 F:\Python314**；
      2. 临时 workaround：把问题包的失败相对导入改成 `__import__('pkg.sub', fromlist=[...])`（openpyxl 已就地打补丁，备份 `excel.py.bak-20260925`）—— 但**重装包会丢补丁**，只能应急。
    - **纪律**：遇到「进程无输出直接消失」，先跑最小复现判定是否本缺陷，再去查自己的代码；**不要**在无 traceback 的情况下盲目调试业务逻辑。

49. **本机可用 Python 清单与选型（2026-09-25 实测）**：
    | 解释器 | 实际版本 | 可用性 |
    | --- | --- | --- |
    | `G:\workbuddy\.workbuddy\binaries\python\versions\3.13.12\python.exe` | **3.13.14** | ✅ **推荐**（实测最小复现 exit 0）|
    | `C:\Users\psw\.workbuddy\binaries\python\versions\3.13.12\python.exe` | **3.13.14** | ✅ 同上（同一份的副本）|
    | `F:\Python314\python.exe` | 3.14.7 | ❌ **有 48 的缺陷，勿用** |
    - **坑**：目录名写 `3.13.12`，**实际版本是 3.13.14** —— **判定版本一律用 `python -V`，不要信目录名**。
    - **另一个真损坏**：`G:\workbuddy\.workbuddy\binaries\python\envs\default\Scripts\python.exe` 是 venv，其 `pyvenv.cfg` 指向 **`C:\Users\13122\...`（旧机路径，已不存在）**，运行报 `did not find executable ... exit 103`。**这些 WorkBuddy venv 在换机后已全部失效，需重建**（本机死根路径门禁报出的 `C:\Users\13122` 多由此而来）。
    - **推荐用法**：给每个需要 Python 的项目建**项目级 `.venv`**：
      `G:\workbuddy\.workbuddy\binaries\python\versions\3.13.12\python.exe -m venv <项目>\.venv`，
      再 `\.venv\Scripts\python.exe -m pip install <依赖>`。
      ⇒ 隔离依赖、钉住版本、不受系统 PATH 里那个坏解释器影响。**并记得把 `.venv/` 写进 `.gitignore`**（`cordis-table-app` 原本漏了，会把整个虚拟环境提交进仓）。

50. **`python -c` 的多行代码不要用 PowerShell here-string 传（2026-09-25 反复踩，代价三轮误判）**：用 `@"... "@` 把多行 Python 喂给 `python -c` 时，**引号与换行会被破坏**，表现为「**什么都没执行就崩**」——极易误判成被测对象崩溃（本次据此错误推断过「大源码编译即崩」三次）。
    - **纪律**：多行 Python 一律**落成 `.py` 文件再执行**；只有单行、无嵌套引号的场景才用 `-c`。
    - 同族坑：`.cmd` 文件**不能存 UTF-8**（cmd 按 ANSI 解码，中文注释会让整条命令解析错乱，实测报 `'）' is not recognized`）—— 中文批处理要么存 ANSI，要么改用 pwsh。

51. **盘健康：外置 USB 盘必须关掉「休眠/选择性暂停」，否则会静默损坏 git 仓（2026-09-25 事故 + 处置）**：
    - **事故**：G: 盘（WD Game Drive，Disk 3，USB）全天持续 `disk 事件 153`（IO 重试，24h 内 190 次），19:07 触发 `Ntfs 事件 132`「**短时间内发生太多修复事件**」+ 9 次「卷 G: 上的文件系统结构现在已经修复」——**NTFS 在线自愈在写入过程中改坏了 git 对象**，造成 **4 个仓损坏**（`allin` 的 pack idx/commit-graph/index，`novel`/`novel-down`/`ncmturnmp3` 的 `.git\objects` 目录项损坏）。
    - **⚠ SMART 会说谎**：`Get-PhysicalDisk` 全程报 `HealthStatus=Healthy`，而盘正在重试 IO。**判盘健康必须看事件日志**（`disk` id 153 计数 + `Ntfs` id 130/132），不能只看 SMART。
    - **处置（已执行，可回滚）**：
      ```powershell
      powercfg /change disk-timeout-ac 0      # 硬盘永不关闭（原 0x4b0=1200s）
      powercfg /change disk-timeout-dc 0      # 原 0x258=600s
      powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
      powercfg /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
      powercfg /setactive SCHEME_CURRENT
      ```
    - **仍待处理**：`F:` **Dirty + Scan Needed** → `chkdsk F: /scan`（只读）；`D:` **Dirty + Full Repair Needed**（**exFAT 无日志，非正常拔插极易损坏**）→ `chkdsk D: /f`；3 个 `G:\repos\{novel,novel-down,ncmturnmp3}\.git-damaged` 损坏空壳 `rmdir` 也删不掉，需 `chkdsk /f`。以上**均需管理员**。
    - **教训**：外置盘上的 git 仓，在盘出现 IO 重试期间**不要做大批量写入**（本次 4 个仓就是在写入窗口内被改坏的）；**仓的权威副本必须在远端**，本地损坏才可无损恢复（本次 4 仓全部由重克隆恢复，工作树文件未丢）。

52. **`git push -u <带令牌的 URL>` 会把凭据写进 `.git/config` 的 `branch.<名>.remote`——最难发现的一处凭据残留（2026-09-25 实测）**：
    - **现象**：用一次性 URL 推送（`git push -u "https://user:<TOKEN>@gitee.com/..." main:main`）后，`remote.origin.url` 是干净的（因为没有 `set-url`），但 `.git/config` **仍然含令牌**。
    - **藏身处**：不在 `[remote "origin"] url`，而在 **`[branch "main"] remote`** —— `-u` 把**带凭据的那个 URL** 直接记成了分支的上游：
      ```ini
      [remote "origin"]
          url = https://gitee.com/siwpan/<repo>.git      # 干净
      [branch "main"]
          remote = https://siwpan:<TOKEN>@gitee.com/...  # ← 令牌在这
      ```
    - **为什么难查**：`git remote -v` 只显示 `remote.origin.url`（干净的），**看不见 branch 段**；只看 remote 就会误判"无残留"。本次即因此先误报了一次"已清理"。
    - **正确排查与处置**：
      ```powershell
      # 排查：直接扫 config 全文，别只扫 remote 段
      Select-String -Path .git\config -Pattern 'https://[^/\s]+:[0-9a-zA-Z]{20,}@'
      # 处置
      git remote set-url origin "https://gitee.com/<owner>/<repo>.git"
      git config --file .git/config branch.<branch>.remote origin   # ← 关键这一条
      ```
    - **连带坑**：`git config` / `[IO.File]::ReadAllBytes` 用**相对路径**时会**静默作用到会话 cwd**（本次 PowerShell 里 cwd 仍是 `D:\local`，导致"改了却没生效"、读数也读错文件）。⇒ **一律用绝对路径**，或用 `git config --file <绝对路径>`。
    - **纪律**：① 用一次性 URL 推送时**不要加 `-u`**（或推完立刻把 `branch.*.remote` 改回 `origin`）；② 凭据残留检查必须**扫 config 全文**并以「正则 `https://user:hex@` 是否命中」为准，不靠肉眼看 remote；③ 建仓后的收尾清单里，**必须包含这一项**。

53. **门禁的"排除项"是它最危险的部位 —— 一个过宽的排除会静默吃掉整类真问题（2026-09-26 实测，死根路径门禁漏检 3 处）**：
    - **现象**：`d20` 仓有 3 处 `E:/D20`（`E:` 盘在本机**不存在** ⇒ 真死根），而门禁报 **0 阻断**。
    - **根因**：排除项 `RxRegexArtifact` 的本意是滤掉文本里的**正则转义伪影**（`\d` `\w` `\s`），原式：
      ```powershell
      [\(\)\[\]\+]|\\(w|d|s|W|D|S)(?![A-Za-z])
      ```
      `E:\D20` 的 `\D` 后跟 `2`（非字母）→ 命中 → **整条路径被当成伪影排除**。
      于是「盘符后紧跟 w/d/s/W/D/S 字母」的路径**整类**被静默吃掉（`E:\D20`、`C:\Users`、`D:\data`、`C:\src`… 全部）。
    - **修法**：加负向后顾 —— 盘符分隔符前必是 `X:`，而真正的转义 `\d` 前不会是冒号：
      ```powershell
      [\(\)\[\]\+]|(?<!:)\\(w|d|s|W|D|S)(?![A-Za-z])
      ```
    - **验证方式（关键）**：修完必须**先跑门禁自检**确认「系统路径/URL/夹具/转义 零误报」仍通过 ——
      **不能为了修漏检而牺牲零误报**，否则是把一类误报换成另一类。本次自检三项仍全绿。
    - **纪律**：① **门禁的排除/白名单/豁免逻辑必须逐条能被自检用例覆盖**（正例能抓 + 反例不误报），
      只测"能抓"不测"不误伤"等于没测；② 发现一处漏检后，**必须反推该排除项的整类影响面**
      （本次是"盘符+w/d/s 字母"全类），不要只修当前这一例；③ 门禁报 0 时，若**同一事实用别的工具能查到**，
      优先怀疑门禁而不是事实 —— 本次正是 `git grep` 查到了 3 处而门禁报 0，才顺藤找出这个盲区。
    - **旁证**：修复后全工作区复扫仍 `阻断 0 / exit 0`，非阻断命中从 1033 升到 1044 —— 说明该排除项此前
      确实**吞掉了一整类**（11 处）被判为伪影的路径。

54. **`git add -A` 会把构建副产物一并提交；判"哪些是产物"不能靠文件名直觉（2026-09-26 实测）**：
    - **现象**：给 `d20` 补 `pyproject.toml` 后为验证可安装性跑了 `pip wheel`，产生了 `d20.egg-info/`；
      随后 `git add -A` 把它**一并提交**（6 个文件）并推送。
    - **为何危险**：`egg-info` 是 setuptools 生成的**构建元数据**，属于"产物入仓"，正是仓库卫生门禁 H3 的拦截对象；
      入库后每次构建都会产生 diff 噪音，且暴露本地绝对路径等信息。
    - **处置**：`git rm -r --cached <dir>` + `.gitignore` 补 `*.egg-info/`，再单独提交修正（**保留磁盘文件，只从跟踪面移除**）。
    - **纪律**：① **提交前先跑仓库卫生门禁**（`repo_hygiene.py --repo <仓>`），它专门拦 `dist/ build/ release/ output/`
      与 `*.egg-info/` 这类产物 —— 本次是**先提交、后跑门禁**才发现，顺序反了；② `git add -A` 前先 `git status --short`
      扫一眼**未预期的 `??` 项**，构建/测试刚跑过尤其要当心；③ 判断产物看**是不是生成出来的**，
      不看名字像不像（`data/` 可能是源码、`*.json` 可能是产物）。
    - **附**：门禁 H3 的 `ARTIFACT_DIRS` 当时**不含 `egg-info`**，故本次是"门禁没覆盖到"而非"门禁没拦住" ——
      已同步把 `*.egg-info/` 纳入判据（否则这条纪律没有机械保障）。
