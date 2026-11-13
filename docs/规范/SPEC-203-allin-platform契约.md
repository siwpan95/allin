# SPEC-203 · allin-platform 契约（架构地图 + 清单规范）

> **编号** SPEC-203 ｜ **效力** 准则（结构约定，可被 registry 校验引用）｜ **状态** 生效
> **生效** 2026-10-26 ｜ **最后修订** 2026-11-13 ｜ **适用面** `platform/` 全部代码与 `platform/registry/` 数据面
> **承载体** `platform/scripts/check.mjs`（注册表审计）、`platform/harness/`（黄金值门禁 exit 0）
> **引用格式** SPEC-203 §关键不变量
> **迁移记账** 本文由原独立仓 `siwpan/allin-platform` 的架构文档 `architecture.md` 就地升级而来（2026-10-26 三仓整合）；
> 原仓远端已随之删除。历次决策理由见 [`docs/记录/决策/`](../记录/决策/)（冻结，永不为现行权威）。本仓落户 `platform/` 后，文中模块路径一律以 `platform/` 为基准。

---

> 本文是有序地图：模块职责与依赖方向。类型细节看源码，决策理由看 `docs/记录/决策/`。

## 分层

```
apps/portal/   前台 @allin/portal —— 零依赖纯 node:http；路由 + 静态资源 + API 门面。
               只做编排：启停/工坊/告警/引擎视图都委托 @allin/core。
apps/cli/      命令行 @allin/cli —— 只读命令直连 registry；启停直连 core（pid 持久化）；
               写命令走门户 HTTP（缓存与事务在门户层）。
packages/core/ 内核 @allin/core —— registry（清单加载/校验/端口查表）/ launch（子进程
               启停 + running.json + tasks.log）/ workshop（订阅=clone/更新=pull/回滚/
               退订）/ gitee（发布面查询，故障显式区分）/ probe（TCP/HTTP 探活 + 慢启动宽限）。
registry/      数据面：projects/*.yaml（一项目一份）+ ports.yaml（env 缺失时的仓内默认）。
harness/       离线黄金值门禁：manifest.json（组合即数据）→ port.mjs（JSON-lines 子进程
               端口）→ driver.mjs（适配器）→ harness.mjs（编排 + 众数共识/分歧 + 退出码绑定）。
scripts/       check.mjs（无 GUI 审计）/ build_batch.mjs（批量打包）/ ensure-mirror.ps1（本地 npm 镜像）/
               check_repos.mjs（本机⇄远端锚点）/ discover_repos.mjs（采集层·扫描登记）/
               publish_repos.mjs（执行层·远端写入编排，默认 dry-run + 逐项确认闸门）。
data/          运行时状态（gitignored）：tasks.log / running.json / workshop.json / portal.port。
```

依赖方向：`portal / cli → core →（js-yaml 唯一三方依赖）`。core 不依赖 apps。

## 关键不变量

- 子进程隔离：`launch.command` 在 `entry.path` 下 shell 执行；pid 落 running.json，
  跨宿主（门户/CLI）可见可停；exit/error 事件双向清理（children Map + running.json）。
- 终止梯：stop.command 优雅停止（15s 封顶）→ 2s settle 窗口 → Windows taskkill 树杀 / POSIX SIGTERM。
- 校验 fail-loud：必填字段、id 形状、path 绝对（+可选存在性）、端口查表 + 服务归属核对、
  gameplay 受控枚举、重复 id。`_valid:false` 条目拒绝启动。
- 日志即事实源：tasks.log（seq/ts/type/project/action）、divergence-events.jsonl（E5 订阅链路）；
  归档/状态写一律 temp+fsync+rename（durable 语义，2026-09-24 Phase 1）。
- Host 围栏：门户全路由前置校验 Host 头（仅回环字面量），防 DNS rebinding——
  GET 读取面与写操作同受保护（2026-09-24 Phase 1）。
- harness 退出码绑定：黄金值全绿 exit 0；任何分歧/报错 exit 1（informational 用例除外，
  但超出声明预期分歧同样失败）。

## 文档税表

| 事实 | 唯一的家 |
|---|---|
| 常备命令 / 环境变量 | [`platform/AGENTS.md`](../../platform/AGENTS.md) |
| 模块职责 / 不变量 | 本文（`docs/规范/SPEC-203-allin-platform契约.md`） |
| 持久决策理由（含后果） | [`docs/记录/决策/`](../记录/决策/)（冻结，永不为现行权威） |
| harness 用例契约 | [`platform/harness/spec.md`](../../platform/harness/spec.md) |
| platform.yaml 字段规范 | 见本文 §清单规范（原引《平台项目清单规范_platform.yaml.md》未随仓迁移，已就地并入） |
| 端口分配 | `PLATFORM_PORTS` 指向的外部端口分配表（仓内 `platform/registry/ports.yaml` 仅为回退默认） |

