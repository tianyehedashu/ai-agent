import { createContext, type RefObject } from 'react'

export interface OverlayScopeContextValue {
  scopeId: string
  /** 已挂载的 Portal 容器（callback ref 更新后触发子树重渲染） */
  portalContainer: HTMLElement | null
  /** 仅供 teardown 使用 */
  portalContainerRef: RefObject<HTMLDivElement | null>
}

export const OverlayScopeContext = createContext<OverlayScopeContextValue | null>(null)
