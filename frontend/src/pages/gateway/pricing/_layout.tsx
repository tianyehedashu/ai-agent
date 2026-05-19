import type React from 'react'

import { NavLink, Outlet } from 'react-router-dom'

import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { cn } from '@/lib/utils'

export default function GatewayPricingLayout(): React.JSX.Element {
  const { isPlatformAdmin, isAdmin } = useGatewayPermission()

  const tabs: { to: string; label: string; show: boolean }[] = [
    { to: 'my-prices', label: '我的价格', show: true },
    { to: 'downstream', label: '下游售价', show: isAdmin },
    { to: 'upstream', label: '上游成本', show: isPlatformAdmin },
  ]

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-border/40 pb-2">
        {tabs
          .filter((t) => t.show)
          .map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              className={({ isActive }) =>
                cn(
                  'rounded-md px-3 py-1.5 text-sm',
                  isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted'
                )
              }
            >
              {t.label}
            </NavLink>
          ))}
      </div>
      <Outlet />
    </div>
  )
}
