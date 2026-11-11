// 예산 "최근 변경": 장소 금액을 넣기·고치기·지우기 한 기록 (🟧 budget_log, DB 트리거가 자동으로 적음)
// 예) 해운대블루라인파크 12,000원 → 15,000원 ▲3,000 · 11/10 12:35
import { useEffect, useState } from 'react';
import { fetchBudgetLog } from './api.js';

const SHOW = 5;   // 처음엔 5줄, '더 보기'로 서버가 주는 10줄까지

const won = (n) => `${Number(n || 0).toLocaleString('ko-KR')}원`;

// '2026-11-10 12:35' → '11/10 12:35'
function shortAt(at) {
  const m = /^\d{4}-(\d{2})-(\d{2}) (\d{2}:\d{2})/.exec(at || '');
  return m ? `${Number(m[1])}/${Number(m[2])} ${m[3]}` : at || '';
}

function LogRow({ log }) {
  if (log.action === 'insert') {
    return <><b>{log.name}</b> {won(log.new)}으로 정함</>;
  }
  if (log.action === 'delete') {
    return <><b>{log.name}</b> {won(log.old)} 지움 <span className="cb-log__note">(AI 예상으로)</span></>;
  }
  const diff = (log.new || 0) - (log.old || 0);
  return (
    <>
      <b>{log.name}</b> {won(log.old)} → {won(log.new)}
      {diff !== 0 && (
        <span className={`cb-log__diff ${diff > 0 ? 'is-up' : 'is-down'}`}>
          {diff > 0 ? '▲' : '▼'}{Math.abs(diff).toLocaleString('ko-KR')}
        </span>
      )}
    </>
  );
}

export default function LogPanel({ cfg, reloadKey }) {
  const [logs, setLogs] = useState(null);   // null = 불러오는 중
  const [error, setError] = useState('');
  const [all, setAll] = useState(false);

  // 처음 열 때 + 저장·바꾸기 뒤(reloadKey)마다 다시 불러옴
  useEffect(() => {
    if (!cfg.logUrl) return undefined;
    let alive = true;
    fetchBudgetLog(cfg)
      .then((rows) => { if (alive) { setLogs(rows); setError(''); } })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [cfg, reloadKey]);

  if (!cfg.logUrl) return null;

  const rows = logs ? (all ? logs : logs.slice(0, SHOW)) : [];

  return (
    <section className="cb-card cb-log" aria-label="예산 최근 변경">
      <header className="cb-head">
        <h2>최근 변경</h2>
        <span className="cb-sub">장소 금액을 넣거나 고치면 자동으로 남아요</span>
      </header>

      {error && <p className="cb-log__empty">기록을 불러오지 못했어요. ({error})</p>}
      {!error && logs === null && <p className="cb-log__empty">불러오는 중...</p>}
      {!error && logs && !logs.length && (
        <p className="cb-log__empty">아직 바꾼 금액이 없어요. 위에서 장소 금액을 고치면 여기에 남아요.</p>
      )}

      {rows.length > 0 && (
        <ul className="cb-log__list">
          {rows.map((log, i) => (
            <li key={`${log.at}-${log.name}-${i}`} className={`cb-log__row is-${log.action}`}>
              <span className="cb-log__text"><LogRow log={log} /></span>
              <time className="cb-log__at">{shortAt(log.at)}</time>
            </li>
          ))}
        </ul>
      )}

      {logs && logs.length > SHOW && (
        <button type="button" className="cb-link" onClick={() => setAll((v) => !v)}>
          {all ? '접기' : `더 보기 (${logs.length - SHOW}줄)`}
        </button>
      )}
    </section>
  );
}
