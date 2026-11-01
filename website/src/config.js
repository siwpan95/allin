'use strict';

/**
 * 站点配置：.env（可选）→ 环境变量 → 内置默认值。
 *
 * 设计口径：
 *   - 不引入 dotenv 依赖，自带一个 20 行的 KEY=VALUE 解析器，保持依赖面最小；
 *   - 已存在的环境变量优先（容器/CI 注入的值不被 .env 覆盖）；
 *   - 路径一律相对项目根解析，源码中不出现机器绝对路径。
 */

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');

function parseEnvFile(file) {
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch {
    return; // 没有 .env 是正常部署姿势，全部走默认值
  }
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    const quoted =
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"));
    if (quoted && value.length >= 2) value = value.slice(1, -1);
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

parseEnvFile(path.join(ROOT, '.env'));

const port = Number.parseInt(process.env.PORT || '9042', 10);
const ttlHours = Number.parseInt(process.env.SESSION_TTL_HOURS || '72', 10);

const config = {
  root: ROOT,
  port: Number.isFinite(port) ? port : 9042,
  baseUrl: process.env.SITE_BASE_URL || `http://localhost:${Number.isFinite(port) ? port : 9042}`,
  dbPath: path.resolve(ROOT, process.env.DB_PATH || './data/site.db'),
  keyDir: path.resolve(ROOT, process.env.KEY_DIR || './data/keys'),
  dataDir: path.resolve(ROOT, path.dirname(process.env.DB_PATH || './data/site.db')),
  masterKeyBase64: (process.env.SITE_MASTER_KEY_BASE64 || '').trim(),
  session: {
    cookieName: process.env.SESSION_COOKIE_NAME || 'allin_sid',
    ttlHours: Number.isFinite(ttlHours) ? ttlHours : 72,
    secure: String(process.env.COOKIE_SECURE || 'false').toLowerCase() === 'true',
  },
  upload: {
    maxBytes: Number.parseInt(process.env.MAX_UPLOAD_MB || '5', 10) * 1024 * 1024,
  },
  site: {
    name: 'ALLIN LAB',
    tagline: 'allin 项目的开发与维护服务',
    motto: 'do it better than future',
    email: 'service@allin.local',
    gitee: 'https://gitee.com/siwpan/allin',
    github: 'https://github.com/siwpan95/allin',
  },
  nav: [
    { href: '/', label: '首页', key: 'home' },
    { href: '/services', label: '产品服务', key: 'services' },
    { href: '/about', label: '关于我们', key: 'about' },
    { href: '/contact', label: '联系我们', key: 'contact' },
  ],
};

module.exports = config;
