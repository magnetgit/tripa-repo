// 3) 지도 칸: 카카오맵에 핀을 찍고, 일정 미리보기가 있으면 방문 순서대로 선을 잇는다.
// 대중교통이면 카카오 대중교통 경로(서버 호출, 실제 노선 모양)로 그린다.
//
// 카카오맵은 React 바깥에서 지도를 직접 그리는 라이브러리라서,
// 지도 객체는 useRef 에 보관하고 그리기는 useEffect 안에서 한다.
import { useEffect, useRef, useState } from 'react';
import Icon from './Icon.jsx';
import { currentDay, dayItems, dayStartPoint } from '../lib/plan.js';
import { ROUTE_COLOR, fetchTransit } from '../lib/transit.js';
import { shortDate } from '../lib/util.js';

function pinOverlay(kakao, kind, label, lat, lon) {
  const wrap = document.createElement('div');
  wrap.className = `tc-mappin tc-mappin--${kind}`;
  const text = document.createElement('span');
  text.className = 'tc-mappin__label';
  text.textContent = label; // 장소 이름은 글자로만 넣음 (innerHTML 사용 안 함)
  const dot = document.createElement('span');
  dot.className = 'tc-mappin__dot';
  wrap.append(text, dot);
  return new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(lat, lon), content: wrap, xAnchor: 0.5, yAnchor: 1 });
}

// 지도에 찍을 점이 하나라도 있는지 (안내 문구용)
function hasPoints(state) {
  const day = currentDay(state);
  if (day) return !!dayStartPoint(state, day) || dayItems(state, day).some((it) => it.lat != null);
  const d = state.draft;
  return !!((d.center && d.center.lat != null) || (d.start_place && d.start_place.lat != null)
    || (d.stays || []).some((s) => s.lat != null));
}

function isTransit(state) {
  const t = (state.plan && state.plan.transport) || '';
  return state.draft.transport === 'public_transport' || t.includes('대중교통');
}

