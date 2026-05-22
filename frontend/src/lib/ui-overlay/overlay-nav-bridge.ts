import { APP_ROOT } from '@/api/paths'

/** 供 overlay-pointer-guard 在 capture 阶段触发 React Router 导航（单例，仅 Sidebar 注册） */
let sidebarNavigate: ((href: string) => void) | null = null

/** 将侧栏 `<a href>` 转为 React Router 路径（去掉 APP_ROOT basename） */
export function hrefToRouterPath(href: string): string {
  if (!href.startsWith('/')) return href
  const root = APP_ROOT.replace(/\/$/, '')
  if (root && (href === root || href.startsWith(`${root}/`))) {
    const stripped = href.slice(root.length)
    return stripped === '' ? '/' : stripped
  }
  return href
}

export function registerSidebarNavigate(navigate: (href: string) => void): () => void {
  sidebarNavigate = navigate
  return () => {
    if (sidebarNavigate === navigate) {
      sidebarNavigate = null
    }
  }
}

export function navigateFromSidebarOverlayGuard(href: string): void {
  sidebarNavigate?.(hrefToRouterPath(href))
}
