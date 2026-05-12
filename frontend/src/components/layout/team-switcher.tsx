/**
 * TeamSwitcher
 *
 * AI Gateway 团队切换器：使用 cmdk Combobox + Popover。
 * 切换 team 时同步 invalidate ['gateway'] 查询。
 */

import { useEffect, useMemo, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronsUpDown, Users } from 'lucide-react'

import { gatewayApi, type GatewayTeam as ApiTeam } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import { useGatewayTeamStore } from '@/stores/gateway-team'
import { useUserStore } from '@/stores/user'

export default function TeamSwitcher(): React.JSX.Element | null {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { currentUser } = useUserStore()
  const { currentTeamId, setCurrentTeamId, setTeams } = useGatewayTeamStore()
  const isAnonymous = currentUser?.is_anonymous ?? true

  const { data: teams } = useQuery({
    queryKey: ['gateway', 'teams'],
    queryFn: () => gatewayApi.listTeams(),
    enabled: !isAnonymous,
  })

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
            <span className="truncate">{current?.name ?? '选择团队'}</span>
            {current?.kind === 'personal' && (
              <span className="rounded bg-muted px-1 py-0.5 text-[10px] uppercase text-muted-foreground">
                我
              </span>
            )}
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[260px] p-0" align="end">
        <Command>
          <CommandInput placeholder="搜索团队..." />
          <CommandList>
            <CommandEmpty>未找到匹配的团队</CommandEmpty>
            <CommandGroup heading="我的团队">
              {teams.map((team) => (
                <CommandItem
                  key={team.id}
                  value={`${team.name} ${team.slug}`}
                  onSelect={() => {
                    setCurrentTeamId(team.id)
                    setOpen(false)
                    // 切换 team 后 invalidate 所有 gateway 数据
                    void queryClient.invalidateQueries({ queryKey: ['gateway'] })
                  }}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      currentTeamId === team.id ? 'opacity-100' : 'opacity-0'
                    )}
                  />
                  <div className="flex flex-1 items-center justify-between gap-2">
                    <span className="truncate">{team.name}</span>
                    <span className="text-[10px] uppercase text-muted-foreground">
                      {team.kind === 'personal' ? '个人' : (team.team_role ?? 'member')}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
