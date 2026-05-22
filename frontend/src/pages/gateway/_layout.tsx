/**
 * AI Gateway 二级布局：左侧二级导航 + 右侧 Outlet
 */

import { useEffect, useMemo } from 'react'
import type { ComponentType } from 'react'
import type React from 'react'

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import {
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

type GatewayNavMatch =
  | 'credentials-default'
  | 'credentials-system'
  | 'models-default'
  | 'models-system'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  end?: boolean
  /** 与带 `?tab=system` 的入口区分高亮 */
  navMatch?: GatewayNavMatch
}

function scopeTabFromSearch(search: string): string | null {
  return new URLSearchParams(search).get('tab')
}

function isGatewayNavActive(pathname: string, search: string, navMatch: GatewayNavMatch): boolean {
  const tab = scopeTabFromSearch(search)
  switch (navMatch) {
    case 'credentials-system':
      return /\/credentials(?:\/|$)/.test(pathname) && tab === 'system'
    case 'credentials-default':
      return /\/credentials(?:\/|$)/.test(pathname) && tab !== 'system'
    case 'models-system':
      return /\/models(?:\/|$)/.test(pathname) && tab === 'system'
    case 'models-default':
      return /\/models(?:\/|$)/.test(pathname) && tab !== 'system'
  }
}

const FLAT_GATEWAY_ROUTES = ['platform-stats', 'guide'] as const

const TEAM_NAV_SEGMENTS = new Set([
  'overview',
  'stats',
  'keys',
  'credentials',
  'models',
  'pricing',
  'routes',
  'budgets',
  'logs',
  'alerts',
  'members',
  'teams',
])

/** 团队工作区侧栏必须使用绝对路径，避免在 platform-stats 等扁平路由下相对跳转叠路径 */
function gatewayTeamNavHref(
  teamId: string | null | undefined,
  segment: string,
  search = ''
): string {
  if (!teamId) return '/gateway'
  const path = `/gateway/teams/${encodeURIComponent(teamId)}/${segment}`
  return search ? `${path}?${search}` : path
}

/** 相对侧栏链接在扁平页叠出的脏路径，回收至合法扁平入口 */
function corruptedFlatGatewayPath(pathname: string): string | null {
  for (const flat of FLAT_GATEWAY_ROUTES) {
    const prefix = `/gateway/${flat}/`
    if (!pathname.startsWith(prefix)) continue
    const firstSegment = pathname.slice(prefix.length).split('/')[0] ?? ''
    if (TEAM_NAV_SEGMENTS.has(firstSegment)) {
      return `/gateway/${flat}`
    }
  }
  return null
}

export default function GatewayLayout(): React.JSX.Element {
  const { isPlatformAdmin, isAdmin } = useGatewayPermission()
  const currentTeam = useGatewayTeamStore((s) => s.current())
  const teamId = currentTeam?.id
  const location = useLocation()
  const navigate = useNavigate()
  const isGuidePage = /\/gateway\/guide(?:\/|$)/.test(location.pathname)

  useEffect(() => {
    const target = corruptedFlatGatewayPath(location.pathname)
    if (target) {
      navigate(target, { replace: true })
    }
  }, [location.pathname, navigate])

  const items = useMemo((): NavItem[] => {
    const base: NavItem[] = [
      { to: gatewayTeamNavHref(teamId, 'overview'), label: '概览', icon: BarChart3, end: true },
      { to: gatewayTeamNavHref(teamId, 'stats'), label: '调用统计', icon: LineChart },
      { to: '/gateway/guide', label: '调用指南', icon: BookOpen },
      { to: gatewayTeamNavHref(teamId, 'keys'), label: '虚拟 Key', icon: Key },
      {
        to: gatewayTeamNavHref(teamId, 'credentials'),
        label: '凭据',
        icon: Database,
        navMatch: 'credentials-default',
      },
      {
        to: gatewayTeamNavHref(teamId, 'models'),
        label: '模型',
        icon: Network,
        navMatch: 'models-default',
      },
      { to: gatewayTeamNavHref(teamId, 'pricing'), label: '定价目录', icon: CircleDollarSign },
      { to: gatewayTeamNavHref(teamId, 'routes'), label: '虚拟路由', icon: Route },
      ...(isAdmin
        ? [{ to: gatewayTeamNavHref(teamId, 'budgets'), label: '预算配额', icon: Receipt }]
        : []),
      { to: gatewayTeamNavHref(teamId, 'logs'), label: '调用日志', icon: FileText },
      { to: gatewayTeamNavHref(teamId, 'members'), label: '团队管理', icon: Users },
    ]
    if (isPlatformAdmin) {
      base.push(
        {
          to: gatewayTeamNavHref(teamId, 'credentials', 'tab=system'),
          label: '系统凭据',
          icon: Database,
          navMatch: 'credentials-system',
        },
        {
          to: gatewayTeamNavHref(teamId, 'models', 'tab=system'),
          label: '系统模型',
          icon: Network,
          navMatch: 'models-system',
        },
        { to: '/gateway/platform-stats', label: '平台统计', icon: LineChart }
      )
    }
    return base
  }, [isAdmin, isPlatformAdmin, teamId])

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
          {items.map((it) => {
            const customActive =
              it.navMatch !== undefined
                ? isGatewayNavActive(location.pathname, location.search, it.navMatch)
                : null
            return (
              <NavLink
                key={`${it.label}-${it.to}`}
                to={it.to}
                end={it.end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                    (customActive ?? isActive)
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )
                }
              >
                <it.icon className="h-4 w-4" />
                <span>{it.label}</span>
              </NavLink>
            )
          })}
        </nav>
      </aside>
      <section
        className={cn(
          'flex-1 overflow-y-auto px-6 pb-6',
          isGuidePage ? 'bg-muted/[0.12] pt-0' : 'pt-6'
        )}
      >
        <Outlet />
      </section>
    </div>
  )
}
