'use strict';

/**
 * 站内回跳白名单：杜绝 open redirect。
 *
 * 2026-11-04 工程审查 P1：原实现只拦 `//` 开头，放行 `/\evil.com`；
 * Express 4 的 res.redirect 不转义反斜杠，浏览器按 WHATWG 规范把
 * `Location: /\evil.com` 归一化成 `//evil.com` ⇒ 跳出本站（端到端复现）。
 * 现在用与浏览器同一套 WHATWG URL 解析，以 origin 相等为唯一放行条件。
 *
 * 抽成独立纯函数模块：只依赖 config（读 .env），零 DB / keystore / express
 * 副作用，便于单测逐一覆盖攻击向量，不必 require 整条 router 依赖链。
 */

const config = require('./config');

const BASE_ORIGIN = new URL(config.baseUrl).origin;

/** 只允许站内相对路径回跳，其余一律收敛到 /member。 */
function safeNext(value) {
  const raw = String(value || '');
  if (!raw) return '/member';
  // 反斜杠 / 字面控制字符（含 CRLF 头注入）一律拒绝，不交给解析器归一化。
  if (/[\\\u0000-\u001f\u007f]/.test(raw)) return '/member';
  let url;
  try {
    url = new URL(raw, config.baseUrl);
  } catch {
    return '/member';
  }
  if (url.origin !== BASE_ORIGIN) return '/member';
  // 只回传站内相对路径，绝不把 scheme / host / userinfo 带进 Location 或表单隐藏域。
  return `${url.pathname}${url.search}${url.hash}` || '/member';
}

/**
 * 给回跳路径追加 notice 参数。
 * 两个坑：① query 已存在时不能再拼一个 `?`；② 路径带 #hash 时 notice
 * 必须插到 hash 之前，否则会落进 fragment，服务端永远收不到。
 */
function withNotice(path, notice) {
  const hashIdx = path.indexOf('#');
  const before = hashIdx >= 0 ? path.slice(0, hashIdx) : path;
  const hash = hashIdx >= 0 ? path.slice(hashIdx) : '';
  const sep = before.includes('?') ? '&' : '?';
  return `${before}${sep}notice=${encodeURIComponent(notice)}${hash}`;
}

module.exports = { safeNext, withNotice, BASE_ORIGIN };
