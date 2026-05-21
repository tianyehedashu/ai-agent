import path from 'path'

import react from '@vitejs/plugin-react'
import type { ProxyOptions } from 'vite'
import { defineConfig, loadEnv } from 'vite'

const DEFAULT_APP_ROOT = '/ai-agent'

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
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const appRootRaw = env.VITE_APP_ROOT
  const appRoot = (appRootRaw === undefined ? DEFAULT_APP_ROOT : appRootRaw).replace(/\/$/, '')
  // 仅代理 API（/ai-agent/api/*），勿代理 SPA 静态页（/ai-agent/）
  const proxyPrefix = appRoot ? `${appRoot}/api` : '/api'

  return {
    base: appRoot ? `${appRoot}/` : '/',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      proxy: {
        [proxyPrefix]: apiDevProxy(),
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
    // Gateway 子树通过 @/lib/lucide-icons 直连 ESM 图标，减轻 dev 冷启动（见 bundle-barrel-imports）
  }
})
