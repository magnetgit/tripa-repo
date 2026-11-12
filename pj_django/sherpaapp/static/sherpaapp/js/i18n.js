/* 화면 언어 바꾸기 (🟧 11/12)
 *
 * 하는 일
 *   1) 화면 오른쪽 위에 언어 버튼(한국어·English·日本語·中文)을 붙인다
 *   2) 고른 언어가 한국어가 아니면, 화면에 보이는 한글 문장을 사전에서 찾아 바꾼다
 *      - 사전: static/sherpaapp/i18n/<언어>.js  →  window.TRIPA_DICT = { "한글 문장": "번역", … }
 *      - 나중에 스크립트가 그린 글자(일정 카드·채팅 말풍선 틀·알림 창)도 MutationObserver 로 따라가며 바꾼다
 *   3) 고른 언어는 쿠키 tripa_lang 에 넣는다 (서버가 이 쿠키를 보고 사전 파일을 골라 붙이고, 챗봇 답 언어도 맞춘다)
 *
 * 문장을 찾는 순서 (한 글자 마디마다)
 *   ① 사전에 통째로 있는 문장
 *   ② 값 자리 {} 가 있는 문장: "{}박 {}일" ↔ "3박 4일"
 *   ③ 앞·뒤에 붙은 조각: "총 " + 3 + "곳" 처럼 스크립트가 이어 붙인 글자 (남는 글자에 한글이 없을 때만)
 *   ④ " · " 로 이어진 줄은 칸마다 따로
 *   ⑤ 그래도 한글이 남으면(장소 이름·주소·리뷰 본문처럼 DB·외부에서 온 글) 서버 /api/translate/ 에 모아 보내
 *      AI 번역을 받아 바꾼다. 한 번 번역한 글은 서버 표(ui_translation)와 브라우저(localStorage)에 남아서 다시 안 부른다
 *      서버가 못 하면(사용량 넘음·AI 오류) 한국어 그대로 둔다
 *
 * 번역하지 않을 곳: 태그에 data-no-i18n 을 붙인다 (채팅의 내 말풍선 .tc-msg--me, 회원 닉네임·이름은 자동으로 빠짐)
 * 이 파일과 사전은 서버(sherpaapp/i18n_middleware.py)가 모든 화면 <head> 에 자동으로 붙인다. 템플릿은 안 고쳐도 된다.
 */
