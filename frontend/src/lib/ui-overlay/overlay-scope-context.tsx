import { useMemo, type RefObject } from 'react'

import { OverlayScopeContext, type OverlayScopeContextValue } from './overlay-scope-def'

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
    (): OverlayScopeContextValue => ({ scopeId, portalContainer, portalContainerRef }),
    [scopeId, portalContainer, portalContainerRef]
  )

  return <OverlayScopeContext.Provider value={value}>{children}</OverlayScopeContext.Provider>
}
