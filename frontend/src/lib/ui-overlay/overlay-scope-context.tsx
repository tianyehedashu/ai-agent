import { createContext, useContext, useMemo, useId, type RefObject } from 'react'

export interface OverlayScopeContextValue {
  scopeId: string
  /** 已挂载的 Portal 容器（callback ref 更新后触发子树重渲染） */
  portalContainer: HTMLElement | null
  /** 仅供 teardown 使用 */
  portalContainerRef: RefObject<HTMLDivElement | null>
}

const OverlayScopeContext = createContext<OverlayScopeContextValue | null>(null)

export function OverlayScopeProvider({
  scopeId,
  portalContainer,
  portalContainerRef,
  children,
}: {
  scopeId: string
  portalContainer: HTMLElement | null
  portalContainerRef: RefObject<HTMLDivElement | null>
  children: React.ReactNode
}): React.JSX.Element {
  const value = useMemo(
    () => ({ scopeId, portalContainer, portalContainerRef }),
    [scopeId, portalContainer, portalContainerRef]
  )

  return <OverlayScopeContext.Provider value={value}>{children}</OverlayScopeContext.Provider>
}

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
