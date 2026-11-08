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
| `npm run smoke` | 端到端冒烟（当前 28 项；判据以 SMOKE_SUMMARY status=clean 为准） |
| `npm run rotate-key` | 密钥轮换 + 全量重新封装 |
| `npm run backup:data` | 数据库一致性快照（只产出密文库，**不带密钥**） |
| `npm run check:data-hygiene` | 运行时数据卫生体检（只读，检出「密钥与密文同处」） |

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
轮换全程在**单个 SQLite 事务**内执行（2026-11-04 起）：中途任一行失败即整体回滚，密钥环与数据保持轮换前状态；
`source=env` 且新注入材质与旧钥相同时拒绝执行（防"换 key_id 不换材质"的伪轮换）。

### 6.5 密钥灾备（2026-11-04 补，SEV1 防线）

**威胁模型**：`data/` 整目录不入 git，`crypto_keys` 表只登记 key_id 不存材质——
主密钥文件一旦丢失（换机误删 / 盘坏），全部密文不可逆丢失，且 fail-loud 设计下没有静默降级逃生门
（解密失败 → 占位图 410 + 全账号不可登录）。**唯一防线是密钥备份**。

```bash
# 备份（必须带口令；口令丢失 = 备份不可解，与密钥丢失同效，口令另妥善保存）
npm run backup-key -- --out <外部目录/介质> --passphrase <强口令>
# 恢复（新机器 / 密钥丢失后）
npm run restore-key -- --from <备份文件> --passphrase <口令>
npm run verify:crypto && npm run smoke   # 恢复后必跑
```

- 备份内容：`data/keys/` 全部 key 文件 + `crypto_keys` 清单（含 is_active），AES-256-GCM 加密
  （scrypt N=2^15 口令派生），备份文件 0600；
- **拒绝写进仓库目录内**（防 git 意外收走）；**拒绝无口令的明文备份**；
- `env` 来源（`SITE_MASTER_KEY_BASE64`）的材质不落盘、不进备份——它的灾备责任在注入通道/密钥管理服务本身；
- **恢复演练月度化**：从备份 restore → verify:crypto 10/10 + smoke 输出 SMOKE_SUMMARY status=clean 才算备份有效。
  （出处：2026-11-04 事故响应演练情景 A，SEV1；收口规范见 `docs/规范/SPEC-106-事故分级与响应约定.md` §6。）

### 6.6 备份纪律：密钥与密文必须分开（2026-11-07 安全加固）

**红线**：本站「全库密文」的安全前提是**主密钥不与数据库同处一份可复制的快照**。
把 `data/` 整目录 `cp -r` 成备份，会同时带走 `site.db` 与 `data/keys/*.key` ——
拿到这份目录的人能解开全部内容、全部邮箱与全部附件，加密等于没做。

```bash
# ✅ 正确：两条命令、两个落点，密钥备份还必须带口令
npm run backup:data -- --out D:/backup/db        # 只产出 allin-site-db-<stamp>.db
npm run backup-key -- --out E:/backup/keys --passphrase <强口令>   # 另一个介质

# ❌ 错误：整目录复制（会被体检判红）
cp -r data/ data-bak/

# 只读体检：发现任何「库 + 密钥」同处即 exit 1，并给出处置步骤（不删任何文件）
npm run check:data-hygiene
```

- `backup:data` 用 SQLite `VACUUM INTO` 出一致性快照：服务运行中可备份，源库只读，
  不带 WAL/SHM 半写状态，**产物里没有 `keys/`、没有 `seed-accounts.json`**；
- 两个脚本都**拒绝写进仓库目录内**（防 git / 网盘同步意外收走）；
- `check:data-hygiene` 只读扫描，检出高危布局只报告、绝不代表人工删除；
  处置（分离保管或删除过期快照）必须先人工确认，并在快照曾外发/上云时按全库泄露处置
  （`npm run rotate-key` + 重置两个种子账号口令）；
