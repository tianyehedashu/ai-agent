import { Suspense, useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FILTER_ALL, parseModelsPageView } from '@/features/gateway-models/constants'
import { usePersonalModelMutations } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import {
  personalModelDetailHref,
  personalModelsRegisterHref,
} from '@/features/gateway-models/paths'
import { channelLabel } from '@/features/gateway-models/utils'
import { Loader2, Plus } from '@/lib/lucide-icons'
import { PROVIDER_CHANNEL_FILTER_HINT_LONG } from '@/lib/provider-channel-hint'
import { useAuthStore } from '@/stores/auth'
import { MODEL_PROVIDERS, MODEL_TYPE_LABELS } from '@/types/user-model'

import { PersonalModelForm, type PersonalModelFormValues } from './personal-model-form'
import { preloadPersonalModelDetailPane, preloadPersonalModelForm } from './personal-model-preload'

const LIST_CHANNEL_ALL = FILTER_ALL

const formSuspenseFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载表单…
  </div>
)

interface PersonalModelsWorkspaceProps {
  /** 由父级传入时优先于 URL `view` */
  pageView?: 'list' | 'register'
}

export function PersonalModelsWorkspace({
  pageView: pageViewProp,
}: PersonalModelsWorkspaceProps): React.JSX.Element {
  const token = useAuthStore((s) => s.token)
  const hasAuthSession = Boolean(token)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const pageView = pageViewProp ?? parseModelsPageView(searchParams.get('view'))
  const isRegisterView = pageView === 'register'
  const [listChannel, setListChannel] = useState<string>(LIST_CHANNEL_ALL)

  const { data: credentials = [] } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })

  const activeCredentials = useMemo(() => credentials.filter((c) => c.is_active), [credentials])

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-models', listChannel],
    queryFn: () =>
      gatewayApi.listMyModels({
        provider: listChannel === LIST_CHANNEL_ALL ? undefined : listChannel,
      }),
    enabled: hasAuthSession && !isRegisterView,
  })

  const { createMutation } = usePersonalModelMutations({
    onCreateSuccess: (created) => {
      if (created.length > 0) {
        navigate(personalModelDetailHref(created[0].id))
        return
      }
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.delete('view')
          return n
        },
        { replace: true }
      )
    },
  })

  const goToRegister = useCallback((): void => {
    preloadPersonalModelForm()
    navigate(personalModelsRegisterHref())
  }, [navigate])

  const goToList = useCallback((): void => {
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.set('tab', 'personal')
        n.delete('view')
        return n
      },
      { replace: true }
    )
  }, [setSearchParams])

  const handleCreateSubmit = useCallback(
    (values: PersonalModelFormValues): void => {
      if (!values.display_name || !values.model_id || !values.credential_id) return
      createMutation.mutate({
        display_name: values.display_name,
        provider: values.provider,
        model_id: values.model_id,
        credential_id: values.credential_id,
        model_types: values.model_types,
      })
    },
    [createMutation]
  )

  if (!hasAuthSession) {
    return <p className="py-8 text-center text-sm text-muted-foreground">请先登录以管理个人模型</p>
  }

  if (isRegisterView) {
    return (
      <Suspense fallback={formSuspenseFallback}>
        <PersonalModelForm
          mode="create"
          credentials={credentials}
          onSubmit={handleCreateSubmit}
          onCancel={goToList}
          isSubmitting={createMutation.isPending}
        />
      </Suspense>
    )
  }

  return (
    <div className="space-y-4">
      {activeCredentials.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          尚无个人凭据，请先到{' '}
          <Link
            to="/gateway/credentials?tab=personal"
            className="text-primary underline-offset-4 hover:underline"
          >
            凭据管理
          </Link>{' '}
          添加 API Key。
        </p>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="grid max-w-xs gap-1.5">
          <Label htmlFor="personal-model-channel">按接入通道筛选</Label>
          <Select
            value={listChannel}
            onValueChange={(v) => {
              setListChannel(v)
            }}
          >
            <SelectTrigger id="personal-model-channel" className="w-full sm:w-[220px]">
              <SelectValue placeholder="全部" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={LIST_CHANNEL_ALL}>全部</SelectItem>
              {MODEL_PROVIDERS.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{PROVIDER_CHANNEL_FILTER_HINT_LONG}</p>
        </div>
        <Button
          size="sm"
          onClick={goToRegister}
          disabled={activeCredentials.length === 0}
          onMouseEnter={preloadPersonalModelForm}
          onFocus={preloadPersonalModelForm}
        >
          <Plus className="mr-1 h-4 w-4" />
          添加模型
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-muted/10 p-8">
          <h3 className="text-lg font-semibold">配置个人模型供给链</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
            <li>
              在{' '}
              <Link
                to="/gateway/credentials?tab=personal"
                className="text-primary underline-offset-4 hover:underline"
              >
                凭据管理
              </Link>{' '}
              添加并启用个人凭据
            </li>
            <li>注册第一条模型（展示名 → 上游模型 ID + 凭据）</li>
            <li>
              在{' '}
              <Link
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>{' '}
              编排对外虚拟名（可选）
            </li>
          </ol>
          <Button
            className="mt-4"
            size="sm"
            onClick={goToRegister}
            disabled={activeCredentials.length === 0}
            onMouseEnter={preloadPersonalModelForm}
            onFocus={preloadPersonalModelForm}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            添加第一个模型
          </Button>
        </div>
      ) : (
        <ul className="divide-y rounded-lg border">
          {items.map((m) => (
            <li key={m.id}>
              <Link
                to={personalModelDetailHref(m.id)}
                className="block px-4 py-3 transition-colors hover:bg-muted/40"
                onMouseEnter={preloadPersonalModelDetailPane}
                onFocus={preloadPersonalModelDetailPane}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{m.display_name}</span>
                  <ModelStatusBadge
                    status={m.last_test_status}
                    testedAt={m.last_tested_at}
                    reason={m.last_test_reason}
                    compact
                  />
                  <Badge variant="outline" className="shrink-0 text-xs">
                    {channelLabel(m.provider)}
                  </Badge>
                  {m.model_types.map((t) => (
                    <Badge key={t} variant="secondary" className="shrink-0 text-xs">
                      {MODEL_TYPE_LABELS[t]}
                    </Badge>
                  ))}
                </div>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">{m.name}</p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{m.model_id}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
