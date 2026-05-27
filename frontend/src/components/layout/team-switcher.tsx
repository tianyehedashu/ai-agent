/**
 * TeamSwitcher
 *
 * AI Gateway 团队切换器：使用 cmdk Combobox + Popover。
 * 切换 team 时同步 invalidate ['gateway'] 查询。
 */

import { useEffect, useMemo, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { ChevronsUpDown, Users } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import type { GatewayTeam as ApiTeam } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { GatewayTeamCommandItems } from '@/features/gateway-teams/gateway-team-command-items'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { switchGatewayTeam } from '@/features/gateway-teams/navigate-team'
import { useGatewayMemberTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamStore } from '@/stores/gateway-team'
import { useUserStore } from '@/stores/user'

export default function TeamSwitcher(): React.JSX.Element | null {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const { currentUser } = useUserStore()
  const { isPlatformAdmin } = useGatewayPermission()
  const { currentTeamId, setTeams } = useGatewayTeamStore()
  const viewerUserId = currentUser?.id ?? null
  const isAnonymous = currentUser?.is_anonymous ?? true

  const {
    data: teams,
    isFetching: memberTeamsFetching,
    refetch: refetchMemberTeams,
  } = useGatewayMemberTeams(!isAnonymous)

  useEffect(() => {
    if (teams) {
      setTeams(
        teams.map(
          (t: ApiTeam): ApiTeam => ({
            id: t.id,
            name: t.name,
            slug: t.slug,
            kind: t.kind,
            owner_user_id: t.owner_user_id,
            team_role: t.team_role,
          })
        )
      )
    }
  }, [teams, setTeams])

  const current = useMemo(
    () => teams?.find((t) => t.id === currentTeamId) ?? null,
    [teams, currentTeamId]
  )

  if (isAnonymous) return null
  if (!teams || teams.length === 0) return null

  const currentLabel = current ? gatewayTeamDisplayLabel(current, { viewerUserId }) : '选择团队'

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="h-8 min-w-[180px] justify-between gap-2 px-3 text-xs font-medium"
        >
          <span className="flex items-center gap-2 truncate">
            <Users className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate">{currentLabel}</span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[260px] p-0" align="end">
        <div className="flex items-center justify-end border-b px-2 py-1">
          <GatewayRefreshButton
            isFetching={memberTeamsFetching}
            ariaLabel="刷新团队列表"
            className="h-7 w-7"
            onRefresh={() => refetchMemberTeams()}
          />
        </div>
        <Command>
          <CommandInput placeholder="搜索团队..." />
          <CommandList>
            <CommandEmpty>未找到匹配的团队</CommandEmpty>
            <CommandGroup heading="我的团队">
              <GatewayTeamCommandItems
                teams={teams}
                selectedTeamId={currentTeamId}
                isPlatformAdmin={isPlatformAdmin}
                viewerUserId={viewerUserId}
                onSelectTeam={(teamId) => {
                  setOpen(false)
                  switchGatewayTeam(teamId, navigate, location, queryClient)
                }}
              />
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
