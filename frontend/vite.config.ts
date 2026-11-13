import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// In development, API calls are proxied to Django on :8000.
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
