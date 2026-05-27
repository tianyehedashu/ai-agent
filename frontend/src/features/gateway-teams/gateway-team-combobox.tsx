import { useMemo, useState } from 'react'
import type React from 'react'

import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { GatewayTeamCommandItems } from '@/features/gateway-teams/gateway-team-command-items'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { ChevronsUpDown } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import { useUserStore } from '@/stores/user'

export interface GatewayTeamComboboxProps {
  value: string
  onChange: (teamId: string) => void
  teams: readonly GatewayTeam[]
  disabled?: boolean
  placeholder?: string
  className?: string
  popoverContentClassName?: string
  id?: string
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
}: Readonly<GatewayTeamComboboxProps>): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const { isPlatformAdmin } = useGatewayPermission()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)

  const selectedTeam = useMemo(
    () => teams.find((team) => team.id === value) ?? null,
    [teams, value]
  )
  const triggerLabel = selectedTeam
    ? gatewayTeamDisplayLabel(selectedTeam, { viewerUserId })
    : placeholder

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled || teams.length === 0}
          className={cn('w-full justify-between font-normal', className)}
        >
          <span className="truncate">{triggerLabel}</span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className={cn('w-[var(--radix-popover-trigger-width)] p-0', popoverContentClassName)}
        align="start"
        side="bottom"
        collisionPadding={8}
      >
        <Command>
          <CommandInput placeholder="搜索团队..." />
          <CommandList>
            <CommandEmpty>未找到匹配的团队</CommandEmpty>
            <CommandGroup heading="团队">
              <GatewayTeamCommandItems
                teams={teams}
                selectedTeamId={value}
                isPlatformAdmin={isPlatformAdmin}
                viewerUserId={viewerUserId}
                onSelectTeam={(teamId) => {
                  onChange(teamId)
                  setOpen(false)
                }}
              />
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
