/**
 * 释放 Radix / RemoveScroll 等可能遗留的 document 级点击封锁。
 *
 * 仅清理 body/html 样式与 focus guard，不手动移除 Portal DOM——
 * 否则会与 React commit 阶段 removeChild 冲突（如 Sidebar Tooltip）。
 */
export function releaseUiOverlayLock(): void {
  if (typeof document === 'undefined') return

  const { body, documentElement: html } = document

  body.style.removeProperty('pointer-events')
  body.style.removeProperty('overflow')
  body.style.removeProperty('padding-right')
  body.style.removeProperty('margin-right')
  html.style.removeProperty('overflow')
  html.style.removeProperty('padding-right')

  body.removeAttribute('data-scroll-locked')
  html.removeAttribute('data-scroll-locked')

  document.querySelectorAll('[data-radix-focus-guard]').forEach((el) => {
    el.remove()
  })
}

/** 关闭 document 上仍打开的 Radix 浮层并释放 body 封锁 */
export function dismissOpenRadixLayers(): void {
  if (typeof document === 'undefined') return

  document.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true })
  )
  releaseUiOverlayLock()
}

/** 在 React commit 完成后再执行，避免与 Portal 卸载竞态 */
export function deferReleaseUiOverlayLock(): void {
  if (typeof document === 'undefined') return
  queueMicrotask(() => {
    releaseUiOverlayLock()
  })
}

/** 路由切换等全局场景：关闭浮层并在下一微任务释放 body 封锁 */
export function deferDismissOpenRadixLayers(): void {
  if (typeof document === 'undefined') return
  document.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true })
  )
  deferReleaseUiOverlayLock()
}
