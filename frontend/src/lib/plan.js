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
