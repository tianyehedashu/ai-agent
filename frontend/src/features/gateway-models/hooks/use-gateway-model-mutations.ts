import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  gatewayApi,
  type GatewayModel,
  type GatewayModelCreateBody,
  type GatewayModelUpdateBody,
} from '@/api/gateway'
import {
  invalidateGatewayModelAliasDependents,
  invalidateGatewayModelCaches,
} from '@/features/gateway-models/utils'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'

import type { UseMutationResult } from '@tanstack/react-query'

interface UseGatewayModelMutationsOptions {
  credentialId?: string
  /** 覆盖路由 teamId（凭据创建 onboarding 等场景） */
  teamId?: string
  onCreateSuccess?: (created: GatewayModel) => void
  onDeleteSuccess?: () => void
}

interface GatewayModelMutations {
  createMutation: UseMutationResult<GatewayModel, Error, GatewayModelCreateBody>
  updateModelMutation: UseMutationResult<
    GatewayModel,
    Error,
    { id: string; body: GatewayModelUpdateBody; teamId?: string }
  >
  deleteModelMutation: UseMutationResult<void, Error, { id: string; teamId?: string }>
  testMutation: UseMutationResult<
    Awaited<ReturnType<typeof gatewayApi.testModel>>,
    Error,
    { id: string; teamId?: string }
  >
}

export function useGatewayModelMutations(
  options?: UseGatewayModelMutationsOptions
): GatewayModelMutations {
  const routeTeamId = useGatewayTeamId()
  const teamId = options?.teamId ?? routeTeamId
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const filterCredentialId = options?.credentialId

  const createMutation = useMutation({
    mutationFn: (body: GatewayModelCreateBody) => gatewayApi.createModel(teamId, body),
    onSuccess: (created) => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId: filterCredentialId ?? created.credential_id,
        usageSummary: true,
      })
      options?.onCreateSuccess?.(created)
      toast({ title: '模型已注册' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '注册失败', description: e.message })
    },
  })

  const updateModelMutation = useMutation({
    mutationFn: ({
      id,
      body,
      teamId: overrideTeamId,
    }: {
      id: string
      body: GatewayModelUpdateBody
      teamId?: string
    }) => gatewayApi.updateModel(overrideTeamId ?? teamId, id, body),
    onSuccess: (_data, { body }) => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId: filterCredentialId,
        usageSummary: true,
      })
      if (typeof body.name === 'string' && body.name.trim() !== '') {
        invalidateGatewayModelAliasDependents(queryClient)
      }
      toast({
        title: body.resync_capabilities ? '能力已从目录同步' : '模型已更新',
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const testMutation = useMutation({
    mutationFn: ({ id, teamId: overrideTeamId }: { id: string; teamId?: string }) =>
      gatewayApi.testModel(overrideTeamId ?? teamId, id),
    onSuccess: (result) => {
      invalidateGatewayModelCaches(queryClient, { credentialId: filterCredentialId })
      if (result.success) {
        toast({ title: '连接成功', description: result.message })
      } else {
        toast({ variant: 'destructive', title: '连接失败', description: result.message })
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '测试出错', description: e.message })
    },
  })

  const deleteModelMutation = useMutation({
    mutationFn: async ({
      id,
      teamId: overrideTeamId,
    }: {
      id: string
      teamId?: string
    }): Promise<void> => {
      await gatewayApi.deleteModel(overrideTeamId ?? teamId, id)
    },
    onSuccess: () => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId: filterCredentialId,
        usageSummary: true,
      })
      invalidateGatewayModelAliasDependents(queryClient)
      options?.onDeleteSuccess?.()
      toast({ title: '模型已删除' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  return {
    createMutation,
    updateModelMutation,
    deleteModelMutation,
    testMutation,
  }
}