## 清单规范

每个接入项目在 `platform/registry/projects/` 下写一个 `platform.yaml`（字段：
`id/name/category/version/path/port/launch/stop/health/publish/manual`）。

- **`port` 必查 ports.yaml**：未登记的端口拒绝登记（唯一的端口事实源是 `PLATFORM_PORTS` 指向的外部端口分配表，仓内副本仅作回退）。
- **`path` 去盘符**：一律写相对于仓库根的 POSIX 相对路径（如 `repos/xxx`），**禁止盘符**（见 SPEC-006 机器与路径约定）——绝对路径在本机会漂移到失效盘符，属 repocheck 规则 7 的检查对象。

## 发行仓可替换性契约（2026-11-13）

> **触发**：全哥提出「repos 是发行仓，内容可以是任何项目；换机部署 allin 后需要治理的发行仓内容甚至可能完全不一样」。
> **结论**：本仓此前只解决「同一套发行仓 × 多机不同检出集」，未解决「清单本身可替换」。本节把边界写死。

### 模式层 / 实例层

| 层 | 内容 | 换发行仓时 |
| --- | --- | --- |
| **模式层（不动）** | `docs/规范/`（SPEC-001 / 002 / 005 / 006 / 105 / 203）、`tools/gate/` 判据、`platform/packages/core/` 与 `platform/scripts/` 的校验逻辑、`scripts/run_all_gates.sh` | 原样保留 |
| **实例层（整体替换 / 重建）** | `platform/registry/projects/*.yaml`、`facts/facts.json` 的 projects / tiering / tools / licenses 投影、`PORTFOLIO.md`、`docs/事实源/组合分级决策索引.md` 与 `组合分级后续路线.md` | 按新发行区重建；旧组合材料按「只增不改」归档，不作现值 |

⚠ 现有 **145 / 140 / 138** 都是**当前组合的实例值**，不是判据常量；`g17` 动态扫 registry，不写死数量。
📌 **口径补充（2026-11-13 二次实测，取代本轮首版）**：145 份 YAML 中 **1 条是仓内条目**（`portal.yaml`，`path: platform`，`publish.repo: siwpan/allin`）；其余 144 份发行区条目归并后 **139 个唯一发行仓名**（`musickit` 主仓 + `mixer` + `remix`、`foolproof-operation` 双入口、`magic-tower` / `magictowel`、`radio` / `video` ⇒ **一仓多条目是既有设计，不是重复登记**）。加上治理仓自身共 **140 个仓名** 参与远端对账。组合分级的「140 决策对象」又是另一套语义 —— 三处数值撞车，一律不得混用。扫描器同时输出 `entries` / `uniqueNames` / `internalEntries` 三个数。

### 发现参数（唯一来源）

| 参数 | 含义 | 默认 | 消费方 |
| --- | --- | --- | --- |
| `PLATFORM_REPOS_ROOT` | 发行区根 | `<allin 同级>/repos` | `registry.js` 的 `reposRoot()` → `resolvePath()` / `isPathContained()` / `pathCheckMode()`；`discover_repos.mjs` |
| `PLATFORM_REGISTRY` | 注册表目录 | `platform/registry/projects` | `check.mjs` / `check_repos.mjs` / `discover_repos.mjs` |
| `PLATFORM_GITEE_OWNER` | 远端账号 | `siwpan` | `check_repos.mjs` / `discover_repos.mjs` / `tools/build_portfolio.py`（2026-11-13 起同源） |
| `PLATFORM_REPOS_OFFLINE` | 离线只做本机面 | 未设 | `check_repos.mjs` / `discover_repos.mjs` |

**2026-11-13 修复**：`resolvePath('repos/...')` 此前固定按 `WORKSPACE_ROOT` 拼接，`PLATFORM_REPOS_ROOT` 只影响 `REPOS_ROOT` 导出 ⇒ 换发行仓后校验 / 启动仍指向默认区，异组合验收 3 仓全量误报「path 不存在」。现改为统一走 `reposRoot()`；**env 未设时解析结果与旧实现逐字节相同**，回归用例并入 `registry.test.mjs` 的 S-2 用例（测试数保持 75）。

### 发现与对账

