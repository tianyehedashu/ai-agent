import { Fragment, type ReactNode } from 'react'

/**
 * pathname 作 key，仅 remount 当前匹配页（不重建整棵 Routes）。
 * 缓解 URL 已变但 outlet 未切换；比 key 挂在 <Routes> 上开销更小。
 */
export function RoutePageOutlet({
  pathname,
  children,
}: Readonly<{
  pathname: string
  children: ReactNode
}>): React.JSX.Element | null {
  if (children === null || children === undefined) return null
  return <Fragment key={pathname}>{children}</Fragment>
}
