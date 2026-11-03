import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { readConfig } from './lib/config.js';
import './chat.css';

// Django 페이지(chat.html)의 #root (.tc-app) 안에 대화·초안·지도 3칸을 그린다.
// 설정(주소·CSRF 토큰 등)은 그리기 전에 #root 의 data- 속성에서 먼저 읽어 둔다.
const root = document.getElementById('root');
const cfg = readConfig(root);

createRoot(root).render(<App cfg={cfg} />);