- `platform/scripts/discover_repos.mjs` 是**采集层 + 扫描登记器**：输出本地发行区 / registry 声明 / 远端 owner 三方差集，支持 `--offline` / `--json` / `--apply` / `--draft` / `--strict` / `--selfcheck`。
- **扫描登记取代手抄（2026-11-13 第二轮）**：`--apply` 把候选仓写成**可直接通过 `validateEntry` 的完整条目** —— `id` / `path` 来自目录名，`name` 取 README 标题，`publish.repo` / `branch` 读 `git remote` 与 `HEAD`，`launch.command` 由仓内入口探测（`main.py` → `python main.py`、`package.json scripts.start` → `npm start`、`index.js` → `node index.js` 等）。默认 dry-run；只写新文件，**已存在的手抄条目一律跳过不覆盖**；二次执行幂等。
- **默认只读、不写盘、不判红、不进 `run_all_gates.sh` 阻断链** —— 离线北极星 + 「证据采集与门禁控制分离」（见 `docs/记录/审计/组合做大做强战略研究_2026-10-31.md` 第 6.1 节）。`--strict` 仅供人工 / CI 显式选用。
- **探测不到启动入口就拒绝登记**：列入 `needs_manual_review`（`仅远端存在无本地目录` / `仓内无可判定启动入口`），不猜命令、不伪造可入库清单。`--draft` 保留为 `--apply` 的 dry-run 预览。
- **仓内条目分流**：`path` 不以 `repos/` 开头的条目（如 `portal.yaml`）不进发行区差集，但其 `publish.repo` 仓名仍参与远端对账 —— 否则治理仓 `allin` 自身会被误报「远端有 / 未登记」。
- **归档残留分类**：本地有 `.git`、远端已无该仓、README / 末次提交含归档声明 ⇒ 标 `retired_local`，不算待登记、不写条目、不删本地资产。

### 本机全量扫描登记（2026-11-13 第四轮，`--audit`）

> **触发**：全哥「在本机实现扫描登记」。此前 `--apply` 只扫**差集**（有 `local_only` 才动手），
> 本机 145 份手抄条目从未被扫描碰过，实战证据来自临时异组合而非本机发行区。
> 本节把扫描登记从「补新仓」推进到「跑满本机、逐仓对账、落盘可复核快照」。

**分层契约（不可越界）**：本机实测 138 仓 / 145 条目，其中 **133 份 `manual`、96 份 `verify`、
47 份 `note`、44 份 `gameplay`** 属扫描推不出的人工语义 ⇒ 它们是**不可覆盖的保留层**：
`--audit` 只登记字段清单，绝不比对、绝不改写、绝不重新生成。`--apply` 的
「只写新文件、已存在条目一律跳过」语义保持不动。

| 层 | 字段 | 扫描行为 |
| --- | --- | --- |
| 机器可判定 | `id` / `path` / `publish.repo` / `publish.branch` | 与扫描值不一致 ⇒ 记 `drift`，`--strict` 判红 |
| 人工保留 | `name` / `category` / `version` / `manual` / `verify` / `gameplay` / `note` / `status` / `order` / `port` / `stop` / `health` / `checkout` | 只登记清单，不比对不覆盖 |
| 参考 | `launch.command` 入口探测 | 68 仓探测不到标准入口 ⇒ 保留手抄值，不猜、不判红 |

- **`publish.branch` 判据 = 该分支在远端存在**，不是「等于本机 HEAD」：`workshop.js` 拿它当发布分支 clone/fetch。
  `radio` / `video` 有意发布私电台仓的 `3.0` / `archived-video` 分支（远端确实存在、默认分支是 `master`），
  判为 `non_default_publish_branch`，**不算漂移**。未登记 `branch` 时按 `workshop.js` 的隐式回退 `master` 对账。
- 远端清单不可得（限流 / 断网）⇒ `branch_check_applicable=false` 并写明 `SKIP ≠ 通过`，
  **不把未运行的判据算成全绿**；此时本机机器字段仍完整可核对。
- **快照**：`--snapshot` 落盘 `platform/registry/scan-snapshot.json`（138 行扫描视角 + 人工字段清单 +
  漂移 + coverage + sha256 指纹）。指纹**只取纯本地字段**，联网派生计数不进指纹 ⇒ 远端抖动不会假红。
  初版把 `branch_verdicts` 算进指纹，实测 403 时 142→0 造成假红，已修（交接卷第一百六十四节留痕）。
- `--verify-snapshot` 重扫比对指纹：登记被改动 / 快照被篡改都判红（exit 1）。
- **基线棘轮（2026-11-13 同批订正）**：快照是**已核准的干净基线**，扫描器无权自动改写。
  `--snapshot` 发现本地机器字段指纹与已落盘快照不同 ⇒ **默认拒绝覆盖**、判非零退出码，
  须人工核实后加 `--accept-baseline-change` 显式接受。初版会自动覆盖，实测注入
  `branch` 漂移后 `repos:scan` 把错误值写成新基线、`repos:verify` 随即报 OK ——
  等于把缺陷洗白。内容一致时沿用旧 `generated_at`、不写盘（幂等，工作树零 diff）。
