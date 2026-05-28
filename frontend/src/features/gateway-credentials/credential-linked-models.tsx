/**
 * 凭据详情 · 关联注册模型：全宽列表，详情/注册走团队模型路由
 */

import { memo, useCallback, useMemo } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  EMBEDDED_CREDENTIAL_CAPABILITIES,
  fromGatewayModel,
  GatewayModelFlatList,
  GatewayModelListShell,
} from '@/features/gateway-models/list'
import type { TeamModelsTab } from '@/features/gateway-models/paths'
import {
  systemModelsFilteredHref,
  teamModelDetailHref,
  teamModelsFilteredHref,
  teamModelsRegisterHref,
} from '@/features/gateway-models/paths'
import { preloadModelNavigation } from '@/features/gateway-models/team/preloads'
import { preloadTeamModelDetailPane } from '@/features/gateway-models/team/team-model-detail-preload'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { ExternalLink, Plus } from '@/lib/lucide-icons'

interface CredentialModelsCardProps {
  credentialId: string
  models: GatewayModel[] | undefined
  isLoading: boolean
  canManageModels: boolean
  /** 系统凭据走 `tab=system` 深链 */
  modelsTab?: TeamModelsTab
  /** 打开就地「添加模型」弹窗；未提供时退回链接跳转 */
  onAddModels?: () => void
}

export const CredentialModelsCard = memo(function CredentialModelsCard({
  credentialId,
  models,
  isLoading,
  canManageModels,
  modelsTab = 'shared',
  onAddModels,
}: CredentialModelsCardProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const manageAllHref =
    modelsTab === 'system'
      ? systemModelsFilteredHref(teamId, credentialId)
      : teamModelsFilteredHref(teamId, credentialId)
  const registerHref = teamModelsRegisterHref(teamId, credentialId, modelsTab)

  const capabilities = EMBEDDED_CREDENTIAL_CAPABILITIES

  const listItems = useMemo(
    () =>
      (models ?? []).map((m) => fromGatewayModel(m, modelsTab === 'system' ? 'system' : 'team')),
    [models, modelsTab]
  )

  const getItemHref = useCallback(
    (item: (typeof listItems)[number]) =>
      teamModelDetailHref(teamId, item.id, { credentialId, tab: modelsTab }),
    [teamId, credentialId, modelsTab]
  )

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0 pb-4">
        <CardTitle className="text-lg">使用此凭据的注册模型</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          {(models?.length ?? 0) > 0 ? (
            <Button variant="outline" size="sm" asChild>
              <Link
                to={manageAllHref}
                onMouseEnter={preloadModelNavigation}
                onFocus={preloadModelNavigation}
              >
                <ExternalLink className="mr-1.5 h-4 w-4" />
                管理全部
              </Link>
            </Button>
          ) : null}
          {canManageModels ? (
            onAddModels ? (
              <Button
                type="button"
                size="sm"
                onMouseEnter={preloadModelNavigation}
                onFocus={preloadModelNavigation}
                onClick={onAddModels}
              >
                <Plus className="mr-1.5 h-4 w-4" />
                添加模型
              </Button>
            ) : (
              <Button size="sm" asChild>
                <Link
                  to={registerHref}
                  onMouseEnter={preloadModelNavigation}
                  onFocus={preloadModelNavigation}
                >
                  <Plus className="mr-1.5 h-4 w-4" />
                  增加
                </Link>
              </Button>
            )
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <GatewayModelListShell
          capabilities={capabilities}
          className="rounded-none border-0 border-t shadow-none"
          isLoading={isLoading}
          isEmpty={(models?.length ?? 0) === 0}
          emptySlot={
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              <p>暂无模型</p>
              {canManageModels ? (
                <p className="mt-2">
                  {onAddModels ? (
                    <button
                      type="button"
                      className="font-medium text-primary underline-offset-4 hover:underline"
                      onClick={onAddModels}
                    >
                      添加第一条模型
                    </button>
                  ) : (
                    <Link
                      to={registerHref}
                      className="font-medium text-primary underline-offset-4 hover:underline"
                    >
                      注册第一条模型
                    </Link>
                  )}
                  <span className="mx-1">·</span>
                  <Link
                    to={manageAllHref}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    在模型管理中查看
                  </Link>
                </p>
              ) : null}
            </div>
          }
        >
          <GatewayModelFlatList
            capabilities={capabilities}
            items={listItems}
            getItemHref={getItemHref}
            onPreloadNavigate={preloadTeamModelDetailPane}
          />
        </GatewayModelListShell>
      </CardContent>
    </Card>
  )
})

/** @deprecated 使用 CredentialModelsCard */
export const CredentialLinkedModels = CredentialModelsCard
