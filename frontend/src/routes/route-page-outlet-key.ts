/**
 * 计算 RoutePageOutlet remount key。
 * 同一路由模板下仅 optional 段变化时不 remount，避免 Chat 首条消息 navigate 后丢 SSE 状态。
 */
export function routePageOutletKey(pathname: string): string {
  let path = pathname
  if (path.length > 1 && path.endsWith('/')) {
    path = path.slice(0, -1)
  }

  if (path === '/chat' || path.startsWith('/chat/')) {
    return '/chat'
  }

  if (
    path === '/video-tasks' ||
    (path.startsWith('/video-tasks/') && !path.startsWith('/video-tasks/history'))
  ) {
    return '/video-tasks'
  }

  return path
}