- 一键命令：`npm run repos:scan`（`--audit --strict --snapshot`）/ `npm run repos:verify`。
- 仍**不接 `run_all_gates.sh` 阻断链**：证据采集与门禁控制分离（离线北极星）。

**本机首跑结果**：138 仓全量扫描，抓到 3 处 `publish.branch` 真漂移并订正 ——
`3dworld-globe` / `pomodmer` 登记 `master` 而远端仅 `main`，`moba-battle` 未登记 `branch`
（隐式 `master`，远端默认 `main`）。`private-radio-stations` 的 `3.0` / `archived-video`
保留并加注释说明是有意的发布分支。修复后 `drift=0`、快照指纹稳定、注入漂移能判红、还原能转绿。


### 远端写入编排与逐项确认闸门（2026-11-13 第三轮）

> **触发**：全哥指出「自动写远端目前应该已经基本具备前置条件才对」。盘点结论：**七项技术前置条件确已齐备** ——
> ① `discover_repos.mjs --json` 识别「已登记 / 远端不存在」候选；② `tools/gitee_release.py` 的
> `create`（幂等 SKIP）/ `public` / `status`；③ `git credential fill` 令牌链（与
> `kernel/services/tools_service.py` 同源，实测可用）；④ `check_repos.mjs` 远端锚点验收；
> ⑤ `origin` 双 pushurl + `g04-push-evidence`；⑥ `SPEC-001` 铁律 4 的两步建仓 / 三件套 / 匿名复验纪律；
> ⑦ `PLATFORM_GITEE_OWNER` 三处同源。**缺的不是能力，是铁律 3 的逐项确认闸门，以及当前组合零候选。**
> 因此落地形态是「可执行编排器 + 四道闸门 + 演练」，不是无人值守自动建仓。

`platform/scripts/publish_repos.mjs` 是**执行层**，与采集层 `discover_repos.mjs` 分离：
复用三面对账的 `declared_missing_remote`（已登记 / 远端不存在 / 非墓碑）候选，
生成五步写入计划 `create → origin → push → public → verify`；复用
`tools/gitee_release.py` 的 `create` / `public` 子命令（**不重写 Gitee API**，规避已沉淀的
PATCH 必带 `name`、406 需 JSON 正体等坑）；**不调用其 `remote` 子命令**（会无条件
`git remote set-url` 覆盖本地 origin）—— 改为「无 origin 才 add / 已指向目标则跳过 /
指向别处则拒绝覆盖」，实测既有 origin 未被改写。

| 闸门 | 判据 | 依据 |
| --- | --- | --- |
| ① 逐项 | `--apply` 必须配 `--only <单个仓名>`；逗号 / 空格批量一律拒绝 | `SPEC-001` 铁律 3 |
| ② 确认 | 必须显式 `--confirm`，不靠「没说不行」推断放行 | `SPEC-002` 执行（4）高风险不分档 |
| ③ 在线 | 远端清单必须 `remote=ok`；离线 / 限流时禁写（避免建重复仓） | 离线北极星 |
| ④ 令牌与资产 | 令牌取自 `GITEE_TOKEN` 或 `git credential fill`，绝不回显 / 落盘；本地 origin 指向别处拒绝覆盖 | `SPEC-003` 治理准则 / `SPEC-101` 推送流程 |

- `--rehearse`：闸门全齐时**只核对前置件 + 打印命令链**（`executed=false`），用于实证「条件齐备」而不产生任何远端副作用；实测 `gitee_release_tool=true` / `local_git_worktree=true` / `token_available=true` / 五步命令链完整。
- `--selfcheck`：离线覆盖计划生成、四道闸门、墓碑 / 盘符路径跳过、origin 资产保护，15 项能红能绿。
- **默认 dry-run、不判红、不进 `run_all_gates.sh` 阻断链** —— 证据采集与门禁控制分离（见 `docs/记录/审计/组合做大做强战略研究_2026-10-31.md` 第 6.1 节）。
- 首推遇 unrelated histories 按铁律 4 走 `merge --allow-unrelated-histories`，**绝不 `force push`**；收尾用匿名视角复验（`git ls-remote` + `GET /repos` 看 `private=false`），不只看建仓响应。
- **候选前置**：未登记仓（`local_only` / `registration.generated`）先跑 `discover_repos.mjs --apply` 建立 registry 锚点，再生成远端写入计划 —— 不建「无锚点的远端仓」（否则 `check_repos.mjs` 仍判锚点错位）。

