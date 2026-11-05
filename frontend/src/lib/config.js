// Django 페이지(chat.html)의 #root 에 달린 data- 속성에서 설정을 읽는다.
// 개발 서버(npm run dev, 5173)에서는 data- 속성이 없으니 기본 주소를 쓴다. (Vite proxy 가 8000 으로 넘김)

function csrfFromCookie() {
  const found = document.cookie.split('; ').find((p) => p.startsWith('csrftoken='));
  return found ? decodeURIComponent(found.slice('csrftoken='.length)) : '';
}

export function readConfig(root) {
  const ds = root.dataset;
  const tokenInput = root.querySelector('input[name="csrfmiddlewaretoken"]');

  return {
    chatUrl: ds.chatUrl || '/travel_chat/',
    applyUrl: ds.applyUrl || '/travel_chat_apply/',
    addUrl: ds.addUrl || '/schedule_place_add/',
    previewUrl: ds.previewUrl || '/travel_chat_preview/',
    estimateUrl: ds.estimateUrl || '/budget_estimate/',
    loginUrl: ds.loginUrl || '/login/',
    manualUrl: ds.manualUrl || '/travel_create/?mode=manual',
    member: ds.member || 'guest',
    odsayKey: ds.odsayKey || '',
    sprite: ds.sprite || '/static/sherpaapp/icons/icons.svg?v=5',
    // 템플릿의 {% csrf_token %} 값이 있으면 그걸, 없으면(개발 서버) 쿠키에서
    csrf: tokenInput ? tokenInput.value : csrfFromCookie(),
  };
}
