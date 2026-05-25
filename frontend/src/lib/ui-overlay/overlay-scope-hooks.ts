import { useContext, useId } from 'react'

import { OverlayScopeContext, type OverlayScopeContextValue } from './overlay-scope-def'

export function useOverlayScope(): OverlayScopeContextValue | null {
  return useContext(OverlayScopeContext)
}

/**
 * Radix Portal 的挂载容器：在 OverlayScope 内时挂到 block 级 mount 点，
 * 随 scope 卸载一并销毁；否则回退 document.body。
 */
export function useOverlayPortalContainer(): HTMLElement | undefined {
  const scope = useOverlayScope()
  return scope?.portalContainer ?? undefined
}

export function useOverlayScopeId(): string {
  return useId()
}
