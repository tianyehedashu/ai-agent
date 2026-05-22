import { useCallback, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { gatewayApi, type GatewayModel, type SystemModelVisibility } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { channelLabel } from '@/features/gateway-models/utils'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Shield } from '@/lib/lucide-icons'

import { SystemGrantsPanel } from './system-grants-panel'

interface SystemModelAdminMetaProps {
  model: GatewayModel
}

export function SystemModelAdminMeta({ model }: SystemModelAdminMetaProps): React.JSX.Element {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [grantsOpen, setGrantsOpen] = useState(false)
  const visibility = model.visibility ?? 'inherit'

  const patchMutation = useMutation({
    mutationFn: (v: SystemModelVisibility) => gatewayApi.patchModelVisibility(model.id, v),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      toast({ title: '可见性已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const handleVisibilityChange = useCallback(
    (v: string) => {
      patchMutation.mutate(v as SystemModelVisibility)
    },
    [patchMutation]
  )

  const cred = model.system_credential

  return (
    <div
      className="mt-2 flex flex-wrap items-center gap-2 border-t border-dashed pt-2"
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
      }}
      onKeyDown={(e) => {
        e.stopPropagation()
      }}
      role="presentation"
    >
      <Select
        value={visibility}
        onValueChange={handleVisibilityChange}
        disabled={patchMutation.isPending}
      >
        <SelectTrigger className="h-7 w-[108px] text-xs" aria-label="模型可见性">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="inherit">继承凭据</SelectItem>
          <SelectItem value="public">公开</SelectItem>
          <SelectItem value="restricted">受限</SelectItem>
        </SelectContent>
      </Select>
      {patchMutation.isPending ? (
        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
      ) : null}
      {cred ? (
        <span className="text-xs text-muted-foreground">
          凭据：{channelLabel(cred.provider)} · {cred.name}
          <span className="ml-1 rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
            {cred.visibility}
          </span>
        </span>
      ) : null}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 text-xs"
        onClick={() => {
          setGrantsOpen(true)
        }}
      >
        <Shield className="mr-1 h-3 w-3" />
        授权
      </Button>
      <SystemGrantsPanel
        open={grantsOpen}
        onOpenChange={setGrantsOpen}
        subjectKind="model"
        subjectId={model.id}
        subjectLabel={model.name}
      />
    </div>
  )
}
