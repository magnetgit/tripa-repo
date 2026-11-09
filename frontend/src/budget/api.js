// 비용 관리(카테고리 예산) 화면이 쓰는 서버 주소 (주소는 category_budget.html 의 #root data- 속성에서 읽음)

export function readBudgetConfig(root) {
  const ds = root.dataset;
  const token = root.querySelector('input[name="csrfmiddlewaretoken"]');
  let travels;
  try {
    travels = JSON.parse(document.getElementById('cbTravels')?.textContent || '[]');
  } catch {
    travels = [];
  }
  return {
    travelId: Number(ds.travelId),
    title: ds.travelTitle || '',
    place: ds.travelPlace || '',
    dates: ds.travelDates || '',
    categoryUrl: ds.categoryUrl,
    altUrl: ds.altUrl,
    swapUrl: ds.swapUrl,
    detailUrl: ds.detailUrl,
    sprite: ds.sprite,
    csrf: token ? token.value : '',
    travels,
  };
}

async function readJson(res) {
  const data = await res.json().catch(() => null);
  if (!res.ok || !data || data.success === false) {
    throw new Error((data && data.message) || '서버에서 답을 받지 못했어요.');
  }
  return data;
}

// GET → {total, limit, by, plan, counts, people}
export async function fetchBudget(cfg) {
  const res = await fetch(`${cfg.categoryUrl}?plan=1`, { credentials: 'same-origin' });
  return (await readJson(res)).budget;
}

// POST {limit: {분류: 금액}, items: {sp_id: 금액 | null(AI 금액으로)}, total: 총예산} → 저장 후 {total, limit, by}
export async function saveLimits(cfg, limit, items = {}, total = null) {
  const res = await fetch(cfg.categoryUrl, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf },
    body: JSON.stringify(total == null ? { limit, items } : { limit, items, total }),
  });
  return (await readJson(res)).budget;
}

// 분류 하나의 더 싼 대안 → [{sp_id, day, name, cat, amount, options: [...]}]
export async function fetchAlternatives(cfg, cat) {
  const res = await fetch(`${cfg.altUrl}?cat=${encodeURIComponent(cat)}`, { credentials: 'same-origin' });
  return (await readJson(res)).suggestions || [];
}

// 일정의 그 자리 장소를 대안으로 바꾸기
export async function swapPlace(cfg, spId, option) {
  const body = new URLSearchParams({
    sp_id: spId, name: option.name, addr: option.addr || '', kind: option.kind || '',
    lat: option.lat, lon: option.lon, kakao_id: option.kakao_id || '',
  });
  const res = await fetch(cfg.swapUrl, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': cfg.csrf },
    body,
  });
  return readJson(res);
}
