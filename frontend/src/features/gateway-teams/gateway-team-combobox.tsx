import { useMemo, useState } from 'react'
import type React from 'react'

import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  gatewayTeamDisplayLabel,
  gatewayTeamRoleSubtitle,
} from '@/features/gateway-teams/gateway-team-display'
import { GATEWAY_FILTER_ALL } from '@/features/gateway-usage/gateway-filter-combobox'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { ChevronsUpDown } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import { useCurrentUser } from '@/stores/user'

function teamOptionSubtitle(team: GatewayTeam, viewerUserId: string | null): string | undefined {
  if (team.kind === 'shared') {
    return team.slug.trim().length > 0 ? team.slug : undefined
  }
  if (viewerUserId && team.owner_user_id !== viewerUserId) {
    return team.owner_email ?? team.owner_name ?? undefined
  }
  return team.slug.trim().length > 0 ? team.slug : undefined
}

function matchesTeamSearch(team: GatewayTeam, query: string, label: string): boolean {
  const haystack = [label, team.slug, team.name, team.owner_email, team.owner_name, team.id]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(query)
}

export interface GatewayTeamComboboxProps {
  value: string
  onChange: (teamId: string) => void
  teams: readonly GatewayTeam[]
  disabled?: boolean
  placeholder?: string
  className?: string
  popoverContentClassName?: string
  id?: string
  active?: boolean
  /** 选项与触发器主文案；默认 gatewayTeamDisplayLabel */
  labelForTeam?: (team: GatewayTeam) => string
  /** 列表首项「全部团队」；value 为 GATEWAY_FILTER_ALL */
  allowAll?: boolean
  allLabel?: string
  /** 选中 allowAll 项时触发器仍显示 placeholder（避免与外层「团队」scope 等重复） */
  allSelectedShowsPlaceholder?: boolean
  /** 团队数超过该值时显示搜索框 */
  searchThreshold?: number
}

export function GatewayTeamCombobox({
  value,
  onChange,
  teams,
  disabled = false,
  placeholder = '选择团队',
  className,
  popoverContentClassName,
  id,
  active = false,
  labelForTeam,
  allowAll = false,
  allLabel = '全部团队',
  allSelectedShowsPlaceholder = false,
  searchThreshold = 8,
}: Readonly<GatewayTeamComboboxProps>): React.JSX.Element {
  const { isPlatformAdmin } = useGatewayPermission()
  const viewerUserId = useCurrentUser()?.id ?? null
  const [search, setSearch] = useState('')

  const resolveLabel = useMemo(() => {
    if (labelForTeam) return labelForTeam
    return (team: GatewayTeam) => gatewayTeamDisplayLabel(team, { viewerUserId })
  }, [labelForTeam, viewerUserId])

  const selectedTeam = useMemo(
    () => teams.find((team) => team.id === value) ?? null,
    [teams, value]
  )

  const isAll = allowAll && value === GATEWAY_FILTER_ALL
  const triggerLabel = isAll
    ? allSelectedShowsPlaceholder
      ? placeholder
      : allLabel
    : selectedTeam
      ? resolveLabel(selectedTeam)
      : placeholder

  const filteredTeams = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return teams
    return teams.filter((team) => {
      const label = resolveLabel(team)
      return matchesTeamSearch(team, q, label)
    })
  }, [teams, search, resolveLabel])

  const showSearch = teams.length >= searchThreshold

  const radioValue = isAll ? GATEWAY_FILTER_ALL : value

  return (
    <DropdownMenu
      onOpenChange={(open) => {
        if (!open) setSearch('')
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button
          id={id}
          type="button"
          variant={active ? 'default' : 'outline'}
          role="combobox"
          disabled={disabled || (!allowAll && teams.length === 0)}
          className={cn(
            'h-9 min-w-[5.5rem] max-w-[14rem] justify-between text-xs font-normal',
            className
          )}
          title={!isAll && selectedTeam ? triggerLabel : undefined}
        >
          <span className="truncate">{triggerLabel}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className={cn(
          'max-h-[min(24rem,70vh)] w-max min-w-[min(20rem,calc(100vw-1.5rem))] max-w-[min(32rem,calc(100vw-1.5rem))] overflow-y-auto',
          popoverContentClassName
        )}
      >
        {showSearch ? (
          <div className="sticky top-0 z-10 border-b bg-popover p-2">
            <Input
              value={search}
              placeholder="搜索团队名称、slug…"
              className="h-8 text-xs"
              onChange={(event) => {
                setSearch(event.target.value)
              }}
              onKeyDown={(event) => {
                event.stopPropagation()
              }}
            />
          </div>
        ) : null}
        <DropdownMenuLabel className="flex items-center justify-between gap-2 px-2 py-1.5 text-xs font-normal text-muted-foreground">
          <span>团队</span>
          <span className="shrink-0 tabular-nums">{filteredTeams.length} 项</span>
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={radioValue}
          onValueChange={(nextTeamId) => {
            if (nextTeamId.length > 0) onChange(nextTeamId)
          }}
        >
          {allowAll ? (
            <DropdownMenuRadioItem
              value={GATEWAY_FILTER_ALL}
              className="gap-2 text-xs"
              onSelect={() => {
                onChange(GATEWAY_FILTER_ALL)
              }}
            >
              <span className="font-medium">{allLabel}</span>
            </DropdownMenuRadioItem>
          ) : null}
          {allowAll && filteredTeams.length > 0 ? <DropdownMenuSeparator /> : null}
          {filteredTeams.length === 0 ? (
            <div className="px-3 py-4 text-center text-xs text-muted-foreground">
              {search.trim() ? '未找到匹配团队' : '暂无团队'}
            </div>
          ) : (
            filteredTeams.map((team) => {
              const label = resolveLabel(team)
              const subtitle = teamOptionSubtitle(team, viewerUserId)
              return (
                <DropdownMenuRadioItem
                  key={team.id}
                  value={team.id}
                  className="items-start gap-2 py-2 text-xs"
                >
                  <div className="min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate font-medium" title={label}>
                      {label}
                    </span>
                    {subtitle ? (
                      <span className="truncate text-[11px] text-muted-foreground" title={subtitle}>
                        {subtitle}
                      </span>
                    ) : null}
                  </div>
                  <span className="shrink-0 pt-0.5 text-[10px] uppercase text-muted-foreground">
                    {gatewayTeamRoleSubtitle(team, isPlatformAdmin)}
                  </span>
                </DropdownMenuRadioItem>
              )
            })
          )}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
