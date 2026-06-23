/**
 * AI Gateway · 模型详情（个人 / 团队深链）
 */

import { Suspense, useCallback } from 'react'

import { useIsFetching, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  canLinkToCredentialDetail,
  credentialSummaryLabel,
} from '@/features/gateway-credentials/credential-summary-display'
import {
  invalidateCredentialSummariesCache,
  useGatewayCredentialDirectory,
} from '@/features/gateway-credentials/use-credential-directory'
import { parseModelsScopeTab } from '@/features/gateway-models/constants'
import { useGatewayModelLabel } from '@/features/gateway-models/hooks/use-gateway-model-label'
import { usePersonalModelLabel } from '@/features/gateway-models/hooks/use-personal-model-label'
import {
  credentialDetailHref,
  credentialsListHref,
  resolveUnifiedModelsReturnHref,
  systemModelsFilteredHref,
  teamModelsFilteredHref,
  unifiedModelsListContextFromSearchParams,
} from '@/features/gateway-models/paths'
import { preloadUnifiedModelsWorkspace } from '@/features/gateway-models/unified/unified-models-preload'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { ChevronLeft, ChevronRight, Loader2 } from '@/lib/lucide-icons'
import { useCurrentUser } from '@/stores/user'

const TeamModelDetailPane = lazyWithReload(() =>
  import('@/features/gateway-models/team/team-model-detail-pane').then((m) => ({
    default: m.TeamModelDetailPane,
  }))
)

const PersonalModelDetailPane = lazyWithReload(() =>
  import('@/features/gateway-models/personal/personal-model-detail-pane').then((m) => ({
    default: m.PersonalModelDetailPane,
  }))
)

const paneSuspenseFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载中…
  </div>
)

export default function GatewayModelDetailPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { modelId } = useParams<{ modelId: string }>()
  const id = modelId ?? ''
  const [searchParams] = useSearchParams()
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const viewerUserId = useCurrentUser()?.id ?? null
  const scopeTab = parseModelsScopeTab(searchParams.get('tab'))
  const credentialId = searchParams.get('credentialId') ?? ''
  const isPersonal = scopeTab === 'personal'
  const isSystem = scopeTab === 'system' && isPlatformAdmin
  const { byId: credentialSummariesById } = useGatewayCredentialDirectory()
  const credentialSummary =
    !isPersonal && credentialId.length > 0 ? credentialSummariesById.get(credentialId) : undefined
  const credentialBreadcrumbLink = canLinkToCredentialDetail(
    credentialSummary,
    viewerUserId,
    canWrite,
    isPlatformAdmin
  )

  const teamLabel = useGatewayModelLabel(isPersonal ? '' : id, credentialId)
  const personalLabel = usePersonalModelLabel(isPersonal ? id : '')
  const modelLabel = isPersonal ? personalLabel : teamLabel

  const queryClient = useQueryClient()
  const modelDetailFetching = useIsFetching({
    queryKey: isPersonal ? ['gateway', 'my-models', id] : ['gateway', 'models', teamId, id],
  })
  const handleRefresh = useCallback((): void => {
    void queryClient.invalidateQueries({
      queryKey: isPersonal ? ['gateway', 'my-models', id] : ['gateway', 'models', teamId, id],
    })
    invalidateCredentialSummariesCache(queryClient)
  }, [id, isPersonal, queryClient, teamId])

  const listContext = unifiedModelsListContextFromSearchParams(searchParams)

  const listReturnHref = resolveUnifiedModelsReturnHref(teamId, searchParams, {
    scope: isSystem ? 'system' : undefined,
    credentialId: credentialId || undefined,
  })

  const backHref = isPersonal
    ? listReturnHref
    : credentialId.length > 0
      ? credentialDetailHref(teamId, credentialId)
      : listReturnHref
  const backLabel = isPersonal
    ? '返回模型列表'
    : credentialId.length > 0
      ? '返回凭据'
      : isSystem
        ? '返回系统模型'
        : '返回模型列表'

  const breadcrumbListHref = isSystem
    ? systemModelsFilteredHref(teamId, undefined, listContext)
    : listReturnHref

  const listPreload = preloadUnifiedModelsWorkspace

  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        {isPersonal ? (
          <>
            <Link
              to={listReturnHref}
              className="hover:text-foreground"
              onMouseEnter={listPreload}
              onFocus={listPreload}
            >
              个人模型
            </Link>
            <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
            <span className="font-medium text-foreground">{modelLabel}</span>
          </>
        ) : credentialId.length > 0 ? (
          <>
            <Link to={credentialsListHref(teamId)} className="hover:text-foreground">
              凭据管理
            </Link>
            <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
            {credentialSummary ? (
              credentialBreadcrumbLink ? (
                <Link
                  to={credentialDetailHref(teamId, credentialId)}
                  className="hover:text-foreground"
                >
                  {credentialSummaryLabel(credentialSummary, credentialId)}
                </Link>
              ) : (
                <span>{credentialSummaryLabel(credentialSummary, credentialId)}</span>
              )
            ) : (
              <span>凭据</span>
            )}
            <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
            <span className="font-medium text-foreground">{modelLabel}</span>
          </>
        ) : (
          <>
            <Link
              to={breadcrumbListHref}
              className="hover:text-foreground"
              onMouseEnter={listPreload}
              onFocus={listPreload}
            >
              {isSystem ? '系统模型' : '团队模型'}
            </Link>
            <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
            <span className="font-medium text-foreground">{modelLabel}</span>
          </>
        )}
      </nav>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" className="h-8" asChild>
          <Link to={backHref} onMouseEnter={listPreload} onFocus={listPreload}>
            <ChevronLeft className="mr-1 h-4 w-4" />
            {backLabel}
          </Link>
        </Button>
        <GatewayRefreshButton
          isFetching={modelDetailFetching > 0}
          ariaLabel="刷新模型详情"
          onRefresh={handleRefresh}
        />
        {!isPersonal && credentialId.length > 0 ? (
          <Button variant="ghost" size="sm" className="h-8" asChild>
            <Link
              to={
                isSystem
                  ? systemModelsFilteredHref(teamId, credentialId, listContext)
                  : teamModelsFilteredHref(teamId, credentialId, listContext)
              }
              onMouseEnter={preloadUnifiedModelsWorkspace}
              onFocus={preloadUnifiedModelsWorkspace}
            >
              此凭据下全部模型
            </Link>
          </Button>
        ) : null}
      </div>

      <div>
        <h2 className="text-2xl font-semibold tracking-tight">模型详情</h2>
        <p className="mt-1 font-mono text-sm text-muted-foreground">{modelLabel}</p>
      </div>

      <Suspense fallback={paneSuspenseFallback}>
        {isPersonal ? (
          <PersonalModelDetailPane modelId={id} />
        ) : (
          <TeamModelDetailPane modelId={id} />
        )}
      </Suspense>
    </div>
  )
}
