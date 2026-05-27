import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  credentialsApi,
  type GatewayCredentialUpdateBody,
  type ProviderCredential,
} from '@/api/gateway/credentials'
import { invalidateGatewayCredentialCaches } from '@/features/gateway-credentials/query-keys'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'

import type { UseMutationResult } from '@tanstack/react-query'

interface UseGatewayCredentialMutationsOptions {
  teamId?: string
  onManagedCreateSuccess?: (cred: ProviderCredential, targetTeamId: string) => void
  onUserCreateSuccess?: (cred: ProviderCredential) => void
  onDeleteSuccess?: () => void
}

export interface GatewayCredentialMutations {
  createManagedMutation: UseMutationResult<
    ProviderCredential,
    Error,
    {
      targetTeamId: string
      body: Parameters<typeof credentialsApi.createCredential>[1]
    }
  >
  createUserMutation: UseMutationResult<
    ProviderCredential,
    Error,
    Parameters<typeof credentialsApi.createMyCredential>[0]
  >
  updateMutation: UseMutationResult<
    ProviderCredential,
    Error,
    {
      id: string
      body: GatewayCredentialUpdateBody
      credentialTeamId: string
    }
  >
  importMutation: UseMutationResult<{ created: number }, Error, { targetTeamId: string }>
  deleteMutation: UseMutationResult<void, Error, { id: string; credentialTeamId: string }>
}

export function useGatewayCredentialMutations(
  options?: UseGatewayCredentialMutationsOptions
): GatewayCredentialMutations {
  const routeTeamId = useGatewayTeamId()
  const teamId = options?.teamId ?? routeTeamId
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const createManagedMutation = useMutation({
    mutationFn: ({
      targetTeamId,
      body,
    }: {
      targetTeamId: string
      body: Parameters<typeof credentialsApi.createCredential>[1]
    }) => credentialsApi.createCredential(targetTeamId, body),
    onSuccess: (cred, variables) => {
      invalidateGatewayCredentialCaches(queryClient, { teamId: variables.targetTeamId })
      options?.onManagedCreateSuccess?.(cred, variables.targetTeamId)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const createUserMutation = useMutation({
    mutationFn: credentialsApi.createMyCredential,
    onSuccess: (cred) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-credentials'] })
      invalidateGatewayCredentialCaches(queryClient)
      options?.onUserCreateSuccess?.(cred)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      body,
      credentialTeamId,
    }: {
      id: string
      body: GatewayCredentialUpdateBody
      credentialTeamId: string
    }) => credentialsApi.updateCredential(credentialTeamId, id, body),
    onSuccess: (_data, variables) => {
      invalidateGatewayCredentialCaches(queryClient, { teamId: variables.credentialTeamId })
      toast({ title: '凭据已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const importMutation = useMutation({
    mutationFn: ({ targetTeamId }: { targetTeamId: string }) =>
      credentialsApi.importFromUserConfig(targetTeamId),
    onSuccess: (r, variables) => {
      invalidateGatewayCredentialCaches(queryClient, { teamId: variables.targetTeamId })
      toast({ title: `已导入 ${String(r.created)} 条` })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '导入失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async ({
      id,
      credentialTeamId,
    }: {
      id: string
      credentialTeamId: string
    }): Promise<void> => {
      await credentialsApi.deleteCredential(credentialTeamId, id)
    },
    onSuccess: () => {
      invalidateGatewayCredentialCaches(queryClient, { teamId })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      options?.onDeleteSuccess?.()
      toast({ title: '凭据已删除', description: '关联的注册模型已一并移除' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  return {
    createManagedMutation,
    createUserMutation,
    updateMutation,
    importMutation,
    deleteMutation,
  }
}
