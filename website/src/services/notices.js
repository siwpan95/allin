'use strict';

/** 友好提示文案表：URL 上只传 code，页面按 code 取文案，不在地址栏里塞中文。 */

const NOTICES = Object.freeze({
  login_required: { kind: 'warn', text: '这个页面需要先登录，登录后会直接回到刚才的位置。' },
  login_needed_file: { kind: 'warn', text: '该文件为登录用户专享，请先登录再下载。' },
  admin_required: { kind: 'warn', text: '这个页面仅管理员可访问，已记录一次越权尝试。' },
  session_expired: { kind: 'warn', text: '会话已过期，请重新登录。' },
  logged_out: { kind: 'ok', text: '已安全退出，会话记录已从服务端销毁。' },
  registered: { kind: 'ok', text: '注册成功，已为你自动登录。' },
  welcome_back: { kind: 'ok', text: '欢迎回来，会话已续期。' },
  contact_sent: { kind: 'ok', text: '留言已提交（内容加密入库），我们会尽快回复。' },
  csrf_failed: { kind: 'error', text: '表单令牌校验失败，请刷新页面后重试。' },
  asset_missing: { kind: 'error', text: '请求的资源不存在或已被移除。' },
  asset_broken: { kind: 'error', text: '资源解密失败（数据可能已损坏），已记录安全日志。' },
  rate_limited: { kind: 'error', text: '尝试过于频繁，请稍后再试。' },
  governance_degraded: { kind: 'warn', text: '治理平台（portal）当前离线，看板处于降级状态；站点其他功能不受影响。' },
  governance_action_fail: { kind: 'error', text: '治理操作未成功，原因见页面提示；该次尝试已记入审计流水。' },
});

function notice(code) {
  return code && NOTICES[code] ? { code, ...NOTICES[code] } : null;
}

module.exports = { notice, NOTICES };
