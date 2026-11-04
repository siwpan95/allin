'use strict';

/**
 * 初始化站点内容：把配图与文案**加密**写进数据库。
 *
 * 三件事：
 *   1) assets-src/ 下的 AI 配图 → assets 表（密文），public/ 目录不留任何图片；
 *   2) 站点文案 / 服务包 / 时间线 / FAQ / 工单 → secure_docs 表（密文）；
 *   3) 建一个管理员账号与一个演示账号，口令随机生成并写入 data/seed-accounts.json
 *      （该文件在 .gitignore 覆盖范围内，**不会进版本库**）。
 *
 * 用法：npm run seed          # 幂等，重复执行覆盖同 key 内容
 *      ADMIN_SEED_PASSWORD=xxx npm run seed   # 需要固定口令时用环境变量指定
 */

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const config = require('../src/config');
const { getDb } = require('../src/db');
const assetService = require('../src/services/assetService');
const contentService = require('../src/services/contentService');
const userService = require('../src/services/userService');

const ASSETS_SRC = path.join(config.root, 'assets-src');

/** 配图登记：文件名即 asset_key（去扩展名），说明与 alt 一并写入 meta。 */
const IMAGE_META = {
  site_home_hero_01: { scope: 'public', title: '首页主视觉 · 霓虹数据城', alt: '霓虹数据中心夜景' },
  site_services_dev_01: { scope: 'public', title: '服务配图 · 平台开发', alt: '全息代码编辑界面' },
  site_services_ops_01: { scope: 'public', title: '服务配图 · 持续维护', alt: '霓虹服务器机房' },
  site_services_gov_01: { scope: 'public', title: '服务配图 · 治理陪跑', alt: '治理门禁流水线概念图' },
  site_about_team_01: { scope: 'public', title: '关于我们 · 工作室', alt: '赛博风格工作室' },
  site_contact_grid_01: { scope: 'public', title: '联系我们 · 通讯枢纽', alt: '霓虹通讯枢纽' },
  site_share_banner_01: { scope: 'public', title: '通用横幅', alt: '霓虹电路横幅' },
};

const CAPABILITIES = [
  { label: '纳管仓库', value: 145, unit: ' 个', note: '注册表在册，生命周期可追踪' },
  { label: '治理门禁', value: 20, unit: ' 道', note: 'g00–g20，提交即跑、红了就拦' },
  { label: '本地克隆', value: 141, unit: ' 个', note: '体检脚本逐仓核对状态' },
  { label: '文档枢纽', value: 76, unit: ' 篇', note: '索引契约自动对账' },
];

const SERVICES = [
  {
    code: 'DEV',
    title: '治理内核落地与平台开发',
    tagline: 'build it right, once',
    summary:
      '从零或接手既有仓库，搭建平台门户、注册表、CLI 与自动化流水线：把散落的脚本收敛成一条能复跑的链路，交付即可用。',
    bullets: [
      '工作区结构与仓库盘点，输出一仓一目录的落位方案',
      '平台门户 / 注册表 / 内核服务图的设计与实现',
      'CLI 前门与配置树挂载，统一入口而非一堆散装脚本',
      '目录索引契约、死根路径与密钥门禁接入 CI',
    ],
    deliverables: ['可运行的代码仓库', '部署与复跑脚本', '架构与设计文档', '一页式交接说明'],
    priceFrom: '¥ 12,000 起',
    sla: '按迭代排期，双周交付',
    assetKey: 'site_services_dev_01',
  },
  {
    code: 'OPS',
    title: '持续维护与值守',
    tagline: 'keep the lights on',
    summary:
      '依赖升级、故障处置、备份校验与容量观察。按周给出运行简报，每次事故留一份复盘与一条新的防复发门禁。',
    bullets: [
      '依赖与安全公告跟踪，升级前后跑回归',
      '故障分级响应（标准 / 优先 / 应急三档）',
      '数据库与密钥的备份恢复演练',
      '月度运行简报：稳定性、债务与建议清单',
    ],
    deliverables: ['月度运行简报', '事故复盘报告', '升级与回滚记录', '备份恢复演练报告'],
    priceFrom: '¥ 3,800 / 月 起',
    sla: '优先响应 4 小时，应急 30 分钟',
    assetKey: 'site_services_ops_01',
  },
  {
    code: 'GOV',
    title: '门禁建设与治理陪跑',
    tagline: 'make the rules executable',
    summary:
      '把团队约定写成可执行的门禁：路径、密钥、文档索引、事实源时点。基线棘轮只许收紧，红了就拦住，不靠人自觉。',
    bullets: [
      '铁律与协作流程成文（SPEC 编号体系）',
      '门禁脚本开发与既有 CI 接入',
      '事实源台账与失效条款机制',
      '两态协作（在场 / 自主）权限矩阵与放行口径',
    ],
    deliverables: ['门禁脚本与配置', '事实源台账模板', '放行与回滚 runbook', '陪跑期答疑记录'],
    priceFrom: '¥ 6,500 起',
    sla: '陪跑 4 周，含事故复盘',
    assetKey: 'site_services_gov_01',
  },
];

