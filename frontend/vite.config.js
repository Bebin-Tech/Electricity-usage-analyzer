import { defineConfig } from 'vite';
export default defineConfig({build:{rollupOptions:{output:{manualChunks:{charts:['recharts']}}}},server:{proxy:{'/api':{target:process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000',changeOrigin:true}}}});
