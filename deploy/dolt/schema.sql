-- allin × Dolt —— 版本化事实库 schema（待落仓骨架）
-- 方言：MySQL（Dolt 线协议兼容）；Dolt 版本口径见 README。
-- 定位：Dolt 存**事实的版本历史与审计**，Git 存**人类可读的结构化真身与制度**。
--       两者不双写：Git -> Dolt 单向导入，Dolt commit 只作「历史/审计」用途，绝不反向写回 Git。
-- 未在真机执行：本机 2026-11-09 实测 dolt 未安装（仅规划），首次落仓须用 dolt sql < 本文件 验证。

-- 在 `dolt init` 生成的库目录里执行（库名 = 目录名），故不做 CREATE DATABASE / USE。
-- 入口：dolt sql < deploy/dolt/schema.sql

-- 实体表：machine_id 是显式主键，彻底消除「本机」歧义（铁律 6 / g20 self-anchor）。
CREATE TABLE IF NOT EXISTS machine (
  machine_id      VARCHAR(64) NOT NULL PRIMARY KEY,
  hostname        VARCHAR(128) NOT NULL,
  os_caption      VARCHAR(128),
  os_build        VARCHAR(32),
  cpu             VARCHAR(128),
  ram_gb          DECIMAL(8,2),
  status          ENUM('active','retired','planned','unknown') NOT NULL DEFAULT 'unknown',
  visibility      ENUM('public','internal','private') NOT NULL DEFAULT 'public',
  evidence_ref    VARCHAR(512) NOT NULL,
  observed_at     DATE NOT NULL,
  valid_from      DATE NOT NULL,
  valid_to        DATE NULL
);

CREATE TABLE IF NOT EXISTS volume (
  volume_id     BIGINT NOT NULL AUTO_INCREMENT,
  machine_id    VARCHAR(64) NOT NULL,
  letter        CHAR(1) NOT NULL,
  label         VARCHAR(128),
  fs            VARCHAR(32),
  size_gb       INT,
  free_gb       INT,
  role          ENUM('system','workspace','data','removable','archive','unknown'),
  observed_at   DATE NOT NULL,
  valid_from    DATE NOT NULL,
  evidence_ref  VARCHAR(512) NOT NULL,
  PRIMARY KEY (volume_id),
  UNIQUE KEY uq_volume (machine_id, letter, valid_from),
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id)
);

CREATE TABLE IF NOT EXISTS runtime (
  runtime_id    BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  machine_id    VARCHAR(64) NOT NULL,
  tool          ENUM('python','node','npm','git','pwsh','docker','dolt','other') NOT NULL,
  exe_path      VARCHAR(512) NOT NULL,
  version       VARCHAR(64),
  flags_json    JSON,
  is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
  observed_at   DATE NOT NULL,
  evidence_ref  VARCHAR(512) NOT NULL,
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id),
  UNIQUE KEY uq_runtime (machine_id, tool, exe_path),
  INDEX ix_runtime_machine (machine_id, tool)
);

CREATE TABLE IF NOT EXISTS repo_checkout (
  checkout_id   BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  machine_id    VARCHAR(64) NOT NULL,
  repo_id       VARCHAR(128) NOT NULL,
  local_path    VARCHAR(512),
  has_git       BOOLEAN,
  has_origin    BOOLEAN,
  state         ENUM('full','partial','remote-only','archived'),
  observed_at   DATE NOT NULL,
  evidence_ref  VARCHAR(512) NOT NULL,
  UNIQUE KEY uq_checkout (machine_id, repo_id, observed_at),
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id)
);

CREATE TABLE IF NOT EXISTS service_port (
  port          INT NOT NULL,
  service       VARCHAR(128) NOT NULL,
  owner_ref     VARCHAR(256),
  segment       VARCHAR(32),
  status        ENUM('active','retired','transient','reserved') NOT NULL,
  machine_id    VARCHAR(64) NULL,
  observed_at   DATE NOT NULL,
  evidence_ref  VARCHAR(512) NOT NULL,
  PRIMARY KEY (port, service)
);

CREATE TABLE IF NOT EXISTS service (
  service_id     VARCHAR(128) NOT NULL PRIMARY KEY,
  name           VARCHAR(256) NOT NULL,
  kind           ENUM('portal','api','worker','site','engine','mcp','database','knowledge','other'),
  lifecycle      ENUM('experimental','production','deprecated','retired'),
  owner_ref      VARCHAR(256),
  depends_on_json JSON,
  visibility     ENUM('public','internal','private') NOT NULL DEFAULT 'public',
  observed_at    DATE NOT NULL,
  evidence_ref   VARCHAR(512) NOT NULL
);