const PROCESS = [
  { title: '对齐', text: '一次结构化的需求对话：目标、现状、约束、时间点，问题不超过四个且带推荐项。' },
  { title: '体检', text: '跑一遍现状：结构、门禁覆盖、文档索引、密钥面，输出可执行清单。' },
  { title: '方案', text: '给出路径与取舍，明确不做什么；方案确认后才进入实现。' },
  { title: '实现', text: '小步提交、每步可跑；门禁全程在线，红了先修再继续。' },
  { title: '交接', text: '文档、脚本、复盘一并交付；交接后仍可按需转入维护档位。' },
];

const TIMELINE = [
  { year: '2026-06', title: '初始提交与标语落地', text: '「do it better than future」写进 README，治理取向就此定调：先落地、先留账，再迭代改好。' },
  { year: '2026-08', title: '文档枢纽迁入', text: 'docs/ 成为唯一文档入口，铁律、流程与事故流水开始分册沉淀。' },
  { year: '2026-09', title: '铁律大修与分册', text: '661 行混装文档拆成 SPEC 系列，规则正文与路由页分离，引用一律带限定词。' },
  { year: '2026-10', title: '平台整仓并入', text: '门户、内核、注册表与黄金值门禁合入主仓，治理内核立档，CLI 前门上线。' },
  { year: '2026-10', title: '可安装包分发', text: '通用能力装成可消费品（allin-governance），一份源码两处消费，不做复制。' },
  { year: '2026-11', title: '官网与加密存储', text: '门面站升级为可登录的服务站点：内容、图片、附件全部加密入库，密钥独立管理。' },
];

const PRINCIPLES = [
  { title: '先共识，后动手', text: '需求问清、计划过目再开工。一次把话说透，胜过三次返工。' },
  { title: '可执行优先于可描述', text: '约定要落成门禁与脚本；写不进代码的规矩，迟早会被绕过。' },
  { title: '不迷信事实源', text: '快照会过期、权威会漂移。动手前现场实测，冲突时两边核实并注明。' },
  { title: '资产与历史只增不减', text: '删除与归档前过冗余三查；推倒重来只用于结构层，内容层一律保全。' },
];

const FAQ = [
  { q: '可以先做一次小规模试点吗？', a: '可以。建议从一个仓库的体检开始（通常 1–2 个工作日），结论清楚后再决定是否进入完整服务包。' },
  { q: '我们已有 CI，会冲突吗？', a: '不会。门禁以脚本形式提供，可挂到现有流水线上；也可以只在本地与提交钩子里跑，逐步收紧。' },
  { q: '代码与数据的归属怎么算？', a: '交付物与仓库归你所有；我们保留在案例中使用抽象化描述的权利，涉及敏感信息会先征得同意。' },
  { q: '服务期间怎么沟通？', a: '默认邮件 + 工单；需要即时沟通可约定固定时段。所有结论落回工单与文档，避免口头约定。' },
  { q: '事故怎么处理？', a: '先恢复服务，再定位根因，最后补一条防复发门禁。每次事故都输出一份复盘，计入当月简报。' },
  { q: '数据存储在哪里？', a: '本站的内容、图片与附件都以 AES-256-GCM 密文存在本地数据库里，密钥独立于数据库文件管理，默认不上传任何第三方。' },
];

const TICKETS = [
  { code: 'T-2026-018', subject: '注册表体检与生命周期标注', owner: '治理组', status: 'done', updated: '2026-10-28', note: '141 个本地克隆全部标注完成' },
  { code: 'T-2026-021', subject: '门禁 g03 密钥面补扫', owner: '安全组', status: 'doing', updated: '2026-11-01', note: '新增机器本地明文凭据检查' },
  { code: 'T-2026-023', subject: '官网内容加密改造', owner: '平台组', status: 'doing', updated: '2026-11-01', note: '图片与附件入库，public/ 清空业务文件' },
  { code: 'T-2026-025', subject: '月度运行简报模板', owner: '运维组', status: 'todo', updated: '2026-11-02', note: '待客户确认字段' },
];

const PROFILE = {
  email: 'service@allin.local',
  gitee: 'https://gitee.com/siwpan/allin',
  github: 'https://github.com/siwpan95/allin',
  hours: '工作日 10:00–19:00（应急档 7×24）',
  responseTime: '1 个工作日内首次响应',
};

