import { useCallback, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  gatewayApi,
  type SystemGatewayGrant,
  type SystemGatewayGrantCreateBody,
} from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/hooks/use-toast'
import { ExternalLink, Loader2, Trash2 } from '@/lib/lucide-icons'

interface SystemGrantsPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjectKind: 'credential' | 'model'
  subjectId: string
  subjectLabel: string
}

function grantsQueryKey(subjectKind: string, subjectId: string): string[] {
  return ['gateway', 'system-grants', subjectKind, subjectId]
}

export function SystemGrantsPanel({
  open,
  onOpenChange,
  subjectKind,
  subjectId,
  subjectLabel,
}: SystemGrantsPanelProps): React.JSX.Element {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [targetKind, setTargetKind] = useState<'team' | 'user'>('team')
  const [targetId, setTargetId] = useState('')
  const [note, setNote] = useState('')

  const { data: grants = [], isLoading } = useQuery({
    queryKey: grantsQueryKey(subjectKind, subjectId),
    queryFn: () =>
      subjectKind === 'credential'
        ? gatewayApi.listCredentialGrants(subjectId)
        : gatewayApi.listModelGrants(subjectId),
    enabled: open,
  })

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: grantsQueryKey(subjectKind, subjectId) })
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
  }, [queryClient, subjectKind, subjectId])

  const createMutation = useMutation({
    mutationFn: (body: SystemGatewayGrantCreateBody) => gatewayApi.createGrant(body),
    onSuccess: () => {
      invalidate()
      setTargetId('')
      setNote('')
      toast({ title: '授权已添加' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '添加失败', description: e.message })
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      gatewayApi.updateGrant(id, { enabled }),
    onSuccess: invalidate,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteGrant(id),
    onSuccess: () => {
      invalidate()
      toast({ title: '授权已移除' })
    },
  })

  const handleAdd = (): void => {
    const tid = targetId.trim()
    if (!tid) {
      toast({ variant: 'destructive', title: '请填写目标 ID' })
      return
    }
    createMutation.mutate({
      subject_kind: subjectKind,
      subject_id: subjectId,
      target_kind: targetKind,
      target_id: tid,
      note: note.trim() || undefined,
    })
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>可见性授权</SheetTitle>
          <SheetDescription className="text-left">
            {subjectLabel} — restricted 时仅下列 team/user 可见。配额与定价请在预算/定价页配置。
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <Button variant="outline" size="sm" className="h-7" asChild>
            <a href="/gateway/budgets" target="_blank" rel="noreferrer">
              预算配额
              <ExternalLink className="ml-1 h-3 w-3" />
            </a>
          </Button>
          <Button variant="outline" size="sm" className="h-7" asChild>
            <a href="/gateway/pricing/downstream" target="_blank" rel="noreferrer">
              下游定价
              <ExternalLink className="ml-1 h-3 w-3" />
            </a>
          </Button>
        </div>

        <div className="mt-4 space-y-3 rounded-md border p-3">
          <p className="text-xs font-medium text-muted-foreground">新增授权</p>
          <div className="grid gap-2">
            <Label className="text-xs">目标类型</Label>
            <Select
              value={targetKind}
              onValueChange={(v) => {
                setTargetKind(v as 'team' | 'user')
              }}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="team">团队 (team_id)</SelectItem>
                <SelectItem value="user">用户 (user_id)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label className="text-xs">目标 UUID</Label>
            <Input
              value={targetId}
              onChange={(e) => {
                setTargetId(e.target.value)
              }}
              placeholder="粘贴 team_id 或 user_id"
              className="h-8 font-mono text-xs"
            />
          </div>
          <div className="grid gap-2">
            <Label className="text-xs">备注（可选）</Label>
            <Input
              value={note}
              onChange={(e) => {
                setNote(e.target.value)
              }}
              className="h-8 text-xs"
            />
          </div>
          <Button
            size="sm"
            className="w-full"
            disabled={createMutation.isPending}
            onClick={handleAdd}
          >
            {createMutation.isPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            添加
          </Button>
        </div>

        <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">加载授权…</p>
          ) : grants.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无授权（restricted 时对所有人不可见）</p>
          ) : (
            <ul className="space-y-2">
              {grants.map((g: SystemGatewayGrant) => (
                <li
                  key={g.id}
                  className="flex items-start justify-between gap-2 rounded-md border px-2 py-2 text-xs"
                >
                  <div className="min-w-0">
                    <p className="font-medium">
                      {g.target_kind} · <span className="font-mono">{g.target_id}</span>
                    </p>
                    {g.note ? <p className="text-muted-foreground">{g.note}</p> : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <Switch
                      checked={g.enabled}
                      onCheckedChange={(checked) => {
                        toggleMutation.mutate({ id: g.id, enabled: checked })
                      }}
                      aria-label="启用授权"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => {
                        deleteMutation.mutate(g.id)
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
