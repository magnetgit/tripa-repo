// 날짜·금액 같은 작은 도우미 (기존 travel_chat.js 와 같은 규칙)

export const WEEK = ['일', '월', '화', '수', '목', '금', '토'];
export const TRANSPORT = { car: '자동차', walk: '도보', public_transport: '대중교통', bike: '자전거' };
export const MAX_SEND = 14;   // AI 에 보내는 최근 대화 수
export const MAX_PINS = 12;   // 대화에서 담을 수 있는 장소 수
export const REQUIRED = ['여행 지역', '출발일', '종료일', '여행 컨셉'];

export const WELCOME =
  '안녕하세요! 어디로, 언제쯤 떠나고 싶으세요? 편하게 말씀해 주세요. 예를 들면 "제주도 2박 3일, 맛집 위주로 가고 싶어요" 처럼요.';

export const EXAMPLES = ['제주 2박 3일 맛집 여행', '부산 당일치기', '강릉 1박 2일 바다 위주로', '서울 3박 4일 커플 여행'];

export function emptyDraft() {
  return {
    place: null, title: null, start: null, end: null, people: null,
    budget_style: null, budget_total: null, transport: null, categories: [],
    start_time: null, start_place: null, stays: [], center: null, pins: [],
  };
}

export function parseDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}

export function shortDate(iso) {
  const d = parseDate(iso);
  if (!d) return '';
  return `${d.getMonth() + 1}/${d.getDate()}(${WEEK[d.getDay()]})`;
}

export function dateText(draft) {
  if (!draft.start && !draft.end) return '';
  if (draft.start && !draft.end) return `${shortDate(draft.start)} 출발 · 종료일 미정`;
  if (!draft.start && draft.end) return `출발일 미정 · ${shortDate(draft.end)} 종료`;
  const nights = Math.round((parseDate(draft.end) - parseDate(draft.start)) / 86400000);
  const span = nights === 0 ? '당일치기' : `${nights}박 ${nights + 1}일`;
  return `${shortDate(draft.start)} ~ ${shortDate(draft.end)} · ${span}`;
}

export function won(n) {
  return `${Number(n).toLocaleString('ko-KR')}원`;
}

const pad2 = (n) => String(n).padStart(2, '0');

export function dayToIso(startIso, day) {
  const d = parseDate(startIso);
  d.setDate(d.getDate() + day - 1);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

// 여행 일수 (날짜가 없으면 0)
export function tripDays(draft) {
  const a = parseDate(draft.start);
  const b = parseDate(draft.end);
  if (!a || !b) return 0;
  return Math.round((b - a) / 86400000) + 1;
}
