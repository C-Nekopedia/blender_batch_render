import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:34567',
        changeOrigin: true,
      },
      '/render': {
        target: 'http://127.0.0.1:34567',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:34567',
        ws: true,
      },
    },
  },
})
