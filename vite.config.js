import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base: './' → GitHub Pages 등 하위 경로에 올려도 동작해요 (HashRouter 사용)
export default defineConfig({
  plugins: [react()],
  base: './',
});