export default function MapPanel({ state, sprite, transitUrl, focus }) {
  const boxRef = useRef(null);
  const mapRef = useRef(null);
  const focusRef = useRef(null);   // 추천 카드를 눌러 띄운 장소 표시 (일정 표시와 따로)
  const overlaysRef = useRef([]);
  const tokenRef = useRef(0); // 다시 그리면 이전 경로 결과는 버림
  const [ready, setReady] = useState(false);
  // 카카오 지도 스크립트가 있는지 (처음 한 번만 확인)
  const [kakaoOk] = useState(() => !!(window.kakao && window.kakao.maps && window.kakao.maps.load));
  const hint = !kakaoOk ? '지도를 불러오지 못했어요.' : hasPoints(state) ? '' : '지역을 정하면 지도에 표시돼요.';

  // 지도 한 번만 만들기
  useEffect(() => {
    if (!kakaoOk) return;
    window.kakao.maps.load(() => {
      if (mapRef.current || !boxRef.current) return;
      mapRef.current = new window.kakao.maps.Map(boxRef.current, { center: new window.kakao.maps.LatLng(36.5, 127.8), level: 13 });
      setReady(true);
    });
  }, [kakaoOk]);

  // 초안·일정·보는 날짜가 바뀔 때마다 다시 그리기
  useEffect(() => {
    const map = mapRef.current;
    const kakao = window.kakao;
    if (!ready || !map) return;

    const token = ++tokenRef.current;
    overlaysRef.current.forEach((o) => o.setMap(null));
    overlaysRef.current = [];
    const keep = (o) => { o.setMap(map); overlaysRef.current.push(o); return o; };

    const line = (points, color, dashed) =>
      keep(new kakao.maps.Polyline({
        path: points.map((p) => new kakao.maps.LatLng(p[0], p[1])),
        strokeWeight: dashed ? 3 : 5, strokeColor: color,
        strokeOpacity: dashed ? 0.8 : 0.85, strokeStyle: dashed ? 'shortdash' : 'solid',
      }));

    const d = state.draft;
    const points = [];
    const add = (kind, label, lat, lon) => {
      if (lat == null || lon == null) return;
      keep(pinOverlay(kakao, kind, label, lat, lon));
      points.push(new kakao.maps.LatLng(lat, lon));
    };

    const day = currentDay(state);
    if (day) {
      // 일정 미리보기가 있으면 선택한 날의 방문 순서대로 번호를 붙여 보여준다
      const stops = [];
      const first = dayStartPoint(state, day);
      if (first) {
        add('start', `출발 · ${day.start_name}`, first.lat, first.lon);
        stops.push({ lat: Number(first.lat), lon: Number(first.lon) });
      }
      dayItems(state, day).forEach((it, i) => {
        if (it.lat == null || it.lon == null) return;
        add(it.is_stay ? 'stay' : 'stop', `${i + 1}. ${it.name}`, it.lat, it.lon);
        stops.push({ lat: Number(it.lat), lon: Number(it.lon) });
      });

      if (stops.length > 1 && isTransit(state)) {
        // 대중교통: 연한 직선 자리표시를 먼저 깔고, 경로를 받는 대로 실제 경로로 바꿈
        stops.slice(1).forEach((b, i) => {
          const a = stops[i];
          const temp = line([[a.lat, a.lon], [b.lat, b.lon]], '#9fb3d9', true);
          fetchTransit(transitUrl, a, b).then((segs) => {
            if (token !== tokenRef.current || !segs) return; // 그사이 지도가 바뀌었거나 실패 → 자리표시 유지
            temp.setMap(null);
            segs.forEach((s) => line(s.points, ROUTE_COLOR[s.mode] || ROUTE_COLOR.walk, s.mode === 'walk'));
          });
        });
      } else if (stops.length > 1) {
        line(stops.map((s) => [s.lat, s.lon]), '#2d6cdf', false);
      }
    } else {
      if (d.center) add('place', d.place || '여행지', d.center.lat, d.center.lon);
      if (d.start_place) add('start', `출발 · ${d.start_place.name || d.start_place.query}`, d.start_place.lat, d.start_place.lon);
      (d.stays || []).forEach((s) => add('stay', `${shortDate(s.date)} ${s.name || s.query}`, s.lat, s.lon));
    }

    map.relayout();

    if (points.length > 1) {
      const bounds = new kakao.maps.LatLngBounds();
      points.forEach((p) => bounds.extend(p));
      map.setBounds(bounds, 70, 70, 70, 70);
    } else if (points.length === 1) {
      map.setCenter(points[0]);
      map.setLevel(d.start_place || (d.stays || []).length ? 5 : 8);
    }
  }, [ready, state, transitUrl]);

  // 추천 카드를 누르면: 그 장소로 지도를 옮기고 주황 핀으로 표시
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !focus || Number.isNaN(focus.lat)) return;
    const kakao = window.kakao;
    if (focusRef.current) focusRef.current.setMap(null);
    focusRef.current = pinOverlay(kakao, 'focus', focus.name, focus.lat, focus.lon);
    focusRef.current.setZIndex(10);
    focusRef.current.setMap(map);
    map.relayout();
    map.setLevel(5);
    map.panTo(new kakao.maps.LatLng(focus.lat, focus.lon));
    // 폰처럼 지도가 화면 밖이면 지도까지 내려가 보여 준다
    const r = boxRef.current.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight) boxRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [ready, focus]);

  return (
    <section className="tc-panel tc-mapPanel" aria-label="지도">
      <header className="tc-panel__head">
        <h2><Icon name="map" sprite={sprite} /> 지도</h2>
      </header>
      <div className="tc-mapWrap">
        <div ref={boxRef} className="tc-map" />
        <p className="tc-map__hint" hidden={!hint}>{hint}</p>
      </div>
    </section>
  );
}
