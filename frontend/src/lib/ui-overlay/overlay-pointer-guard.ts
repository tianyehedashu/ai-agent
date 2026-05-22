import { navigateFromSidebarOverlayGuard, registerSidebarNavigate } from './overlay-nav-bridge'
import { dismissOpenRadixLayers, releaseUiOverlayLock } from './release-overlay-lock'

const NAV_LINK_SELECTOR = '[data-app-sidebar] a[href]'

const OPEN_RADIX_OVERLAY_SELECTOR = [
  '[role="listbox"][data-state="open"]',
  '[data-radix-menu-content][data-state="open"]',
  '[data-radix-popover-content][data-state="open"]',
  '[data-radix-select-content][data-state="open"]',
].join(', ')

function hasOpenModalLayer(): boolean {
  return !!document.querySelector(
    '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]'
  )
}

/** Select 无 modal 属性，打开时仍会锁 body；Dropdown/Popover 在 modal=false 时也可能残留 */
export function hasOpenRadixOverlay(): boolean {
  return !!document.querySelector(OPEN_RADIX_OVERLAY_SELECTOR)
}

function isSidebarNavTarget(target: EventTarget | null): target is Element {
  return target instanceof Element && !!target.closest(NAV_LINK_SELECTOR)
}

function shouldForceSidebarNav(): boolean {
  return (
    hasOpenRadixOverlay() ||
    document.body.style.pointerEvents === 'none' ||
    document.body.hasAttribute('data-scroll-locked')
  )
}

/** 释放 Radix 浮层卸载后偶发残留的 body pointer-events:none（非 Dialog / 非仍打开的浮层） */
export function releaseStuckBodyPointerEvents(): void {
  if (typeof document === 'undefined') return
  if (document.body.style.pointerEvents !== 'none') return
  if (hasOpenModalLayer()) return
  if (hasOpenRadixOverlay()) return
  releaseUiOverlayLock()
}

export function installOverlayPointerGuard(): () => void {
  if (typeof document === 'undefined') return () => {}

  const onPointerDown = (event: PointerEvent): void => {
    const target = event.target
    const isNav = isSidebarNavTarget(target)

    if (isNav) {
      const href = target instanceof Element ? target.closest('a')?.getAttribute('href') : null

      if (shouldForceSidebarNav() && href) {
        event.preventDefault()
        event.stopImmediatePropagation()
        dismissOpenRadixLayers()
        releaseUiOverlayLock()
        navigateFromSidebarOverlayGuard(href)
        return
      }
    }

    releaseStuckBodyPointerEvents()
  }

  document.addEventListener('pointerdown', onPointerDown, true)
  return () => {
    document.removeEventListener('pointerdown', onPointerDown, true)
  }
}

export { registerSidebarNavigate }