(function () {
  'use strict';
  if (window.__tripaI18n) return;
  window.__tripaI18n = true;

  var LANGS = [['ko', '한국어'], ['en', 'English'], ['ja', '日本語'], ['zh', '中文']];
  var lang = window.TRIPA_LANG || 'ko';
  var dict = window.TRIPA_DICT || {};
  var KO = /[가-힣]/;
  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, CODE: 1 };

  // ---------- 언어 저장 ----------
  function setLang(code) {
    document.cookie = 'tripa_lang=' + code + ';path=/;max-age=31536000;samesite=lax';
    try { localStorage.setItem('tripa_lang', code); } catch (e) { /* 저장 못 해도 쿠키로 됨 */ }
    location.reload();
  }

  // ---------- 사전 준비 ----------
  var patterns = [];      // 값 자리 {} 가 있는 문장 → 정규식
  var byFirst = {};       // 첫 글자 → 조각 목록 (긴 것부터)
  var byLast = {};        // 끝 글자 → 조각 목록 (긴 것부터)
  var cache = Object.create(null);

  function esc(s) { return s.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&'); }

  function prepare() {
    Object.keys(dict).forEach(function (key) {
      if (key.indexOf('{}') >= 0) {
        var lit = key.replace(/\{\}/g, '');
        // 한글이 두 글자는 있어야 문장 틀로 본다 ("{}원 {}" 같은 틀이 장소 이름을 잘라 먹지 않게)
        if ((lit.match(/[가-힣]/g) || []).length < 2) return;
        try {
          patterns.push({
            re: new RegExp('^' + key.split('{}').map(esc).join('([\\s\\S]+?)') + '$'),
            out: dict[key], size: lit.length
          });
        } catch (e) { /* 정규식으로 못 만드는 문장은 건너뜀 */ }
      } else if (KO.test(key)) {
        (byFirst[key[0]] = byFirst[key[0]] || []).push(key);
        var last = key[key.length - 1];
        (byLast[last] = byLast[last] || []).push(key);
      }
    });
    patterns.sort(function (a, b) { return b.size - a.size; });
    var longFirst = function (a, b) { return b.length - a.length; };
    Object.keys(byFirst).forEach(function (k) { byFirst[k].sort(longFirst); });
    Object.keys(byLast).forEach(function (k) { byLast[k].sort(longFirst); });
  }

  // 조각을 이어 붙일 때 영어 낱말·숫자가 딱 붙으면 한 칸 띄운다 ("Total" + "3" → "Total 3")
  function join(a, b) {
    return (/[A-Za-z0-9]$/.test(a) && /^[A-Za-z0-9]/.test(b)) ? a + ' ' + b : a + b;
  }

  // ---------- 한 문장 번역 ----------
  function core(s, depth) {
    if (!KO.test(s)) return s;
    if (Object.prototype.hasOwnProperty.call(dict, s)) return dict[s];
    if (depth > 4 || s.length > 400) return null;
    var i, m;
    // ② 값 자리
    for (i = 0; i < patterns.length; i++) {
      m = patterns[i].re.exec(s);
      if (!m) continue;
      var n = 0;
      return patterns[i].out.replace(/\{\}/g, function () {
        n += 1;
        var part = m[n] || '';
        var done = translate(part, depth + 1);
        return done === null ? part : done;
      });
    }
    // ③ 앞 조각: 조각 바로 뒤가 한글이 아닐 때만 (장소 이름 '부산역'에서 '부산'만 바뀌는 일 막기)
    var list = byFirst[s[0]] || [];
    for (i = 0; i < list.length; i++) {
      var head = list[i];
      if (head.length < s.length && s.lastIndexOf(head, 0) === 0 &&
          (!KO.test(s[head.length]) || !KO.test(head[head.length - 1]))) {
        var restRaw = s.slice(head.length);
        var rest = translate(restRaw, depth + 1);
        if (rest === null && KO.test(restRaw)) continue;     // 남은 글자에 한글이 있으면 사용자가 쓴 글 → 통째로 둔다
        return join(dict[head], rest === null ? restRaw : rest);
      }
    }
    // ③ 뒤 조각: 조각 바로 앞이 한글이 아닐 때만
    list = byLast[s[s.length - 1]] || [];
    for (i = 0; i < list.length; i++) {
      var tail = list[i];
      var cut = s.length - tail.length;
      if (cut > 0 && s.indexOf(tail, cut) === cut &&
          (!KO.test(s[cut - 1]) || !KO.test(tail[0]))) {
        var frontRaw = s.slice(0, cut);
        var front = translate(frontRaw, depth + 1);
        if (front === null && KO.test(frontRaw)) continue;
        return join(front === null ? frontRaw : front, dict[tail]);
      }
    }
    // ④ " · " 로 이어진 줄: 칸마다 따로 (못 바꾸는 칸은 그대로)
    if (s.indexOf(' · ') > 0) {
      var changed = false;
      var cells = s.split(' · ').map(function (cell) {
        var t = translate(cell, depth + 1);
        if (t !== null) changed = true;
        return t === null ? cell : t;
      });
      if (changed) return cells.join(' · ');
    }
    return null;
  }

  /** 번역한 글자를 돌려준다. 바꿀 게 없으면 null */
  function translate(raw, depth) {
    if (!raw || !KO.test(raw)) return null;
    if (!depth && raw in cache) return cache[raw];
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(raw);
    var body = m[2].replace(/\s+/g, ' ');
    var out = core(body, depth || 0);
    var result = (out === null || out === body) ? null : m[1] + out + m[3];
    if (!depth) cache[raw] = result;
    return result;
  }

  // ---------- 화면에 적용 ----------
  var done = new WeakMap();     // 글자 마디 → 우리가 넣은 글자 (다시 바꾸지 않게)

  function skipped(el) {
    for (; el && el.nodeType === 1; el = el.parentNode) {
      if (SKIP[el.tagName] || el.hasAttribute('data-no-i18n') || el.isContentEditable) return true;
      if (el.classList.contains('tc-msg--me')) return true;      // 채팅에서 내가 쓴 말풍선은 쓴 그대로
    }
    return false;
  }

  // 영어는 낱말 사이를 띄운다: 한글로는 "429,000" + "원이고" 처럼 붙어 있던 옆 글자와 붙지 않게 한 칸 넣는다
  function spaced(node, raw, out) {
    if (lang !== 'en') return out;
    var prev = node.previousSibling, next = node.nextSibling;
    if (prev && /^[A-Za-z]/.test(out) && !/^\s/.test(raw) && /[A-Za-z0-9]$/.test(prev.textContent || '')) out = ' ' + out;
    if (next && /[A-Za-z]$/.test(out) && !/\s$/.test(raw) && /^[A-Za-z0-9]/.test(next.textContent || '')) out += ' ';
    return out;
  }

  function textNode(node) {
    var value = node.nodeValue;
    if (!value || done.get(node) === value || !KO.test(value)) return;
    if (skipped(node.parentNode)) return;
    var out = translate(value);
    if (out !== null) { out = spaced(node, value, out); done.set(node, out); node.nodeValue = out; }
    // ⑤ 사전으로 다 못 바꾼 글은 서버 번역을 기다린다 (원래 한글 문장 통째로 보냄)
    if (out === null || KO.test(out)) remote(node, value, out === null ? value : out);
  }

  // ---------- ⑤ 서버 자동 번역 ----------
  var STORE = 'tripa_tr_' + lang;
  var saved = {};               // 원래 글 → 번역 (브라우저에 남겨 둠)
  var waiting = {};             // 원래 글 → 기다리는 글자 마디들
  var failed = {};              // 서버가 못 한 글 (이 화면에서는 다시 안 물음)
  var timer = null;
  try { saved = JSON.parse(localStorage.getItem(STORE) || '{}') || {}; } catch (e) { saved = {}; }

  function keep() {
    try {
      var keys = Object.keys(saved);
      if (keys.length > 3000) keys.slice(0, keys.length - 2000).forEach(function (k) { delete saved[k]; });
      localStorage.setItem(STORE, JSON.stringify(saved));
    } catch (e) { /* 저장 공간이 없으면 서버 표에서 다시 받음 */ }
  }

  function put(node, shown, text, raw) {
    if (node.nodeValue !== shown) return;      // 그사이 화면이 다른 글로 바뀜
    var m = /^(\s*)[\s\S]*?(\s*)$/.exec(raw);
    var out = m[1] + text + m[2];
    done.set(node, out);
    node.nodeValue = out;
  }

  function remote(node, raw, shown) {
    var key = raw.replace(/\s+/g, ' ').trim();
    if (key.length < 2 || key.length > 600 || failed[key]) return;
    if (Object.prototype.hasOwnProperty.call(saved, key)) { put(node, shown, saved[key], raw); return; }
    (waiting[key] = waiting[key] || []).push({ node: node, raw: raw, shown: shown });
    if (!timer) timer = setTimeout(send, 200);
  }

  function send() {
    timer = null;
    var keys = Object.keys(waiting).slice(0, 40);
    if (!keys.length) return;
    var batch = {};
    keys.forEach(function (k) { batch[k] = waiting[k]; delete waiting[k]; });
    fetch('/api/translate/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang: lang, texts: keys })
    }).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      var texts = (data && data.success && data.texts) || [];
      keys.forEach(function (k, i) {
        var text = texts[i];
        if (typeof text !== 'string' || !text) { failed[k] = true; return; }
        saved[k] = text;
        batch[k].forEach(function (w) { put(w.node, w.shown, text, w.raw); });
      });
      keep();
    }).catch(function () {
      keys.forEach(function (k) { failed[k] = true; });
    }).then(function () {
      if (Object.keys(waiting).length && !timer) timer = setTimeout(send, 50);
    });
  }

  function attrs(el) {
    var i, out;
    for (i = 0; i < ATTRS.length; i++) {
      var v = el.getAttribute(ATTRS[i]);
      if (v && KO.test(v)) {
        out = translate(v);
        if (out !== null) el.setAttribute(ATTRS[i], out);
      }
    }
    // 버튼 모양 input 의 글자
    if (el.tagName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type) && KO.test(el.value)) {
      out = translate(el.value);
      if (out !== null) el.value = out;
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { textNode(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9) return;
    if (root.nodeType === 1) {
      if (root.tagName === 'TEXTAREA') { attrs(root); return; }
      if (skipped(root)) return;
      attrs(root);
    }
    var it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
    var node;
    while ((node = it.nextNode())) {
      if (node.nodeType === 3) textNode(node);
      else if (!SKIP[node.tagName] || node.tagName === 'TEXTAREA') attrs(node);     // 글 상자는 placeholder 만
    }
  }

  function start() {
    var t = translate(document.title);
    if (t !== null) document.title = t;
    walk(document.body);
    new MutationObserver(function (list) {
      for (var i = 0; i < list.length; i++) {
        var m = list[i];
        if (m.type === 'characterData') textNode(m.target);
        else if (m.type === 'attributes') { if (m.target.tagName === 'TEXTAREA' || !skipped(m.target)) attrs(m.target); }
        else for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
      }
    }).observe(document.body, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTRS.concat(['value'])
    });
    document.documentElement.classList.remove('i18n-wait');
  }

  // 알림 창 글자도 번역
  function wrapDialogs() {
    ['alert', 'confirm', 'prompt'].forEach(function (name) {
      var old = window[name];
      if (typeof old !== 'function') return;
      window[name] = function (msg) {
        var args = Array.prototype.slice.call(arguments);
        if (typeof msg === 'string') {
          args[0] = msg.split('\n').map(function (line) {
            var out = translate(line);
            return out === null ? line : out;
          }).join('\n');
        }
        return old.apply(window, args);
      };
    });
  }

  // ---------- 언어 버튼 ----------
  function toggle() {
    if (document.getElementById('tripaLang')) return;
    var css = document.createElement('style');
    css.textContent =
      '#tripaLang{position:fixed;top:10px;right:12px;z-index:9000;font:500 13px/1 system-ui,sans-serif}' +
      '#tripaLang select{appearance:none;-webkit-appearance:none;cursor:pointer;padding:7px 26px 7px 28px;' +
      'border:1px solid rgba(0,0,0,.14);border-radius:999px;background:rgba(255,255,255,.94);color:#1b2740;' +
      'box-shadow:0 2px 8px rgba(0,0,0,.10);font:inherit}' +
      '#tripaLang:before{content:"\\1F310";position:absolute;left:8px;top:7px;font-size:13px;pointer-events:none}' +
      '#tripaLang:after{content:"";position:absolute;right:11px;top:11px;border:4px solid transparent;' +
      'border-top-color:#5d6a83;pointer-events:none}' +
      // 위쪽에 가로 메뉴(로그인·회원가입 버튼)가 있는 화면에서는 버튼을 가리지 않게 왼쪽 아래로
      '#tripaLang.is-low{top:auto;right:auto;left:14px;bottom:14px}' +
      // 폰 화면: 버튼을 가리지 않게 지구본만 보이는 작은 동그라미로 (누르면 언어 목록은 그대로 나옴)
      '@media (max-width:900px){#tripaLang,#tripaLang.is-low{top:auto;left:auto;bottom:74px;right:10px}' +
      '#tripaLang select{width:38px;height:38px;padding:0;color:transparent;text-indent:-999px}' +
      '#tripaLang select option{color:#1b2740}' +
      '#tripaLang:before{left:11px;top:11px;font-size:16px}#tripaLang:after{display:none}}' +
      '@media print{#tripaLang{display:none}}' +
      // 번역하면 글자가 길어져서 겹치는 곳 (한국어일 때는 안 건드림)
      (lang === 'ko' ? '' : '.tc-row{grid-template-columns:minmax(76px,max-content) 1fr !important;column-gap:8px}');
    document.head.appendChild(css);
    var box = document.createElement('div');
    box.id = 'tripaLang';
    box.setAttribute('data-no-i18n', '');
    if (document.querySelector('body > header:not(.m-topbar)')) box.className = 'is-low';
    var sel = document.createElement('select');
    sel.setAttribute('aria-label', 'Language');
    LANGS.forEach(function (l) {
      var o = document.createElement('option');
      o.value = l[0]; o.textContent = l[1];
      if (l[0] === lang) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener('change', function () { setLang(sel.value); });
    box.appendChild(sel);
    document.body.appendChild(box);
  }

  // 다른 스크립트에서 쓸 수 있게: TRIPA_I18N.t('한글') · TRIPA_I18N.lang · TRIPA_I18N.set('en')
  window.TRIPA_I18N = {
    lang: lang,
    set: setLang,
    t: function (s) { var out = lang === 'ko' ? null : translate(s); return out === null ? s : out; }
  };

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  if (lang !== 'ko') {
    document.documentElement.lang = lang === 'zh' ? 'zh-Hans' : lang;
    prepare();
    wrapDialogs();
    // 혹시 늦어져도 화면이 계속 숨겨져 있지 않게
    setTimeout(function () { document.documentElement.classList.remove('i18n-wait'); }, 1500);
    ready(start);
  }
  ready(toggle);
})();
