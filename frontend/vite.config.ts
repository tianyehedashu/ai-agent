import path from 'path'

import react from '@vitejs/plugin-react'
import type { ProxyOptions } from 'vite'
import { defineConfig } from 'vite'

/** 开发代理：鉴权走 Authorization / X-Anonymous-User-Id，避免 Cookie 在 localhost 膨胀触发 431 */
function apiDevProxy(): ProxyOptions {
  return {
    target: 'http://localhost:8000',
    changeOrigin: true,
    secure: false,
    configure: (proxy) => {
      proxy.on('proxyReq', (proxyReq) => {
        proxyReq.removeHeader('cookie')
      })
      proxy.on('proxyRes', (proxyRes) => {
        delete proxyRes.headers['set-cookie']
      })
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': apiDevProxy(),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  // Gateway 子树通过 @/lib/lucide-icons 直连 ESM 图标，减轻 dev 冷启动（见 bundle-barrel-imports）
})
