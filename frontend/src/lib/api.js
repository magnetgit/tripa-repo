// 서버와 이야기하는 곳은 이 파일 하나에 모아 둔다.
// 나중에 /api/chat/ (mock.json 모양)으로 바꿀 때 이 파일만 고치면 되게.

// JSON 으로 POST 하고, 응답에 HTTP 상태 코드를 붙여 돌려준다.
export function postJson(url, body, csrf) {
  return fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
    body: JSON.stringify(body),
  }).then((res) =>
    res
      .json()
      .catch(() => ({ ok: false, error: '서버 응답을 읽지 못했어요.' }))
      .then((data) => ({ ...data, status: res.status })),
  );
}

// 대화 한 번: 지난 대화 + 지금 초안 → AI 답변·새 초안
export function sendChat(cfg, messages, draft) {
  return postJson(cfg.chatUrl, { messages, draft }, cfg.csrf);
}

// 일정 미리보기 (날짜별 타임라인)
export function fetchPreview(cfg, draft, removed, order) {
  return postJson(cfg.previewUrl, { draft, removed, order }, cfg.csrf);
}

// '이 일정 적용하기' → 여행 저장
export function applyPlan(cfg, draft, removed, order) {
  return postJson(cfg.applyUrl, { draft, removed, order }, cfg.csrf);
}

// 만들어진 여행에 담아 둔 장소 하나 넣기 (일정 상세의 '장소 추가'와 같은 주소, 폼 방식)
export function addPlaceToSchedule(cfg, fields) {
  return fetch(cfg.addUrl, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': cfg.csrf, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(fields).toString(),
  }).then(
    (res) =>
      res
        .json()
        .catch(() => ({ success: false }))
        .then((j) => res.ok && !!j.success),
    () => false,
  );
}
