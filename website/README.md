# ALLIN LAB · allin 项目开发与维护服务官网

围绕 [`allin`](https://gitee.com/siwpan/allin) 治理仓的**开发与维护服务**官方网站。
本地一键部署、账号体系完整、站点内容与文件**全量加密入库**（AES-256-GCM）。

- 页面：首页 / 关于我们 / 产品服务 / 联系我们（导航互通）+ 登录、注册、客户控制台、管理台
- 风格：赛博朋克 —— 深色底 + 霓虹（青 / 紫 / 品红）、发光边框、扫描线、故障字，桌面移动端自适应
- 存储：文案、图片、附件一律加密写进 SQLite，磁盘 `public/` 目录内**没有任何业务文件**
- 运行：Node.js ≥ 22.5（内置 `node:sqlite`），无原生编译依赖，离线可跑

---

## 1. 目录结构

```
website/
├─ README.md                 本文件（结构 / 启动 / 加密设计 / 图片命名规范）
├─ package.json              依赖清单与脚本
├─ .env.example              配置样例（复制为 .env；.env 已忽略，禁止提交）
├─ .gitignore                忽略 node_modules / data（库与密钥）/ .env / *.key
├─ assets-src/               AI 配图源文件（**非公开目录**，仅 seed 时读取后加密入库）
│  ├─ README.md              配图命名规范与清单
│  └─ site_*.jpg
├─ scripts/
│  ├─ init-db.js             建库 + 建表 + 生成/校验主密钥（幂等）
│  ├─ seed.js                配图与文案加密入库 + 建演示账号
│  ├─ rotate-key.js          密钥轮换（全量重新封装）
│  ├─ verify-crypto.js       加密层自检（含"应该失败"的用例）
│  └─ smoke-test.js          端到端冒烟（起真服务 + 真请求 + 明文泄漏检查）
├─ src/
│  ├─ server.js              Express 入口与中间件装配
│  ├─ config.js              配置：.env → 环境变量 → 默认值
│  ├─ crypto/
│  │  ├─ gcm.js              AES-256-GCM 封套加解密（HKDF 派生 DEK / AAD / 摘要）
│  │  ├─ keystore.js         主密钥（KEK）：生成、加载、轮换、fail-loud
│  │  ├─ envelope.js         单列密文的序列化（如 users.email_cipher）
│  │  └─ errors.js           解密失败分类错误码
│  ├─ db/
│  │  ├─ index.js            连接、建表、schema 版本
│  │  └─ schema.sql          表结构（密文列 + 最小明文索引列）
│  ├─ services/
│  │  ├─ assetService.js     图片 / 附件加密存取与投递
│  │  ├─ assetDelivery.js    资源 HTTP 投递与失败处理（占位图 / 403 / 审计）
│  │  ├─ contentService.js   加密文档仓库（文案、服务包、工单、留言）
│  │  ├─ userService.js      scrypt 口令、会话、CSRF 令牌
│  │  ├─ contactService.js   联系留言（加密）
│  │  ├─ notices.js          友好提示文案表
│  │  └─ audit.js            审计流水
│  ├─ middleware/
│  │  ├─ auth.js             会话装载 / requireAuth / requireRole / CSRF
│  │  └─ security.js         安全响应头 / 登录限流
│  ├─ routes/                pages / auth / member / admin / contact / assets
│  ├─ views/                 EJS 模板（partials: head / header / footer）
│  └─ public/                **只有** css 与 js，不含任何业务图片
└─ data/                     运行时生成（已忽略）：site.db、keys/、seed-accounts.json
```

## 2. 依赖清单

| 依赖 | 版本 | 用途 | 说明 |
|---|---|---|---|
| Node.js | ≥ 22.5 | 运行时 | 用到内置 `node:sqlite`，启动时带 `--experimental-sqlite`（已写进 npm scripts） |
| express | ^4.21.2 | HTTP 与路由 | |
| ejs | ^3.1.10 | 服务端渲染 | 无前端构建步骤 |
| multer | ^2.0.2 | 表单附件（内存） | 2.x 起修复 1.x 的已知漏洞 |

无其它第三方依赖：口令哈希用内置 `crypto.scryptSync`，加密用内置 `crypto`（AES-256-GCM / HKDF），会话与 CSRF 自建。

## 3. 本地启动（三步）

```bash
npm install          # 装依赖
npm run bootstrap    # = npm run init + npm run seed：建库、生成密钥、导入配图与文案
npm start            # 打开 http://localhost:9042
```

启动后管理员账号写在 **`data/seed-accounts.json`**（该目录已被忽略，不会进版本库）：

```bash
cat data/seed-accounts.json     # 含 admin@allin.local / demo@allin.local 与各自口令
```

需要固定口令时：

```bash
ADMIN_SEED_PASSWORD='...' MEMBER_SEED_PASSWORD='...' npm run seed
```

常用脚本：

| 命令 | 作用 |
|---|---|
| `npm start` / `npm run dev` | 启动 / 带 watch 启动 |
| `npm run init` | 建库建表 + 密钥环就绪（幂等） |
| `npm run seed` | 配图与文案加密入库（幂等，同 key 覆盖） |
| `npm run verify:crypto` | 加密层自检（10 项，含篡改 / 错密钥 / 摘要不符） |
| `npm run smoke` | 端到端冒烟（19 项，含落盘明文检查） |
| `npm run rotate-key` | 密钥轮换 + 全量重新封装 |

## 4. 配置（.env，全部可省略）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORT` | `9042` | 监听端口 |
| `SITE_BASE_URL` | `http://localhost:9042` | 站点地址 |
| `SESSION_COOKIE_NAME` | `allin_sid` | 会话 Cookie 名 |
| `SESSION_TTL_HOURS` | `72` | 会话有效期 |
| `COOKIE_SECURE` | `false` | 走 HTTPS 反向代理后改 `true` |
| `DB_PATH` | `./data/site.db` | 数据库文件 |
| `KEY_DIR` | `./data/keys` | 主密钥目录 |
| `SITE_MASTER_KEY_BASE64` | 空 | 主密钥（base64 的 32 字节）；留空则由 `init` 生成密钥文件 |
| `MAX_UPLOAD_MB` | `5` | 附件上限 |

> 生产建议：把 `SITE_MASTER_KEY_BASE64` 注入环境变量（如密钥管理服务），不要依赖磁盘密钥文件。

## 5. 数据库

- 引擎：SQLite（Node 内置 `node:sqlite`），文件在 `data/site.db`（WAL 模式）
- 初始化：`npm run init` 会建目录、执行 `src/db/schema.sql`、写入 `schema_meta.version`，并保证**恰好一把 active 主密钥**
- 表：`crypto_keys` / `users` / `sessions` / `assets` / `secure_docs` / `audit_log`
- 明文只保留必须被索引、排序、统计的最小集合（主键、`kind`、`status`、时间、MIME、字节数），其余全是密文

## 6. 存储与加密设计

### 6.1 密钥体系

```
KEK（主密钥，32B，来自环境变量或 data/keys/<key_id>.key，权限 0600）
  └─ HKDF-SHA256(salt=16B 随机, info="allin-site:v1:<key_id>") → DEK（32B，每条数据独立）
       └─ AES-256-GCM(nonce=12B 随机, AAD="asset:<key>" / "doc:<key>") → 密文 + 16B 认证标签
```

- **主密钥从不直接碰明文**，只用于派生；单条数据的 DEK 随独立盐变化，爆炸半径最小
- 密钥材质**不入库**，`crypto_keys` 只登记 `key_id` / `source` / `is_active`
- 取不到密钥时 **fail loud**（抛 `KeyUnavailableError`），不做静默降级

### 6.2 完整性：三层

1. **GCM 认证标签** —— 密文或 AAD 任一字节被改，解密直接失败
2. **AAD 绑定业务主键** —— `asset:<key>` / `doc:<key>` / `user-email:<hmac>`，密文行被整行搬到别的记录同样解不开
3. **明文 SHA-256 落库** —— 解密后再比对一次，识别"密钥正确但明文被换"的极端情形

### 6.3 解密失败处理

失败**绝不返回可疑明文**，也不对用户吐栈：

| 分类码 | 含义 | 行为 |
|---|---|---|
| `AUTH_FAILED` | 密文/AAD/密钥不匹配（篡改或配置事故） | 资源回占位图 410；文档标记不可用；写审计 |
| `INTEGRITY_MISMATCH` | 标签通过但摘要不符 | 同上 |
| `KEY_UNAVAILABLE` | 密钥未配置或已移除 | 同上，日志明确提示检查 `KEY_DIR` / 环境变量 |
| `VERSION_UNSUPPORTED` / `ENVELOPE_BAD` | 封套版本或结构问题 | 同上 |

审计流水在管理台可见（`auth.denied` / `authz.denied` / `asset.decrypt_failed` / `csrf.failed` / `rate_limit.*`）。

### 6.4 密钥轮换

```bash
npm run rotate-key
# 生成新密钥 → 旧密钥解密 / 新密钥重加密（assets + secure_docs + users）→ 置为 active
```

注意：用户登录用的 `email_hmac` 由主密钥派生，轮换脚本会**同步重算**，否则轮换后全部账号将无法登录。

## 7. 账号与权限

| 区域 | 要求 | 未满足时 |
|---|---|---|
| 四个公开页 | 无需登录 | — |
| `/member` 客户控制台 | 登录 | 302 → `/login?next=…&notice=login_required`；JSON 请求返回 401 `LOGIN_REQUIRED` |
| `/member/files/:key` | 登录 | 同上（提示"该文件为登录用户专享"） |
| `/admin` 管理台 | `admin` 角色 | 403 页面 + 审计 `authz.denied` |

- 口令：scrypt（N=16384, r=8, p=1）+ 16B 随机盐，参数随行存储便于未来调参；用户不存在时也跑一次等价 scrypt，抹平时序侧信道
- 会话：256bit 随机 ID 仅存于 httpOnly + SameSite=Lax Cookie，其余信息在库里；登出即服务端销毁
- CSRF：会话内令牌 + 表单隐藏域，所有写操作校验；失败回 403 友好页
- 限流：登录 / 注册按 IP+邮箱固定窗口限流，超限回 429 友好页
- 邮箱：存 `HMAC(主密钥, 小写邮箱)` 供登录检索 + GCM 密文供展示；审计流水只记 `user:<id>`

## 8. 配图命名规范（摘要）

配图由 AI 生成，源文件放在 `assets-src/`（**不是公开目录**），`npm run seed` 时加密写入数据库。
命名：`site_<page>_<slot>_<nn>.<ext>`，全小写 ASCII、下划线分隔，入库后的 `asset_key` = 文件名去掉扩展名。
完整规范与逐图清单见 [`assets-src/README.md`](assets-src/README.md)。

## 9. 冒烟验证（`npm run smoke`）

自动起一个临时实例（端口 9155）并跑 19 项检查：

四页可达与样式加载 · 配图由数据库解密投递 · 缺失资源回占位图 · 匿名访问受保护区跳转登录 · 匿名 JSON 请求 401 · 注册下发会话 · 登录进控制台 · 会员文件下载 · 会员文件对匿名重定向 · 越权访问管理台 403 · 留言（含附件）入库 · 管理员登录与查看留言 · 登出失效 · **数据库内无业务明文**。

## 10. 已知边界

- 会话与限流状态在进程内 / 库内，多实例部署需要共享存储（接口已隔离，替换实现即可）
- `node:sqlite` 在 Node 22 上仍标记 experimental，启动带 `--experimental-sqlite`；Node 23.4+ 可去掉该标志
- 配图为 AI 生成，仅用于版式演示；正式上线建议替换为品牌素材

## 11. 许可

与主仓一致：MIT。配图由 AI 生成（2026-11-01，工具：ImageGen），无第三方版权素材引入。
