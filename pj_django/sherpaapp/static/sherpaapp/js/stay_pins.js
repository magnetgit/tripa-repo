/* 채팅 지도: 추천 숙소를 '보라색 점 + 이름·가격 카드'로 표시 (🟧 11/16, cloud-tripa 방식)
 *
 * 채팅에서 숙소를 추천받으면(추천 카드의 kind 가 '숙박') 그 숙소들을 지도에 같이 보여 준다.
 *   - 숙소 자리에 번호가 든 보라색 점
 *   - 점 옆에 카드: [번호] 숙소 이름 / 1박 약 9만원
 *   - 카드는 점·다른 카드와 겹치지 않는 자리를 골라 놓고, 점과 카드를 가는 선으로 잇는다
 *     (cloud-tripa 는 카드가 점 바로 위에 있어서, 가까운 숙소끼리 카드가 남의 점을 가렸음)
 *   - 지도를 확대·축소하면 자리를 다시 잡는다
 *
 * 쓰는 곳: 여행 만들기(travel_chat.js 의 updateMap), React 채팅(frontend/src/components/MapPanel.jsx)
 *   var pins = TripaStayPins.draw(map, items, { chosen: function (item) { return 담았는지; } });
 *   pins.points  → kakao.maps.LatLng 목록 (지도 범위를 숙소에 맞출 때)
 *   pins.clear() → 지우기 (다시 그리기 전에)
 *   TripaStayPins.fromMessages(messages) → 가장 최근 추천 중 숙소만 (좌표 있는 것)
 *   TripaStayPins.forDraft(messages, draft) → 위 목록에서 고른 숙소 빼기, 모든 밤을 정했으면 [] (🟦 11/18)
 *
 * items 는 추천 카드 그대로 (mock.json recommendation.items): name, lat, lon, kind, cost{per, unit}
 */
