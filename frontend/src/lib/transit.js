// 대중교통 실제 경로 (카카오 대중교통 길찾기, 서버 /transit_route/ 호출) — ODsay 대신 (11/06 결정)
// - 서버가 카카오를 부르고 같은 구간은 7일 저장한다. 키는 브라우저로 나가지 않는다.
// - 이 화면에서도 받은 구간은 localStorage 에 잠깐 저장해서 지도를 다시 그릴 때 또 부르지 않는다.
// - 700m 이내는 걷는 거리라 부르지 않는다. (서버도 같은 규칙)

const ROUTE_STORE = 'tripa_transit_route_v1';
const ROUTE_WALK_METERS = 700;

export const ROUTE_COLOR = { bus: '#2f9e5b', subway: '#2d6cdf', train: '#7b4bc4', air: '#7b4bc4', transit: '#2d6cdf', walk: '#8a94a6' };

function loadMemo() {
  try {
    localStorage.removeItem('tripa_odsay_route_v1');   // 예전 ODsay 저장 칸 정리
    return JSON.parse(localStorage.getItem(ROUTE_STORE) || '{}') || {};
  } catch {
    return {};
  }
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

// 한 구간의 경로 → [{mode, points:[[lat,lon],...]}]. 실패면 null → 화면은 직선 점선으로 대신 그림
export function fetchTransit(transitUrl, a, b) {
  const key = routeKey(a, b);
  if (memo[key]) return Promise.resolve(memo[key]);
  if (meters(a, b) <= ROUTE_WALK_METERS) {
    return Promise.resolve([{ mode: 'walk', points: [[a.lat, a.lon], [b.lat, b.lon]] }]);
  }
  if (!transitUrl) return Promise.resolve(null);
  if (pending[key]) return pending[key];

  const params = new URLSearchParams({
    from: `${Number(a.lat).toFixed(6)},${Number(a.lon).toFixed(6)}`,
    to: `${Number(b.lat).toFixed(6)},${Number(b.lon).toFixed(6)}`,
  });

  pending[key] = fetch(`${transitUrl}?${params}`, { credentials: 'same-origin' })
    .then((r) => r.json())
    .then((data) => {
      const segs = data && data.success && data.route && Array.isArray(data.route.segments) && data.route.segments.length
        ? data.route.segments
        : null;
      if (segs) { memo[key] = segs; saveMemo(); }
      return segs;
    })
    .catch(() => null)
    .then((segs) => { delete pending[key]; return segs; });

  return pending[key];
}
