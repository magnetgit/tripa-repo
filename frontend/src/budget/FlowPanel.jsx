// 오른쪽: AI가 장소를 고르는 방식 + 분류마다 '한 곳당 상한' (예산 ÷ 장소 수)
import Icon from '../components/Icon.jsx';
import { CATS, won } from './cats.js';

const STEPS = [
  '여행을 만들 때 AI가 일정의 장소마다 가격을 매겨요. 관광공사 요금이 있으면 그 요금, 없으면 가게 종류로 보통 가격을 예상해요.',
  '장소 가격 × 인원으로 분류별 예상 비용을 더하고, 그걸 분류별 예산으로 먼저 채워 둬요.',
  '예산을 장소 수로 나누면 한 곳당 쓸 수 있는 금액이 나와요. 아래 표가 그 금액이에요.',
  '예상 비용이 예산보다 많은 분류는 같은 분류 안에서만 더 싼 근처 장소를 찾아 줘요. 다른 분류의 돈은 직접 옮길 때만 움직여요.',
];

export default function FlowPanel({ cfg, limits, counts, people }) {
  const rows = CATS.filter((c) => counts[c.key] > 0 && limits[c.key] > 0);

  return (
    <section className="cb-card cb-flow">
      <header className="cb-head">
        <h2><Icon name="bulb" sprite={cfg.sprite} /> AI가 장소를 고르는 방식</h2>
      </header>

      <ol className="cb-steps">
        {STEPS.map((s, i) => <li key={i}>{s}</li>)}
      </ol>

      <h3 className="cb-flow__title">한 곳당 상한 ({people}명 기준)</h3>
      {rows.length ? (
        <ul className="cb-caps">
          {rows.map((c) => {
            const each = Math.floor(limits[c.key] / counts[c.key]);
            return (
              <li key={c.key}>
                <span className="cb-dot" style={{ background: c.color }} />
                <span className="cb-caps__name">{c.name}</span>
                <span className="cb-caps__calc">{won(limits[c.key])} ÷ {counts[c.key]}곳</span>
                <b>곳당 {won(each)}</b>
                {people > 1 && c.key !== 'stay' && <small>1인 {won(Math.floor(each / people))}</small>}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="cb-sub">일정에 가격을 아는 장소가 생기면 여기에 나와요.</p>
      )}
      <p className="cb-formula">한 곳당 상한 = 분류 예산 ÷ 그 분류 장소 수 · 계산은 코드, 장소 찾기는 AI</p>
    </section>
  );
}
