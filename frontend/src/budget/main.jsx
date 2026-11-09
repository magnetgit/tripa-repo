import { createRoot } from 'react-dom/client';
import BudgetApp from './BudgetApp.jsx';
import { readBudgetConfig } from './api.js';
import './budget.css';

// Django 페이지(category_budget.html)의 #root 안에 카테고리 예산 화면을 그린다.
// 예산 차트 기본 모양 (예전 비용 관리 차트와 같게) — Chart.js 는 HTML 에서 먼저 불러옴
if (window.Chart) {
  const d = window.Chart.defaults;
  d.font.family = getComputedStyle(document.body).fontFamily;
  d.font.size = 11;
  d.color = '#7b88a1';
  d.plugins.legend.labels.boxWidth = 10;
  d.plugins.legend.labels.boxHeight = 10;
}

const root = document.getElementById('root');
const cfg = readBudgetConfig(root);

createRoot(root).render(<BudgetApp cfg={cfg} />);
