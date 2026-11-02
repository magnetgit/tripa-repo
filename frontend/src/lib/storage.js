// 대화 보관 (새로고침해도 대화 유지). 회원마다 칸을 따로 둔다.
// 기존 여행 만들기 화면과 같은 이름·모양이라, 두 화면이 같은 대화를 이어서 볼 수 있다.
import { emptyDraft } from './util.js';

const storeKey = (member) => `tripa_chat_v2_${member}`;

const isMessage = (m) =>
  m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string';
const isRemoved = (r) => r && typeof r.day === 'number' && typeof r.name === 'string';

function cleanOrder(raw) {
  const out = {};
  if (!raw || typeof raw !== 'object') return out;
  Object.keys(raw).forEach((k) => {
    if (!/^\d{1,2}$/.test(k) || !Array.isArray(raw[k])) return;
    const names = raw[k].filter((n) => typeof n === 'string' && n);
    if (names.length) out[k] = names;
  });
  return out;
}

// 저장된 대화가 있으면 상태 조각을, 없으면 null
export function loadChat(member) {
  try {
    sessionStorage.removeItem('tripa_chat_v1'); // 예전 공용 칸 정리
    const raw = sessionStorage.getItem(storeKey(member));
    if (!raw) return null;
    const saved = JSON.parse(raw);
    if (!saved || !Array.isArray(saved.messages) || !saved.draft) return null;
    const messages = saved.messages.filter(isMessage);
    if (!messages.length) return null;
    return {
      messages,
      draft: { ...emptyDraft(), ...saved.draft },
      missing: Array.isArray(saved.missing) ? saved.missing : null,
      ready: !!saved.ready,
      plan: saved.plan && Array.isArray(saved.plan.days) ? saved.plan : null,
      removed: Array.isArray(saved.removed) ? saved.removed.filter(isRemoved) : [],
      order: cleanOrder(saved.order),
    };
  } catch {
    return null;
  }
}

export function saveChat(member, state) {
  try {
    sessionStorage.setItem(
      storeKey(member),
      JSON.stringify({
        messages: state.messages.filter((m) => !m.error).slice(-40),
        draft: state.draft,
        missing: state.missing,
        ready: state.ready,
        plan: state.plan,
        removed: state.removed,
        order: state.order,
      }),
    );
  } catch {
    /* 저장이 안 돼도 동작에는 문제 없음 */
  }
}

export function clearChat(member) {
  try { sessionStorage.removeItem(storeKey(member)); } catch { /* 무시 */ }
}
