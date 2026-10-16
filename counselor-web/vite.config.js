import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base: './' → GitHub Pages 등 하위 경로에 올려도 동작해요 (HashRouter 사용)
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    // 개발 중 API 호출을 Backend 로 넘긴다. 같은 출처가 되므로 CORS 설정이 필요 없다.
    // Backend 주소가 다르면 VITE_BACKEND_URL 로 바꾼다(예: VITE_BACKEND_URL=http://127.0.0.1:8013 npm run dev).
    // 키를 '^/api/v1' 로 두어 API 접두사만 정확히 넘긴다.
    proxy: {
      '^/api/v1': {
        target: process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