- `data/seed-accounts.json` 含明文种子口令（0600 + gitignore）。本机单用户可接受，
  但共享主机 / 上云备份 / 曾外发过 `data/` 时必须重置这两个账号。

## 7. 账号与权限

| 区域 | 要求 | 未满足时 |
|---|---|---|
| 四个公开页 | 无需登录 | — |
| `/member` 客户控制台 | 登录 | 302 → `/login?next=…&notice=login_required`；JSON 请求返回 401 `LOGIN_REQUIRED` |
| `/member/files/:key` | 登录 | 同上（提示"该文件为登录用户专享"） |
| `/admin` 管理台 | `admin` 角色 | 403 页面 + 审计 `authz.denied` |

- 口令：scrypt（N=32768, r=8, p=1）+ 16B 随机盐，参数随行存储便于未来调参；用户不存在时也跑一次等价 scrypt，抹平时序侧信道
- 会话：256bit 随机 ID 仅存于 httpOnly + SameSite=Lax Cookie，其余信息在库里；登出即服务端销毁
- CSRF：会话内令牌 + 表单隐藏域，所有写操作校验；失败回 403 友好页
- 限流：登录 / 注册按 IP+邮箱固定窗口限流，超限回 429 友好页
- 邮箱：存 `HMAC(主密钥, 小写邮箱)` 供登录检索 + GCM 密文供展示；审计流水只记 `user:<id>`

## 8. 配图命名规范（摘要）

配图由 AI 生成，源文件放在 `assets-src/`（**不是公开目录**），`npm run seed` 时加密写入数据库。
命名：`site_<page>_<slot>_<nn>.<ext>`，全小写 ASCII、下划线分隔，入库后的 `asset_key` = 文件名去掉扩展名。
完整规范与逐图清单见 [`assets-src/README.md`](assets-src/README.md)。

## 9. 冒烟验证（`npm run smoke`）

自动起一个临时实例（端口 9155）并跑 28 项检查（2026-11-05 起，原 19 项 + 9 项治理用例）：

四页可达与样式加载 · 配图由数据库解密投递 · 缺失资源回占位图 · 匿名访问受保护区跳转登录 · 匿名 JSON 请求 401 · 注册下发会话 · 登录进控制台 · 会员文件下载 · 会员文件对匿名重定向 · 越权访问管理台 403 · 留言（含附件）入库 · 管理员登录与查看留言 · 登出失效 · **数据库内无业务明文** · 治理看板 9 项（匿名看板 302 / 治理 API 401 / platform 离线看板仍 200 且降级提示 / member 调写接口 403 / admin 缺 CSRF 403 / 非法 id 400 等）。

## 9.1 治理看板（2026-11-05 增量，ADR-0010）

- `/member/dashboard`（登录即可）：平台状态卡 / 门禁健康卡 / 编排健康卡，**只读**，数据经服务端 BFF 代理（`services/portalProxy.js`：3s 超时、错误三分类、内存快照缓存）取自 platform portal——浏览器零新增暴露面，platform 离线时页面照常 200 并显示降级提示。
- `/admin/governance`（仅 admin）：项目启停（CSRF + 两段式确认，代理转发 portal 既有端点）+ 审计流水过滤视图（`audit_log` 的 `governance.*` 流水）。
- 配置：`PORTAL_*` 环境变量段（见 §4，缺省走 `platform/data/portal.port` 文件发现）；写操作成败均落审计，`governance.view` 仅页面加载记一次（不挂轮询）。

## 10. 已知边界

- 会话与限流状态在进程内 / 库内，多实例部署需要共享存储（接口已隔离，替换实现即可）
- `node:sqlite` 在 Node 22 上仍标记 experimental，启动带 `--experimental-sqlite`；Node 23.4+ 可去掉该标志
- 配图为 AI 生成，仅用于版式演示；正式上线建议替换为品牌素材

## 11. 许可

与主仓一致：MIT。配图由 AI 生成（2026-11-01，工具：ImageGen），无第三方版权素材引入。
