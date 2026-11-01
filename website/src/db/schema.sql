-- allin 官网 · 数据库结构（SQLite）
--
-- 口径：**任何业务载荷都不以明文落盘**。
--   图片/附件 → assets.ciphertext
--   文案/留言 → secure_docs.ciphertext
--   用户邮箱 → users.email_cipher（另存 email_hmac 供登录检索）
-- 明文只保留"必须被索引/排序/统计"的最小集合（主键、kind、status、时间）。

CREATE TABLE IF NOT EXISTS schema_meta (
  version    INTEGER NOT NULL,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 密钥环：记录 key_id 与当前生效者，密钥材质本身绝不入库
CREATE TABLE IF NOT EXISTS crypto_keys (
  key_id     TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  is_active  INTEGER NOT NULL DEFAULT 0,
  source     TEXT NOT NULL DEFAULT 'file'   -- file | env
);
CREATE INDEX IF NOT EXISTS idx_crypto_keys_active ON crypto_keys(is_active);

CREATE TABLE IF NOT EXISTS users (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  email_hmac      TEXT NOT NULL UNIQUE,          -- HMAC(主密钥, 小写邮箱)：可检索、不可逆
  email_cipher    BLOB NOT NULL,                 -- 邮箱明文经 GCM 加密后的密文
  display_name    TEXT NOT NULL,
  role            TEXT NOT NULL DEFAULT 'member',-- member | admin
  status          TEXT NOT NULL DEFAULT 'active',-- active | disabled
  password_hash   BLOB NOT NULL,                 -- scrypt
  password_salt   BLOB NOT NULL,
  password_params TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,                   -- 256bit 随机串，cookie 里只放它
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  ip         TEXT,
  user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- 图片 / 附件：二进制一律加密后入库，public/ 目录不存任何业务文件
CREATE TABLE IF NOT EXISTS assets (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_key    TEXT NOT NULL UNIQUE,
  mime         TEXT NOT NULL,
  byte_size    INTEGER NOT NULL,
  sha256_plain TEXT NOT NULL,
  alg          TEXT NOT NULL,
  key_id       TEXT NOT NULL,
  salt         BLOB NOT NULL,
  nonce        BLOB NOT NULL,
  tag          BLOB NOT NULL,
  ciphertext   BLOB NOT NULL,
  aad          TEXT NOT NULL,
  is_public    INTEGER NOT NULL DEFAULT 0,
  meta_cipher  BLOB,                            -- 描述信息（标题/alt/作用域）同样加密
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_assets_public ON assets(is_public);

-- 通用加密文档：站点文案、服务包、时间线、联系留言……
CREATE TABLE IF NOT EXISTS secure_docs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_key      TEXT NOT NULL UNIQUE,
  kind         TEXT NOT NULL,                    -- service | capability | timeline | faq | setting | contact | ticket
  status       TEXT NOT NULL DEFAULT 'new',
  alg          TEXT NOT NULL,
  key_id       TEXT NOT NULL,
  salt         BLOB NOT NULL,
  nonce        BLOB NOT NULL,
  tag          BLOB NOT NULL,
  ciphertext   BLOB NOT NULL,
  aad          TEXT NOT NULL,
  sha256_plain TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_secure_docs_kind ON secure_docs(kind, status);

-- 审计流水：登录、越权尝试、解密失败（安全事件的可追责证据）
CREATE TABLE IF NOT EXISTS audit_log (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  at     TEXT NOT NULL DEFAULT (datetime('now')),
  actor  TEXT,
  action TEXT NOT NULL,
  target TEXT,
  ok     INTEGER NOT NULL DEFAULT 1,
  detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, at);
