'use strict';

/** 四个公开页面：首页 / 关于我们 / 产品服务 / 联系我们。文案全部来自加密文档库。 */

const express = require('express');
const content = require('../services/contentService');

const router = express.Router();

/** 解密失败的条目不进页面（已在读取时留痕），页面照常渲染而不是整页 500。 */
function ok(docs) {
  return docs.filter((d) => d.data).map((d) => ({ ...d.data, _meta: d._meta }));
}

function load(keys) {
  const out = {};
  for (const [name, kind] of Object.entries(keys)) out[name] = ok(content.listDocs(kind));
  return out;
}

router.get('/', (req, res) => {
  const { capability, service, timeline } = load({ capability: 'capability', service: 'service', timeline: 'timeline' });
  res.render('home', {
    title: '首页 · allin 项目开发与维护服务',
    pageKey: 'home',
    capabilities: capability,
    services: service,
    milestones: timeline.slice(-4),
  });
});

router.get('/about', (req, res) => {
  const { timeline, principle } = load({ timeline: 'timeline', principle: 'principle' });
  res.render('about', {
    title: '关于我们 · allin 项目开发与维护服务',
    pageKey: 'about',
    milestones: timeline,
    principles: principle,
  });
});

router.get('/services', (req, res) => {
  const { service, process, faq } = load({ service: 'service', process: 'process', faq: 'faq' });
  res.render('services', {
    title: '产品服务 · allin 项目开发与维护服务',
    pageKey: 'services',
    services: service,
    steps: process,
    faqs: faq,
  });
});

router.get('/contact', (req, res) => {
  const profile = content.getDoc('site-profile');
  const { faq } = load({ faq: 'faq' });
  res.render('contact', {
    title: '联系我们 · allin 项目开发与维护服务',
    pageKey: 'contact',
    profile: profile || {},
    faqs: faq.slice(0, 4),
    form: {},
    errors: [],
  });
});

module.exports = router;
