import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 카테고리 예산 화면 (React) 빌드 설정 — /chat/ 빌드(vite.config.js)와 따로 만들어서 서로 안 건드림
// npm run build 하면 두 설정이 차례로 돈다 (package.json)
// 결과: pj_django/sherpaapp/static/budget/budget.js · budget.css  ← category_budget.html 이 읽음
export default defineConfig({
  plugins: [react()],
  base: '/static/budget/',
  build: {
    outDir: '../pj_django/sherpaapp/static/budget',
    emptyOutDir: true,
    copyPublicDir: false,
    rollupOptions: {
      input: 'src/budget/main.jsx',
      output: {
        // 파일 이름 고정 (category_budget.html 을 매번 안 고치게)
        entryFileNames: 'budget.js',
        chunkFileNames: 'budget-[name].js',
        assetFileNames: 'budget.[ext]',
      },
    },
  },
})
