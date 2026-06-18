/**
 * AI Gateway 二级布局：左侧二级导航 + 右侧 Outlet
 */

import { useEffect, useMemo } from 'react'
import type { ComponentType } from 'react'
import type React from 'react'

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useSyncGatewayTeamRoute } from '@/features/gateway-teams/use-sync-gateway-team-route'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useResolvedGatewayTeamId } from '@/hooks/use-gateway-team-id'
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
  UserCog,
  Users,
} from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

type GatewayNavMatch = 'credentials-default' | 'credentials-system'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  section: GatewayNavSection
  end?: boolean
  /** 与带 legacy `?tab=system` 的入口区分高亮（凭据） */
  navMatch?: GatewayNavMatch
}

type GatewayNavSection = 'observe' | 'access' | 'control' | 'admin'

const GATEWAY_NAV_SECTION_LABELS: Record<GatewayNavSection, string> = {
  observe: '观测',
  access: '接入',
  control: '治理',
  admin: '组织',
}

const GATEWAY_NAV_SECTION_ORDER: GatewayNavSection[] = ['observe', 'access', 'control', 'admin']

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
  const teamId = useResolvedGatewayTeamId()
  const location = useLocation()
  const navigate = useNavigate()
  const isGuidePage = /\/gateway\/guide(?:\/|$)/.test(location.pathname)

  useSyncGatewayTeamRoute()

  useEffect(() => {
    const target = corruptedFlatGatewayPath(location.pathname)
    if (target) {
      navigate(target, { replace: true })
    }
  }, [location.pathname, navigate])

  const items = useMemo((): NavItem[] => {
    const base: NavItem[] = [
      {
        to: gatewayTeamNavHref(teamId, 'overview'),
        label: '概览',
        icon: BarChart3,
        section: 'observe',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'stats'),
        label: '调用统计',
        icon: LineChart,
        section: 'observe',
        end: true,
      },
      { to: '/gateway/guide', label: '调用指南', icon: BookOpen, section: 'observe', end: true },
      {
        to: gatewayTeamNavHref(teamId, 'keys'),
        label: '虚拟 Key',
        icon: Key,
        section: 'access',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'credentials'),
        label: '凭据',
        icon: Database,
        section: 'access',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'models'),
        label: '模型',
        icon: Network,
        section: 'access',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'pricing'),
        label: '定价目录',
        icon: CircleDollarSign,
        section: 'control',
      },
      {
        to: gatewayTeamNavHref(teamId, 'routes'),
        label: '虚拟路由',
        icon: Route,
        section: 'control',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'budgets'),
        label: isAdmin ? '配额中心' : '我的配额',
        icon: Receipt,
        section: 'control',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'logs'),
        label: '调用日志',
        icon: FileText,
        section: 'control',
        end: true,
      },
      {
        to: gatewayTeamNavHref(teamId, 'members'),
        label: '团队管理',
        icon: Users,
        section: 'admin',
        end: true,
      },
    ]
    if (isPlatformAdmin) {
      base.push(
        {
          to: '/gateway/platform-stats',
          label: '平台统计',
          icon: LineChart,
          section: 'admin',
          end: true,
        },
        {
          to: '/admin/users',
          label: '用户管理',
          icon: UserCog,
          section: 'admin',
          end: true,
        }
      )
    }
    return base
  }, [isAdmin, isPlatformAdmin, teamId])
  const navSections = useMemo(
    () =>
      GATEWAY_NAV_SECTION_ORDER.map((section) => ({
        section,
        items: items.filter((item) => item.section === section),
      })).filter((group) => group.items.length > 0),
    [items]
  )

  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-60 flex-col border-r border-border/60 bg-card/55 px-3 py-4 backdrop-blur-xl">
        <div className="mb-4 rounded-lg border border-primary/15 bg-primary/10 px-3 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold tracking-tight text-foreground">
            <Server className="h-4 w-4 shrink-0 text-primary" />
            AI Gateway
          </div>
          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
            模型、凭据、调用与预算中心
          </p>
        </div>
        <nav className="flex flex-col gap-4">
          {navSections.map(({ section, items: sectionItems }) => (
            <div key={section} className="space-y-1">
              <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/60">
                {GATEWAY_NAV_SECTION_LABELS[section]}
              </p>
              {sectionItems.map((it) => {
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
                        'group flex items-center gap-2 rounded-lg border border-transparent px-3 py-2 text-sm transition-colors',
                        (customActive ?? isActive)
                          ? 'border-primary/20 bg-primary/10 text-primary shadow-sm shadow-primary/10'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      )
                    }
                  >
                    {({ isActive }) => {
                      const active = customActive ?? isActive
                      return (
                        <>
                          <span
                            className={cn(
                              'h-4 w-0.5 rounded-full transition-colors',
                              active ? 'bg-primary' : 'bg-transparent group-hover:bg-border'
                            )}
                          />
                          <it.icon className="h-4 w-4" />
                          <span>{it.label}</span>
                        </>
                      )
                    }}
                  </NavLink>
                )
              })}
            </div>
          ))}
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
