'use strict';

/**
 * allin 官网 · 服务入口。
 *
 * 启动顺序：配置 → 数据库（自动建表 + 密钥环就绪）→ 中间件 → 路由 → 监听。
 * 无外网依赖、无原生编译依赖，`npm install && npm start` 即可本地跑起来。
 */

const path = require('node:path');
const express = require('express');

const config = require('./config');
const { getDb } = require('./db');
const userService = require('./services/userService');
const { notice } = require('./services/notices');
const { securityHeaders } = require('./middleware/security');
const { attachUser } = require('./middleware/auth');

const pages = require('./routes/pages');
const authRoutes = require('./routes/auth');
const memberRoutes = require('./routes/member');
const adminRoutes = require('./routes/admin');
const governanceRoutes = require('./routes/governance');
const contactRoutes = require('./routes/contact');
const assetRoutes = require('./routes/assets');

function createApp() {
  const app = express();
  app.disable('x-powered-by');
  app.set('view engine', 'ejs');
  app.set('views', path.join(__dirname, 'views'));
  app.set('trust proxy', false);

  app.use(express.urlencoded({ extended: false, limit: '1mb' }));
  app.use(express.json({ limit: '1mb' }));
  app.use(securityHeaders);
  app.use(attachUser);

  app.use((req, res, next) => {
    res.locals.site = config.site;
    res.locals.nav = config.nav;
    res.locals.pageKey = res.locals.pageKey || '';
    res.locals.notice = notice(req.query.notice);
    res.locals.currentYear = new Date().getFullYear();
    // 图片/文件一律走 /media/<key>，由数据库解密后投递
    res.locals.assetUrl = (key) => `/media/${encodeURIComponent(key)}`;
    next();
  });

  // public/ 只放 css/js 这类静态资产；业务图片与用户文件全部在数据库里
  app.use(
    express.static(path.join(__dirname, 'public'), {
      index: false,
      maxAge: '1h',
      setHeaders: (res, filePath) => {
        if (filePath.endsWith('.css') || filePath.endsWith('.js')) {
          res.setHeader('Cache-Control', 'public, max-age=3600');
        }
      },
    })
  );

  app.use('/media', assetRoutes);
  app.use('/', pages);
  app.use('/', authRoutes);
  app.use('/', memberRoutes);
  app.use('/', adminRoutes);
  app.use('/', governanceRoutes);
  app.use('/', contactRoutes);

  app.get('/healthz', (req, res) => {
    const db = getDb();
    const row = db.prepare('SELECT COUNT(*) AS n FROM assets').get();
    res.json({ ok: true, assets: row.n, time: new Date().toISOString() });
  });

  app.use((req, res) => {
    res.status(404).render('error', {
      title: '页面不存在',
      status: 404,
      message: '这个坐标上没有页面。',
      hint: '可以从顶部导航回到首页。',
      pageKey: '',
    });
  });

  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    console.error('[error]', err);
    res.status(500).render('error', {
      title: '服务出错了',
      status: 500,
      message: '请求没能正常完成，已记录日志。',
      hint: process.env.NODE_ENV === 'development' ? String(err.message || err) : '请稍后重试，或联系我们反馈。',
      pageKey: '',
    });
  });

  return app;
}

function start() {
  getDb(); // 触发建表 + 密钥环初始化
  const removed = userService.purgeExpiredSessions();
  const app = createApp();
  const server = app.listen(config.port, () => {
    console.log(`\n  ALLIN 官网已启动`);
    console.log(`  地址      ${config.baseUrl}`);
    console.log(`  数据库    ${config.dbPath}`);
    console.log(`  密钥目录  ${config.keyDir}`);
    console.log(`  清理会话  ${removed} 条过期会话\n`);
  });

  const shutdown = () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 3000).unref();
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
  return server;
}

if (require.main === module) start();

module.exports = { createApp, start };
