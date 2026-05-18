import { useCallback, useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Loader2, Pencil, Trash2, Zap } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { usePersonalModelMutations } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import { personalModelEditHref, personalModelsIndexHref } from '@/features/gateway-models/paths'
import { MODEL_PROVIDERS, MODEL_TYPE_LABELS } from '@/types/user-model'

interface PersonalModelDetailPaneProps {
  modelId: string
}

export function PersonalModelDetailPane({
  modelId,
}: PersonalModelDetailPaneProps): React.JSX.Element {
  const navigate = useNavigate()

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-models'],
    queryFn: () => gatewayApi.listMyModels(),
  })

  const model = useMemo(() => items.find((m) => m.id === modelId) ?? null, [items, modelId])

  const { deleteMutation, testMutation } = usePersonalModelMutations({
    onDeleteSuccess: () => {
      navigate(personalModelsIndexHref())
    },
  })

  const handleTest = useCallback((): void => {
    if (model) testMutation.mutate(model.id)
  }, [model, testMutation])

  const handleDelete = useCallback((): void => {
    if (!model) return
    if (
      !window.confirm(
        `\u786e\u5b9a\u5220\u9664\u300c${model.display_name}\u300d\uff1f\u6b64\u64cd\u4f5c\u4e0d\u53ef\u64a4\u9500\u3002`
      )
    ) {
      return
    }
    deleteMutation.mutate(model.id)
  }, [model, deleteMutation])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载模型…
      </div>
    )
  }

  if (!model) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        未找到该模型，可能已被删除。
      </p>
    )
  }

  const providerName = MODEL_PROVIDERS.find((p) => p.id === model.provider)?.name ?? model.provider

  return (
    <div className="space-y-6 rounded-lg border bg-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-xl font-semibold">{model.display_name}</h3>
            <ModelStatusBadge
              status={model.last_test_status}
              testedAt={model.last_tested_at}
              reason={model.last_test_reason}
            />
            {!model.is_active ? (
              <Badge variant="outline" className="text-amber-600">
                已禁用
              </Badge>
            ) : null}
          </div>
          <p className="font-mono text-sm text-muted-foreground">
            <span className="font-sans text-muted-foreground/80">注册别名 </span>
            {model.name}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Zap className="mr-1 h-4 w-4" />
            )}
            测试连接
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to={personalModelEditHref(model.id)}>
              <Pencil className="mr-1 h-4 w-4" />
              编辑
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            删除
          </Button>
        </div>
      </div>

      <dl className="grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs font-medium text-muted-foreground">提供商</dt>
          <dd className="mt-0.5 text-sm">{providerName}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted-foreground">上游模型 ID</dt>
          <dd className="mt-0.5 font-mono text-sm">{model.model_id}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted-foreground">能力类型</dt>
          <dd className="mt-1 flex flex-wrap gap-1">
            {model.model_types.map((t) => (
              <Badge key={t} variant="secondary" className="text-xs">
                {MODEL_TYPE_LABELS[t]}
              </Badge>
            ))}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted-foreground">凭据 ID</dt>
          <dd className="mt-0.5 font-mono text-xs text-muted-foreground">{model.credential_id}</dd>
        </div>
      </dl>

      {model.last_test_status === 'failed' && model.last_test_reason ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4">
          <p className="text-xs font-medium text-destructive">最近测试失败</p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-destructive/90 [overflow-wrap:anywhere]">
            {model.last_test_reason}
          </p>
        </div>
      ) : null}
    </div>
  )
}
