// 예산 분류 (서버 travel_budget 분류 키 · 비용 관리 화면과 같은 이름·색)
export const CATS = [
  { key: 'sight', name: '관광지', color: '#2d6cdf', icon: 'landmark' },
  { key: 'food', name: '식비', color: '#f0a03c', icon: 'utensils' },
  { key: 'cafe', name: '카페', color: '#a9744f', icon: 'cup' },
  { key: 'move', name: '교통', color: '#7a8cf0', icon: 'bus' },
  { key: 'stay', name: '숙박', color: '#2fb59b', icon: 'bed' },
  { key: 'shop', name: '쇼핑', color: '#e46b9b', icon: 'bag' },
  { key: 'etc', name: '기타', color: '#9aa5b8', icon: 'card' },
];

// 더 싼 대안을 찾을 수 있는 분류 (서버 budget_service.ALT_SEARCH 와 같게)
export const ALT_CATS = ['food', 'stay', 'sight', 'shop'];

export const won = (n) => `${Number(n || 0).toLocaleString('ko-KR')}원`;

export const distText = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${m}m`);
