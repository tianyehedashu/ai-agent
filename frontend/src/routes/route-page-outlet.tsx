import { Fragment, type ReactNode } from 'react'

import { routePageOutletKey } from '@/routes/route-page-outlet-key'

/**
 * pathname 作 key，仅 remount 当前匹配页（不重建整棵 Routes）。
 * 缓解 URL 已变但 outlet 未切换；比 key 挂在 <Routes> 上开销更小。
 *
 * optional 路由段（如 /chat → /chat/:id）使用稳定 key，避免同页 remount。
 */
export function RoutePageOutlet({
  pathname,
  children,
}: Readonly<{
  pathname: string
  children: ReactNode
}>): React.JSX.Element | null {
  if (children === null || children === undefined) return null
  return <Fragment key={routePageOutletKey(pathname)}>{children}</Fragment>
}
