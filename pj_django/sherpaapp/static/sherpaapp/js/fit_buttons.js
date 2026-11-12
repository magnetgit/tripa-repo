/* 폰 화면: 버튼 글자가 버튼 밖으로 나가거나 두 줄이 되면 한 줄로 맞추기 (🟧 11/12)
 *
 * 화면 폭이 900px 이하일 때만 돈다 (PC 화면은 안 건드림).
 * 버튼처럼 생긴 것(button, submit, 이름에 btn 이 든 링크, 아래 탭, 고르는 칩)을 훑어서
 *   글자가 두 줄 이상이거나 버튼 밖으로 삐져나오면  →  .tp-fit   : 줄바꿈 금지 + 버튼 폭을 글자만큼 늘림
 *   그래서 옆 버튼과 한 줄에 못 들어가면             →  .tp-fit-row: 그 줄(부모)을 여러 줄로 내려 쌓음
 *   그래도 화면보다 넓으면                           →  .tp-fit-small: 글자·좌우 여백을 조금 줄임
 *   그래도 넘으면                                    →  .tp-fit-clip : 화면 폭까지만, 끝은 … 으로
 * 화면이 바뀔 때(일정 카드가 새로 그려짐, 언어 바꿈, 화면 돌림)마다 다시 본다.
 *
 * 맞추면 안 되는 버튼은 태그에 data-no-fit 을 붙인다.
 * 이 파일은 서버(sherpaapp/i18n_middleware.py)가 모든 화면에 자동으로 붙인다.
 */
