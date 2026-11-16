/* 폰 화면 [맨 위로] 버튼 (🟦 11/16)
 *
 * 모든 화면에 자동으로 붙는다 (i18n_middleware.py). 템플릿은 안 고친다.
 * - 화면 폭 900px 이하에서만, 아래로 400px 넘게 내렸을 때만 오른쪽 아래(아래 탭 위)에 작게 보인다
 * - 창 전체가 아니라 안쪽 상자(일정 목록 등)가 스크롤되는 화면도 있어서, 마지막으로 스크롤한 상자를 기억해 둔다
 */
(function () {
  if (window.__tripaToTop) return;
  window.__tripaToTop = true;

  var SHOW_AFTER = 400;
  var phone = window.matchMedia('(max-width: 900px)');
  var scroller = null;   // 마지막으로 스크롤한 안쪽 상자 (없으면 창 전체)

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    var css = document.createElement('style');
    css.textContent =
      '#tripaToTop{position:fixed;right:12px;bottom:calc(76px + var(--tp-safe-bottom,0px));z-index:8900;' +
      'width:38px;height:38px;border:1px solid rgba(37,99,235,.25);border-radius:50%;' +
      'background:rgba(255,255,255,.95);color:#2563eb;box-shadow:0 3px 10px rgba(15,23,42,.16);' +
      'display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0;' +
      'opacity:0;transform:translateY(8px);pointer-events:none;transition:opacity .2s,transform .2s}' +
      '#tripaToTop.is-on{opacity:1;transform:none;pointer-events:auto}' +
      '#tripaToTop svg{width:18px;height:18px}' +
      '@media (min-width:901px){#tripaToTop{display:none}}' +
      '@media print{#tripaToTop{display:none}}';
    document.head.appendChild(css);

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'tripaToTop';
    btn.title = '맨 위로';
    btn.setAttribute('aria-label', '맨 위로');
    btn.setAttribute('data-no-fit', '');
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
    document.body.appendChild(btn);

    function offset() {
      var page = window.scrollY || document.documentElement.scrollTop || 0;
      var inner = scroller && document.contains(scroller) ? scroller.scrollTop : 0;
      return Math.max(page, inner);
    }

    function update() {
      btn.classList.toggle('is-on', phone.matches && offset() > SHOW_AFTER);
    }

    // capture: true → 안쪽 상자의 스크롤도 여기서 받는다 (스크롤 이벤트는 위로 안 올라와서)
    document.addEventListener('scroll', function (e) {
      var t = e.target;
      if (t && t.nodeType === 1 && t.scrollHeight > t.clientHeight) scroller = t;
      update();
    }, { capture: true, passive: true });

    btn.addEventListener('click', function () {
      if (scroller && document.contains(scroller)) scroller.scrollTo({ top: 0, behavior: 'smooth' });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    if (phone.addEventListener) phone.addEventListener('change', update);
    update();
  });
})();
