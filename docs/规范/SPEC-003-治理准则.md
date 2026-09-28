# SPEC-003 · 治理准则

> **编号** SPEC-003 ｜ **效力** 准则（事故驱动固化，铁律级） ｜ **状态** 生效
> **生效** 2026-08-27 ｜ **最后修订** 2026-09-28 ｜ **适用面** 借鉴/复制/调整/退役/敏感信息/插件化选型/外部文档落点
> **承载体** `g03-credentials`（敏感信息）、`g08-deletion-evidence`（冗余三查）、`repo_hygiene.py` H1–H8；「借鉴必记账」由 DSH `verify-third-party-notices` 部分覆盖
> **引用格式** SPEC-003 §创新三原则 1

---

## 治理准则：创新三原则（2026-08-27 深度审核固化，铁律级）

> **创新 = 借鉴 + 调整 + 同步 + 记账；「推倒重来」只允许发生在结构层，资产与历史永远保全。**
> 依据：`docs/记录/审计/深度审核报告_2026-08-27.md`（对照 deepseek-harness-master 与 gitee.com/siwpan 全量审核）。

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
- **remote URL 明文凭据面（2026-09-22 实测记账，用户拍板维持现状）**：4 个 `.git/config` 的 origin 内含 `siwpan:<token>@gitee.com` —— `G:\platform`、`/repos/bee`、`/repos/particle`、`/archive/arcade2-collection-model-retired-20260827`（R1 时记为 16 处，09-22 实测 4 处）。凭据源 = `G:\私人令牌.txt`，属已知现状，**只记账不清理**；日后若轮换令牌，这 4 处需同步更新。
- **`G:\私人令牌.txt` 凭据清单（2026-09-22 盘点，只记种类不记值）**：① gitee token（32-hex）② DeepSeek key（`sk-…`）③ Tavily（`tvly-dev-…` + MCP URL）④ TestPyPI / PyPI 令牌各 1（`pypi-AgE…`）⑤ **unsplash**（Application ID / Access Key / Secret key，2026-09-22 从 `/Users/13122/Downloads/key.txt` 并入）⑥ **pexels** API Key（同上并入）。
  - **取用方式（image-scraper）**：`CLI/GUI 参数 → 环境变量 <NAME>_KEY（UNSPLASH_KEY / PEXELS_KEY） → config.json 的 keys`；**该仓 `config.json` 是已跟踪文件，密钥绝不写进去**（key 位保持空串占位）。
  - 令牌文件位于 `G:\` 根，而 `G:\` 根**不是任何 git 仓**（allin 仓根已迁 `G:\allin`，其 `.gitignore` 仍声明 `私人令牌.txt`）——即不入库；每次改动前先备份到 `/archive/私人令牌-bak-<时间戳>.txt`。

### 插件化选型（2026-08-27 用户拍板）
- **爬虫类适合插件化**（crawl-hub 模式：多站点 worker = 多插件、频繁增删、子进程隔离）；**单机 GUI 小游戏不适合**（D20 的 E:\D20 整体插件化/网页插件版实验已证明不划算，勿再尝试）。
- 判定标准：宿主是否天然「多能力组合 + 频繁增删 + 生命周期可逆」——是 → 插件化；否 → 单体优先。

### 外部机器完成的项目（2026-09-22 用户澄清）
- 已知**整个项目主要在别的机器上完成、本机是镜像/运行副本**的仓：`private-radio-stations`（siwpan/private-radio-stations）、`santi-teleprompter`（siwpan/santi-teleprompter）。
- **口径：本地一律对齐 gitee**（`git fetch` + `git pull --ff-only`）——**「远端领先本地」是正常状态**，不是异常、不是丢数据。
- 判据（避免再当事故查）：某仓出现「本地零领先 + 远端持续领先 + 本机 memory 无对应记录」→ **先按「外部机器完成」核对**，再考虑其他解释。
- ⚠ **2026-09-23 用户纠正**：「外部机器完成」**只解释"远端为什么领先"，不代表本机不能改**——本地照常可以修改、提交、推送（推送仍按高风险逐项确认）。此前把这条引申成「不以本机作为改动源」属**我方的过度引申**，已作废。


## 借用外部文档的落点纪律（2026-09-25 沉淀，源自 gitee 三篇文档）

> gitee 三篇文档（`docs/规范/SPEC-101-推送流程.md` / `docs/规范/SPEC-102-发版指南.md` / `docs/规范/SPEC-103-社区协作规范.md`）是**从外部整理借鉴**进来的，
> 内容（9 手段绕过确认、三层验收、平台坑表、发版门禁）全部有效且有价值，**但落点表写的是原型机**。
> 本次逐条实测核出三处不符，且**都不是文档笔误**，而是「换机后没做落点复核」的必然结果。

**实测核出的不符（2026-09-25，本机 `DESKTOP-8RSV60V` / 用户 `psw`）**：

| 文档所写（原型机） | 本机实测 | 后果 |
|---|---|---|
| Python = `/Python314/python.exe` | **`E:\` 卷不存在**；实际 `/Python314/python.exe`（已在 PATH，含 openpyxl 3.1.5） | 照抄即「找不到文件」 |
| 凭据 `~/.git-credentials`（`/Users/13122/…`） | `/Users/13122` **不存在**；`~/.git-credentials` **也不存在**；`credential.https://gitee.com.helper=store` **未配** | 照抄取令牌必失败 |
| 全局已配 `user.name` / `user.email` | **全局为空**；各仓靠**仓库级**配置（`siwpan` / `siwpan@users.noreply.gitee.com`） | 新 clone 的仓 `commit` 报 `Author identity unknown` |
| 「F/G 盘已移除，仅 C/D/E 三卷」 | F:/G: **都在**（原型机的外置盘已接到新机） | 结论方向相反 |

**两条纪律（本次实证）**：

