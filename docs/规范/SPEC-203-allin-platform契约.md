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
scripts/       check.mjs（无 GUI 审计）/ build_batch.mjs（批量打包）/ ensure-mirror.ps1（本地 npm 镜像）。
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
📌 **口径补充（2026-11-13 实测）**：145 份 YAML 归并后只有 **140 个唯一仓名**（`musickit` 3 条，`foolproof-operation` / `magic-tower` / `private-radio-stations` 各 2 条）；组合分级的「140 决策对象」与这个「140 唯一仓名」**数值相同、语义无关**，不得当成一个数。

### 发现参数（唯一来源）

| 参数 | 含义 | 默认 | 消费方 |
| --- | --- | --- | --- |
| `PLATFORM_REPOS_ROOT` | 发行区根 | `<allin 同级>/repos` | `registry.js` 的 `reposRoot()` → `resolvePath()` / `isPathContained()` / `pathCheckMode()`；`discover_repos.mjs` |
| `PLATFORM_REGISTRY` | 注册表目录 | `platform/registry/projects` | `check.mjs` / `check_repos.mjs` / `discover_repos.mjs` |
| `PLATFORM_GITEE_OWNER` | 远端账号 | `siwpan` | `check_repos.mjs` / `discover_repos.mjs` / `tools/build_portfolio.py`（2026-11-13 起同源） |
| `PLATFORM_REPOS_OFFLINE` | 离线只做本机面 | 未设 | `check_repos.mjs` / `discover_repos.mjs` |

**2026-11-13 修复**：`resolvePath('repos/...')` 此前固定按 `WORKSPACE_ROOT` 拼接，`PLATFORM_REPOS_ROOT` 只影响 `REPOS_ROOT` 导出 ⇒ 换发行仓后校验 / 启动仍指向默认区，异组合验收 3 仓全量误报「path 不存在」。现改为统一走 `reposRoot()`；**env 未设时解析结果与旧实现逐字节相同**，回归用例并入 `registry.test.mjs` 的 S-2 用例（测试数保持 75）。

### 发现与对账

- `platform/scripts/discover_repos.mjs` 是**采集层**：输出本地发行区 / registry 声明 / 远端 owner 三方差集，支持 `--offline` / `--json` / `--draft` / `--strict` / `--selfcheck`。
- **默认只读、不写盘、不判红、不进 `run_all_gates.sh` 阻断链** —— 离线北极星 + 「证据采集与门禁控制分离」（见 `docs/记录/审计/组合做大做强战略研究_2026-10-31.md` 第 6.1 节）。`--strict` 仅供人工 / CI 显式选用。
- `--draft` 生成的条目**缺 launch / stop / health**，直接入库会被 `validateEntry` 判红 —— 刻意不伪造「看起来能直接入库」的清单。

### 换发行仓 SOP

1. 定新发行区根 → `PLATFORM_REPOS_ROOT`；定远端账号 → `PLATFORM_GITEE_OWNER`。
2. `node platform/scripts/discover_repos.mjs --json` 看三方差集；`--draft` 出待补登记草稿（人工复核）。
3. 重建实例层：registry YAML（补齐 launch / stop / health）→ `tools/facts/build_projects.py` 重建 `facts.json.projects` → `tools/build_portfolio.py --owner <账号> --apply` 重建 PORTFOLIO → 组合分级按新组合重做。
4. `node platform/scripts/check.mjs` / `check_repos.mjs` 对账；`npm run check:governance` 与 `scripts/run_all_gates.sh` 复跑。
5. **异组合验收**：临时 `PLATFORM_REGISTRY` + 临时 `PLATFORM_REPOS_ROOT`（3 个假仓）跑同一套判据，要能绿（exit 0 / 零差集）也要能红（注入盘符 path 判红）。2026-11-13 实测 `ALT_REPO_VERIFY bad=0`。
6. 交接卷记账，注明新组合的实例值，不覆盖旧组合历史。

### 借鉴来源记账（铁律 4：来源 + 许可证 + 范围）

仅参考**公开文档中的概念**，未复制任何代码 / 配置片段 / 引入依赖，因此不触发对应项目的代码许可义务。

| 来源 | 官方文档 | 许可证 | 借鉴范围 |
| --- | --- | --- | --- |
| Backstage GitHub Discovery | `https://backstage.io/docs/integrations/github/discovery/` | Apache-2.0 | 「discovery 优于手工登记」；`organization` / `catalogPath` / `filters.repository` / `schedule` 的参数形态 |
| Argo CD SCM Provider Generator | `https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-SCM-Provider/` | Apache-2.0 | 从 SCM 组织自动发现仓的 generator 概念与过滤口径 |
| Mend Renovate autodiscover | `https://docs.renovatebot.com/self-hosted-configuration/` | 未取用代码 → 不适用（仅公开文档概念） | `autodiscover` + `autodiscoverFilter` / `autodiscoverTopics`：「账号可访问集合 = 发现域」 |
