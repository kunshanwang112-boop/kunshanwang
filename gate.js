/* 访问门禁：chuping/fushen/admin 页面需密码校验（本会话有效） */
(function () {
  var KEY = 'tg_gate_ok';
  var PASS_B64 = 'MTAyNw==';
  var READONLY = /chuping\.html|fushen\.html/.test(location.href);
  function passOk() { try { return sessionStorage.getItem(KEY) === '1'; } catch (e) { return false; } }
  function hideMain() { var w = document.querySelector('.wrap'); if (w) w.style.display = 'none'; }
  function showMain() { var w = document.querySelector('.wrap'); if (w) w.style.display = ''; }
  function applyReadonly() {
    var w = document.querySelector('.wrap');
    if (!w) return;
    var banner = document.createElement('div');
    banner.style.cssText = 'background:#fdf2f2;border:2px solid #c00000;border-radius:10px;color:#c00000;font-size:14px;padding:12px 16px;margin-bottom:16px;font-weight:600';
    banner.textContent = '该轮评审已结束：评分入口已关闭，页面仅供查阅，提交功能已停用。';
    w.insertBefore(banner, w.firstChild);
    document.querySelectorAll('.submit-btn,.save-btn').forEach(function (b) {
      b.disabled = true; b.style.opacity = .5; b.title = '评审已结束，提交已停用';
    });
    var j = document.getElementById('judge'); if (j) j.readOnly = true;
    var bar = document.getElementById('filled');
    var cnt = document.querySelector('.bar .count');
    if (cnt) cnt.textContent = '评审已结束 · 表单只读查阅';
  }
  function openGate() {
    try { sessionStorage.setItem(KEY, '1'); } catch (e) {}
    var g = document.getElementById('tgGate'); if (g) g.remove();
    showMain();
    if (READONLY) applyReadonly();
    var pwd = document.getElementById('pwd'); if (pwd && !pwd.value) pwd.value = '1027';
  }
  function tryOpen() {
    var el = document.getElementById('tgPwd');
    var v = (el && el.value || '').trim();
    var pass;
    try { pass = atob(PASS_B64); } catch (e) { pass = ''; }
    if (v && v === pass) { openGate(); return; }
    var err = document.getElementById('tgErr');
    if (err) err.textContent = '密码不正确，请重试';
    if (el) { el.value = ''; el.focus(); }
  }
  function buildGate() {
    var st = document.createElement('style');
    st.textContent = "#tgGate{position:fixed;inset:0;background:#f4f6fb;z-index:99999;display:flex;align-items:center;justify-content:center}"
      + "#tgGate .gcard{background:#fff;border:1px solid #e3e8f0;border-radius:12px;padding:36px 28px;width:88%;max-width:360px;box-shadow:0 10px 30px rgba(0,0,0,.08);text-align:center}"
      + "#tgGate h2{font-size:18px;color:#c00000;margin-bottom:10px}"
      + "#tgGate p{font-size:13px;color:#6b7788;margin-bottom:18px;line-height:1.7}"
      + "#tgGate input{width:100%;border:2px solid #c00000;border-radius:8px;padding:11px;font-size:16px;text-align:center;letter-spacing:6px;margin-bottom:12px;box-sizing:border-box}"
      + "#tgGate .gerr{color:#c00000;font-size:12px;min-height:18px;margin-bottom:10px}"
      + "#tgGate button{background:#c00000;color:#fff;border:0;border-radius:8px;padding:12px 0;width:100%;font-size:15px;cursor:pointer;font-weight:600}";
    document.head.appendChild(st);
    var g = document.createElement('div'); g.id = 'tgGate';
    var title = READONLY ? '评分入口已关闭' : '请输入访问密码';
    var desc = READONLY ? '该轮评审已结束，二维码与链接不再开放打分。如需查阅评分表单，请输入管理密码。' : '该页面已启用访问校验，请输入管理密码进入。';
    g.innerHTML = '<div class="gcard"><h2>' + title + '</h2><p>' + desc
      + '</p><input type="password" id="tgPwd" maxlength="12" placeholder="管理密码" autocomplete="off">'
      + '<div class="gerr" id="tgErr"></div><button id="tgGo">验 证</button></div>';
    document.body.appendChild(g);
    hideMain();
    document.getElementById('tgGo').onclick = tryOpen;
    document.getElementById('tgPwd').addEventListener('keydown', function (ev) { if (ev.key === 'Enter') tryOpen(); });
    var el = document.getElementById('tgPwd'); if (el) el.focus();
  }
  if (passOk()) { openGate(); } else { buildGate(); }
})();
