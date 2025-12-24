import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    // 5173 被占用时自动尝试下一个端口（5174/5175...），避免启动失败
    strictPort: false,
    proxy: {
      // 同域代理：避免 CORS / 系统代理导致的 Failed to fetch
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})