(function () {
  'use strict';
  if (window.__tripaFit) return;
  window.__tripaFit = true;

  var SELECTOR = 'button, input[type=submit], input[type=button], [role=button], ' +
    'a[class*=btn], .btn, .m-tab, label[class*=chip], a[class*=chip]';
  // 안내용 칩(예: 교통 안내 .transport-chip-main)은 버튼이 아니라서 넣지 않는다 → 긴 안내는 지금처럼 두 줄로 보임
  var MAX_TEXT = 40;        // 이보다 긴 글은 버튼이 아니라 카드로 본다
  var media = window.matchMedia('(max-width: 900px)');

  var css = document.createElement('style');
  css.textContent =
    '@media (max-width:900px){' +
    '.tp-fit{white-space:nowrap!important;min-width:max-content!important;flex-shrink:0!important;height:auto;}' +
    '.tp-fit-row{flex-wrap:wrap!important;row-gap:6px;}' +
    '.tp-fit.tp-fit-small{font-size:.88em!important;padding-left:8px!important;padding-right:8px!important;letter-spacing:-.01em;}' +
    '.tp-fit.tp-fit-clip{min-width:0!important;max-width:100%!important;overflow:hidden!important;text-overflow:ellipsis!important;}' +
    // 고르는 상자(select)가 카드보다 넓어지지 않게 (긴 여행 제목)
    'select{max-width:100%;}' +
    '}' +
    // 아주 좁은 폰(갤럭시 S 등 420px 이하): 홈 머리의 [내 여행 · 닉네임 · 로그아웃]이 화면 밖으로 나가지 않게 간격을 줄임
    '@media (max-width:420px){' +
    '.header-inner{padding-left:12px!important;padding-right:12px!important;gap:6px!important;}' +
    '.header-inner .logo{font-size:20px!important;}' +
    '.header-actions{gap:4px!important;min-width:0;}' +
    '.header-actions a{padding-left:8px!important;padding-right:8px!important;font-size:13px!important;white-space:nowrap;}' +
    '.header-actions .header-user{max-width:30vw;overflow:hidden;text-overflow:ellipsis;}' +
    '}';
  (document.head || document.documentElement).appendChild(css);

  function textNodes(el) {
    var out = [], walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), node;
    while ((node = walker.nextNode())) if (node.nodeValue.trim()) out.push(node);
    return out;
  }

  /** 글자가 두 줄 이상이거나 버튼 밖으로 나갔는지 */
  function broken(el, box) {
    var nodes = textNodes(el), range = document.createRange(), i, j;
    for (i = 0; i < nodes.length; i++) {
      range.selectNodeContents(nodes[i]);
      var rects = range.getClientRects(), tops = [];
      for (j = 0; j < rects.length; j++) {
        var r = rects[j];
        if (r.width < 1) continue;
        if (r.right > box.right + 1.5 || r.left < box.left - 1.5) return true;       // 밖으로 나감
        if (tops.indexOf(Math.round(r.top)) < 0) tops.push(Math.round(r.top));
      }
      if (tops.length > 1) return true;                                                // 줄바꿈
    }
    return false;
  }

  function candidate(el) {
    if (el.hasAttribute('data-no-fit') || el.closest('[data-no-fit]')) return null;
    if (el.classList.contains('tp-fit')) return null;                                  // 이미 맞춤
    var box = el.getBoundingClientRect();
    if (box.width < 1 || box.height < 1) return null;                                  // 안 보임
    var text = (el.tagName === 'INPUT' ? el.value : el.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text || text.length > MAX_TEXT) return null;
    if (el.querySelector('br, p, div, ul, img')) return null;                          // 여러 줄로 쓰려고 만든 것(카드)
    var style = getComputedStyle(el);
    if (style.display === 'inline') return null;                                       // 글 속 링크
    // 그림만 보이는 작은 버튼(글자는 화면 낭독용으로 숨김)은 그대로
    if (box.width < 48 && el.querySelector('svg') && (style.overflow === 'hidden' || parseFloat(style.fontSize) < 2)) return null;
    return box;
  }

  function fit(el) {
    var box = candidate(el);
    if (!box || !broken(el, box)) return;
    el.classList.add('tp-fit');
  }

  /** 늘린 버튼이 옆 버튼과 한 줄에 못 들어가면 그 줄을 내려 쌓고, 그래도 화면보다 넓으면 줄인다 */
  function settle(el) {
    var limit = document.documentElement.clientWidth;
    var parent = el.parentElement;
    if (parent && !parent.classList.contains('tp-fit-row')) {
      var ps = getComputedStyle(parent);
      var row = (ps.display === 'flex' || ps.display === 'inline-flex') && ps.flexDirection.indexOf('row') === 0;
      if (row) {
        var pbox = parent.getBoundingClientRect();
        var last = parent.lastElementChild ? parent.lastElementChild.getBoundingClientRect() : pbox;
        if (parent.scrollWidth > parent.clientWidth + 1 || last.right > pbox.right + 1 || last.right > limit - 2) {
          parent.classList.add('tp-fit-row');
        }
      }
    }
    var box = el.getBoundingClientRect();
    if (box.right > limit - 4 || box.width > limit - 16) {
      el.classList.add('tp-fit-small');
      box = el.getBoundingClientRect();
      if (box.right > limit - 4 || box.width > limit - 16) el.classList.add('tp-fit-clip');
    }
  }

  function run() {
    timer = null;
    if (!media.matches || !document.body) return;
    var list = document.body.querySelectorAll(SELECTOR);
    var i;
    for (i = 0; i < list.length; i++) {
      try { fit(list[i]); } catch (e) { /* 한 버튼에서 실패해도 나머지는 계속 */ }
    }
    // 한 줄의 버튼을 모두 늘린 다음에 줄이 넘치는지 본다
    var fitted = document.body.querySelectorAll('.tp-fit');
    for (i = 0; i < fitted.length; i++) {
      try { settle(fitted[i]); } catch (e) { /* 위와 같음 */ }
    }
  }

  var timer = null;
  function later() { if (!timer) timer = setTimeout(run, 250); }

  // 화면을 돌리거나 폭이 바뀌면 처음부터 다시 (늘려 둔 것을 풀고 다시 잼)
  function reset() {
    var marked = document.querySelectorAll('.tp-fit, .tp-fit-row');
    for (var i = 0; i < marked.length; i++) marked[i].classList.remove('tp-fit', 'tp-fit-row', 'tp-fit-small', 'tp-fit-clip');
    later();
  }

  function start() {
    run();
    new MutationObserver(later).observe(document.body, { childList: true, subtree: true, characterData: true });
    window.addEventListener('resize', reset);
    window.addEventListener('load', later);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(later);      // 글꼴이 늦게 오면 폭이 달라짐
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
