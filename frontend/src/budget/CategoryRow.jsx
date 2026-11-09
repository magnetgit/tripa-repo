// 분류 한 줄: 금액 입력 · 예산 대비 일정 예상 막대 · 넘치면 같은 분류의 더 싼 대안
import { useState } from 'react';
import Icon from '../components/Icon.jsx';
import { fetchAlternatives, swapPlace } from './api.js';
import { ALT_CATS, distText, won } from './cats.js';

const digits = (text) => text.replace(/[^\d]/g, '').slice(0, 9);   // 쉼표는 화면용, 숫자만 보관
const comma = (text) => (text === '' ? '' : Number(text).toLocaleString('ko-KR'));

export default function CategoryRow({
  cfg, cat, value, limit, plan, onChange, onSwapped,
  items = [], itemInputs = {}, resets = [], onItemChange, onItemReset,
}) {
  const [alts, setAlts] = useState(null);   // null(닫힘) | 'loading' | 'error' | [제안…]
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);  // 장소별 상세 펼침
  const itemSum = items.reduce((s, it) => s + Number(itemInputs[it.sp_id] || 0), 0);

  // 막대: 예산과 일정 예상 중 큰 쪽을 100%로
  const whole = Math.max(limit, plan, 1);
  const over = limit > 0 ? plan - limit : 0;
  const canAlt = ALT_CATS.includes(cat.key) && plan > 0;

  const openAlts = async () => {
    if (alts && alts !== 'error') { setAlts(null); return; }
    setAlts('loading');
    try {
      setAlts(await fetchAlternatives(cfg, cat.key));
    } catch {
      setAlts('error');
    }
  };

  const swap = async (sg, o) => {
    if (!window.confirm(`DAY ${sg.day} '${sg.name}' 대신 '${o.name}'(으)로 바꿀까요?\n예상 ${won(o.save)} 줄어요. 그날 시간은 다시 계산돼요.`)) return;
    setBusy(true);
    try {
      await swapPlace(cfg, sg.sp_id, o);
      setAlts(null);
      onSwapped();   // 일정 예상 비용 다시 불러오기
    } catch (err) {
      window.alert(err.message || '바꾸지 못했어요.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={`cb-row${over > 0 ? ' is-over' : ''}`}>
      <div className="cb-row__head">
        <span className="cb-dot" style={{ background: cat.color }} />
        <Icon name={cat.icon} sprite={cfg.sprite} />
        <strong className="cb-row__name">{cat.name}</strong>
        <label className="cb-input">
          <input
            type="text"
            inputMode="numeric"
            aria-label={`${cat.name} 예산`}
            value={Number(value || 0).toLocaleString('ko-KR')}
            onChange={(e) => onChange(e.target.value.replace(/[^\d]/g, '').slice(0, 9))}   // 쉼표는 화면용, 숫자만 보관
          />
          <span>원</span>
        </label>
      </div>

      {/* 예산(연한 막대) 위에 일정 예상(색 막대) */}
      <div className="cb-bar" aria-hidden="true">
        <span className="cb-bar__limit" style={{ width: `${(limit / whole) * 100}%` }} />
        <span className="cb-bar__plan" style={{ width: `${(plan / whole) * 100}%`, background: cat.color }} />
      </div>

      <p className="cb-row__meta">
        일정 예상 {won(plan)}
        {limit > 0 && (over > 0
          ? <b className="cb-bad"> · 예산보다 {won(over)} 많아요</b>
          : <span className="cb-good"> · {won(limit - plan)} 남아요</span>)}
      </p>

      {/* 장소별 상세: AI가 매긴 금액을 장소마다 보고 고치기 (고치면 분류 금액 = 장소 합계) */}
      {items.length > 0 && (
        <button type="button" className="cb-detail-btn" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? '상세 접기' : `상세 ${items.length}곳 보기 · 고치기`} <span aria-hidden="true">{open ? '▴' : '▾'}</span>
        </button>
      )}
      {open && (
        <div className="cb-items">
          <ul>
            {items.map((it) => {
              const text = itemInputs[it.sp_id] ?? '';
              const isReset = resets.includes(it.sp_id);
              const mine = !isReset && (it.edited || (text !== '' && Number(text) !== (it.ai ?? -1)));
              return (
                <li key={it.sp_id} className={mine ? 'is-mine' : ''}>
                  <div className="cb-items__info">
                    <b title={it.name}><em>DAY {it.day}</em> {it.name}</b>
                    <span>
                      {it.ai == null
                        ? '가격 정보 없음 · 직접 적어 주세요'
                        : `AI ${won(it.ai)}${it.per ? (it.unit === 'room' ? ` (1박 방 ${won(it.per)})` : ` (1인 ${won(it.per)})`) : ' (무료)'}`}
                      {mine && ' · 직접 고침'}
                    </span>
                  </div>
                  <label className="cb-input cb-input--sm">
                    <input
                      type="text"
                      inputMode="numeric"
                      aria-label={`${it.name} 예산`}
                      placeholder="0"
                      value={comma(text)}
                      onChange={(e) => onItemChange(it, digits(e.target.value))}
                    />
                    <span>원</span>
                  </label>
                  {mine && it.ai != null && (
                    <button type="button" className="cb-items__reset" onClick={() => onItemReset(it)} title="AI 금액으로 되돌리기">AI 금액</button>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="cb-items__sum">
            장소 합계 {won(itemSum)}
            {limit !== itemSum && <span> · 분류 예산과 {won(Math.abs(limit - itemSum))} 차이 (장소 밖 비용으로 남겨 둘 수 있어요)</span>}
          </p>
        </div>
      )}

      {canAlt && (over > 0 || alts) && (
        <button type="button" className="cb-alt-btn" onClick={openAlts}>
          {alts && alts !== 'error' ? '대안 접기' : `${cat.name}에서 더 싼 곳 찾기`}
        </button>
      )}

      {alts === 'loading' && <p className="cb-alt-msg">근처에서 같은 분류의 더 싼 곳을 찾는 중이에요...</p>}
      {alts === 'error' && <p className="cb-alt-msg">대안을 찾지 못했어요. 다시 눌러 보세요.</p>}
      {Array.isArray(alts) && !alts.length && <p className="cb-alt-msg">근처에서 더 싼 {cat.name} 장소를 찾지 못했어요.</p>}
      {Array.isArray(alts) && alts.map((sg) => (
        <div className="cb-alt" key={sg.sp_id}>
          <p className="cb-alt__now"><em>DAY {sg.day}</em> {sg.name} <span>{won(sg.amount)}</span></p>
          <ul>
            {sg.options.map((o) => (
              <li key={o.kakao_id || o.name}>
                <div className="cb-alt__info">
                  <b title={o.name}>{o.name}</b>
                  <span>{o.kind} · {distText(o.distance)} · {won(o.cost.amount)}{o.cost.source === 'tour' ? '' : ' (예상)'}</span>
                </div>
                <em className="cb-alt__save">-{won(o.save)}</em>
                <button type="button" disabled={busy} onClick={() => swap(sg, o)}>바꾸기</button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </li>
  );
}
