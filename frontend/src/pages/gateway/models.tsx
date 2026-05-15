/**
 * AI Gateway · 注册模型（个人 / 团队）
 */

import { Suspense, lazy, useCallback, useEffect } from 'react'

import { Loader2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  type ModelScopeTab,
  type TeamModelsView,
  parseScopeTab,
  parseTeamModelsView,
} from '@/features/gateway-models/constants'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'

const PersonalModelsPanel = lazy(() =>
  import('@/features/gateway-models/personal-models-panel').then((m) => ({
    default: m.PersonalModelsPanel,
  }))
)

const TeamModelsWorkspace = lazy(() =>
  import('@/features/gateway-models/team/team-models-workspace').then((m) => ({
    default: m.TeamModelsWorkspace,
  }))
)

function preloadRegisterModelForm(): void {
  void import('@/features/gateway-models/team/register-model-form')
}

function ModelsPanelFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载中…
    </div>
  )
}

export default function GatewayModelsPage(): React.JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams()
  const scopeTab = parseScopeTab(searchParams.get('tab'))
  const teamView = parseTeamModelsView(searchParams.get('view'))
  const { canWrite } = useGatewayPermission()

  const setScopeTab = useCallback(
    (next: ModelScopeTab): void => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', next)
          if (next !== 'team') {
            n.delete('view')
          }
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const setTeamView = useCallback(
    (next: TeamModelsView): void => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', 'team')
          if (next === 'register') {
            n.set('view', 'register')
          } else {
            n.delete('view')
          }
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  useEffect(() => {
    const raw = searchParams.get('tab')
    if (raw !== null && raw !== 'personal' && raw !== 'team') {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', 'team')
          return n
        },
        { replace: true }
      )
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (searchParams.get('wizard') !== '1') return
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.delete('wizard')
        n.set('tab', 'team')
        n.set('view', 'register')
        return n
      },
      { replace: true }
    )
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (teamView === 'register' && !canWrite) {
      setTeamView('list')
    }
  }, [teamView, canWrite, setTeamView])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">注册模型</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {scopeTab === 'team' ? (
            <>
              团队别名映射至 LiteLLM 上游；对外暴露名在{' '}
              <Link
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>{' '}
              编排。
            </>
          ) : (
            <>
              个人模型进入 LiteLLM Router，可用于产品内对话与虚拟 Key / OpenAI 兼容 API（请求体{' '}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">model</code> 填列表中的
              注册别名）。需先配置{' '}
              <Link
                to="/gateway/credentials?tab=personal"
                className="text-primary underline-offset-4 hover:underline"
              >
                个人凭据
              </Link>
              ；对外统一名可配置{' '}
              <Link
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>
              。
            </>
          )}
        </p>
      </div>

      <Tabs
        value={scopeTab}
        onValueChange={(v) => {
          if (v === 'personal' || v === 'team') setScopeTab(v)
        }}
      >
        <TabsList>
          <TabsTrigger value="personal">个人</TabsTrigger>
          <TabsTrigger value="team">团队</TabsTrigger>
        </TabsList>

        {scopeTab === 'personal' ? (
          <TabsContent value="personal" className="mt-4 focus-visible:outline-none">
            <Suspense fallback={<ModelsPanelFallback />}>
              <PersonalModelsPanel />
            </Suspense>
          </TabsContent>
        ) : (
          <TabsContent value="team" className="mt-4 focus-visible:outline-none">
            {canWrite ? (
              <Tabs
                value={teamView}
                onValueChange={(v) => {
                  if (v === 'list' || v === 'register') {
                    if (v === 'register') {
                      preloadRegisterModelForm()
                    }
                    setTeamView(v)
                  }
                }}
              >
                <TabsList>
                  <TabsTrigger value="list">模型清单</TabsTrigger>
                  <TabsTrigger
                    value="register"
                    onMouseEnter={preloadRegisterModelForm}
                    onFocus={preloadRegisterModelForm}
                  >
                    注册模型
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="list" className="mt-4 focus-visible:outline-none">
                  <Suspense fallback={<ModelsPanelFallback />}>
                    <TeamModelsWorkspace hideRegisterAction teamView="list" />
                  </Suspense>
                </TabsContent>
                <TabsContent value="register" className="mt-4 focus-visible:outline-none">
                  <Suspense fallback={<ModelsPanelFallback />}>
                    <TeamModelsWorkspace hideRegisterAction teamView="register" />
                  </Suspense>
                </TabsContent>
              </Tabs>
            ) : (
              <Suspense fallback={<ModelsPanelFallback />}>
                <TeamModelsWorkspace hideRegisterAction teamView="list" />
              </Suspense>
            )}
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
