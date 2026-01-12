import type { ReactNode } from 'react'

import Header from './header'
import Sidebar from './sidebar'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps): React.JSX.Element {
  return (
    <div className="flex h-screen bg-background">
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