const MEMBER_FILE_CONTENT = [
  '# 客户交付清单（示例文件）',
  '',
  '> 本文件从数据库中解密后投递，服务端 public/ 目录下不存在对应文件。',
  '',
  '## 交付物',
  '1. 可运行的仓库与部署脚本',
  '2. 门禁配置与 CI 接入说明',
  '3. 事实源台账模板',
  '4. 交接文档与事故复盘模板',
  '',
  '## 验收口径',
  '- 门禁全绿（`npm run check`）',
  '- 文档索引契约通过（`npm run check:docs`）',
  '- 备份恢复演练有报告',
].join('\n');

function seedImages() {
  if (!fs.existsSync(ASSETS_SRC)) {
    console.log('  [跳过] 未找到 assets-src/ 目录');
    return 0;
  }
  const files = fs.readdirSync(ASSETS_SRC).filter((f) => /\.(jpg|jpeg|png|webp|gif|svg)$/i.test(f));
  let n = 0;
  for (const file of files) {
    const buffer = fs.readFileSync(path.join(ASSETS_SRC, file));
    const assetKey = file.replace(/\.[^.]+$/, '');
    const meta = IMAGE_META[assetKey] || { scope: 'public', title: assetKey, alt: assetKey };
    assetService.putAsset({
      assetKey,
      buffer,
      mime: assetService.detectMime(buffer, file),
      isPublic: meta.scope === 'public',
      meta: { ...meta, sourceFile: file },
    });
    n += 1;
    console.log(`  [图片] ${file} → ${assetKey}（${(buffer.length / 1024).toFixed(0)} KB，加密入库）`);
  }
  return n;
}

function seedMemberFile() {
  const buffer = Buffer.from(MEMBER_FILE_CONTENT, 'utf8');
  assetService.putAsset({
    assetKey: 'member_delivery_checklist_01',
    buffer,
    mime: 'text/markdown; charset=utf-8',
    isPublic: false,
    meta: { scope: 'member', title: '客户交付清单（示例）', note: '登录用户可下载，验证权限校验链路' },
  });
  console.log('  [文件] 会员专区示例文件加密入库');
}

function seedContent() {
  CAPABILITIES.forEach((item, i) =>
    contentService.putDoc({ docKey: `capability-${String(i + 1).padStart(2, '0')}`, kind: 'capability', data: item, status: 'published' })
  );
  SERVICES.forEach((item, i) =>
    contentService.putDoc({ docKey: `service-${String(i + 1).padStart(2, '0')}`, kind: 'service', data: item, status: 'published' })
  );
  PROCESS.forEach((item, i) =>
    contentService.putDoc({ docKey: `process-${String(i + 1).padStart(2, '0')}`, kind: 'process', data: item, status: 'published' })
  );
  TIMELINE.forEach((item, i) =>
    contentService.putDoc({ docKey: `timeline-${String(i + 1).padStart(2, '0')}`, kind: 'timeline', data: item, status: 'published' })
  );
  PRINCIPLES.forEach((item, i) =>
    contentService.putDoc({ docKey: `principle-${String(i + 1).padStart(2, '0')}`, kind: 'principle', data: item, status: 'published' })
  );
  FAQ.forEach((item, i) =>
    contentService.putDoc({ docKey: `faq-${String(i + 1).padStart(2, '0')}`, kind: 'faq', data: item, status: 'published' })
  );
  TICKETS.forEach((item, i) =>
    contentService.putDoc({ docKey: `ticket-${String(i + 1).padStart(2, '0')}`, kind: 'ticket', data: item, status: 'published' })
  );
  contentService.putDoc({ docKey: 'site-profile', kind: 'setting', data: PROFILE, status: 'published' });
  console.log(
    `  [文案] ${CAPABILITIES.length + SERVICES.length + PROCESS.length + TIMELINE.length + PRINCIPLES.length + FAQ.length + TICKETS.length + 1} 条加密文档写入`
  );
}

/**
 * 生成一定满足 validatePassword（字母 + 数字）的随机口令。
 * 原实现 randomBytes(9).toString('base64url').slice(0, 14) 有约 12.8% 概率
 * 不含数字（base64url 里数字只占 10/64），createUser 会直接抛错、seed 半途失败。
 * 用无易混淆字符的字母表，先各放一个字母和一个数字再洗牌，确定性满足约束。
 */
