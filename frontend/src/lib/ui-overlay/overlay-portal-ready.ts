import { useOverlayScope } from './overlay-scope-hooks'

/** Portal 容器：scope 内优先用 state，同步回退 ref（避免首次打开下拉时 Content 为 null） */
export function useOverlayPortalReady(): {
  container: HTMLElement | undefined
  /** scope 内 mount 尚未就绪，应暂缓渲染 Portal 内容 */
  deferPortal: boolean
} {
  const scope = useOverlayScope()
  const container = scope?.portalContainer ?? scope?.portalContainerRef.current ?? undefined
  return {
    container,
    deferPortal: !!scope && !container,
  }
}
