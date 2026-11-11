// AI가 찾아 준 장소 추천 카드 (말풍선 아래)
import { useState } from 'react';
import Icon from './Icon.jsx';
import { dayToIso, tripDays } from '../lib/util.js';

const KIND_ICON = { 카페: 'cup', 음식: 'utensils', 숙박: 'bed', 쇼핑: 'bag', 관광: 'landmark' };
const KAKAO_LINK = /^https?:\/\/(place\.)?map\.kakao\.com\//;

// 카드 왼쪽: 사진(photo.url)이 있으면 사진, 없거나 못 불러오면 종류 아이콘(기본 이미지)
function CardPhoto({ item, sprite }) {
  const [broken, setBroken] = useState(false);
  const photo = item.photo;

  if (!photo || !photo.url || broken) {
    return (
      <div className="tc-card__icon">
        <Icon name={KIND_ICON[item.kind] || 'pin'} sprite={sprite} />
      </div>
    );
  }

  return (
    <figure className="tc-card__photo">
      <img
        src={photo.url}
        alt={`${item.name} 사진`}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
      />
      {/* 관광공사 사진은 출처 표시가 이용 조건 */}
      {photo.source === 'tour' && <figcaption>사진: 한국관광공사</figcaption>}
    </figure>
  );
}

const wonText = (n) => `${Number(n).toLocaleString('ko-KR')}원`;

// 인원 기준 금액 (가격 모르면 0) — 일정 미리보기 합계에도 씀
export function costAmount(cost, people) {
  if (!cost || cost.per == null || cost.same_stay) return 0; // 숙소 두 번째 줄은 0원
  const n = Math.max(1, Number(people) || 1);
  return cost.unit === 'room' ? cost.per * Math.ceil(n / Math.max(1, cost.cap || 2)) : cost.per * n;
}

// 예상 비용: 1인 요금 × 인원, 방 요금 × 방 개수(인원 ÷ 방 기준 인원). 인원은 지금 초안 값으로 다시 계산
export function costText(cost, people) {
  if (cost && cost.same_stay) return '숙박비는 체크인 줄에'; // 같은 날 같은 숙소 두 번째 줄 (금액 0)
  if (!cost || cost.per == null) return '';
  const n = Math.max(1, Number(people) || 1);
  const tag = cost.source === 'tour' ? '관광공사 요금' : cost.source === 'ai' ? 'AI 예상' : '보통 가격 예상';
  if (cost.unit === 'room') {
    const rooms = Math.ceil(n / Math.max(1, cost.cap || 2));
    return `1박 방 ${wonText(cost.per)}${rooms > 1 ? ` × ${rooms}개` : ''} = ${n}명 ${wonText(cost.per * rooms)} (${tag})`;
  }
  if (!cost.per) return `무료 (${tag})`;
  return n > 1
    ? `1인 ${wonText(cost.per)} · ${n}명 ${wonText(cost.per * n)} (${tag})`
    : `1인 ${wonText(cost.per)} (${tag})`;
}

// 실내 / 실외 (indoor: true · false · null 모름 → 표시 안 함). 비·눈 오는 날이면 실내는 강조, 실외는 흐리게
const isRainy = (w) => !!w && (w.kind === 'rain' || w.kind === 'snow');

// 실내 카드가 하나도 없으면 '1일차 실내 추천'이라고 말해 보라고 안내
function weatherNote(w, rec) {
  const mark = w.kind === 'snow' ? '❄' : '☔';
  const when = w.date ? `${w.date.slice(5).replace('-', '/')} ` : '';
  const pct = w.rain_pct != null ? `(강수 ${w.rain_pct}%)` : '';
  const tip = rec.items.some((it) => it.indoor === true)
    ? '실내 장소를 먼저 보여 드려요'
    : `실내 장소는 '${rec.day ? `${rec.day}일차 ` : ''}실내 추천'이라고 말해 보세요`;
  return `${mark} ${when}${w.label || '비'} 예보${pct} · ${tip}`;
}

export function PlaceTag({ indoor, rainy }) {
  if (indoor === true) {
    return <span className={`tc-tag tc-tag--indoor${rainy ? ' is-rain' : ''}`}>{rainy ? '실내 · 비 와도 OK' : '실내'}</span>;
  }
  if (indoor === false) {
    return <span className={`tc-tag tc-tag--outdoor${rainy ? ' is-rain' : ''}`}>{rainy ? '실외 · 비 오면 아쉬워요' : '실외'}</span>;
  }
  if (indoor === null) {
    // 시장·전망대처럼 곳마다 다른 곳 (서버가 판단 못 함)
    return <span className="tc-tag tc-tag--mixed">실내·실외 섞임</span>;
  }
  return null;
}

