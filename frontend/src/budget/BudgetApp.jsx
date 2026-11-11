// 비용 관리 화면 (React) — 카테고리 예산
// - 분류(관광지·식비·카페·교통·숙박·쇼핑·기타)별 예산을 보고 고친다 → budget_category 로 저장
// - 일정 예상 비용(AI)보다 예산이 적은 분류는 '같은 분류의 더 싼 대안'을 보여 주고 바꿀 수 있다
import { useCallback, useEffect, useMemo, useState } from 'react';
import Icon from '../components/Icon.jsx';
import CategoryRow from './CategoryRow.jsx';
import ChartPanel from './ChartPanel.jsx';
import FlowPanel from './FlowPanel.jsx';
import { fetchBudget, saveLimits } from './api.js';
import LogPanel from './LogPanel.jsx';
import { CATS, won } from './cats.js';

// 서버 금액 {분류: 숫자} → 입력 칸 값 {분류: '숫자 글자'}
const toInputs = (limit) => Object.fromEntries(CATS.map((c) => [c.key, String((limit && limit[c.key]) || 0)]));
const toNumber = (text) => Math.max(0, Math.round(Number(String(text).replace(/[^\d]/g, '')) || 0));
// 장소별 금액 입력 칸 {sp_id: '숫자 글자'} (가격을 모르는 곳은 '')
const toItemInputs = (items) => Object.fromEntries((items || []).map((it) => [it.sp_id, it.amount == null ? '' : String(it.amount)]));

