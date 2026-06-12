import { useCallback } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { credentialsApi, type ProviderCredential } from '@/api/gateway/credentials'
import { invalidateCredentialProbeCache } from '@/features/gateway-credentials/credential-probe-cache'
import {
  credentialDetailQueryKey,
  invalidateGatewayCredentialCaches,
} from '@/features/gateway-credentials/query-keys'
import { managedCredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { useToast } from '@/hooks/use-toast'

export interface UseCredentialActiveToggleOptions {
  credential: ProviderCredential | undefined
  routeTeamId: string
  scope: 'user' | 'team' | 'system'
}

export function useCredentialActiveToggle({
  credential,
  routeTeamId,
  scope,
}: UseCredentialActiveToggleOptions): {
  isPending: boolean
  toggle: (nextActive: boolean) => void
} {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const credentialId = credential?.id ?? ''
  const upstreamScope = managedCredentialUpstreamScope(scope)
  const detailTeamId =
    scope === 'team' && credential?.tenant_id ? credential.tenant_id : routeTeamId

  const mutation = useMutation({
    mutationFn: async (nextActive: boolean): Promise<boolean> => {
      if (!credential) {
        throw new Error('凭据未加载')
      }
      if (scope === 'user') {
        await gatewayApi.updateMyCredential(credential.id, { is_active: nextActive })
        return nextActive
      }
      await credentialsApi.updateCredential(detailTeamId, credential.id, {
        is_active: nextActive,
      })
      return nextActive
    },
    onMutate: async (nextActive: boolean) => {
      if (!credential) return { previous: undefined }
      const detailKey = credentialDetailQueryKey(detailTeamId, credential.id)
      await queryClient.cancelQueries({ queryKey: detailKey })
      const previous = queryClient.getQueryData<ProviderCredential>(detailKey)
      if (previous) {
        queryClient.setQueryData<ProviderCredential>(detailKey, {
          ...previous,
          is_active: nextActive,
        })
      }
      return { previous }
    },
    onSuccess: (nextActive) => {
      toast({ title: nextActive ? '凭据已启用' : '凭据已停用' })
    },
    onError: (e: Error, _next, ctx) => {
      if (ctx?.previous && credential) {
        queryClient.setQueryData(
          credentialDetailQueryKey(detailTeamId, credential.id),
          ctx.previous
        )
      }
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
    onSettled: () => {
      if (!credential) return
      invalidateCredentialProbeCache(queryClient, upstreamScope, credentialId)
      invalidateGatewayCredentialCaches(queryClient, {
        teamId: routeTeamId,
        credentialTeamId: detailTeamId,
        credentialId: credential.id,
      })
    },
  })

  const toggle = useCallback(
    (nextActive: boolean): void => {
      if (!credential) return
      mutation.mutate(nextActive)
    },
    [credential, mutation]
  )

  return { isPending: mutation.isPending, toggle }
}
