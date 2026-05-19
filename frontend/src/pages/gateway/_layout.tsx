/**
 * AI Gateway 二级布局：左侧二级导航 + 右侧 Outlet
 */

import { useMemo } from 'react'
import type { ComponentType } from 'react'
import type React from 'react'

import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { CurrencyToggle } from '@/components/currency-toggle'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  CircleDollarSign,
  Database,
  FileText,
  Key,
  LineChart,
  Network,
  Route,
  Receipt,
  Server,
  Users,
} from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import { useGatewayTeamStore } from '@/stores/gateway-team'

type NavItem = { to: string; label: string; icon: ComponentType<{ className?: string }> }

/** 以下页面不展示币种切换：指南、上游成本（固定 USD） */
const HIDE_CURRENCY_TOGGLE_PATH_RE = /\/gateway\/(?:guide|pricing\/upstream)(?:\/|$)/

export default function GatewayLayout(): React.JSX.Element {
  const { isPlatformAdmin } = useGatewayPermission()
  const currentTeam = useGatewayTeamStore((s) => s.current())
  const location = useLocation()
  const isGuidePage = /\/gateway\/guide(?:\/|$)/.test(location.pathname)
  const showCurrencyToggle = useMemo(
    () => !HIDE_CURRENCY_TOGGLE_PATH_RE.test(location.pathname),
    [location.pathname]
  )

  const items = useMemo((): NavItem[] => {
    const base: NavItem[] = [
      { to: 'overview', label: '概览', icon: BarChart3 },
      { to: 'guide', label: '调用指南', icon: BookOpen },
      { to: 'keys', label: '虚拟 Key', icon: Key },
      { to: 'credentials', label: '凭据', icon: Database },
      { to: 'models', label: '模型', icon: Network },
      { to: 'pricing', label: '定价目录', icon: CircleDollarSign },
      { to: 'routes', label: '虚拟路由', icon: Route },
      { to: 'budgets', label: '预算配额', icon: Receipt },
      { to: 'logs', label: '调用日志', icon: FileText },
      { to: 'alerts', label: '告警规则', icon: AlertTriangle },
      { to: 'teams', label: '团队成员', icon: Users },
    ]
    if (isPlatformAdmin) {
      base.push({ to: 'platform-stats', label: '平台统计', icon: LineChart })
    }
    return base
  }, [isPlatformAdmin])

  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-56 flex-col border-r border-border/40 bg-background/60 px-3 py-4">
        <div className="mb-3 flex items-center gap-2 px-2 text-sm font-semibold tracking-tight">
          <Server className="h-4 w-4 shrink-0 text-primary" />
          AI Gateway
        </div>
        {currentTeam ? (
          <div
            className="mb-2 truncate px-2 text-xs text-muted-foreground"
            title={currentTeam.name}
          >
            {currentTeam.name}
          </div>
        ) : null}
        <nav className="flex flex-col gap-1">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === 'overview'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )
              }
            >
              <it.icon className="h-4 w-4" />
              <span>{it.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <section
        className={cn(
          'flex-1 overflow-y-auto px-6 pb-6',
          isGuidePage ? 'bg-muted/[0.12] pt-0' : 'pt-6'
        )}
      >
        {showCurrencyToggle ? (
          <div className="mb-4 flex justify-end">
            <CurrencyToggle />
          </div>
        ) : null}
        <Outlet />
      </section>
    </div>
  )
}
