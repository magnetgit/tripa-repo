// 지도 위 장소 팝업 카드 (추천 카드를 누르면 지도에 뜸)
// 카카오 CustomOverlay 에 넣을 DOM 을 만든다. 글자는 textContent 로만 넣음 (innerHTML 사용 안 함)
// travel_chat.js·travel_detail.html 에도 같은 모양(.tc-mappop)으로 있음

// 추천 카드 item → 팝업에 보여 줄 값 (없는 값은 빼고)
export function recPopupInfo(item) {
  const lines = [];
  if (item.addr) lines.push(item.addr);
  if (item.pick && item.pick.hours) lines.push(`영업 ${item.pick.hours}`);
  else if (item.open && item.open.closed) lines.push('오늘 휴무');
  return {
    name: item.name,
    kind: item.kind || '',
    lines,
    rating: item.review && item.review.count
      ? `★ ${Number(item.review.rating).toFixed(1)} · 리뷰 ${item.review.count}개` : '',
    photo: item.photo && item.photo.url ? item.photo.url : '',
  };
}

// 일정 미리보기 한 줄 → 팝업 값 (도착·출발 시각, 주소, 운영시간)
export function planPopupInfo(it, order) {
  const time = [it.arrive && `${it.arrive} 도착`, !it.is_stay && it.leave && `${it.leave} 출발`].filter(Boolean).join(' · ');
  const lines = [];
  if (time) lines.push(time);
  if (it.addr) lines.push(it.addr);
  if (it.hours && it.hours.open && it.hours.close) lines.push(`영업 ${it.hours.open}~${it.hours.close}`);
  return {
    name: order ? `${order}. ${it.name}` : it.name,
    kind: it.is_stay ? '숙소 체크인' : it.kind || '',
    lines,
    rating: '',
    photo: it.photo && it.photo.url ? it.photo.url : '',
  };
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

// 작은 핀 (팝업을 닫으면 이걸로 바뀜)
export function focusPinEl(name) {
  const wrap = el('div', 'tc-mappin tc-mappin--focus');
  wrap.append(el('span', 'tc-mappin__label', name), el('span', 'tc-mappin__dot'));
  return wrap;
}

// 팝업 카드: [사진] 이름·종류 / 주소·영업 / 평점 + × 닫기
export function popupEl(info, onClose) {
  const wrap = el('div', 'tc-mappop');
  const card = el('div', 'tc-mappop__card');

  if (info.photo) {
    const img = el('img', 'tc-mappop__photo');
    img.src = info.photo;
    img.alt = '';
    img.referrerPolicy = 'no-referrer';
    img.onerror = () => img.remove();   // 사진을 못 불러오면 사진 칸 없이
    card.append(img);
  }

  const body = el('div', 'tc-mappop__body');
  body.append(el('strong', 'tc-mappop__name', info.name));
  if (info.kind) body.append(el('span', 'tc-mappop__kind', info.kind));
  info.lines.forEach((t) => body.append(el('span', 'tc-mappop__line', t)));
  if (info.rating) body.append(el('span', 'tc-mappop__rating', info.rating));
  card.append(body);

  const close = el('button', 'tc-mappop__close', '×');
  close.type = 'button';
  close.setAttribute('aria-label', '닫기');
  // 지도 끌기·클릭으로 넘어가지 않게 막고 닫기
  close.addEventListener('mousedown', (e) => e.stopPropagation());
  close.addEventListener('click', (e) => { e.stopPropagation(); onClose(); });
  card.append(close);

  wrap.append(card, el('span', 'tc-mappop__tail'), el('span', 'tc-mappop__dot'));
  return wrap;
}
