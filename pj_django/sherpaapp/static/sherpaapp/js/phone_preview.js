/* PC에서 폰 화면 미리보기 — 모든 화면 공통 (🟧 11/18)
 *
 * 전에는 홈(index.html)에만 [💻 PC | 📱 폰] 버튼이 있었고, 폰 틀 안은 항상 홈부터 열렸다.
 * 이제 어느 화면에서든 버튼이 보이고, [📱 폰]을 누르면 **지금 보고 있는 화면**이 폰 크기 틀 안에 바로 뜬다.
 *   - 틀 안에서 다른 화면으로 옮긴 뒤 [💻 PC]를 누르면 PC 화면도 그 화면으로 옮겨 간다
 *   - 폰 모드는 이 탭에서 유지된다 (다른 화면으로 가도 폰 틀로 열림). 기기 종류는 브라우저에 기억
 *   - 진짜 폰·좁은 화면(900px 이하)과 폰 틀 안에서는 버튼을 만들지 않는다
 * 붙는 곳: sherpaapp/i18n_middleware.py 의 head_snippet (css/phone_preview.css 와 같이)
 * 원래 코드: 🟦 11/11 index.html (PC/폰 버튼) + 🟧 11/12 기기 종류·카메라 자리
 */
(function () {
  'use strict';

  if (window.self !== window.top) return;            // 폰 틀 안: 틀 안에 또 틀이 생기지 않게
  if (window.TRIPA_PHONE_PREVIEW) return;            // 두 번 붙지 않게
  window.TRIPA_PHONE_PREVIEW = true;

  // w·h: 그 기기 화면의 CSS 픽셀 크기(대략값) · cam: 카메라 모양(island 알약 / punch 점 / none 없음)
  // top·bottom: 카메라·상태 표시줄, 홈 막대가 차지하는 높이 → 틀 안 화면의 --tp-safe-top/bottom (css/safe_area.css)
  var DEVICES = [
    { id: 's24',    group: '휴대폰', name: '갤럭시 S24',            w: 360,  h: 780,  cam: 'punch',  top: 30, bottom: 16 },
    { id: 'ultra',  group: '휴대폰', name: '갤럭시 S24 울트라',     w: 384,  h: 824,  cam: 'punch',  top: 30, bottom: 16 },
    { id: 'se',     group: '휴대폰', name: '아이폰 SE',             w: 375,  h: 667,  cam: 'none',   top: 20, bottom: 0 },
    { id: 'iphone', group: '휴대폰', name: '아이폰 15',             w: 393,  h: 852,  cam: 'island', top: 47, bottom: 34 },
    { id: 'max',    group: '휴대폰', name: '아이폰 15 Pro Max',     w: 430,  h: 932,  cam: 'island', top: 47, bottom: 34 },
    { id: 'flip',   group: '폴더블', name: '갤럭시 Z 플립',         w: 412,  h: 1006, cam: 'punch',  top: 30, bottom: 16 },
    { id: 'foldc',  group: '폴더블', name: '갤럭시 Z 폴드 (접음)',  w: 344,  h: 882,  cam: 'punch',  top: 30, bottom: 16 },
    { id: 'foldo',  group: '폴더블', name: '갤럭시 Z 폴드 (펼침)',  w: 690,  h: 830,  cam: 'punch',  tablet: true, top: 30, bottom: 16 },
    { id: 'mini',   group: '태블릿', name: '아이패드 미니',         w: 744,  h: 1133, cam: 'none',   tablet: true, top: 0, bottom: 0 },
    { id: 'air',    group: '태블릿', name: '아이패드 에어',         w: 820,  h: 1180, cam: 'none',   tablet: true, top: 0, bottom: 0 },
    { id: 'pro',    group: '태블릿', name: '아이패드 프로 12.9',    w: 1024, h: 1366, cam: 'none',   tablet: true, top: 0, bottom: 0 },
    { id: 'tabs9',  group: '태블릿', name: '갤럭시 탭 S9',          w: 800,  h: 1280, cam: 'none',   tablet: true, top: 0, bottom: 0 }
  ];

  function make(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text) el.textContent = text;
    return el;
  }

  function start() {
    if (document.getElementById('viewToggle')) return;    // 옛 홈 템플릿이 이미 그렸으면 그대로 둠

    // ---- 버튼 + 기기 고르기 ----
    var toggle = make('div', 'view-toggle');
    toggle.id = 'viewToggle';
    toggle.setAttribute('role', 'group');
    toggle.setAttribute('aria-label', '화면 모드');
    var pcBtn = make('button', 'is-on', '💻 PC');
    pcBtn.type = 'button';
    pcBtn.setAttribute('data-view', 'pc');
    var phoneBtn = make('button', '', '📱 폰');
    phoneBtn.type = 'button';
    phoneBtn.setAttribute('data-view', 'phone');
    var select = make('select');
    select.id = 'phoneDevice';
    select.setAttribute('aria-label', '기기 크기');
    select.setAttribute('data-no-fit', '');
    select.hidden = true;
    toggle.appendChild(pcBtn);
    toggle.appendChild(phoneBtn);
    toggle.appendChild(select);

    // ---- 폰 틀 ----
    var preview = make('div', 'phone-preview');
    preview.id = 'phonePreview';
    preview.hidden = true;
    var box = make('div', 'phone-preview__frame');
    var notch = make('span', 'phone-preview__notch');
    notch.setAttribute('aria-hidden', 'true');
    var frame = make('iframe');
    frame.id = 'phoneFrame';
    frame.title = '폰 화면 미리보기';
    box.appendChild(notch);
    box.appendChild(frame);
    var hint = make('p', 'phone-preview__hint');
    var hintSize = make('span');
    hintSize.id = 'phoneHintSize';
    hint.appendChild(hintSize);
    hint.appendChild(document.createTextNode(' · 안에서 눌러 볼 수 있어요 · Esc 또는 바깥을 누르면 닫혀요'));
    preview.appendChild(box);
    preview.appendChild(hint);

    document.body.appendChild(toggle);
    document.body.appendChild(preview);

    ['휴대폰', '폴더블', '태블릿'].forEach(function (groupName) {
      var group = document.createElement('optgroup');
      group.label = groupName;
      DEVICES.forEach(function (d) {
        if (d.group !== groupName) return;
        var option = document.createElement('option');
        option.value = d.id;
        option.textContent = d.name + ' (' + d.w + '×' + d.h + ')';
        group.appendChild(option);
      });
      select.appendChild(group);
    });
    try { select.value = localStorage.getItem('tripa_device') || 'iphone'; } catch (e) { select.value = 'iphone'; }
    if (!select.value) select.value = 'iphone';

    function device() {
      for (var i = 0; i < DEVICES.length; i++) if (DEVICES[i].id === select.value) return DEVICES[i];
      return DEVICES[3];
    }

    // 틀 안 화면에 이 기기의 카메라·홈 막대 높이를 알려 줌
    function markSafe() {
      try {
        var root = frame.contentDocument && frame.contentDocument.documentElement;
        if (!root) return;
        var d = device();
        root.style.setProperty('--tp-safe-top', d.top + 'px');
        root.style.setProperty('--tp-safe-bottom', d.bottom + 'px');
      } catch (e) { /* 다른 사이트(카카오맵 등)로 나가면 못 넣음 */ }
    }

    // 고른 기기 크기로 틀을 맞추고, 창보다 크면 통째로 줄여서 보여 줌 (안의 화면 폭은 기기 그대로)
    function fit() {
      var d = device();
      frame.style.width = d.w + 'px';
      frame.style.height = d.h + 'px';
      box.setAttribute('data-cam', d.cam);
      box.classList.toggle('is-tablet', !!d.tablet);
      var scale = Math.min(1, (window.innerHeight - 110) / (d.h + 24), (window.innerWidth - 60) / (d.w + 24));
      box.style.transform = 'scale(' + scale + ')';
      hintSize.textContent = d.name + ' 화면(' + d.w + '×' + d.h + ')이에요';
      markSafe();
    }

    // 틀 안에서 지금 보고 있는 주소 (같은 사이트일 때만 읽힘)
    function innerUrl() {
      try {
        var loc = frame.contentWindow && frame.contentWindow.location;
        if (loc && loc.href && loc.href !== 'about:blank' && loc.origin === window.location.origin) return loc.href;
      } catch (e) { /* 다른 사이트 */ }
      return '';
    }

    function setView(view, byUser) {
      var phone = view === 'phone';
      try { sessionStorage.setItem('tripa_view', view); } catch (e) { /* 저장 못 해도 동작 */ }

      // [💻 PC]: 틀 안에서 다른 화면으로 옮겨 갔으면 PC 화면도 거기로
      if (!phone && byUser) {
        var inside = innerUrl();
        if (inside && inside !== window.location.href) {
          window.location.href = inside;
          return;
        }
      }

      preview.hidden = !phone;
      select.hidden = !phone;
      if (phone) {
        fit();
        // 지금 보고 있는 화면을 그대로 폰 틀에 (처음 열 때, 또는 PC 쪽 주소가 바뀌었을 때)
        if (!frame.getAttribute('src')) frame.src = window.location.href;
      }
      document.body.classList.toggle('is-phone-preview', phone);
      var buttons = toggle.querySelectorAll('button');
      for (var i = 0; i < buttons.length; i++) {
        var on = buttons[i].getAttribute('data-view') === view;
        buttons[i].classList.toggle('is-on', on);
        buttons[i].setAttribute('aria-pressed', on ? 'true' : 'false');
      }
    }

    select.addEventListener('change', function () {
      try { localStorage.setItem('tripa_device', select.value); } catch (e) { /* 저장 못 해도 동작 */ }
      fit();
    });
    window.addEventListener('resize', function () { if (!preview.hidden) fit(); });

    // 틀 안 페이지가 열릴 때마다: 카메라 자리 알려 주기 + 스크롤바 숨기기 (폰처럼. 휠·끌기 스크롤은 그대로)
    var HIDE_BARS = 'html{scrollbar-width:none;-ms-overflow-style:none}'
      + 'html::-webkit-scrollbar,body::-webkit-scrollbar{display:none;width:0;height:0}';
    frame.addEventListener('load', function () {
      markSafe();
      try {
        var doc = frame.contentDocument;
        if (!doc || doc.getElementById('tripaPhoneBars')) return;
        var style = doc.createElement('style');
        style.id = 'tripaPhoneBars';
        style.textContent = HIDE_BARS;
        doc.head.appendChild(style);
      } catch (e) { /* 다른 사이트로 나가면 못 넣음 → 그대로 둠 */ }
    });

    toggle.addEventListener('click', function (event) {
      var btn = event.target.closest ? event.target.closest('button[data-view]') : null;
      if (btn) setView(btn.getAttribute('data-view'), true);
    });

    // 어두운 바깥을 누르거나 Esc → PC로
    preview.addEventListener('click', function (event) {
      if (event.target === preview) setView('pc', true);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !preview.hidden) setView('pc', true);
    });

    // 이 탭에서 폰 모드를 골라 두었으면 어느 화면을 열어도 폰 틀로
    var saved = '';
    try { saved = sessionStorage.getItem('tripa_view') || ''; } catch (e) { /* 무시 */ }
    if (saved === 'phone' && window.matchMedia('(min-width: 901px)').matches) setView('phone', false);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