export default function BudgetApp({ cfg }) {
  const [data, setData] = useState(null);       // {total, limit, by, plan, counts, people}
  const [inputs, setInputs] = useState({});     // 입력 중인 금액
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [saving, setSaving] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);   // 바꾸기 뒤에 다시 불러올 때 +1
  const [itemInputs, setItemInputs] = useState({}); // 장소별 금액 입력 중
  const [resets, setResets] = useState([]);          // 'AI 금액으로' 되돌린 장소 (저장 때 null)
  const [totalInput, setTotalInput] = useState('');  // 총예산 입력 중 (숫자 글자)

  // 처음 열 때와 장소를 바꾼 뒤: 예산·일정 예상 비용 불러오기
  useEffect(() => {
    let alive = true;
    fetchBudget(cfg)
      .then((budget) => {
        if (!alive) return;
        setData(budget);
        setInputs(toInputs(budget.limit));
        setItemInputs(toItemInputs(budget.items));
        setTotalInput(String(budget.total || 0));
        setResets([]);
        setError('');
      })
      .catch((err) => { if (alive) setError(err.message); });
    return () => { alive = false; };
  }, [cfg, reloadKey]);

  const load = useCallback(() => setReloadKey((k) => k + 1), []);

  const limits = useMemo(() => Object.fromEntries(CATS.map((c) => [c.key, toNumber(inputs[c.key])])), [inputs]);
  const items = (data && data.items) || [];
  // 저장할 장소 금액: 입력이 서버 값과 다른 곳 + 'AI 금액으로' 되돌린 곳(null)
  const itemChanges = {};
  items.forEach((it) => {
    const text = itemInputs[it.sp_id] ?? '';
    if (resets.includes(it.sp_id)) {
      if (it.edited) itemChanges[it.sp_id] = null;
    } else if (text !== '' && toNumber(text) !== (it.amount ?? -1)) {
      itemChanges[it.sp_id] = toNumber(text);
    }
  });
  const total = toNumber(totalInput);   // 총예산 (내가 정한 금액, 분류 합계와 따로)
  const changed = !!data && (
    total !== (data.total || 0) ||
    CATS.some((c) => limits[c.key] !== ((data.limit || {})[c.key] || 0)) || Object.keys(itemChanges).length > 0
  );

  if (error && !data) {
    return <div className="cb-card cb-error">카테고리 예산을 불러오지 못했어요. {error}</div>;
  }
  if (!data) {
    return <div className="cb-card cb-loading">일정 기준 예상 비용을 계산하는 중이에요...</div>;
  }

  const plan = data.plan || {};
  const sumLimit = CATS.reduce((s, c) => s + limits[c.key], 0);
  const sumPlan = CATS.reduce((s, c) => s + (plan[c.key] || 0), 0);
  const unassigned = total - sumLimit;   // + 면 아직 분류에 안 나눈 금액, - 면 분류에 더 많이 나눔
  const overPlan = sumPlan - total;      // + 면 일정 예상이 예산보다 많음
  const left = total - sumPlan;          // 남은 금액 = 총예산 - 일정 예상 (- 면 초과)

  // 금액이 있는 분류만 기본으로 보여 주고, 나머지는 '다른 분류도 보기'
  // (금액이 0이어도 일정 장소가 있는 분류는 보여 줌 → 가격 모르는 곳을 직접 적을 수 있게)
  const active = CATS.filter((c) => limits[c.key] || plan[c.key] || items.some((it) => it.cat === c.key));
  const rows = showAll || !active.length ? CATS : active;

  const setOne = (key, text) => { setInputs((prev) => ({ ...prev, [key]: text })); setMsg(''); };

  // 장소 금액을 고치면 그 분류 예산 = 그 분류 장소 금액 합계
  const sumOfCat = (cat, next) => items
    .filter((it) => it.cat === cat)
    .reduce((s, it) => s + toNumber(next[it.sp_id] ?? ''), 0);
  const setItem = (it, text) => {
    const next = { ...itemInputs, [it.sp_id]: text };
    setItemInputs(next);
    setResets((prev) => prev.filter((id) => id !== it.sp_id));
    setInputs((prev) => ({ ...prev, [it.cat]: String(sumOfCat(it.cat, next)) }));
    setMsg('');
  };
  const resetItem = (it) => {
    const next = { ...itemInputs, [it.sp_id]: it.ai == null ? '' : String(it.ai) };
    setItemInputs(next);
    setResets((prev) => (prev.includes(it.sp_id) ? prev : [...prev, it.sp_id]));
    setInputs((prev) => ({ ...prev, [it.cat]: String(sumOfCat(it.cat, next)) }));
  };

  const fillFromPlan = () => {
    setInputs(toInputs(plan));
    setItemInputs(Object.fromEntries(items.map((it) => [it.sp_id, it.ai == null ? '' : String(it.ai)])));
    setResets(items.filter((it) => it.edited).map((it) => it.sp_id));
    setMsg('일정 예상 비용(AI)으로 채웠어요. 저장을 눌러야 반영돼요.');
  };
  const reset = () => {
    setInputs(toInputs(data.limit)); setItemInputs(toItemInputs(items)); setResets([]);
    setTotalInput(String(data.total || 0)); setMsg('');
  };

  const save = async () => {
    setSaving(true);
    try {
      await saveLimits(cfg, limits, itemChanges, total);
      setMsg('예산을 저장했어요.');
      load();   // 장소별 금액까지 새로 불러오기
    } catch (err) {
      setMsg(`저장하지 못했어요. ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const goTravel = (e) => { if (e.target.value) window.location.href = e.target.value; };

  return (
    <div className="cb-wrap">
      {/* 여행 고르기 + 요약 */}
      <section className="cb-card cb-top">
        <div className="cb-top__trip">
          <label className="cb-switch">
            <Icon name="suitcase" sprite={cfg.sprite} />
            <select aria-label="다른 여행 고르기" value={`/budget/${cfg.travelId}/`} onChange={goTravel}>
              {cfg.travels.map((t) => (
                <option key={t.id} value={t.url}>{t.title} · {t.dates}</option>
              ))}
            </select>
          </label>
          <span className="cb-sub">{cfg.place} · {cfg.dates} · {data.people || 1}명 기준</span>
        </div>

        {/* 총예산은 직접 고침 (여행 만들 때 정한 금액에서 시작), 분류 예산은 그 안에서 나눔 */}
        <dl className="cb-stats">
          <div>
            <dt><label htmlFor="cbTotal">총예산 (직접 고치기)</label></dt>
            <dd>
              <label className="cb-input cb-input--total">
                <input
                  id="cbTotal"
                  type="text"
                  inputMode="numeric"
                  className={total !== (data.total || 0) ? 'is-edit' : ''}
                  value={total.toLocaleString('ko-KR')}
                  onChange={(e) => { setTotalInput(e.target.value.replace(/[^\d]/g, '').slice(0, 9)); setMsg(''); }}
                />
                <span>원</span>
              </label>
            </dd>
          </div>
          <div><dt>일정 예상 (AI)</dt><dd className={overPlan > 0 ? 'is-over' : ''}>{won(sumPlan)}</dd></div>
          <div><dt>남은 금액</dt><dd className={left < 0 ? 'is-over' : ''}>{left < 0 ? `${won(-left)} 초과` : won(left)}</dd></div>
        </dl>

        <p className={`cb-note${overPlan > 0 ? ' is-warn' : ''}`}>
          {overPlan > 0
            ? <>일정 예상 비용이 예산보다 <b>{won(overPlan)}</b> 많아요. 빨간 분류의 '더 싼 곳 찾기'로 줄여 보세요.</>
            : <>일정 예상 비용이 예산 안에 있어요{left > 0 ? <> ({won(left)} 여유)</> : null}.</>}
          {unassigned > 0 && <> 분류에 나눈 금액은 {won(sumLimit)}이고, {won(unassigned)}은 아직 안 나눴어요.</>}
          {unassigned < 0 && <> <b className="cb-bad">분류 예산 합계({won(sumLimit)})가 총예산보다 {won(-unassigned)} 많아요.</b></>}
          {changed && <> 저장을 눌러야 반영돼요.</>}
        </p>
      </section>

      <div className="cb-grid">
        {/* 분류별 예산 정하기 */}
        <section className="cb-card">
          <header className="cb-head">
            <h2><Icon name="wallet" sprite={cfg.sprite} /> 카테고리별 예산 정하기</h2>
            <div className="cb-actions">
              <button type="button" className="cb-btn is-ghost" onClick={fillFromPlan}>AI 예상대로 채우기</button>
              <button type="button" className="cb-btn is-ghost" onClick={reset} disabled={!changed}>되돌리기</button>
              <button type="button" className="cb-btn" onClick={save} disabled={!changed || saving}>
                {saving ? '저장 중...' : '저장'}
              </button>
            </div>
          </header>

          {msg && <p className="cb-msg" role="status">{msg}</p>}

          <ul className="cb-rows">
            {rows.map((c) => (
              <CategoryRow
                key={c.key}
                cfg={cfg}
                cat={c}
                value={inputs[c.key] ?? '0'}
                limit={limits[c.key]}
                plan={plan[c.key] || 0}
                onChange={(text) => setOne(c.key, text)}
                onSwapped={load}
                items={items.filter((it) => it.cat === c.key)}
                itemInputs={itemInputs}
                resets={resets}
                onItemChange={setItem}
                onItemReset={resetItem}
              />
            ))}
          </ul>

          {active.length > 0 && active.length < CATS.length && (
            <button type="button" className="cb-link" onClick={() => setShowAll((v) => !v)}>
              {showAll ? '금액 있는 분류만 보기' : `다른 분류도 보기 (${CATS.length - active.length}개)`}
            </button>
          )}
        </section>

        {/* AI가 장소를 고르는 방식 + 분류별 한 곳당 상한 */}
        <FlowPanel cfg={cfg} limits={limits} counts={data.counts || {}} people={data.people || 1} />
      </div>

      {/* 예산 최근 변경 (🟧 budget_log): 저장·바꾸기 뒤 reloadKey 가 바뀌면 다시 불러옴 */}
      <LogPanel cfg={cfg} reloadKey={reloadKey} />

      {/* 예전 비용 관리의 차트 3개 (고치는 금액이 바로 반영됨) */}
      <ChartPanel
        cfg={cfg}
        limits={limits}
        total={total}
        plan={plan}
        days={data.days || []}
        dayAmounts={items.reduce((acc, it) => {
          const text = itemInputs[it.sp_id] ?? '';
          acc[it.date] = (acc[it.date] || 0) + (text === '' ? (it.ai || 0) : toNumber(text));
          return acc;
        }, {})}
      />

      <p className="cb-foot">
        <a href={cfg.detailUrl}>여행 일정 보기</a>
      </p>
    </div>
  );
}
