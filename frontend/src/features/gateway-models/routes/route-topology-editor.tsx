import { useEffect, useMemo, useState } from 'react'

import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react'

import type { GatewayModel, GatewayRoute, GatewayRouteUpdateBody } from '@/api/gateway'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { ROUTING_STRATEGIES } from '@/features/gateway-models/constants'
import { parseModelList } from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { cn } from '@/lib/utils'

interface RouteTopologyEditorProps {
  route: GatewayRoute | null
  models: GatewayModel[]
  isSaving: boolean
  onSave: (id: string, body: GatewayRouteUpdateBody) => void
}

function modelByName(models: GatewayModel[], name: string): GatewayModel | undefined {
  return models.find((m) => m.name === name)
}

export function RouteTopologyEditor({
  route,
  models,
  isSaving,
  onSave,
}: RouteTopologyEditorProps): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const enabledModelNames = useMemo(
    () => models.filter((m) => m.enabled).map((m) => m.name),
    [models]
  )
  const allModelNames = useMemo(() => models.map((m) => m.name), [models])

  const [primaryModels, setPrimaryModels] = useState<string[]>([])
  const [strategy, setStrategy] = useState('simple-shuffle')
  const [enabled, setEnabled] = useState(true)
  const [fallbacksGeneral, setFallbacksGeneral] = useState('')
  const [fallbacksContentPolicy, setFallbacksContentPolicy] = useState('')
  const [fallbacksContextWindow, setFallbacksContextWindow] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)

  useEffect(() => {
    if (!route) return
    setPrimaryModels([...route.primary_models])
    setStrategy(route.strategy)
    setEnabled(route.enabled)
    setFallbacksGeneral(route.fallbacks_general.join(', '))
    setFallbacksContentPolicy(route.fallbacks_content_policy.join(', '))
    setFallbacksContextWindow(route.fallbacks_context_window.join(', '))
  }, [route])

  const validationIssues = useMemo(() => {
    if (!route) return []
    const issues: string[] = []
    for (const name of primaryModels) {
      const m = modelByName(models, name)
      if (!m) issues.push(`主模型「${name}」未注册`)
      else if (!m.enabled) issues.push(`主模型「${name}」已禁用`)
    }
    for (const name of parseModelList(fallbacksGeneral)) {
      if (!allModelNames.includes(name)) issues.push(`Fallback「${name}」未注册`)
    }
    if (primaryModels.length === 0) issues.push('至少选择一个主模型')
    return issues
  }, [route, primaryModels, fallbacksGeneral, models, allModelNames])

  function togglePrimary(name: string, checked: boolean): void {
    setPrimaryModels((prev) => {
      if (checked) return prev.includes(name) ? prev : [...prev, name]
      return prev.filter((n) => n !== name)
    })
  }

  function movePrimary(index: number, dir: -1 | 1): void {
    setPrimaryModels((prev) => {
      const next = [...prev]
      const j = index + dir
      if (j < 0 || j >= next.length) return prev
      const tmp = next[index]
      const atJ = next[j]
      next[index] = atJ
      next[j] = tmp
      return next
    })
  }

  function handleSave(): void {
    if (!route || validationIssues.length > 0) return
    onSave(route.id, {
      primary_models: primaryModels,
      fallbacks_general: parseModelList(fallbacksGeneral),
      fallbacks_content_policy: parseModelList(fallbacksContentPolicy),
      fallbacks_context_window: parseModelList(fallbacksContextWindow),
      strategy,
      enabled,
    })
  }

  if (!route) {
    return (
      <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/10 p-8 text-center">
        <p className="text-sm font-medium">选择左侧虚拟路由</p>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          配置对外暴露的 model 名、主模型池与 Router 策略。
        </p>
      </div>
    )
  }

  const dirty =
    JSON.stringify(primaryModels) !== JSON.stringify(route.primary_models) ||
    strategy !== route.strategy ||
    enabled !== route.enabled ||
    parseModelList(fallbacksGeneral).join(',') !== route.fallbacks_general.join(',') ||
    parseModelList(fallbacksContentPolicy).join(',') !== route.fallbacks_content_policy.join(',') ||
    parseModelList(fallbacksContextWindow).join(',') !== route.fallbacks_context_window.join(',')

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="border-b p-4">
        <p className="font-mono text-base font-semibold">{route.virtual_model}</p>
        <p className="mt-1 text-sm text-muted-foreground">虚拟名 · 客户端请求 model 字段</p>
        {canWrite ? (
          <div className="mt-3 flex items-center gap-2">
            <Switch
              checked={enabled}
              onCheckedChange={setEnabled}
              aria-label={enabled ? '停用路由' : '启用路由'}
            />
            <span className="text-sm text-muted-foreground">{enabled ? '已启用' : '已禁用'}</span>
          </div>
        ) : null}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {validationIssues.length > 0 ? (
          <Alert variant="destructive">
            <AlertDescription>
              <ul className="list-disc pl-4 text-sm">
                {validationIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}

        <section className="space-y-2">
          <Label className="text-xs font-semibold uppercase text-muted-foreground">
            Router 策略
          </Label>
          <Select value={strategy} onValueChange={setStrategy} disabled={!canWrite}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROUTING_STRATEGIES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </section>

        <section className="space-y-2">
          <Label className="text-xs font-semibold uppercase text-muted-foreground">
            主模型（按优先级从上到下）
          </Label>
          {enabledModelNames.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无已启用的注册模型</p>
          ) : (
            <ul className="space-y-1 rounded-md border p-2">
              {enabledModelNames.map((name) => {
                const checked = primaryModels.includes(name)
                const order = primaryModels.indexOf(name)
                return (
                  <li
                    key={name}
                    className={cn(
                      'flex items-center gap-2 rounded px-1 py-1 hover:bg-muted/30',
                      checked && 'bg-primary/5'
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      disabled={!canWrite}
                      onCheckedChange={(c) => {
                        togglePrimary(name, c === true)
                      }}
                      aria-label={`主模型 ${name}`}
                    />
                    <span className="min-w-0 flex-1 truncate font-mono text-sm">{name}</span>
                    {checked && canWrite ? (
                      <div className="flex shrink-0 gap-0.5">
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          disabled={order <= 0}
                          onClick={() => {
                            movePrimary(order, -1)
                          }}
                          aria-label="上移"
                        >
                          <ChevronUp className="h-4 w-4" />
                        </Button>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          disabled={order >= primaryModels.length - 1}
                          onClick={() => {
                            movePrimary(order, 1)
                          }}
                          aria-label="下移"
                        >
                          <ChevronDown className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          )}
          {primaryModels.length > 0 ? (
            <p className="text-xs text-muted-foreground">当前顺序：{primaryModels.join(' → ')}</p>
          ) : null}
        </section>

        <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
          <CollapsibleTrigger asChild>
            <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-xs">
              <ChevronDown
                className={cn('mr-1 h-4 w-4 transition-transform', advancedOpen && 'rotate-180')}
              />
              Fallback 分组
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-3">
            <div>
              <Label className="text-xs">通用 Fallback（逗号分隔别名）</Label>
              <Input
                className="mt-1 font-mono text-sm"
                value={fallbacksGeneral}
                readOnly={!canWrite}
                onChange={(e) => {
                  setFallbacksGeneral(e.target.value)
                }}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label className="text-xs">内容策略</Label>
                <Input
                  className="mt-1 font-mono text-sm"
                  value={fallbacksContentPolicy}
                  readOnly={!canWrite}
                  onChange={(e) => {
                    setFallbacksContentPolicy(e.target.value)
                  }}
                />
              </div>
              <div>
                <Label className="text-xs">上下文窗口</Label>
                <Input
                  className="mt-1 font-mono text-sm"
                  value={fallbacksContextWindow}
                  readOnly={!canWrite}
                  onChange={(e) => {
                    setFallbacksContextWindow(e.target.value)
                  }}
                />
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {canWrite ? (
          <Button
            size="sm"
            disabled={!dirty || isSaving || validationIssues.length > 0}
            onClick={handleSave}
          >
            {isSaving ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
            保存路由
          </Button>
        ) : null}
      </div>
    </div>
  )
}
