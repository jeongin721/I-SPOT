import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 개발 중 API 호출을 Backend 로 넘긴다. 같은 출처가 되므로 CORS 설정이 필요 없다.
    // Backend 주소가 다르면 VITE_BACKEND_URL 로 바꾼다.
    //
    // 키를 '^/api/v1' 로 둔 이유: '/api' 로 두면 '/api-demo' 같은 화면 경로까지
    // Backend 로 넘어가 404 가 난다. API 접두사만 정확히 잡는다.
    proxy: {
      '^/api/v1': {
        target: process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: { host: '0.0.0.0', port: 4173 },
})