function randomPassword() {
  const letters = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  const digits = '23456789';
  const all = letters + digits;
  const pick = (alphabet) => alphabet[crypto.randomInt(alphabet.length)];
  const chars = [pick(letters), pick(digits)];
  for (let i = 0; i < 14; i += 1) chars.push(pick(all));
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = crypto.randomInt(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join('');
}

/** 读回上次 seed 写下的真实口令（账号文件与 DB 同在 data/，同生命周期）。 */
function previousPasswords() {
  const accountsFile = path.join(config.dataDir, 'seed-accounts.json');
  try {
    const data = JSON.parse(fs.readFileSync(accountsFile, 'utf8'));
    const out = {};
    for (const a of data.accounts || []) {
      if (a && a.email && typeof a.password === 'string') out[a.email] = a.password;
    }
    return out;
  } catch {
    return {};
  }
}

function ensureUser(email, displayName, role, envVar, previous) {
  const existing = userService.findUserByEmail(email);
  const envPassword = process.env[envVar];

  if (existing) {
    // 只有「确实能解开库内 hash」的口令才写进账号文件。原实现把 env 值或
    // 占位串 `(已存在，沿用原口令)` 直接写出，与库内 hash 不一致 ⇒ 登录 302。
    // 候选顺序：显式 env > 上次账本；都不能复用时写 null + 说明，绝不写假口令。
    const candidates = [envPassword, previous[email]].filter(Boolean);
    const usable = candidates.find((p) => userService.verifyPassword(existing, p));
    if (usable) {
      const note = envPassword && usable !== envPassword
        ? `${envVar} 与库内口令不一致，已忽略；文件写的是可登录的既有口令`
        : undefined;
      return { email, password: usable, reused: true, id: existing.id, ...(note ? { note } : {}) };
    }
    return {
      email,
      password: null,
      reused: true,
      id: existing.id,
      note: `账号已存在但口令不可复用（账号文件缺失或已损坏）；本脚本不自动重置已有账号，请删除 data/ 下数据库后重跑 seed`,
    };
  }

  const password = envPassword || randomPassword();
  const pwdError = userService.validatePassword(password);
  if (pwdError) throw new Error(`${envVar} 不合法：${pwdError}`);
  const created = userService.createUser({ email, password, displayName, role });
  return { email, password, reused: false, id: created.id };
}

function main() {
  const db = getDb();
  console.log('\n  allin 官网 · 内容种子（全部加密写入）');
  console.log('  ------------------------------------------');

  const imageCount = seedImages();
  seedMemberFile();
  seedContent();

  const previous = previousPasswords();
  const admin = ensureUser('admin@allin.local', '站点管理员', 'admin', 'ADMIN_SEED_PASSWORD', previous);
  const member = ensureUser('demo@allin.local', '演示用户', 'member', 'MEMBER_SEED_PASSWORD', previous);

  // 口令只写进被忽略的运行时目录，绝不进版本库
  const accountsFile = path.join(config.dataDir, 'seed-accounts.json');
  fs.mkdirSync(config.dataDir, { recursive: true });
  fs.writeFileSync(
    accountsFile,
    JSON.stringify({ generatedAt: new Date().toISOString(), accounts: [admin, member] }, null, 2),
    { mode: 0o600 }
  );

  const assets = assetService.countAssets();
  console.log('  ------------------------------------------');
  console.log(`  资源条目    ${assets.n}（${(assets.bytes / 1024).toFixed(0)} KB 明文，库内为密文）`);
  console.log(`  配图数量    ${imageCount}`);
  console.log(`  账号        ${admin.email}（admin） / ${member.email}（member）`);
  console.log(`  账号文件    ${path.relative(config.root, accountsFile)}（已被 .gitignore 忽略）`);
  // 口令默认不打印到控制台（避免共享终端 / CI 日志泄漏）；需要时可设 SEED_SHOW_PASSWORDS=1
  if (!admin.reused && process.env.SEED_SHOW_PASSWORDS) console.log(`  管理员口令  ${admin.password}`);
  if (!member.reused && process.env.SEED_SHOW_PASSWORDS) console.log(`  演示口令    ${member.password}`);
  if ((!admin.reused || !member.reused) && !process.env.SEED_SHOW_PASSWORDS) {
    console.log(`  账号口令    见 ${path.relative(config.root, accountsFile)}（权限 0600，默认不打印明文；设 SEED_SHOW_PASSWORDS=1 可打印）`);
  }
  console.log('\n  下一步：npm start → 打开 ' + config.baseUrl + '\n');
  db.close();
}

// 直接执行（npm run seed）时跑 main()；被 require 时不产生任何 DB 副作用，
// 便于回归测试直接调用 randomPassword / previousPasswords / ensureUser。
if (require.main === module) main();

module.exports = { randomPassword, previousPasswords, ensureUser };
