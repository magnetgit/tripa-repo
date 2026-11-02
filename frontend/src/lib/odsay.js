// 대중교통 실제 경로 (ODsay) — 기존 travel_chat.js 와 같은 규칙
// - 받은 구간은 localStorage 에 저장해서 같은 구간은 다시 부르지 않는다. (무료 호출 한도 절약)
// - 700m 이내는 걷는 거리라 부르지 않는다. (ODsay 도 이 거리에서는 오류를 냄)
// - 버스·지하철이 지나는 정류장 좌표를 이어 선을 그린다. (추가 호출이 드는 노선 그래픽은 쓰지 않음)
// - 저장 이름이 기존 화면과 같아서, 두 화면이 저장해 둔 경로를 함께 쓴다.

const ROUTE_STORE = 'tripa_odsay_route_v1';
const ROUTE_WALK_METERS = 700;

export const ROUTE_COLOR = { bus: '#2f9e5b', subway: '#2d6cdf', train: '#7b4bc4', walk: '#8a94a6' };

function loadMemo() {
  try { return JSON.parse(localStorage.getItem(ROUTE_STORE) || '{}') || {}; } catch { return {}; }
}

const memo = loadMemo();
const pending = {};

function saveMemo() {
  try {
    const keys = Object.keys(memo);
    if (keys.length > 200) keys.slice(0, keys.length - 200).forEach((k) => { delete memo[k]; });
    localStorage.setItem(ROUTE_STORE, JSON.stringify(memo));
  } catch { /* 저장이 안 돼도 동작에는 문제 없음 */ }
}

const routeKey = (a, b) => [a.lat, a.lon, b.lat, b.lon].map((n) => Number(n).toFixed(4)).join(',');

function meters(a, b) {
  const R = 6371000;
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// ODsay 응답 → [{mode, points:[[lat,lon],...]}]  (도보 구간은 앞뒤 대중교통 구간을 이어 줌)
function parseTransit(data, a, b) {
  const path = data && data.result && data.result.path && data.result.path[0];
  if (!path || !Array.isArray(path.subPath)) return null;

  const segs = [];
  let last = [Number(a.lat), Number(a.lon)];
  path.subPath.forEach((sec) => {
    const type = Number(sec.trafficType);
    if (type !== 1 && type !== 2 && type !== 4) return; // 3 = 도보
    const pts = [];
    if (sec.startY != null && sec.startX != null) pts.push([Number(sec.startY), Number(sec.startX)]);
    const stations = sec.passStopList && Array.isArray(sec.passStopList.stations) ? sec.passStopList.stations : [];
    stations.forEach((s) => { if (s.y != null && s.x != null) pts.push([Number(s.y), Number(s.x)]); });
    if (sec.endY != null && sec.endX != null) pts.push([Number(sec.endY), Number(sec.endX)]);
    if (pts.length < 2) return;
    segs.push({ mode: 'walk', points: [last, pts[0]] });
    segs.push({ mode: type === 1 ? 'subway' : type === 2 ? 'bus' : 'train', points: pts });
    last = pts[pts.length - 1];
  });
  if (!segs.length) return null;
  segs.push({ mode: 'walk', points: [last, [Number(b.lat), Number(b.lon)]] });
  return segs;
}

// 한 구간의 경로. 실패(한도 초과 등)면 null → 화면은 직선 점선으로 대신 그림
export function fetchTransit(odsayKey, a, b) {
  const key = routeKey(a, b);
  if (memo[key]) return Promise.resolve(memo[key]);
  if (meters(a, b) <= ROUTE_WALK_METERS) {
    return Promise.resolve([{ mode: 'walk', points: [[a.lat, a.lon], [b.lat, b.lon]] }]);
  }
  if (!odsayKey) return Promise.resolve(null);
  if (pending[key]) return pending[key];

  const url =
    'https://api.odsay.com/v1/api/searchPubTransPathT' +
    `?SX=${a.lon}&SY=${a.lat}&EX=${b.lon}&EY=${b.lat}&apiKey=${encodeURIComponent(odsayKey)}`;

  pending[key] = fetch(url)
    .then((r) => r.json())
    .then((data) => {
      const segs = parseTransit(data, a, b);
      if (segs) { memo[key] = segs; saveMemo(); }
      return segs;
    })
    .catch(() => null)
    .then((segs) => { delete pending[key]; return segs; });

  return pending[key];
}
