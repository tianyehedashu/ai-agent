import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

const CHUNK_RELOAD_KEY = 'ai-agent:chunk-reload'

/** 成功加载任意路由 chunk 后清除，避免正常导航触发重复刷新 */
export function clearChunkReloadFlag(): void {
  sessionStorage.removeItem(CHUNK_RELOAD_KEY)
}

type LazyModule<T extends ComponentType> = { default: T }

function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false
  }
  const message = error.message.toLowerCase()
  return (
    message.includes('failed to fetch dynamically imported module') ||
    message.includes('importing a module script failed') ||
    message.includes('error loading dynamically imported module')
  )
}

/**
 * 路由 lazy import：部署后旧 chunk 404 时自动刷新一次以拉取新 index/assets。
 *
 * 泛型约束与 React.lazy 一致（@types/react 使用 ComponentType<any>），
 * 否则带具体 props 的页面组件无法通过 strictFunctionTypes 检查。
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- parity with React.lazy()
export function lazyWithReload<T extends ComponentType<any>>(
  factory: () => Promise<LazyModule<T>>
): LazyExoticComponent<T> {
  return lazy(() =>
    factory().catch((error: unknown) => {
      if (isChunkLoadError(error) && !sessionStorage.getItem(CHUNK_RELOAD_KEY)) {
        sessionStorage.setItem(CHUNK_RELOAD_KEY, '1')
        window.location.reload()
        return new Promise<LazyModule<T>>(() => {
          /* 等待 reload */
        })
      }
      throw error
    })
  )
}
