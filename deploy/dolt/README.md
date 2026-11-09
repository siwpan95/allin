# allin × Dolt 部署与分工说明（已落仓于 `deploy/dolt/`）

> 定位：**事实的版本历史与审计层**。Git 内的结构化真身仍是唯一写入权威；
> Dolt 的 commit DAG 提供「谁在什么时候知道什么」的 transaction time，补齐 Git 做不到的行级 diff / as-of。

## 1. 版本与安装（官方 / 一手）

| 项 | 结论 | 来源 |
|---|---|---|
| 许可 | **Apache-2.0** | `dolthub/dolt` README |
| Windows | 官方提供 **MSI**；官方最新 **v2.7.2（2026-11-05）**；winget `DoltHub.Dolt` 包管理器快照 v2.6.1 / 2026-10（**以 GitHub Releases 为准，别被 winget 快照骗了**） | <https://github.com/dolthub/dolt/releases> · <https://winpkg.com/apps/DoltHub.Dolt> |
| 形态 | 单个约 103 MB 二进制，无服务依赖 | 官方 README |
| 服务模式 | `dolt sql-server` → **localhost:3306**，MySQL 线协议，客户端可到 MySQL 8.4 | <https://docs.dolthub.com/> |
| Docker | `dolthub/dolt`（CLI）、`dolthub/dolt-sql-server`（server） | 官方 README |
| 公开托管 | **DoltHub 公开数据免费**，`dolt clone` 可拉公开库；与 GitHub/Gitee 是两套独立远端 | <https://github.com/dolthub/dolt> |

> 本机 2026-11-09 实测：`winget install --id DoltHub.Dolt --exact --silent` 已装 **dolt 2.7.2**
> （`C:/Program Files/Dolt/bin/dolt.exe`，PATH 未刷新故脚本通过临时 PATH 注入调用）。
> `schema.sql` 已真机执行（exit 0），`import_from_git.py --apply` 已产出带
> `CALL DOLT_COMMIT` 的提交，`--verify` 已验 `AS OF 'HEAD'` / `AS OF 'HEAD~1'` 与 `dolt_diff_fact`。
> 库目录 `facts/dolt-workspace/` 是可重建派生物，被 `.gitignore` 排除。

## 2. 与 Git 的分工（**不双写**，这是本方案的关键裁决）

| 层 | 存什么 | 谁是权威 |
|---|---|---|
| Git（`docs/事实源/_structured/facts.json` + schema） | 人类可读的**当前真身**、制度、生成物 | ✅ 唯一写入权威 |
| Dolt（`allin_facts`） | 由 Git 单向导入的**事实行 + commit 历史** | ❌ 派生物，可重建 |
| SQLite（`build/facts.sqlite`） | 本机查询用派生缓存，不入库 | ❌ 派生物，可重建 |
| NetBox | 资产/关系视图 | ❌ 派生物，可重建 |
| GraphRAG | 叙述层语义索引 | ❌ 派生物，可重建 |

**防双写漂移**：`facts import --from-git` 是唯一写 Dolt 的入口；Dolt 侧每次导入后打 tag
`git-<short-sha>`，门禁用 tag 与 `git rev-parse HEAD` 对账。任何人不得在 Dolt 里直接 `UPDATE fact`
来"修事实"——要改就改 Git 真身再重导。

## 3. 初始化命令序列

```bash
winget install --id DoltHub.Dolt --exact
dolt config --global --add user.name  "allin-agent"
dolt config --global --add user.email "allin@example.invalid"

mkdir E:/allin-dolt && cd E:/allin-dolt
dolt init --name allin_facts --email allin@example.invalid
dolt sql < D:/projects/allin/.../blueprint/deploy/dolt/schema.sql
dolt add . && dolt commit -m "chore(facts): init schema from facts.schema.json v0.1.0"

# 服务模式（按需启动，绑回环；端口 3306 本机实测空闲；MCP server 默认 7007/HTTP）
dolt sql-server --host 127.0.0.1 --port 3306
```

### ⚠ 最容易踩的一条：SQL COMMIT ≠ dolt commit

Dolt 的 SQL `COMMIT` 只结束事务，**不会**产生版本历史；导入/改值后必须显式
`CALL DOLT_COMMIT('-m', '...', '--author', 'allin-agent <...>')`，
否则 `AS OF` / `dolt_diff_*` 全线失效，transaction time 直接断掉。
`source_git_sha` 写进每条 commit message，作为跨 Git / NetBox / Dolt / GraphRAG 的统一溯源键。

```sql
CALL DOLT_COMMIT('-m', 'facts: import from git 9b1c2ab', '--author', 'allin-agent <allin@example.invalid>');
SELECT * FROM dolt_log;
SELECT * FROM dolt_diff_fact WHERE to_commit = HASHOF('HEAD');
```

### 远端：可以直接把 GitHub / Gitee 当 Dolt remote

