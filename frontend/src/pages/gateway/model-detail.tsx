/**
 * AI Gateway · 模型详情（个人 / 团队深链）
 */

import { Suspense, lazy } from 'react'

import { Link, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  canLinkToCredentialDetail,
  credentialSummaryLabel,
} from '@/features/gateway-credentials/credential-summary-display'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'
import { parseModelsPageView, parseModelsScopeTab } from '@/features/gateway-models/constants'
import { useGatewayModelLabel } from '@/features/gateway-models/hooks/use-gateway-model-label'
import { usePersonalModelLabel } from '@/features/gateway-models/hooks/use-personal-model-label'
import {
  credentialDetailHref,
  credentialsTeamListHref,
  personalModelsIndexHref,
  systemModelsFilteredHref,
  teamModelsFilteredHref,
  teamModelsIndexHref,
} from '@/features/gateway-models/paths'
import { preloadPersonalModelsWorkspace } from '@/features/gateway-models/personal/personal-model-preload'
import { preloadTeamModelsWorkspace } from '@/features/gateway-models/team/preloads'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { ChevronLeft, ChevronRight, Loader2 } from '@/lib/lucide-icons'

const TeamModelDetailPane = lazy(() =>
  import('@/features/gateway-models/team/team-model-detail-pane').then((m) => ({
    default: m.TeamModelDetailPane,
  }))
)

const PersonalModelDetailPane = lazy(() =>
  import('@/features/gateway-models/personal/personal-model-detail-pane').then((m) => ({
    default: m.PersonalModelDetailPane,
  }))
)

const PersonalModelEditPane = lazy(() =>
  import('@/features/gateway-models/personal/personal-model-edit-pane').then((m) => ({
    default: m.PersonalModelEditPane,
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
  const { isAdmin, isPlatformAdmin } = useGatewayPermission()
  const scopeTab = parseModelsScopeTab(searchParams.get('tab'))
  const pageView = parseModelsPageView(searchParams.get('view'))
  const credentialId = searchParams.get('credentialId') ?? ''
  const isPersonal = scopeTab === 'personal'
  const isSystem = scopeTab === 'system' && isPlatformAdmin
  const isEdit = isPersonal && pageView === 'edit'
  const { byId: credentialSummariesById } = useGatewayCredentialDirectory()
  const credentialSummary =
    !isPersonal && credentialId.length > 0 ? credentialSummariesById.get(credentialId) : undefined
  const credentialBreadcrumbLink = canLinkToCredentialDetail(
    credentialSummary,
    isAdmin,
    isPlatformAdmin
  )

  const teamLabel = useGatewayModelLabel(isPersonal ? '' : id, credentialId)
  const personalLabel = usePersonalModelLabel(isPersonal ? id : '')
  const modelLabel = isPersonal ? personalLabel : teamLabel

  const backHref = isPersonal
    ? personalModelsIndexHref(teamId)
    : credentialId.length > 0
      ? credentialDetailHref(teamId, credentialId)
      : isSystem
        ? systemModelsFilteredHref(teamId)
        : teamModelsIndexHref(teamId)
  const backLabel = isPersonal
    ? '全部个人模型'
    : credentialId.length > 0
      ? '返回凭据'
      : isSystem
        ? '全部系统模型'
        : '全部模型'

  const listPreload = isPersonal ? preloadPersonalModelsWorkspace : preloadTeamModelsWorkspace

  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        {isPersonal ? (
          <>
            <Link
              to={personalModelsIndexHref(teamId)}
              className="hover:text-foreground"
              onMouseEnter={listPreload}
              onFocus={listPreload}
            >
              个人模型
            </Link>
            <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
            <span className="font-medium text-foreground">{isEdit ? '编辑' : modelLabel}</span>
          </>
        ) : credentialId.length > 0 ? (
          <>
            <Link to={credentialsTeamListHref(teamId)} className="hover:text-foreground">
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
              to={isSystem ? systemModelsFilteredHref(teamId) : teamModelsIndexHref(teamId)}
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
        {!isPersonal && credentialId.length > 0 ? (
          <Button variant="ghost" size="sm" className="h-8" asChild>
            <Link
              to={
                isSystem
                  ? systemModelsFilteredHref(teamId, credentialId)
                  : teamModelsFilteredHref(teamId, credentialId)
              }
              onMouseEnter={preloadTeamModelsWorkspace}
              onFocus={preloadTeamModelsWorkspace}
            >
              此凭据下全部模型
            </Link>
          </Button>
        ) : null}
      </div>

      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          {isEdit ? '编辑模型' : '模型详情'}
        </h2>
        {!isEdit ? (
          <p className="mt-1 font-mono text-sm text-muted-foreground">{modelLabel}</p>
        ) : null}
      </div>

      <Suspense fallback={paneSuspenseFallback}>
        {isPersonal ? (
          isEdit ? (
            <PersonalModelEditPane modelId={id} />
          ) : (
            <PersonalModelDetailPane modelId={id} />
          )
        ) : (
          <TeamModelDetailPane modelId={id} />
        )}
      </Suspense>
    </div>
  )
}
