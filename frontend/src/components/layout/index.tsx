import { useEffect, type ReactNode } from 'react'

import { useLocation } from 'react-router-dom'

import { installOverlayPointerGuard } from '@/lib/ui-overlay/overlay-pointer-guard'
import { teardownAllOverlayScopes } from '@/lib/ui-overlay/teardown-overlay-scope'

import Header from './header'
import Sidebar from './sidebar'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: Readonly<LayoutProps>): React.JSX.Element {
  const { pathname } = useLocation()

  useEffect(() => {
    teardownAllOverlayScopes()
  }, [pathname])

  useEffect(() => installOverlayPointerGuard(), [])

  return (
    <div className="pointer-events-auto flex h-screen bg-background">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <Header />

        {/* Page Content */}
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
