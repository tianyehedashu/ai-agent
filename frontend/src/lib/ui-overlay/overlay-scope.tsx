/**
 * OverlayScope — block 级浮层作用域
 *
 * 设计目标：
 * 1. 子树内 Select/Dropdown/Popover Portal 挂到 scope 内 mount 点，折叠/卸载时 DOM 一并移除
 * 2. unmount 时防御性释放 body 级 pointer-events / scroll-lock 泄漏
 *
 * 用法：可折叠 block 的「展开内容」外包一层 <OverlayScope>，无需在各处手动 dismiss。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

import { OverlayScopeProvider, useOverlayScopeId } from './overlay-scope-context'
import { teardownOverlayScope } from './teardown-overlay-scope'

export interface OverlayScopeProps {
  children: React.ReactNode
  className?: string
}

export function OverlayScope({ children, className }: OverlayScopeProps): React.JSX.Element {
  const scopeId = useOverlayScopeId()
  const portalContainerRef = useRef<HTMLDivElement | null>(null)
  const [portalContainer, setPortalContainer] = useState<HTMLDivElement | null>(null)

  const setPortalMountRef = useCallback((node: HTMLDivElement | null) => {
    portalContainerRef.current = node
    setPortalContainer(node)
  }, [])

  useEffect(() => {
    return () => {
      teardownOverlayScope(portalContainerRef.current)
    }
  }, [])

  return (
    <OverlayScopeProvider
      scopeId={scopeId}
      portalContainer={portalContainer}
      portalContainerRef={portalContainerRef}
    >
      <div data-overlay-scope={scopeId} className={cn('relative', className)}>
        {children}
        {/* 零尺寸 mount：避免 absolute inset-0 覆盖 block 内可点击区域 */}
        <div
          ref={setPortalMountRef}
          data-overlay-portal-mount=""
          className="pointer-events-none fixed left-0 top-0 z-[9999] h-0 w-0 overflow-visible [&_[data-radix-popper-content-wrapper]]:pointer-events-auto"
          aria-hidden
        />
      </div>
    </OverlayScopeProvider>
  )
}