Dolt 支持 `refs/dolt/data` 推到普通 git 托管（官方文档 Working with Dolt data on GitHub），
与 allin 的 Gitee + GitHub 双核推送纪律天然契合；也可 `dolt push origin` 到 DoltHub 公开库（免费）。
两条远端**只推 `visibility=public` 的行**，私有字段不得出本机。

## 4. 双时态：Dolt commit = transaction time，表内区间 = valid time

`fact` 表用 SCD-2：`valid_from/valid_to` 表达"现实何时为真"，改值 = 关闭旧行 + 追加新行，
绝不 `UPDATE`。Dolt 的 commit 历史表达"库何时知道"：

```sql
-- 现在的事实
SELECT * FROM current_facts WHERE subject='global' AND attribute='gitee_remote_repo_count';

-- 某日期现实为真的值（as-of）
SELECT * FROM fact WHERE subject='global' AND valid_from<='2026-11-01'
  AND (valid_to IS NULL OR valid_to>'2026-11-01');

-- 某个历史提交里库以为的值（as-was / transaction time）
SELECT * FROM fact AS OF 'HEAD~3' WHERE subject='global';

-- 行级 diff 与 blame
SELECT * FROM dolt_diff_fact WHERE to_commit = HASHOF('HEAD');
SELECT * FROM dolt_log;
```

## 5. 已知限制（别当银弹）

- `dolt sql-server` 是**本地服务**，多机同步要靠 `dolt push/pull` 到 DoltHub，不是实时多写；
  并发写冲突需 `dolt conflicts` 人工裁决（与 Git 同源，也比 Git 更容易在 schema 变更时打架）。
- schema 变更的 merge 比数据 merge 脆弱 → 用 `schema_version` + ADR 管控，禁止在分支上改列类型。
- Windows 路径 / 大小写：Dolt 库目录用 ASCII 短路径（`E:/allin-dolt`），别放中文目录。
- 二进制 `.dolt` 数据目录**不得进 Git**（`.gitignore` 已忽略 `*.db`，需补 `.dolt/`）。
- 备份：`dolt backup` + DoltHub 公开远端双通道；公开远端只放 `visibility=public` 的行。
- 与 NetBox 的区别：NetBox 管"资产应该是什么样"（desired state），Dolt 管"事实曾经是什么"（history），
  **两者不是替代关系**，别让 NetBox 的 changelog 和 Dolt 的 commit 各记一套互不校验的账。

## 6. 最小验收

1. `dolt sql -q "SELECT COUNT(*) FROM current_facts"` 与 `facts_cli.py query --sql "SELECT count(*) FROM current_facts"` **逐字符相等**；
2. 改 Git 真身一个值 → 重导 → `dolt diff` 恰好 1 行变化，`dolt_log` 多 1 条；
3. `AS OF 'HEAD~1'` 能查到改前的值；
4. 删掉整个 Dolt 目录重建，两次导入的 `dolt hash` 一致（可重建性）；
5. Dolt 服务停掉，`scripts/run_all_gates.sh` 仍 20/20 全绿。

## 7. P1-2 / P1-3 运行手册（脚本已落仓，执行待授权）

> 以下动作要么改本机 `.dolt` 配置、要么需网络/拉起本地服务，属需授权的系统级变更；
> 脚本默认 **dry-run** 打印计划，加 `--apply` 才真正执行。沙箱/agent 不代跑重安装与服务启动。

### P1-2 配置 remote + DOLT_BACKUP 灾备

```bash
bash deploy/dolt/remote_backup.sh            # dry-run：打印 remote / backup 计划
bash deploy/dolt/remote_backup.sh --apply    # 真正 dolt remote add + backup add
# 之后每次同步：
dolt backup sync local-backup                 # 本地灾备（E:/allin-dolt-backup，离线可跑）
dolt push allin-git                          # 推到 GitHub refs/dolt/data（需网络）
```

- 远端 `allin-git` = `git@github.com:siwpan95/allin.git`，借用 allin 仓的 `refs/dolt/data` 命名空间（GitHub Dolt 集成，官方支持），与 Gitee + GitHub 双核推送纪律同源；
- 本地灾备 `local-backup` = `file://E:/allin-dolt-backup`，**离线可跑**，只放可重建派生物；
- 两个远端**只推 `visibility=public` 的行**，私有字段不得出本机（见 §2 分工裁决）。

### P1-3 启动 dolt sql-server（本地服务，绑回环）

```bash
bash deploy/dolt/sql_server.sh               # dry-run
bash deploy/dolt/sql_server.sh --apply --background   # 后台拉起 127.0.0.1:3306
```

- 服务模式（localhost:3306，MySQL 线协议）；多机同步靠 `dolt push/pull`，非实时多写（见 §5 限制）；
- 启动后可用任何 MySQL 8.4 客户端连 `127.0.0.1:3306` 查 `allin_facts`；停掉服务不影响门禁（派生物，门禁不依赖）。
