// AI와 여행 만들기 (React 버전)
// 화면 3칸: 대화 / 일정 초안 / 지도
// - 서버(/travel_chat/)가 AI 답변과 '검증된 일정 초안'을 돌려준다. (기존 화면과 같은 진짜 AI 주소)
// - 상태(state)는 여기 한 곳에서 관리하고, 각 칸은 받은 상태를 그리기만 한다.
// - AI가 보낸 글자는 React 가 글자로만 넣는다. (HTML 로 해석하지 않음)
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import ChatPanel from './components/ChatPanel.jsx';
import DraftPanel from './components/DraftPanel.jsx';
import MapPanel from './components/MapPanel.jsx';
import { addPlaceToSchedule, applyPlan, fetchPreview, sendChat } from './lib/api.js';
import { isPlanFresh, orderList, planSig, removedKey, isGone, dayItems } from './lib/plan.js';
import { clearChat, loadChat, saveChat } from './lib/storage.js';
import { MAX_PINS, MAX_SEND, REQUIRED, WELCOME, dayToIso, emptyDraft, tripDays } from './lib/util.js';

const PLACEHOLDER = '여행 이야기를 편하게 적어 주세요';

function freshState() {
  return {
    messages: [],
    draft: emptyDraft(),
    missing: REQUIRED.slice(),
    ready: false,
    notes: [],
    busy: false,
    plan: null,        // {sig, rkey, days, transport} 서버가 만들어 준 일정 미리보기
    removed: [],       // 미리보기에서 지운 장소 [{day, name}]
    order: {},         // 미리보기에서 바꾼 순서 {일차: [장소 이름...]}
    planBusy: false,
    planError: '',
    dayTab: 0,
    changed: [],       // 이번에 바뀐 초안 칸 이름 (반짝임 표시)
    changeTick: 0,
  };
}

// 처음 화면: 저장된 대화가 있으면 이어서, 없으면 인사말부터
function startState(cfg, allowRestore) {
  const base = freshState();
  const saved = allowRestore ? loadChat(cfg.member) : null;
  if (saved) return { ...base, ...saved, missing: saved.missing || base.missing };
  return { ...base, messages: [{ role: 'assistant', content: WELCOME, local: true }] };
}

