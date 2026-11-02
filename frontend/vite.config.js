import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Django(8000)로 넘길 때 공통 설정
const toDjango = {
  target: 'http://localhost:8000',     // 어디로 보낼지 (Django 주소)
  changeOrigin: true,                  // 받는 쪽에 "8000으로 온 요청"처럼 보이게
  // 브라우저가 붙인 출처표(Origin: localhost:5173)를 8000으로 바꿔서 전달.
  // 안 바꾸면 Django CSRF 검사가 "모르는 출처"라며 POST를 403으로 막음
  headers: { origin: 'http://localhost:8000' },
}

// https://vite.dev/config/
// command: 'serve'(npm run dev) 또는 'build'(npm run build)
export default defineConfig(({ command }) => ({
  plugins: [react()],

  // 빌드한 파일은 Django가 /static/chat/ 주소로 내보내므로, 그 주소를 기준으로 경로를 만든다.
  // 개발 중(npm run dev)에는 그냥 '/' 기준.
  base: command === 'build' ? '/static/chat/' : '/',

  server: {                 // 개발 서버(npm run dev) 설정
    proxy: {                // 심부름꾼 목록: 이 글자로 시작하는 요청은 Django 로 넘김
      '/api': toDjango,
      '/travel_chat': toDjango,          // 대화 · 미리보기(_preview) · 적용(_apply)
      '/schedule_place_add': toDjango,   // 적용 후 담은 장소 넣기
      '/static': toDjango,               // style.css · 아이콘
    },
  },

  // npm run build 설정
  build: {
    // 결과물을 Django 정적 폴더로 바로 보냄 → /static/chat/chat.js 로 열림
    outDir: '../pj_django/sherpaapp/static/chat',
    emptyOutDir: true,      // 빌드할 때마다 예전 결과물 지우고 새로 (frontend 바깥 폴더라 직접 허락)
    copyPublicDir: false,   // public/ 의 예시 아이콘은 필요 없어서 복사 안 함
    rollupOptions: {
      output: {
        // 파일 이름 고정: 빌드할 때마다 이름이 바뀌면 chat.html 을 매번 고쳐야 하니까
        entryFileNames: 'chat.js',
        chunkFileNames: 'chat-[name].js',
        assetFileNames: 'chat.[ext]',
      },
    },
  },
}))
