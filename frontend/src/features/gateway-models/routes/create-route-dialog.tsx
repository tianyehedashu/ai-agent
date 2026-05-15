import { useState } from 'react'

import { Route } from 'lucide-react'

import type { GatewayModel, GatewayRouteCreateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ROUTING_STRATEGIES } from '@/features/gateway-models/constants'
import { parseModelList } from '@/features/gateway-models/utils'

interface RouteFormValues {
  virtualModel: string
  primaryModels: string
  fallbacksGeneral: string
  strategy: string
}

const emptyForm: RouteFormValues = {
  virtualModel: '',
  primaryModels: '',
  fallbacksGeneral: '',
  strategy: 'simple-shuffle',
}

interface CreateRouteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  models: GatewayModel[]
  onSubmit: (body: GatewayRouteCreateBody) => void
  isSubmitting?: boolean
}

export function CreateRouteDialog({
  open,
  onOpenChange,
  models,
  onSubmit,
  isSubmitting,
}: CreateRouteDialogProps): React.JSX.Element {
  const [values, setValues] = useState<RouteFormValues>(emptyForm)
  const modelNames = models.filter((m) => m.enabled).map((m) => m.name)

  function resetClose(next: boolean): void {
    if (!next) setValues(emptyForm)
    onOpenChange(next)
  }

  function submit(): void {
    const primary = parseModelList(values.primaryModels)
    if (!values.virtualModel.trim() || primary.length === 0) return
    onSubmit({
      virtual_model: values.virtualModel.trim(),
      primary_models: primary,
      fallbacks_general: parseModelList(values.fallbacksGeneral),
      strategy: values.strategy,
    })
  }

  return (
    <Dialog open={open} onOpenChange={resetClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Route className="h-4 w-4" />
            新建虚拟路由
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>虚拟名（对外 model）</Label>
            <Input
              className="mt-1 font-mono"
              value={values.virtualModel}
              onChange={(e) => {
                setValues({ ...values, virtualModel: e.target.value })
              }}
              placeholder="agent-default"
            />
          </div>
          <div>
            <Label>主模型（逗号分隔，须为已注册别名）</Label>
            <Input
              className="mt-1 font-mono text-sm"
              value={values.primaryModels}
              onChange={(e) => {
                setValues({ ...values, primaryModels: e.target.value })
              }}
              placeholder={modelNames.slice(0, 2).join(', ') || 'model-a, model-b'}
            />
          </div>
          <div>
            <Label>通用 Fallback（可选）</Label>
            <Input
              className="mt-1 font-mono text-sm"
              value={values.fallbacksGeneral}
              onChange={(e) => {
                setValues({ ...values, fallbacksGeneral: e.target.value })
              }}
            />
          </div>
          <div>
            <Label>策略</Label>
            <Select
              value={values.strategy}
              onValueChange={(v) => {
                setValues({ ...values, strategy: v })
              }}
            >
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROUTING_STRATEGIES.map((strategy) => (
                  <SelectItem key={strategy} value={strategy}>
                    {strategy}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              resetClose(false)
            }}
          >
            取消
          </Button>
          <Button
            onClick={submit}
            disabled={
              isSubmitting === true ||
              values.virtualModel.trim() === '' ||
              parseModelList(values.primaryModels).length === 0
            }
          >
            {isSubmitting ? '创建中…' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