**现值**：当前组合 `declared_missing_remote=0` ⇒ 远端写入候选 **0**，`--apply` 无对象。
能力验收来自临时异组合（3 假仓，`REMOTE_WRITE_VERIFY bad=0`，21 项）与真实 CLI
`--rehearse` 演练；远端 API 对演练仓返回 `Not Found Project`，**确认零远端写入**。
真正执行需 `--apply --only <仓名> --confirm` 逐项放行 —— 这是 `SPEC-001` 铁律 3 的治理约束，
不是技术缺口。

### 换发行仓 SOP

1. 定新发行区根 → `PLATFORM_REPOS_ROOT`；定远端账号 → `PLATFORM_GITEE_OWNER`。
2. `node platform/scripts/discover_repos.mjs --json` 看三方差集；确认后 `--offline --apply` 扫描登记（默认 dry-run，先看 `registration.generated` / `needs_manual_review`）。
   已有条目用 `npm run repos:scan` 做全量对账（跑满本机、只判机器字段、人工字段保留），
   `npm run repos:verify` 核对快照；两者不覆盖手抄条目。
3. 重建实例层：registry YAML（补齐 launch / stop / health）→ `tools/facts/build_projects.py` 重建 `facts.json.projects` → `tools/build_portfolio.py --owner <账号> --apply` 重建 PORTFOLIO → 组合分级按新组合重做。
4. `node platform/scripts/check.mjs` / `check_repos.mjs` 对账；`npm run check:governance` 与 `scripts/run_all_gates.sh` 复跑。
5. **（可选）远端写入**：仅当新组合含「已登记 / 远端不存在」的仓时才需要。先看
   `node platform/scripts/publish_repos.mjs` 的 dry-run 计划，再 `--rehearse --only <仓> --confirm`
   演练，最后逐项 `--apply --only <仓> --confirm`（铁律 3，不批量）。当前组合零候选，默认不执行。
6. **异组合验收**：临时 `PLATFORM_REGISTRY` + 临时 `PLATFORM_REPOS_ROOT`（3 个假仓）跑同一套判据，要能绿（exit 0 / 零差集）也要能红（注入盘符 path 判红）。2026-11-13 实测 `ALT_REPO_VERIFY bad=0`、`REMOTE_WRITE_VERIFY bad=0`。
7. 交接卷记账，注明新组合的实例值，不覆盖旧组合历史。

### 借鉴来源记账（铁律 4：来源 + 许可证 + 范围）

仅参考**公开文档中的概念**，未复制任何代码 / 配置片段 / 引入依赖，因此不触发对应项目的代码许可义务。

| 来源 | 官方文档 | 许可证 | 借鉴范围 |
| --- | --- | --- | --- |
| Backstage GitHub Discovery | `https://backstage.io/docs/integrations/github/discovery/` | Apache-2.0 | 「discovery 优于手工登记」；`organization` / `catalogPath` / `filters.repository` / `schedule` 的参数形态 |
| Argo CD SCM Provider Generator | `https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-SCM-Provider/` | Apache-2.0 | 从 SCM 组织自动发现仓的 generator 概念与过滤口径 |
| Mend Renovate autodiscover | `https://docs.renovatebot.com/self-hosted-configuration/` | 未取用代码 → 不适用（仅公开文档概念） | `autodiscover` + `autodiscoverFilter` / `autodiscoverTopics`：「账号可访问集合 = 发现域」 |
### 当前组合的对齐状态（2026-11-13 实测）

`node platform/scripts/discover_repos.mjs --json`（联网）现值：
`local=138` / `entries=145` / `uniqueNames=139` / `internalEntries=1` / `remote=138`；
`local_only=0`、`remote_undeclared=0`、`declared_missing_remote=0`、
`declared_missing_local=2`（`sin-virtue-game` 墓碑 + `write-agent` remote-only，**全部豁免，未豁免 0**）、
`retired_local=1`（`calculator`：远端 404 + README 归档声明，交接卷第一百四十五节历史决策后的本地残留）、
`registration.generated=0` / `needs_manual_review=0` ⇒ **当前组合完全对齐，无待登记项**。

> 历史遗留处置口径：`calculator` 只做正确分类与留痕，**不删目录、不补条目、不推翻交接卷第一百四十五节「用户自行移除」的决策**；一仓多条目属既有设计，只澄清口径不合并条目；`PORTFOLIO.md` 属生成物，用参数化脚本刷新即可。