(function () {
  'use strict';
  if (window.TripaStayPins) return;

  var css = document.createElement('style');
  css.textContent =
    '.sp-pin{position:relative;width:0;height:0;font-family:inherit}' +
    '.sp-dot{position:absolute;left:-11px;top:-11px;width:22px;height:22px;border-radius:50%;box-sizing:border-box;' +
    'background:#6b5bd6;border:2px solid #fff;box-shadow:0 2px 6px rgba(40,30,110,.35);color:#fff;' +
    'font:700 11px/18px system-ui,sans-serif;text-align:center;z-index:2}' +
    '.sp-line{position:absolute;left:0;top:0;height:2px;margin-top:-1px;background:#6b5bd6;opacity:.75;' +
    'transform-origin:0 50%;border-radius:2px;z-index:1;pointer-events:none}' +
    '.sp-card{position:absolute;left:0;top:0;display:flex;align-items:center;gap:6px;white-space:nowrap;' +
    'padding:5px 10px 5px 6px;border-radius:10px;background:#fff;border:1.5px solid #6b5bd6;' +
    'box-shadow:0 4px 12px rgba(40,30,110,.18);z-index:3;cursor:default}' +
    '.sp-card__no{flex:none;width:18px;height:18px;border-radius:50%;background:#6b5bd6;color:#fff;' +
    'font:700 11px/18px system-ui,sans-serif;text-align:center}' +
    '.sp-card__text{display:flex;flex-direction:column;line-height:1.25}' +
    '.sp-card__name{font-size:12.5px;font-weight:700;color:#1e1b4b;max-width:150px;overflow:hidden;text-overflow:ellipsis}' +
    '.sp-card__price{font-size:11px;font-weight:600;color:#5b4fc4}' +
    // 일정에 담은 숙소: 꽉 찬 보라색
    '.sp-pin.is-chosen .sp-card{background:#6b5bd6}' +
    '.sp-pin.is-chosen .sp-card__name,.sp-pin.is-chosen .sp-card__price{color:#fff}' +
    '.sp-pin.is-chosen .sp-card__no{background:#fff;color:#6b5bd6}' +
    // 카드나 점에 마우스를 올리면 그 숙소만 맨 위로
    '.sp-pin:hover .sp-card,.sp-pin:hover .sp-dot{z-index:9}.sp-pin:hover .sp-line{opacity:1}';
  (document.head || document.documentElement).appendChild(css);

  function node(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text != null) el.textContent = text;      // 숙소 이름은 글자로만 넣는다 (innerHTML 안 씀)
    return el;
  }

  /** 숙소 1박 가격 글자: 90000 → '1박 약 9만원', 85000 → '1박 약 8.5만원'. 값이 없으면 '' */
  function priceText(item) {
    var cost = item && item.cost;
    var per = cost && cost.per != null ? Number(cost.per) : (cost && cost.amount ? Number(cost.amount) : 0);
    if (!per) return '';
    // 한국어가 아니면 '만' 단위를 풀어서 (번역 사전의 "1박 약 {}원" 한 줄로 바뀌게)
    if ((window.TRIPA_LANG || 'ko') !== 'ko') return '1박 약 ' + per.toLocaleString('ko-KR') + '원';
    var man = Math.round(per / 1000) / 10;
    var text = per >= 10000 ? man.toLocaleString('ko-KR') + '만원' : per.toLocaleString('ko-KR') + '원';
    return '1박 약 ' + text;
  }

  /** 가장 최근 추천 중 숙소(좌표 있는 것)만 */
  function fromMessages(messages) {
    for (var i = (messages || []).length - 1; i >= 0; i--) {
      var rec = messages[i] && messages[i].rec;
      var items = rec && rec.items;
      if (items && items.length) {
        return items.filter(function (it) { return it.kind === '숙박' && it.lat != null && it.lon != null; });
      }
    }
    return [];
  }

  /** 지도에 그릴 추천 숙소 (🟦 11/18): 고른 뒤에는 겹치지 않게
   *  - 모든 밤에 숙소를 정했으면 [] (추천 숙소는 더 안 보여 줌)
   *  - 빈 밤이 남았으면 추천 중 이미 고른 숙소만 뺌 (고른 숙소는 일정의 주황색 숙소 표시로 보임)
   */
  function forDraft(messages, draft) {
    var items = fromMessages(messages);
    if (!items.length || !draft) return items;
    var stays = (draft.stays || []).filter(function (s) { return s && s.lat != null; });
    var start = draft.start ? new Date(draft.start + 'T00:00:00') : null;
    var end = draft.end ? new Date(draft.end + 'T00:00:00') : null;
    var nights = start && end ? Math.round((end - start) / 86400000) : 0;
    var booked = {};
    stays.forEach(function (s) { if (s.date) booked[s.date] = true; });
    if (nights > 0 && Object.keys(booked).length >= nights) return [];
    var names = stays.map(function (s) { return s.name || s.query; });
    return items.filter(function (it) { return names.indexOf(it.name) < 0; });
  }

  function overlap(a, b, gap) {
    return a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;
  }

  /** 점(0,0)에서 카드까지 선을 긋는다: 카드 상자에서 점과 가장 가까운 자리까지 */
  function setLine(line, box) {
    var x = Math.max(box.x, Math.min(0, box.x + box.w));
    var y = Math.max(box.y, Math.min(0, box.y + box.h));
    var len = Math.sqrt(x * x + y * y);
    line.style.width = Math.max(0, len) + 'px';
    line.style.transform = 'rotate(' + Math.atan2(y, x) + 'rad)';
  }

  /** 카드 자리 잡기: 점·다른 카드와 안 겹치고 지도 안에 들어오는 가장 가까운 자리 */
  function layout(map, pins) {
    var proj = map.getProjection && map.getProjection();
    var box = map.getNode && map.getNode();
    if (!proj || !box) return;
    var W = box.clientWidth, H = box.clientHeight;
    var DOT = 13;                                   // 점 반지름 + 여유
    pins.forEach(function (p) {
      var pt = proj.containerPointFromCoords(p.pos);
      p.x = pt.x; p.y = pt.y;
      p.w = p.card.offsetWidth || 120;
      p.h = p.card.offsetHeight || 38;
    });
    var dots = pins.map(function (p) { return { x: p.x - DOT, y: p.y - DOT, w: DOT * 2, h: DOT * 2 }; });
    var placed = [];
    // 위쪽 점부터 자리를 잡으면 아래 점의 카드가 위 카드를 덜 밀어낸다
    pins.slice().sort(function (a, b) { return a.y - b.y || a.x - b.x; }).forEach(function (p) {
      var best = null;
      // 점에서 떨어지는 거리(가까운 것부터) × 방향 8가지
      [18, 34, 54, 78, 104, 134].some(function (r) {
        var cand = [
          { x: -p.w / 2, y: -r - p.h },             // 위
          { x: r, y: -p.h / 2 },                    // 오른쪽
          { x: -r - p.w, y: -p.h / 2 },             // 왼쪽
          { x: -p.w / 2, y: r },                    // 아래
          { x: r * 0.7, y: -r * 0.7 - p.h },        // 오른쪽 위
          { x: -r * 0.7 - p.w, y: -r * 0.7 - p.h }, // 왼쪽 위
          { x: r * 0.7, y: r * 0.7 },               // 오른쪽 아래
          { x: -r * 0.7 - p.w, y: r * 0.7 }         // 왼쪽 아래
        ];
        return cand.some(function (c) {
          var abs = { x: p.x + c.x, y: p.y + c.y, w: p.w, h: p.h };
          if (abs.x < 4 || abs.y < 4 || abs.x + abs.w > W - 4 || abs.y + abs.h > H - 4) return false;   // 지도 밖
          if (dots.some(function (d) { return overlap(abs, d, 2); })) return false;                      // 점을 가림
          if (placed.some(function (q) { return overlap(abs, q, 4); })) return false;                    // 다른 카드와 겹침
          best = { rel: c, abs: abs };
          return true;
        });
      });
      if (!best) {                                  // 자리가 없으면 점 바로 위 (겹치더라도 선으로 구분)
        var c = { x: -p.w / 2, y: -18 - p.h };
        best = { rel: c, abs: { x: p.x + c.x, y: p.y + c.y, w: p.w, h: p.h } };
      }
      placed.push(best.abs);
      p.card.style.transform = 'translate(' + Math.round(best.rel.x) + 'px,' + Math.round(best.rel.y) + 'px)';
      setLine(p.line, { x: best.rel.x, y: best.rel.y, w: p.w, h: p.h });
    });
  }

  function draw(map, items, options) {
    var kakao = window.kakao;
    var chosen = (options && options.chosen) || function () { return false; };
    var overlays = [], pins = [], points = [];
    (items || []).forEach(function (item, i) {
      if (item.lat == null || item.lon == null) return;
      var no = String(i + 1);
      var wrap = node('div', 'sp-pin' + (chosen(item) ? ' is-chosen' : ''));
      var line = node('span', 'sp-line');
      var dot = node('span', 'sp-dot', no);
      var card = node('div', 'sp-card');
      card.title = item.name + (item.addr ? ' · ' + item.addr : '');
      var text = node('span', 'sp-card__text');
      text.appendChild(node('span', 'sp-card__name', item.name));     // 이름은 추천 카드와 같게 (다른 언어면 자동 번역이 양쪽을 같이 바꿈)
      var price = priceText(item);
      if (price) text.appendChild(node('span', 'sp-card__price', price));
      card.appendChild(node('span', 'sp-card__no', no));
      card.appendChild(text);
      wrap.appendChild(line); wrap.appendChild(dot); wrap.appendChild(card);
      var pos = new kakao.maps.LatLng(item.lat, item.lon);
      var overlay = new kakao.maps.CustomOverlay({ position: pos, content: wrap, xAnchor: 0, yAnchor: 0, zIndex: 5 });
      overlay.setMap(map);
      overlays.push(overlay);
      points.push(pos);
      pins.push({ pos: pos, card: card, line: line });
    });

    var timer = null;
    function relayout() {
      clearTimeout(timer);
      timer = setTimeout(function () { layout(map, pins); }, 30);
    }
    if (pins.length) {
      relayout();
      kakao.maps.event.addListener(map, 'zoom_changed', relayout);
      kakao.maps.event.addListener(map, 'idle', relayout);         // 범위를 맞춘 뒤·끌어 옮긴 뒤 (지도 가장자리 기준이 바뀜)
    }
    return {
      points: points,
      relayout: relayout,
      clear: function () {
        clearTimeout(timer);
        overlays.forEach(function (o) { o.setMap(null); });
        if (pins.length) {
          kakao.maps.event.removeListener(map, 'zoom_changed', relayout);
          kakao.maps.event.removeListener(map, 'idle', relayout);
        }
      }
    };
  }

  window.TripaStayPins = { draw: draw, fromMessages: fromMessages, forDraft: forDraft, priceText: priceText };
})();