-- 事实行（SCD-2 + 观测时间）：改值 = 关闭旧行 valid_to + 追加新行，绝不 UPDATE。
-- valid_from/valid_to = 现实为真的区间；Dolt commit 历史 = 库何时知道（transaction time）。
CREATE TABLE IF NOT EXISTS fact (
  fact_id        VARCHAR(32) NOT NULL PRIMARY KEY,
  subject        VARCHAR(256) NOT NULL,
  attribute      VARCHAR(128) NOT NULL,
  value_text     TEXT,
  value_number   DECIMAL(20,4),
  unit           ENUM('count','gb','version','path','bool','text','enum','none'),
  scope          ENUM('global','machine','repo','service','doc') NOT NULL,
  machine_id     VARCHAR(64) NULL,
  status         ENUM('current','superseded','disputed','retracted') NOT NULL,
  valid_from     DATE NOT NULL,
  valid_to       DATE NULL,
  observed_at    DATE NOT NULL,
  observed_by    VARCHAR(256),
  evidence_ref   VARCHAR(512) NOT NULL,
  source_file    VARCHAR(512),
  source_line    INT,
  supersedes     VARCHAR(32),
  visibility     ENUM('public','internal','private') NOT NULL DEFAULT 'public',
  INDEX ix_fact_lookup (subject, attribute, valid_from, valid_to),
  INDEX ix_fact_asof (valid_from, valid_to),
  INDEX ix_fact_machine (machine_id, observed_at)
);

-- 文档登记（把 D9/D13/D14 的章节引用变成可查外键）
CREATE TABLE IF NOT EXISTS doc_ref (
  doc_id       VARCHAR(64) NOT NULL PRIMARY KEY,
  path         VARCHAR(512) NOT NULL,
  section      VARCHAR(64),
  kind         ENUM('spec','fact','record','adr','index','history'),
  is_generated  BOOLEAN NOT NULL DEFAULT FALSE,
  visibility   ENUM('public','internal','private') NOT NULL DEFAULT 'public'
);

-- 采集流水：采集值是原始值，不是事实（tools/facts/README.md）
CREATE TABLE IF NOT EXISTS observation_run (
  run_id          VARCHAR(64) NOT NULL PRIMARY KEY,
  machine_id      VARCHAR(64) NOT NULL,
  ts              DATETIME NOT NULL,
  command         VARCHAR(512) NOT NULL,
  raw_hash        VARCHAR(128) NOT NULL,
  adjudicated_by  VARCHAR(128),
  evidence_ref    VARCHAR(512)
);

-- 当前值视图：所有 COUNT/口径查询都只走这里，杜绝 138/137/140 混用
CREATE OR REPLACE VIEW current_facts AS
  SELECT * FROM fact
  WHERE status = 'current' AND valid_to IS NULL;

-- 机器汇总视图：跨机聚合的单一入口
CREATE OR REPLACE VIEW machine_summary AS
  SELECT m.machine_id, m.hostname, m.status,
         (SELECT COUNT(*) FROM repo_checkout r WHERE r.machine_id = m.machine_id
            AND r.observed_at = (SELECT MAX(observed_at) FROM repo_checkout r2
                                 WHERE r2.machine_id = m.machine_id)) AS repo_count
  FROM machine m WHERE m.status = 'active';

-- 溯源锚点：每次 Git -> Dolt 导入写一行，source_git_sha 是跨四系统的统一溯源键。
-- 正常审计按 source_git_sha 直接 join Git / NetBox changelog_message / dolt_log；
-- 本表用于「某条变更找不到对应提交」的异常排查（双路径：直接 join + 索引兜底）。
CREATE TABLE IF NOT EXISTS fact_version (
  fact_version_id   BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  table_name        VARCHAR(64) NOT NULL,
  row_pk            VARCHAR(64) NOT NULL,
  source_path       VARCHAR(512) NOT NULL,
  source_git_sha    VARCHAR(64) NOT NULL,
  ingest_run_id     VARCHAR(64) NOT NULL,
  ingested_at       DATETIME NOT NULL,
  UNIQUE KEY uq_fv (table_name, row_pk, source_git_sha),
  INDEX ix_fv_git (source_git_sha),
  INDEX ix_fv_run (ingest_run_id),
  INDEX ix_fv_lookup (table_name, row_pk)
);

-- ---------- Dolt 特有的时间旅行用法（首次 commit 之后才可用） ----------
-- SELECT * FROM fact AS OF 'HEAD~1' WHERE subject = 'global';            -- 上一个提交
-- SELECT * FROM dolt_diff_fact WHERE to_commit = HASHOF('HEAD');         -- 行级 diff
-- SELECT * FROM dolt_log;                                                -- 提交历史
-- SELECT * FROM DOLT_JSON_DIFF(@before, @after);                         -- JSON 文档逐路径 diff
-- SELECT * FROM fact AS OF 'feature/machine-04' WHERE machine_id='...';  -- 分支对比
-- 官方系统表文档：https://docs.dolthub.com/reference/sql/dolt-system-tables
