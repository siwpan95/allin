/* allin 官网 · 前端交互（无框架、无依赖）
   只做三件事：移动端导航、表单可用性增强、提示条自动收起。 */

(function () {
  'use strict';

  // 1) 移动端导航抽屉
  var toggle = document.getElementById('nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    links.addEventListener('click', function (event) {
      if (event.target.tagName === 'A' && window.innerWidth <= 860) {
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // 2) 提示条：10 秒后淡出，不打扰阅读
  var notices = document.querySelectorAll('.notice[data-auto-dismiss]');
  Array.prototype.forEach.call(notices, function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity .5s ease';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 500);
    }, 10000);
  });

  // 3) 表单：字数计数 + 提交按钮防重复
  var counted = document.querySelector('textarea[data-count]');
  if (counted) {
    var out = document.getElementById(counted.getAttribute('data-count'));
    var sync = function () {
      if (out) out.textContent = counted.value.length + ' / 4000';
    };
    counted.addEventListener('input', sync);
    sync();
  }

  var forms = document.querySelectorAll('form[data-guard]');
  Array.prototype.forEach.call(forms, function (form) {
    form.addEventListener('submit', function () {
      var btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.textContent = '提交中…';
      }
    });
  });
})();
