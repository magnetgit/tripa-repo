// AI가 찾아 준 장소 추천 카드 (말풍선 아래)
import Icon from './Icon.jsx';
import { dayToIso, tripDays } from '../lib/util.js';

const KIND_ICON = { 카페: 'cup', 음식: 'utensils', 숙박: 'bed', 쇼핑: 'bag', 관광: 'landmark' };
const KAKAO_LINK = /^https?:\/\/(place\.)?map\.kakao\.com\//;

function hasPin(draft, item, day) {
  return (draft.pins || []).some((p) => p.day === day && p.name === item.name);
}

function hasStay(draft, item, day) {
  const iso = dayToIso(draft.start, day);
  const s = (draft.stays || []).find((x) => x.date === iso);
  return !!s && (s.name === item.name || s.query === item.name);
}

export default function RecCards({ rec, draft, sprite, onAddPin, onAddStay }) {
  const cond = [];
  if (rec.anchor) cond.push(`${rec.anchor} 기준`);
  if (rec.day) cond.push(`${rec.day}일차`);
  if (rec.time) cond.push(rec.time);

  const n = tripDays(draft);

  return (
    <div className="tc-rec">
      <p className="tc-rec__cond">
        <span>조건</span>
        <span className="tc-chip">{cond.join(' · ') || rec.title}</span>
      </p>

      {rec.items.map((item) => {
        // 넣을 수 있는 날짜: AI가 정해 준 날짜, 아니면 1일차부터(최대 7일)
        let days = [];
        if (rec.day && (!n || rec.day <= n)) days = [rec.day];
        else for (let d = 1; d <= Math.min(n, 7); d++) days.push(d);

        // 숙소는 '잠자는 밤'마다 하나. 마지막 날은 집으로 돌아가니 숙소가 필요 없다.
        const lodging = item.kind === '숙박';
        if (lodging && n) {
          days = days.filter((d) => d < n);
          if (!days.length && n > 1) for (let d = 1; d < n && d <= 7; d++) days.push(d);
        }

        const meta = [];
        if (item.distance) meta.push(`${rec.anchor || '기준'}에서 ${item.distance}`);
        if (item.addr) meta.push(item.addr);
        const showLink = item.url && KAKAO_LINK.test(item.url);

        return (
          <div className="tc-card" key={`${item.name}-${item.addr || ''}`}>
            <div className="tc-card__icon">
              <Icon name={KIND_ICON[item.kind] || 'pin'} sprite={sprite} />
            </div>

            <div className="tc-card__body">
              <div className="tc-card__head">
                <strong>{item.name}</strong>
                <span className="tc-tag">{item.kind || '장소'}</span>
              </div>

              <p className="tc-card__meta">
                <Icon name="pin" sprite={sprite} /> {meta.join(' · ')}
              </p>

              {(item.phone || showLink) && (
                <p className="tc-card__sub">
                  {item.phone}
                  {item.phone && showLink && ' · '}
                  {showLink && (
                    <a className="tc-link" href={item.url} target="_blank" rel="noopener noreferrer">
                      카카오맵에서 보기
                    </a>
                  )}
                </p>
              )}

              <div className="tc-card__actions">
                {!days.length && (
                  <button type="button" className="tc-addbtn" disabled>
                    {lodging && n === 1 ? '당일치기라 숙소가 필요 없어요' : '날짜를 정하면 넣을 수 있어요'}
                  </button>
                )}
                {days.map((day) => {
                  const done = lodging ? hasStay(draft, item, day) : hasPin(draft, item, day);
                  return (
                    <button
                      key={day}
                      type="button"
                      className={`tc-addbtn${done ? ' is-done' : ''}`}
                      disabled={done}
                      onClick={() => (lodging ? onAddStay(item, day) : onAddPin(item, day, rec.time))}
                    >
                      <Icon name={done ? 'check' : lodging ? 'bed' : 'calendar'} sprite={sprite} />
                      {lodging
                        ? ` ${day}일차 숙소로 ${done ? '담음' : '넣기'}`
                        : ` ${day}일차에 ${done ? '담음' : '넣기'}`}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
