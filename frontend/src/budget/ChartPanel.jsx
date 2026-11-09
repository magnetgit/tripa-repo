// 예산 차트 (예전 비용 관리의 '지출 차트' 3개를 그대로 옮김, Chart.js 는 category_budget.html 에서 CDN 으로 불러옴)
// 1) 분류별 예산 비율 (도넛)  2) 날짜별 예상 비용 + 하루 예산 점선  3) 분류별 예산 · 일정 예상 (가로 막대)
// 입력 칸을 고치면 바로 다시 그린다
import { useEffect, useRef } from 'react';
import Icon from '../components/Icon.jsx';
import { CATS, won } from './cats.js';

// 1만 단위로 짧게: 15000 → 1.5만
const short = (v) => (Math.abs(v) >= 10000 ? `${Math.round(v / 1000) / 10}만` : String(v));
const mmdd = (iso) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;

export default function ChartPanel({ cfg, limits, plan, days, dayAmounts }) {
  const donutRef = useRef(null);
  const dailyRef = useRef(null);
  const catRef = useRef(null);
  const hasChart = typeof window !== 'undefined' && !!window.Chart;

  // 차트에 쓸 값 (바뀔 때만 다시 그리도록 글자로 묶음)
  const cats = CATS.filter((c) => limits[c.key] || plan[c.key]);
  const sumLimit = CATS.reduce((s, c) => s + (limits[c.key] || 0), 0);
  const daily = days.map((iso, i) => ({
    label: `${i + 1}일차 ${mmdd(iso)}`,
    plan: dayAmounts[iso] || 0,
  }));
  const dayBudget = days.length && sumLimit ? Math.round(sumLimit / days.length) : 0;
  const key = JSON.stringify([cats.map((c) => [c.key, limits[c.key], plan[c.key]]), daily, dayBudget]);

  useEffect(() => {
    const Chart = window.Chart;   // category_budget.html 에서 CDN 으로 불러온 Chart.js
    if (!Chart) return undefined;
    const ds = JSON.parse(key);
    const catList = ds[0].map(([k, limit, p]) => ({ ...CATS.find((c) => c.key === k), limit: limit || 0, plan: p || 0 }));
    const days2 = ds[1];
    const perDay = ds[2];


    const charts = [];

    // 1) 분류별 예산 비율 (예산이 없으면 일정 예상으로)
    const pie = catList.filter((c) => (c.limit || c.plan) > 0);
    charts.push(new Chart(donutRef.current, {
      type: 'doughnut',
      data: {
        labels: pie.map((c) => c.name),
        datasets: [{
          data: pie.map((c) => c.limit || c.plan),
          backgroundColor: pie.map((c) => c.color),
          borderColor: '#fff',
          borderWidth: 2,
        }],
      },
      options: {
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const sum = ctx.dataset.data.reduce((a, b) => a + b, 0);
                return ` ${ctx.label} ${won(ctx.parsed)} (${sum ? Math.round((ctx.parsed / sum) * 100) : 0}%)`;
              },
            },
          },
        },
      },
    }));

    // 2) 날짜별 예상 비용 (막대) + 하루 예산 (점선)
    const dailySets = [
      { type: 'bar', label: '예상 비용', data: days2.map((d) => d.plan), backgroundColor: '#9fbdf0', borderRadius: 4, maxBarThickness: 32, order: 3 },
    ];
    if (perDay > 0) {
      dailySets.push({
        type: 'line', label: '하루 예산', data: days2.map(() => perDay),
        borderColor: '#f0a03c', borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, fill: false, order: 1,
      });
    }
    charts.push(new Chart(dailyRef.current, {
      data: { labels: days2.map((d) => d.label), datasets: dailySets },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label} ${won(ctx.parsed.y)}` } },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: short }, grid: { color: '#eef1f6' } },
        },
      },
    }));

    // 3) 분류별 예산(연한 막대) · 일정 예상(분류 색)
    catRef.current.parentNode.style.height = `${Math.max(140, catList.length * 50 + 70)}px`;
    charts.push(new Chart(catRef.current, {
      type: 'bar',
      data: {
        labels: catList.map((c) => c.name),
        datasets: [
          { label: '예산', data: catList.map((c) => c.limit), backgroundColor: '#dfe7f7', borderRadius: 6, barPercentage: 0.9, categoryPercentage: 0.85, grouped: false, order: 3 },
          { label: '일정 예상', data: catList.map((c) => c.plan), backgroundColor: catList.map((c) => c.color), borderRadius: 6, barPercentage: 0.5, categoryPercentage: 0.85, grouped: false, order: 2 },
        ],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: {
              // '일정 예상'은 분류마다 색이 달라서 범례 색은 파랑 하나로
              generateLabels: (chart) => chart.data.datasets.map((d, i) => ({
                text: d.label,
                fillStyle: d.label === '예산' ? '#dfe7f7' : '#2d6cdf',
                strokeStyle: 'transparent',
                datasetIndex: i,
                hidden: !chart.isDatasetVisible(i),
              })),
            },
          },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label} ${won(ctx.parsed.x)}` } },
        },
        scales: {
          x: { beginAtZero: true, ticks: { callback: short }, grid: { color: '#eef1f6' } },
          y: { grid: { display: false } },
        },
      },
    }));

    return () => charts.forEach((c) => c.destroy());
  }, [key]);

  return (
    <section className="cb-card cb-chart" aria-labelledby="cbChartTitle">
      <header className="cb-head">
        <h2 id="cbChartTitle"><Icon name="chart" sprite={cfg.sprite} /> 예산 차트</h2>
        <span className="cb-sub">총예산 {won(sumLimit)} · 하루 예산 {won(dayBudget)}</span>
      </header>

      {!hasChart ? (
        <p className="bg-chart__empty">차트 그리는 파일을 불러오지 못했어요. 새로고침해 보세요.</p>
      ) : !cats.length ? (
        <p className="bg-chart__empty">분류별 예산이 생기면 여기에 차트가 그려져요.</p>
      ) : (
        <div className="bg-chart__grid">
          <figure className="bg-chart__box">
            <figcaption>분류별 예산 비율</figcaption>
            <div className="bg-chart__canvas bg-chart__canvas--donut">
              <canvas ref={donutRef} role="img" aria-label="분류별 예산 비율 도넛 차트" />
            </div>
          </figure>

          <figure className="bg-chart__box">
            <figcaption>날짜별 예상 비용</figcaption>
            <div className="bg-chart__canvas">
              <canvas ref={dailyRef} role="img" aria-label="날짜별 예상 비용 막대 차트" />
            </div>
          </figure>

          <figure className="bg-chart__box bg-chart__box--wide">
            <figcaption>분류별 예산 · 일정 예상</figcaption>
            <div className="bg-chart__canvas">
              <canvas ref={catRef} role="img" aria-label="분류별 예산 대비 일정 예상 가로 막대 차트" />
            </div>
          </figure>
        </div>
      )}
    </section>
  );
}