export default function App({ cfg }) {
  const [state, setState] = useState(() => startState(cfg, true));
  const [input, setInput] = useState('');
  const [placeholder, setPlaceholder] = useState(PLACEHOLDER);
  const [applyLabel, setApplyLabel] = useState('');   // 적용 중 버튼 글자
  const [applyLink, setApplyLink] = useState('');     // 경고가 있을 때 '만들어진 여행 보러 가기'

  // 비동기(서버 응답) 안에서 '지금' 상태를 읽기 위한 거울
  const stateRef = useRef(state);
  useLayoutEffect(() => { stateRef.current = state; }, [state]);
  const inputRef = useRef(null);
  const draftBodyRef = useRef(null);
  const errorSigRef = useRef('');
  const hadPlanRef = useRef(!!state.plan);

  const update = useCallback((fn) => setState((prev) => ({ ...prev, ...fn(prev) })), []);

  // 대화·초안이 바뀌면 브라우저에 보관 (새로고침해도 유지)
  useEffect(() => {
    saveChat(cfg.member, state);
  }, [cfg.member, state.messages, state.draft, state.missing, state.ready, state.plan, state.removed, state.order]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---------- 대화 보내기 ---------- */

  const send = useCallback((raw) => {
    const text = (raw || '').trim();
    const cur = stateRef.current;
    if (!text || cur.busy) return;

    const messages = [...cur.messages, { role: 'user', content: text }];
    const history = messages.filter((m) => !m.local).slice(-MAX_SEND).map((m) => ({ role: m.role, content: m.content }));
    update(() => ({ messages, busy: true, notes: [], changed: [] }));
    setInput('');

    const fail = (msg) =>
      update((prev) => ({
        busy: false,
        // 실패한 메시지는 되돌려서 다시 보낼 수 있게 한다
        messages: [...prev.messages.slice(0, -1), { role: 'assistant', content: msg, error: true, local: true }],
      }));

    sendChat(cfg, history, cur.draft).then(
      (data) => {
        if (!data.ok) {
          setInput(text);
          fail(data.login ? '로그인이 풀렸어요. 다시 로그인한 뒤 이어서 해 주세요.' : data.error || '대화를 처리하지 못했어요.');
          return;
        }
        update((prev) => ({
          busy: false,
          draft: { ...emptyDraft(), ...data.draft },
          missing: data.missing || [],
          ready: !!data.ready,
          notes: data.notes || [],
          messages: [...prev.messages, { role: 'assistant', content: data.reply, rec: data.recommendation || null }],
          changed: data.changed || [],
          changeTick: prev.changeTick + 1,
        }));
      },
      () => {
        setInput(text);
        fail('네트워크에 문제가 있어요. 연결을 확인하고 다시 보내 주세요.');
      },
    );
  }, [cfg, update]);

  /* ---------- 일정 미리보기 ---------- */

  const fetchPlan = useCallback(() => {
    const cur = stateRef.current;
    if (cur.planBusy || !cur.ready) return;

    const sig = planSig(cur.draft);
    const rkey = removedKey(cur.removed, cur.order);
    update(() => ({ planBusy: true, planError: '' }));

    fetchPreview(cfg, cur.draft, cur.removed, orderList(cur.order)).then(
      (data) => {
        if (data.ok && Array.isArray(data.days)) {
          errorSigRef.current = '';
          update(() => ({ planBusy: false, plan: { sig, rkey, days: data.days, transport: data.transport || '' } }));
        } else {
          errorSigRef.current = sig; // 같은 초안으로는 저절로 다시 부르지 않음 ('다시 만들기'로만)
          update(() => ({
            planBusy: false,
            planError: data.login ? '로그인이 풀렸어요. 다시 로그인한 뒤 이어서 해 주세요.' : data.error || '일정 미리보기를 만들지 못했어요.',
          }));
        }
      },
      () => {
        errorSigRef.current = sig;
        update(() => ({ planBusy: false, planError: '네트워크에 문제가 있어요. 다시 시도해 주세요.' }));
      },
    );
  }, [cfg, update]);

  // 초안이 바뀌면(말이 오가는 중엔 0.5초 기다렸다가) 한 번만 새로 만든다
  const sig = planSig(state.draft);
  const fresh = isPlanFresh(state);
  useEffect(() => {
    if (!state.ready || fresh || state.planBusy || errorSigRef.current === sig) return undefined;
    const t = setTimeout(fetchPlan, 500);
    return () => clearTimeout(t);
  }, [sig, state.ready, fresh, state.planBusy, fetchPlan]);

  // 지우거나 순서를 바꾸면 0.9초 기다렸다가 시간을 다시 계산한다 (연달아 바꿀 수 있으니)
  const rkey = removedKey(state.removed, state.order);
  useEffect(() => {
    if (!state.ready || !fresh || state.planBusy || !state.plan || state.plan.rkey === rkey) return undefined;
    const t = setTimeout(fetchPlan, 900);
    return () => clearTimeout(t);
  }, [rkey, state.ready, fresh, state.planBusy, state.plan, fetchPlan]);

  // 처음 일정이 나오면 일정 미리보기가 보이도록 초안 칸을 아래로 내려 준다
  useEffect(() => {
    if (!state.plan || hadPlanRef.current) return;
    hadPlanRef.current = true;
    const box = draftBodyRef.current;
    const section = box && box.querySelector('.tc-plan');
    if (box && section && typeof box.scrollTo === 'function') {
      box.scrollTo({ top: Math.max(section.offsetTop - box.offsetTop - 8, 0), behavior: 'smooth' });
    }
  }, [state.plan]);

  /* ---------- 추천 카드에서 담기 / 초안에서 빼기 ---------- */

  const addPin = useCallback((item, day, time) => update((prev) => {
    const pins = prev.draft.pins || [];
    if (prev.busy || pins.some((p) => p.day === day && p.name === item.name)) return {};
    if (pins.length >= MAX_PINS) return { notes: [`담을 수 있는 장소는 최대 ${MAX_PINS}곳이에요.`] };
    const pin = { day, name: item.name, addr: item.addr, kind: item.kind, lat: item.lat, lon: item.lon, phone: item.phone, url: item.url, time: time || null };
    return { draft: { ...prev.draft, pins: [...pins, pin] }, notes: [], changed: ['추가한 장소'], changeTick: prev.changeTick + 1 };
  }), [update]);

  const addStay = useCallback((item, day) => update((prev) => {
    const n = tripDays(prev.draft);
    if (prev.busy || !n || day >= n) return {};
    const iso = dayToIso(prev.draft.start, day);
    const stays = (prev.draft.stays || []).filter((s) => s.date !== iso);
    stays.push({ date: iso, query: item.name, name: item.name, addr: item.addr, lat: item.lat, lon: item.lon, arrival_time: null, departure_time: null });
    stays.sort((a, b) => (a.date < b.date ? -1 : 1));
    return { draft: { ...prev.draft, stays }, notes: [], changed: ['숙소'], changeTick: prev.changeTick + 1 };
  }), [update]);

  const removeStay = useCallback((index) => update((prev) => (prev.busy ? {} : {
    draft: { ...prev.draft, stays: (prev.draft.stays || []).filter((s, i) => i !== index) }, changed: [],
  })), [update]);

  const removePin = useCallback((index) => update((prev) => (prev.busy ? {} : {
    draft: { ...prev.draft, pins: (prev.draft.pins || []).filter((p, i) => i !== index) }, changed: [],
  })), [update]);

  /* ---------- 미리보기에서 순서 바꾸기 · 지우기 ---------- */

  const moveItem = useCallback((day, from, to) => update((prev) => {
    const names = dayItems(prev, day).map((it) => it.name);
    if (from === to || from < 0 || to < 0 || from >= names.length || to >= names.length) return {};
    const moved = names.splice(from, 1)[0];
    names.splice(to, 0, moved);
    return { order: { ...prev.order, [day.day]: names } };
  }), [update]);

  const resetOrder = useCallback((day) => update((prev) => {
    const order = { ...prev.order };
    delete order[day.day];
    return { order };
  }), [update]);

  const removeItem = useCallback((day, it) => {
    if (it.pin) {
      const idx = (stateRef.current.draft.pins || []).findIndex((p) => p.day === day.day && p.name === it.name);
      if (idx > -1) removePin(idx);
      return;
    }
    update((prev) => (isGone(prev.removed, day, it) ? {} : { removed: [...prev.removed, { day: day.day, name: it.name }] }));
  }, [update, removePin]);

  const restoreDay = useCallback((day) => update((prev) => ({ removed: prev.removed.filter((r) => r.day !== day.day) })), [update]);

  const refreshPlan = useCallback(() => {
    errorSigRef.current = '';
    update(() => ({ planError: '' }));
    setTimeout(fetchPlan, 0);
  }, [update, fetchPlan]);

  /* ---------- 이 일정 적용하기 ---------- */

  // 만들어진 여행의 날짜별 일정에, 대화에서 담아 둔 장소를 하나씩 넣는다 (실패한 이름 목록을 돌려줌)
  const addPins = useCallback(async (data) => {
    const failed = [];
    for (const p of data.pins || []) {
      const fields = {
        travel_id: data.travel_id, s_day: dayToIso(data.start, p.day), place_name: p.name,
        place_addr: p.addr || '', place_kind: p.kind || '', place_lat: p.lat, place_lon: p.lon,
      };
      if (p.time) fields.arrive_time = p.time;
      const ok = await addPlaceToSchedule(cfg, fields);
      if (!ok) failed.push(p.name);
    }
    return failed;
  }, [cfg]);

  const apply = useCallback(() => {
    const cur = stateRef.current;
    if (!cur.ready || cur.busy) return;

    update(() => ({ busy: true }));
    setApplyLabel('일정을 만드는 중...');

    const fail = (msg) => {
      update((prev) => ({ busy: false, messages: [...prev.messages, { role: 'assistant', content: msg, error: true, local: true }] }));
      setApplyLabel('');
    };

    applyPlan(cfg, cur.draft, cur.removed, orderList(cur.order)).then(
      async (data) => {
        if (!data.ok) { fail(data.error || '일정을 만들지 못했어요.'); return; }
        clearChat(cfg.member);
        if ((data.pins || []).length) setApplyLabel('장소를 일정에 담는 중...');
        const failed = await addPins(data);
        let warning = data.warning;
        if (failed.length) {
          warning = `${warning ? `${warning} ` : ''}일정에 넣지 못한 장소가 있어요: ${failed.join(', ')} (상세 화면에서 직접 추가해 주세요)`;
        }
        if (warning) {
          fail(warning);
          setApplyLink(data.url);
          return;
        }
        window.location.href = data.url;
      },
      () => fail('네트워크에 문제가 있어요. 다시 시도해 주세요.'),
    );
  }, [cfg, update, addPins]);

  /* ---------- 그 밖의 버튼 ---------- */

  const onEdit = useCallback(() => {
    setPlaceholder('바꾸고 싶은 내용을 말해 주세요. 예) 숙소는 해운대 쪽으로 바꿔줘');
    const el = inputRef.current;
    if (el) {
      el.focus();
      if (window.matchMedia('(max-width: 859px)').matches) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  const onReset = useCallback(() => {
    if (stateRef.current.busy) return;
    clearChat(cfg.member);
    hadPlanRef.current = false;
    errorSigRef.current = '';
    setState(startState(cfg, false));
    setPlaceholder(PLACEHOLDER);
    setApplyLabel('');
    setApplyLink('');
  }, [cfg]);

  return (
    <>
      <ChatPanel
        state={state} sprite={cfg.sprite}
        input={input} setInput={setInput} placeholder={placeholder} inputRef={inputRef}
        onSend={send} onReset={onReset} onAddPin={addPin} onAddStay={addStay}
      />
      <DraftPanel
        ref={draftBodyRef}
        state={state} sprite={cfg.sprite} manualUrl={cfg.manualUrl}
        applyLabel={applyLabel} applyLink={applyLink}
        onRemoveStay={removeStay} onRemovePin={removePin} onApply={apply} onEdit={onEdit}
        plan={{
          onTab: (i) => update(() => ({ dayTab: i })),
          onMove: moveItem, onRemove: removeItem, onResetOrder: resetOrder, onRestore: restoreDay, onRefresh: refreshPlan,
        }}
      />
      <MapPanel state={state} sprite={cfg.sprite} odsayKey={cfg.odsayKey} />
    </>
  );
}
