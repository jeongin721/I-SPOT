import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 고령자(온담 시니어) 상담사 웹. 서버 호출(api · 로그인 상태 등)은 counselor-web/src 를 '@cw' 로 그대로 가져다 쓴다.
// counselor-web 파일이 부르는 react 도 이 앱의 것 하나만 쓰게 dedupe 한다(둘이 섞이면 훅이 깨진다).
export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: {
    alias: { '@cw': fileURLToPath(new URL('../counselor-web/src', import.meta.url)) },
    dedupe: ['react', 'react-dom', 'react-router-dom'],
  },
  server: {
    port: 5174,
    fs: { allow: ['..'] },
    proxy: {
      '^/api/v1': {
        target: process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
