// 일정 미리보기: 일차 탭 + 날짜별 타임라인 (순서 바꾸기·삭제·끌어서 옮기기)
import { useState } from 'react';
import Icon from './Icon.jsx';
import { dayItems, isPlanFresh, removedKey } from '../lib/plan.js';
import { PlaceTag, costText } from './RecCards.jsx';
import { planPopupInfo } from '../lib/mapPopup.js';

// 날씨 표시 (days[].weather: kind sun/cloud/rain/snow, temp, rainy)
const WX_MARK = { sun: '☀', cloud: '☁', rain: '☔', snow: '❄' };
const wxText = (w) => `${WX_MARK[w.kind] || '☁'}${w.temp != null ? ` ${w.temp}°` : ''}`;

function Msg({ text, loading, error }) {
  return (
    <div className="tc-plan__body" aria-live="polite">
      <p className={`tc-plan__msg${loading ? ' is-loading' : ''}${error ? ' is-error' : ''}`}>{text}</p>
    </div>
  );
}

export default function PlanPreview({
  state, sprite, onTab, onMove, onRemove, onResetOrder, onRestore, onRefresh, focus, onFocusPlace,
}) {
  const [dragFrom, setDragFrom] = useState(-1);
  const [overIndex, setOverIndex] = useState(-1);

  const head = (
    <div className="tc-plan__head">
      <h3><Icon name="route" sprite={sprite} /> 일정 미리보기</h3>
      <button type="button" className="tc-link" hidden={!state.ready || state.planBusy} onClick={onRefresh}>
        다시 만들기
      </button>
    </div>
  );

  const fresh = isPlanFresh(state);
  let body = null;

  if (!state.ready) body = <Msg text="필수 정보를 모두 채우면 날짜별 일정 미리보기가 여기에 나와요." />;
  else if (state.planBusy && !fresh) body = <Msg text="일정을 짜는 중이에요... 잠시만 기다려 주세요." loading />;
  else if (state.planError) body = <Msg text={state.planError} error />;
  else if (!fresh) body = <Msg text="일정을 짜는 중이에요... 잠시만 기다려 주세요." loading />;

  if (body) {
    return (
      <section className="tc-plan" aria-label="일정 미리보기">
        {head}
        <div className="tc-tabs" role="tablist" />
        {body}
        <p className="tc-plan__sum" />
      </section>
    );
  }

  const days = state.plan.days;
  const tab = Math.min(state.dayTab, days.length - 1);
  const day = days[tab];
  const items = dayItems(state, day);
  const reordered = !!state.order[day.day];
  const pending = state.plan.rkey !== removedKey(state.removed, state.order);
  const moveSum = items.reduce((s, it) => s + (it.move != null ? it.move : 0), 0);
  const goneToday = state.removed.filter((r) => r.day === day.day).length;

  return (
    <section className="tc-plan" aria-label="일정 미리보기">
      {head}

      <div className="tc-tabs" role="tablist">
        {days.map((d, i) => (
          <button
            key={d.day}
            type="button"
            role="tab"
            className={`tc-tab${i === tab ? ' is-on' : ''}`}
            aria-selected={i === tab}
            onClick={() => onTab(i)}
          >
            <strong>{d.day}일차</strong>
            <span>{d.label}</span>
            {d.weather && (
              <span className={`tc-tab__wx${d.weather.rainy ? ' is-rain' : ''}${d.weather.source === 'last_year' ? ' is-old' : ''}`}>
                {wxText(d.weather)}{d.weather.source === 'last_year' ? ' 작년' : ''}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="tc-plan__body" aria-live="polite">
        {'weather' in day && (
          <p className={day.weather && day.weather.rainy ? 'tc-rec__rain' : 'tc-plan__wx'}>
            {!day.weather
              ? '날씨 정보를 찾지 못했어요.'
              : day.weather.source === 'last_year'
                ? `${wxText(day.weather)} 작년 이맘때 ${day.weather.label || ''}${day.weather.last_year_rain ? ' · 작년엔 비·눈이 왔어요' : ''} · 예보는 여행 16일 전부터 나와요`
                : day.weather.source === 'past'
                  ? `${wxText(day.weather)} 그날 날씨 ${day.weather.label || ''}`
                  : `${wxText(day.weather)} ${day.weather.label || ''}${day.weather.rain_pct != null ? ` · 강수 ${day.weather.rain_pct}%` : ''}${day.weather.rainy ? ' · 실외 장소는 실내로 바꾸는 걸 생각해 보세요' : ' · 실외 일정도 괜찮아요'}`}
          </p>
        )}
        <ol className="tc-tl">
          {/* 1) 출발 시간 + 출발점 */}
          <li className="tc-tl__item is-start">
            <span className="tc-tl__time">{day.start_time || ''}</span>
            <span className="tc-tl__dot" />
            <div className="tc-tl__body">
              <div className="tc-tl__head">
                <Icon name="flag" sprite={sprite} />
                <strong>출발 · {day.start_name}</strong>
              </div>
            </div>
          </li>

          {/* 2) 그다음 장소들을 순서대로 */}
          {items.map((it, i) => {
            const sub = [];
            if (it.move != null) sub.push(`${it.move}분 이동${state.plan.transport ? ` · ${state.plan.transport} 기준` : ''}`);
            if (it.stay && !it.is_stay) sub.push(`체류 ${it.stay}분`);

            const cls = ['tc-tl__item'];
            if (it.is_stay) cls.push('is-stay');
            if (it.pin) cls.push('is-pin');
            if (dragFrom === i) cls.push('is-drag');
            if (overIndex === i) cls.push('is-over');

            // 위치가 있으면 눌러서 지도에서 보기 (지금 지도에 띄운 장소면 강조)
            const canFocus = it.lat != null && it.lon != null && !!onFocusPlace;
            if (canFocus) cls.push('is-clickable');
            if (canFocus && focus && focus.name === it.name
              && Math.abs(focus.lat - Number(it.lat)) < 1e-6 && Math.abs(focus.lon - Number(it.lon)) < 1e-6) cls.push('is-focus');

            return (
              <li
                key={`${it.name}-${i}`}
                className={cls.join(' ')}
                title={canFocus ? '눌러서 지도에서 위치 보기' : undefined}
                // ↑↓·삭제 버튼은 그대로 동작
                onClick={(e) => { if (canFocus && !e.target.closest('button, a')) onFocusPlace(it, planPopupInfo(it, i + 1)); }}
                draggable={items.length > 1}
                onDragStart={(e) => {
                  setDragFrom(i);
                  if (e.dataTransfer) { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(i)); }
                }}
                onDragOver={(e) => { if (dragFrom < 0) return; e.preventDefault(); setOverIndex(i); }}
                onDragLeave={() => setOverIndex(-1)}
                onDragEnd={() => { setDragFrom(-1); setOverIndex(-1); }}
                onDrop={(e) => { e.preventDefault(); const from = dragFrom; setDragFrom(-1); setOverIndex(-1); onMove(day, from, i); }}
              >
                {/* 순서를 바꿔서 시간을 다시 계산하는 동안에는 옛 시간을 보여 주지 않는다 */}
                <span className="tc-tl__time">{reordered && pending ? '··:··' : it.arrive || ''}</span>
                <span className="tc-tl__dot">{i + 1}</span>
                <div className="tc-tl__body">
                  <div className="tc-tl__head">
                    <strong>{it.name}</strong>
                    {it.is_stay ? (
                      // 🟩 stay_role: checkin / return (없으면 같은 숙소가 앞에 있는지로 짐작, 숙소 두 줄 규칙)
                      <span className="tc-tag tc-tag--stay">
                        <Icon name="bed" sprite={sprite} />
                        {(it.stay_role ? it.stay_role === 'return' : items.slice(0, i).some((x) => x.is_stay && x.name === it.name))
                          ? ' 숙소로 귀가'
                          : it.stay_role === 'checkin' ? ' 체크인 · 짐 두기' : ' 체크인'}
                      </span>
                    ) : it.pin ? (
                      <span className="tc-tag tc-tag--pin">담은 장소</span>
                    ) : it.kind ? (
                      <span className="tc-tag">{it.kind}</span>
                    ) : null}
                    {!it.is_stay && <PlaceTag indoor={it.indoor} rainy={!!(day.weather && day.weather.rainy)} />}
                    <span className="tc-tl__mv">
                      <button type="button" className="tc-tl__mvbtn" title="위로" aria-label={`${it.name} 위로 옮기기`}
                        disabled={i === 0} onClick={() => onMove(day, i, i - 1)}>↑</button>
                      <button type="button" className="tc-tl__mvbtn" title="아래로" aria-label={`${it.name} 아래로 옮기기`}
                        disabled={i === items.length - 1} onClick={() => onMove(day, i, i + 1)}>↓</button>
                    </span>
                    <button type="button" className="tc-tl__del" aria-label={`${it.name} 일정에서 빼기`}
                      onClick={() => onRemove(day, it)}>삭제</button>
                  </div>
                  {sub.length > 0 && (
                    <p className="tc-tl__meta"><Icon name="route" sprite={sprite} /> {sub.join(' · ')}</p>
                  )}
                  {/* 🟩 숙소 체크인 시각 안내 (경고 아님, 없으면 안 보임) */}
                  {it.checkin && it.checkin.message && (
                    <p className="tc-tl__checkin"><Icon name="clock" sprite={sprite} /> {it.checkin.message}</p>
                  )}
                  {/* 예상 비용 (인원 기준, 자동으로 들어간 식당·카페 포함) */}
                  {costText(it.cost, state.draft.people) && (
                    <p className="tc-card__cost tc-tl__cost" title={it.cost.text || ''}>
                      <Icon name="wallet" sprite={sprite} /> {costText(it.cost, state.draft.people)}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      <p className="tc-plan__sum">
        {`방문 ${items.length}곳`}
        {moveSum ? ` · 이동 합계 ${moveSum}분` : ''}
        {state.planBusy ? ' · 시간을 다시 계산하는 중...' : ''}
        {reordered && (
          <button type="button" className="tc-link tc-tl__undo" onClick={() => onResetOrder(day)}>순서 원래대로</button>
        )}
        {goneToday > 0 && (
          <button type="button" className="tc-link tc-tl__undo" onClick={() => onRestore(day)}>
            삭제한 {goneToday}곳 되돌리기
          </button>
        )}
      </p>
    </section>
  );
}
