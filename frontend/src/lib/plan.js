// 일정 미리보기 계산 (기존 travel_chat.js 와 같은 규칙)

// 일정에 영향을 주는 값이 바뀌었는지 알아보는 표식 (담은 장소/제목은 일정 생성에 영향이 없다)
export function planSig(d) {
  const sp = d.start_place;
  return JSON.stringify([
    d.place, d.start, d.end, d.people, d.budget_style, d.budget_total, d.transport, d.categories, d.start_time,
    sp ? [sp.name, sp.lat, sp.lon] : null,
    (d.stays || []).map((x) => [x.date, x.name, x.lat, x.lon, x.arrival_time, x.departure_time]),
    (d.pins || []).map((p) => [p.day, p.name, p.time, p.lat, p.lon]),
  ]);
}

// {일차: [이름...]} → [{day, names}] (서버로 보내는 모양)
export function orderList(order) {
  return Object.keys(order)
    .sort((a, b) => a - b)
    .map((k) => ({ day: parseInt(k, 10), names: order[k] }));
}

export function removedKey(removed, order) {
  return JSON.stringify([removed.map((r) => `${r.day}:${r.name}`).sort(), orderList(order)]);
}

export function isPlanFresh(state) {
  return !!(state.plan && state.plan.sig === planSig(state.draft));
}

export function currentDay(state) {
  if (!isPlanFresh(state)) return null;
  const days = state.plan.days;
  return days[Math.min(state.dayTab, days.length - 1)] || null;
}

export function isGone(removed, day, it) {
  return removed.some((r) => r.day === day.day && r.name === it.name);
}

// 서버가 짠 일정에서 지운 것을 빼고, 사용자가 바꾼 순서대로 보여 준다
export function dayItems(state, day) {
  let items = (day.items || []).filter((it) => !isGone(state.removed, day, it));
  const names = state.order[day.day];
  if (names) {
    const pos = {};
    names.forEach((n, i) => { if (!(n in pos)) pos[n] = i; });
    items = items
      .map((it, i) => ({ it, i }))
      .sort((a, b) => {
        const pa = a.it.name in pos ? pos[a.it.name] : 1000 + a.i;
        const pb = b.it.name in pos ? pos[b.it.name] : 1000 + b.i;
        return pa - pb;
      })
      .map((x) => x.it);
  }
  return items;
}

// 그날의 출발점: 1일차는 출발지, 그다음 날은 전날 숙소
export function dayStartPoint(state, day) {
  if (day.day === 1) {
    const sp = state.draft.start_place;
    return sp && sp.lat != null ? { lat: sp.lat, lon: sp.lon } : null;
  }
  const prev = state.plan.days[day.day - 2];
  const arr = prev ? prev.items || [] : [];
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i].is_stay && arr[i].lat != null) return { lat: arr[i].lat, lon: arr[i].lon };
  }
  return null;
}

// ---------- 먼 길(비행기·배·KTX로 가는 구간) ----------
// 첫날 출발지 → 첫 장소가 바다를 건너 섬(제주·울릉)으로 가거나 직선 80km를 넘으면 차 길 시간 대신 안내
// (일정을 적용하면 여행 상세 '여행지까지 가는 길'(🟧 access_service)에서 비행기·배·KTX 가격을 비교해 고름)
export const FAR_KM = 80;

function kmBetween(a, b) {
  const r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r;
  const dLon = (b.lon - a.lon) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

// 육지와 다리로 이어지지 않은 큰 섬 (위도·경도 범위)
const ISLANDS = [
  { name: '제주', lat: [33.1, 33.6], lon: [126.1, 127.0] },
  { name: '울릉', lat: [37.43, 37.56], lon: [130.78, 130.95] },
];

function islandOf(p) {
  const lat = Number(p.lat);
  const lon = Number(p.lon);
  const hit = ISLANDS.find((s) => lat >= s.lat[0] && lat <= s.lat[1] && lon >= s.lon[0] && lon <= s.lon[1]);
  return hit ? hit.name : '';
}

// → null 이거나 {km, island: '제주' | '', to: 첫 장소 이름}
export function farLeg(state, day) {
  if (!day || day.day !== 1) return null;
  const a = dayStartPoint(state, day);
  const b = dayItems(state, day).find((it) => it.lat != null && it.lon != null);
  if (!a || !b) return null;
  const from = { lat: Number(a.lat), lon: Number(a.lon) };
  const to = { lat: Number(b.lat), lon: Number(b.lon) };
  const island = islandOf(to) && islandOf(to) !== islandOf(from) ? islandOf(to) : '';
  const km = Math.round(kmBetween(from, to));
  if (!island && km < FAR_KM) return null;
  return { km, island, to: b.name };
}

// 안내 문구 두 줄 (미리보기·travel_chat.js 같은 문장)
export function farLegText(far) {
  return {
    title: far.island
      ? `✈ 🚢 ${far.island}까지는 바다를 건너요 · 비행기나 배로 가요`
      : `🚄 ✈ 먼 길이에요 (약 ${far.km}km) · KTX·고속버스·비행기로 가요`,
    sub: "일정을 적용하면 여행 상세 '🧭 여행지까지 가는 길'에서 가격·시간을 비교하고 고를 수 있어요",
  };
}
