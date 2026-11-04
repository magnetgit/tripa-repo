// 2) 일정 초안 칸: 지역·날짜·인원·숙소·출발·예산·컨셉·이동수단·담은 장소 + 일정 미리보기 + 적용 버튼
import { forwardRef } from 'react';
import Icon from './Icon.jsx';
import PlanPreview from './PlanPreview.jsx';
import { TRANSPORT, dateText, dayToIso, shortDate, tripDays, won } from '../lib/util.js';

// 한 줄. 이번 대화로 바뀐 칸은 is-new 로 잠깐 반짝임 (tick 이 바뀌면 다시 반짝이도록 key 에 넣음)
function Row({ rowKey, icon, label, filled, isNew, sprite, children }) {
  return (
    <div
      className={`tc-row${filled ? '' : ' is-empty'}${isNew ? ' is-new' : ''}`}
      data-row={rowKey}
    >
      <dt><Icon name={icon} sprite={sprite} /><span>{label}</span></dt>
      <dd className="tc-val">{filled ? children : <span className="tc-empty">아직 정해지지 않았어요</span>}</dd>
    </div>
  );
}

const DraftPanel = forwardRef(function DraftPanel(
  { state, sprite, manualUrl, applyLabel, applyLink, onRemoveStay, onRemovePin, onApply, onEdit, plan },
  bodyRef,
) {
  const d = state.draft;
  const changed = state.changed || [];
  const isNew = (label) => changed.includes(label);
  const tick = state.changeTick;
  // 바뀐 칸은 key 를 바꿔서 새로 그림 → 반짝임 애니메이션이 매번 다시 나옴
  const rk = (k, label) => (isNew(label) ? `${k}-${tick}` : k);

  // 숙소: '잠자는 밤'마다 하나만 필요 (1박 2일이면 첫날 밤 하나, 마지막 날은 없음)
  const nTrip = tripDays(d);
  let stayFilled = (d.stays || []).length > 0;
  let stayNote = null;
  if (nTrip === 1) {
    stayNote = <span className="tc-sub">당일치기라 숙소가 필요 없어요</span>;
    stayFilled = true;
  } else if (nTrip > 1 && stayFilled) {
    const booked = {};
    (d.stays || []).forEach((s) => { booked[s.date] = true; });
    const open = [];
    for (let k = 1; k < nTrip; k++) {
      const iso = dayToIso(d.start, k);
      if (!booked[iso]) open.push(shortDate(iso));
    }
    if (open.length) stayNote = <span className="tc-sub tc-stays__open">{open.join(', ')} 숙소는 아직 미정</span>;
  }

  const sp = d.start_place;
  const budgetText = d.budget_total ? `총 ${won(d.budget_total)}` : ''; // 예산은 총예산만 (성향은 회의에서 없앰)
  const done = 4 - state.missing.length;

  return (
    <section className="tc-panel tc-draft" aria-label="일정 초안">
      <header className="tc-panel__head">
        <h2><Icon name="calendar" sprite={sprite} /> 일정 초안</h2>
        <span className="tc-panel__sub">적용 전 미리보기</span>
      </header>

      <div className="tc-draft__body" ref={bodyRef}>
        <p className="tc-draft__title">{d.title || '새 여행'}</p>

        <div className="tc-progress" aria-hidden="true">
          <span style={{ width: `${Math.round((done / 4) * 100)}%` }} />
        </div>
        <p className="tc-progress__text">
          <strong>{state.ready ? '필수 정보를 모두 모았어요' : `필수 정보 ${done}/4`}</strong>{' '}
          <span>
            {applyLink ? (
              <a className="tc-go" href={applyLink}>만들어진 여행 보러 가기</a>
            ) : state.ready ? '' : `남은 항목: ${state.missing.join(', ')}`}
          </span>
        </p>

        <ul className="tc-notes" hidden={!(state.notes || []).length}>
          {(state.notes || []).map((n, i) => <li key={i}>{n}</li>)}
        </ul>

        <dl className="tc-rows">
          <Row key={rk('place', '지역')} rowKey="place" icon="pin" label="지역" filled={!!d.place} isNew={isNew('지역')} sprite={sprite}>
            {d.place}
          </Row>
          <Row key={rk('date', '날짜')} rowKey="date" icon="calendar" label="날짜" filled={!!(d.start || d.end)} isNew={isNew('날짜')} sprite={sprite}>
            {dateText(d)}
          </Row>
          <Row key={rk('people', '인원')} rowKey="people" icon="users" label="인원" filled={!!d.people} isNew={isNew('인원')} sprite={sprite}>
            {d.people ? `${d.people}명` : ''}
          </Row>
          <Row key={rk('stay', '숙소')} rowKey="stay" icon="bed" label="숙소" filled={stayFilled} isNew={isNew('숙소')} sprite={sprite}>
            <span className="tc-stays">
              {(d.stays || []).map((s, i) => (
                <span className="tc-stay" key={`${s.date}-${i}`}>
                  <span className="tc-stay__date">{shortDate(s.date)}</span>
                  {s.name || s.query}
                  {s.arrival_time && <span className="tc-sub"> · {s.arrival_time} 도착</span>}
                  {s.lat == null && <span className="tc-warn"> (위치 못 찾음)</span>}
                  <button type="button" className="tc-x" aria-label={`${s.name || s.query} 빼기`} onClick={() => onRemoveStay(i)}>×</button>
                </span>
              ))}
              {stayNote}
            </span>
          </Row>
          <Row key={rk('start', '출발지')} rowKey="start" icon="flag" label="출발" filled={!!sp} isNew={isNew('출발지')} sprite={sprite}>
            {sp && (
              <span>
                {sp.name || sp.query}
                {d.start_time && <span className="tc-sub"> · {d.start_time} 출발</span>}
                {sp.lat == null && <span className="tc-warn"> (위치 못 찾음)</span>}
              </span>
            )}
          </Row>
          <Row key={rk('budget', '예산')} rowKey="budget" icon="wallet" label="예산" filled={!!budgetText} isNew={isNew('예산')} sprite={sprite}>
            {budgetText}
          </Row>
          <Row key={rk('concept', '컨셉')} rowKey="concept" icon="tag" label="컨셉" filled={(d.categories || []).length > 0} isNew={isNew('컨셉')} sprite={sprite}>
            <span className="tc-chips">
              {(d.categories || []).map((c) => <span className="tc-chip" key={c}>{c}</span>)}
            </span>
          </Row>
          <Row key={rk('transport', '이동수단')} rowKey="transport" icon="route" label="이동수단" filled={!!TRANSPORT[d.transport]} isNew={isNew('이동수단')} sprite={sprite}>
            {TRANSPORT[d.transport] || ''}
          </Row>
          <Row key={rk('pins', '추가한 장소')} rowKey="pins" icon="pin" label="담은 장소" filled={(d.pins || []).length > 0} isNew={isNew('추가한 장소')} sprite={sprite}>
            <span className="tc-stays">
              {(d.pins || []).map((p, i) => (
                <span className="tc-stay" key={`${p.day}-${p.name}-${i}`}>
                  <span className="tc-stay__date">{p.day}일차</span>
                  {p.name}
                  {p.time && <span className="tc-sub"> · {p.time}</span>}
                  <button type="button" className="tc-x" aria-label={`${p.name} 빼기`} onClick={() => onRemovePin(i)}>×</button>
                </span>
              ))}
            </span>
          </Row>
        </dl>

        <PlanPreview state={state} sprite={sprite} {...plan} />
      </div>

      <footer className="tc-draft__foot">
        <button type="button" className="tc-btn tc-btn--primary" disabled={!state.ready || state.busy} onClick={onApply}>
          {applyLabel ? applyLabel : <><Icon name="check" sprite={sprite} /> 이 일정 적용하기</>}
        </button>
        <button type="button" className="tc-btn tc-btn--ghost" onClick={onEdit}>
          <Icon name="chat" sprite={sprite} /> 채팅으로 고치기
        </button>
      </footer>
    </section>
  );
});

export default DraftPanel;
