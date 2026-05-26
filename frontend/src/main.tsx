import React from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { APP_ROOT } from './api/paths'
import App from './App'
import { clearChunkReloadFlag } from './lib/lazy-with-reload'
import './index.css'

clearChunkReloadFlag()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element not found')
}
ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {/*
        不开启 v7_startTransition：会把 navigate 引起的内部 state 更新包进 React.startTransition，
        与 src/lib/ui-overlay/overlay-pointer-guard.ts 在 pointerdown capture 阶段同步触发的
        navigate + Radix Select onOpenChange 紧急更新冲突，导致 Listing 创作页展开 Select 后
        点击侧栏菜单时 transition 被推迟/丢弃（URL 不变 / 页面不刷新）。
        参考：frontend/docs/UI_OVERLAY.md
      */}
      <BrowserRouter
        basename={APP_ROOT || undefined}
        future={{
          v7_relativeSplatPath: true,
        }}
      >
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
