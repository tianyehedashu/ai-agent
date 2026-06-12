/**
 * AI Gateway · 模型（统一列表）
 */

import { Suspense, useEffect } from 'react'

import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { parseModelsPageView } from '@/features/gateway-models/constants'
import { personalModelsIndexHref } from '@/features/gateway-models/paths'
import { preloadUnifiedModelsWorkspace } from '@/features/gateway-models/unified/unified-models-preload'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { ChevronLeft, Loader2 } from '@/lib/lucide-icons'

const PersonalModelsWorkspace = lazyWithReload(() =>
  import('@/features/gateway-models/personal/personal-models-workspace').then((m) => ({
    default: m.PersonalModelsWorkspace,
  }))
)

const TeamModelsWorkspace = lazyWithReload(() =>
  import('@/features/gateway-models/team/team-models-workspace').then((m) => ({
    default: m.TeamModelsWorkspace,
  }))
)

const UnifiedModelsWorkspace = lazyWithReload(() =>
  import('@/features/gateway-models/unified/unified-models-workspace').then((m) => ({
    default: m.UnifiedModelsWorkspace,
  }))
)

function ModelsPanelFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载中…
    </div>
  )
}

export default function GatewayModelsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { canWrite, canContribute, isPlatformAdmin } = useGatewayPermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const pageView = parseModelsPageView(searchParams.get('view'))
  const registerScope = searchParams.get('scope')

  const canRegisterTeamModel = canWrite || canContribute
  const isRegisterView = pageView === 'register'
  const isPersonalRegister = isRegisterView && registerScope === 'personal'
  const isTeamRegister =
    isRegisterView &&
    (registerScope === 'team' || registerScope === 'shared') &&
    canRegisterTeamModel
  const isSystemRegister = isRegisterView && registerScope === 'system' && isPlatformAdmin

  useEffect(() => {
    let needsUpdate = false
    const next = new URLSearchParams(searchParams)

    if (searchParams.get('wizard') === '1') {
      next.delete('wizard')
      next.set('view', 'register')
      next.set('scope', 'team')
      needsUpdate = true
    }

    if (searchParams.get('tab')) {
      const legacyTab = searchParams.get('tab')
      next.delete('tab')
      if (legacyTab === 'personal') {
        next.set('scope', 'personal')
      } else if (legacyTab === 'system') {
        next.set('scope', 'system')
      } else if (legacyTab === 'shared') {
        next.set('scope', 'team')
      }
      needsUpdate = true
    }

    if (pageView === 'register' && registerScope === 'team' && !canRegisterTeamModel) {
      next.delete('view')
      next.delete('scope')
      needsUpdate = true
    }

    if (pageView === 'register' && registerScope === 'system' && !isPlatformAdmin) {
      next.delete('view')
      next.delete('scope')
      needsUpdate = true
    }

    if (needsUpdate) {
      setSearchParams(next, { replace: true })
    }
  }, [
    searchParams,
    setSearchParams,
    pageView,
    registerScope,
    canRegisterTeamModel,
    isPlatformAdmin,
  ])

  const listBackHref = personalModelsIndexHref(teamId)

  if (isPersonalRegister) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">添加个人模型</h2>
        </div>
        <Button variant="ghost" size="sm" className="h-8" asChild>
          <Link
            to={listBackHref}
            onMouseEnter={preloadUnifiedModelsWorkspace}
            onFocus={preloadUnifiedModelsWorkspace}
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            返回模型列表
          </Link>
        </Button>
        <Suspense fallback={<ModelsPanelFallback />}>
          <PersonalModelsWorkspace pageView="register" />
        </Suspense>
      </div>
    )
  }

  if (isSystemRegister) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">注册系统模型</h2>
        </div>
        <Button variant="ghost" size="sm" className="h-8" asChild>
          <Link
            to={listBackHref}
            onMouseEnter={preloadUnifiedModelsWorkspace}
            onFocus={preloadUnifiedModelsWorkspace}
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            返回模型列表
          </Link>
        </Button>
        <Suspense fallback={<ModelsPanelFallback />}>
          <TeamModelsWorkspace pageView="register" hideRegisterAction listMode="system" />
        </Suspense>
      </div>
    )
  }

  if (isTeamRegister) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">添加团队模型</h2>
        </div>
        <Button variant="ghost" size="sm" className="h-8" asChild>
          <Link
            to={listBackHref}
            onMouseEnter={preloadUnifiedModelsWorkspace}
            onFocus={preloadUnifiedModelsWorkspace}
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            返回模型列表
          </Link>
        </Button>
        <Suspense fallback={<ModelsPanelFallback />}>
          <TeamModelsWorkspace pageView="register" hideRegisterAction />
        </Suspense>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">模型</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          同一列表查看个人、协作团队与系统模型；「归属」列标明所属范围。对外暴露名可在{' '}
          <Link to="/gateway/routes" className="text-primary underline-offset-4 hover:underline">
            虚拟路由
          </Link>{' '}
          编排，经{' '}
          <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
            虚拟 Key
          </Link>{' '}
          / OpenAI 兼容 API 调用。
        </p>
      </div>

      <Suspense fallback={<ModelsPanelFallback />}>
        <UnifiedModelsWorkspace />
      </Suspense>
    </div>
  )
}
