import { useCallback, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import type { ProviderCredential } from '@/api/gateway'
import { ToastAction } from '@/components/ui/toast'
import { isWritableTargetTeam } from '@/features/gateway-credentials/credential-permissions'
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { switchGatewayTeam } from '@/features/gateway-teams/navigate-team'
import {
  resolveGatewayTeamLabel,
  useGatewayTeamNameMap,
  useGatewayWritableTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useToast } from '@/hooks/use-toast'

export interface JustCreatedCredential {
  id: string
  teamId: string
  provider: string
  name: string
  scope: CredentialUpstreamScope
  is_active: boolean
}

interface UseCredentialCreateFlowOptions {
  routeTeamId: string
  onCloseCreateUi: () => void
}

interface UseCredentialCreateFlowResult {
  justCreated: JustCreatedCredential | null
  clearJustCreated: () => void
  handleManagedCreateSuccess: (
    cred: ProviderCredential,
    targetTeamId: string,
    scope: CredentialUpstreamScope
  ) => void
  handleUserCreateSuccess: (cred: ProviderCredential) => void
}

export function useCredentialCreateFlow({
  routeTeamId,
  onCloseCreateUi,
}: UseCredentialCreateFlowOptions): UseCredentialCreateFlowResult {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const writableTeams = useGatewayWritableTeams()
  const teamNameById = useGatewayTeamNameMap()
  const [justCreated, setJustCreated] = useState<JustCreatedCredential | null>(null)

  const clearJustCreated = useCallback((): void => {
    setJustCreated(null)
  }, [])

  const openAddModelsAfterCreate = useCallback(
    (cred: ProviderCredential, scope: CredentialUpstreamScope, targetTeamId: string): void => {
      onCloseCreateUi()
      setJustCreated({
        id: cred.id,
        teamId: targetTeamId,
        provider: cred.provider,
        name: cred.name,
        scope,
        is_active: cred.is_active,
      })
      const targetTeamName = resolveGatewayTeamLabel(teamNameById, targetTeamId)
      if (
        scope === 'team' &&
        targetTeamId !== routeTeamId &&
        isWritableTargetTeam(targetTeamId, writableTeams)
      ) {
        toast({
          title: '凭据已创建',
          description: `已创建到「${targetTeamName}」。正在准备添加模型，也可稍后在凭据详情中操作。`,
          action: (
            <ToastAction
              altText="切换团队"
              onClick={() => {
                switchGatewayTeam(targetTeamId, navigate, location, queryClient)
              }}
            >
              切换团队
            </ToastAction>
          ),
        })
        return
      }
      toast({
        title: '凭据已创建',
        description: '正在准备添加模型，也可稍后在凭据详情中操作。',
      })
    },
    [
      location,
      navigate,
      onCloseCreateUi,
      queryClient,
      routeTeamId,
      teamNameById,
      toast,
      writableTeams,
    ]
  )

  const handleManagedCreateSuccess = useCallback(
    (cred: ProviderCredential, targetTeamId: string, scope: CredentialUpstreamScope) => {
      openAddModelsAfterCreate(cred, scope, targetTeamId)
    },
    [openAddModelsAfterCreate]
  )

  const handleUserCreateSuccess = useCallback(
    (cred: ProviderCredential) => {
      openAddModelsAfterCreate(cred, 'user', routeTeamId)
    },
    [openAddModelsAfterCreate, routeTeamId]
  )

  return {
    justCreated,
    clearJustCreated,
    handleManagedCreateSuccess,
    handleUserCreateSuccess,
  }
}