// TRIPA 추천 장소: 팀이 확인한 영업시간·입장료·휴무·주차·메모 (pick, 값이 있는 것만)
const PICK_ROWS = [['hours', '영업'], ['fee', '입장료'], ['rest', '휴무'], ['parking', '주차'], ['memo', '팁']];

function PickInfo({ pick }) {
  if (!pick) return null;
  const rows = PICK_ROWS.filter(([key]) => pick[key]);
  if (!rows.length) return null;
  return (
    <dl className="tc-pick">
      {rows.map(([key, label]) => (
        <div className={`tc-pick__row${key === 'memo' ? ' tc-pick__memo' : ''}`} key={key}>
          <dt>{label}</dt>
          <dd>{pick[key]}</dd>
        </div>
      ))}
    </dl>
  );
}

// 평점(review)은 값이 올 때만 (mock.json 키)
function cardExtra(item) {
  const parts = [];
  if (item.review && item.review.count) {
    parts.push(`★ ${Number(item.review.rating).toFixed(1)} · 리뷰 ${item.review.count}개`);
  }
  return parts.join(' · ');
}

function hasPin(draft, item, day) {
  return (draft.pins || []).some((p) => p.day === day && p.name === item.name);
}

function hasStay(draft, item, day) {
  const iso = dayToIso(draft.start, day);
  const s = (draft.stays || []).find((x) => x.date === iso);
  return !!s && (s.name === item.name || s.query === item.name);
}

export default function RecCards({ rec, draft, sprite, onAddPin, onAddStay, focus, onFocus, profileHint }) {
  const cond = [];
  if (rec.anchor) cond.push(`${rec.anchor} 기준`);
  if (rec.day) cond.push(`${rec.day}일차`);
  if (rec.time) cond.push(rec.time);

  const n = tripDays(draft);
  const rainy = isRainy(rec.weather);
  const canFocus = (item) => item.lat != null && item.lon != null;
  const isFocused = (item) => !!focus && focus.name === item.name
    && Math.abs(focus.lat - Number(item.lat)) < 1e-6 && Math.abs(focus.lon - Number(item.lon)) < 1e-6;

  return (
    <div className="tc-rec">
      <p className="tc-rec__cond">
        <span>조건</span>
        <span className="tc-chip">{cond.join(' · ') || rec.title}</span>
      </p>
      {rainy && <p className="tc-rec__rain">{weatherNote(rec.weather, rec)}</p>}
      {/* 성별·나이대를 안 넣은 회원에게만 (억지로 받지 않기, × 로 닫기) */}
      {profileHint && (
        <p className="tc-rec__profile">
          <span>
            💡 {profileHint.half ? '성별·나이대를 다 넣으면' : '성별·나이대를 넣으면'} 나와 비슷한 사람들이 좋아한 곳을 먼저 보여 드려요.
            {' '}<a className="tc-link" href={profileHint.url}>내 정보에서 넣기</a>
          </span>
          <button type="button" className="tc-x" aria-label="안내 닫기" onClick={profileHint.onClose}>×</button>
        </p>
      )}

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
          <div
            className={`tc-card${item.pick ? ' is-pick' : ''}${canFocus(item) ? ' is-clickable' : ''}${isFocused(item) ? ' is-focus' : ''}`}
            key={`${item.name}-${item.addr || ''}`}
            title={canFocus(item) ? '눌러서 지도에서 위치 보기' : undefined}
            // 카드를 누르면 지도에서 위치 보기 (넣기 버튼·카카오맵 링크는 그대로 동작)
            onClick={(e) => { if (canFocus(item) && onFocus && !e.target.closest('button, a')) onFocus(item); }}
          >
            <CardPhoto item={item} sprite={sprite} />

            <div className="tc-card__body">
              <div className="tc-card__head">
                <strong>{item.name}</strong>
                {/* 팀이 직접 고른 장소 (부산 장소 표) */}
                {item.pick && <span className="tc-tag tc-tag--pick">★ TRIPA 추천</span>}
                <span className="tc-tag">{item.kind || '장소'}</span>
                <PlaceTag indoor={item.indoor} rainy={rainy} />
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

              <PickInfo pick={item.pick} />

              {cardExtra(item) && <p className="tc-card__extra">{cardExtra(item)}</p>}
              {costText(item.cost, draft.people) && (
                <p className="tc-card__cost" title={item.cost.text || ''}>
                  <Icon name="wallet" sprite={sprite} /> {costText(item.cost, draft.people)}
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
