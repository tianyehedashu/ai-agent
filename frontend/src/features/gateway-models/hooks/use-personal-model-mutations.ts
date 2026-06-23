import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  gatewayApi,
  type PersonalGatewayModel,
  type PersonalGatewayModelCreateBody,
  type PersonalGatewayModelUpdateBody,
} from '@/api/gateway'
import { useToast } from '@/hooks/use-toast'

import type { UseMutationResult } from '@tanstack/react-query'

export const personalModelsListQueryKey = (provider?: string): readonly unknown[] =>
  provider ? (['gateway', 'my-models', provider] as const) : (['gateway', 'my-models'] as const)

export function invalidatePersonalModelCaches(
  queryClient: ReturnType<typeof useQueryClient>
): void {
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] })
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'unified-models'] })
  void queryClient.invalidateQueries({ queryKey: ['gateway-models-available'] })
}

interface UsePersonalModelMutationsOptions {
  onCreateSuccess?: (created: PersonalGatewayModel[]) => void
  onUpdateSuccess?: (updated: PersonalGatewayModel) => void
  onDeleteSuccess?: () => void
}

interface PersonalModelMutations {
  createMutation: UseMutationResult<PersonalGatewayModel[], Error, PersonalGatewayModelCreateBody>
  updateMutation: UseMutationResult<
    PersonalGatewayModel,
    Error,
    { id: string; body: PersonalGatewayModelUpdateBody }
  >
  deleteMutation: UseMutationResult<unknown, Error, string>
  testMutation: UseMutationResult<Awaited<ReturnType<typeof gatewayApi.testMyModel>>, Error, string>
}

export function usePersonalModelMutations(
  options?: UsePersonalModelMutationsOptions
): PersonalModelMutations {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const createMutation = useMutation({
    mutationFn: gatewayApi.createMyModel,
    onSuccess: (created) => {
      invalidatePersonalModelCaches(queryClient)
      toast({ title: '模型已创建' })
      options?.onCreateSuccess?.(created)
    },
    onError: (e: Error) => {
      toast({ title: '创建失败', description: e.message, variant: 'destructive' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: PersonalGatewayModelUpdateBody }) =>
      gatewayApi.updateMyModel(id, body),
    onSuccess: (updated, { body }) => {
      invalidatePersonalModelCaches(queryClient)
      toast({
        title: body.resync_capabilities ? '能力已从目录同步' : '模型已更新',
      })
      options?.onUpdateSuccess?.(updated)
    },
    onError: (e: Error) => {
      toast({ title: '更新失败', description: e.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: gatewayApi.deleteMyModel,
    onSuccess: () => {
      invalidatePersonalModelCaches(queryClient)
      toast({ title: '模型已删除' })
      options?.onDeleteSuccess?.()
    },
    onError: (e: Error) => {
      toast({ title: '删除失败', description: e.message, variant: 'destructive' })
    },
  })

  const testMutation = useMutation({
    mutationFn: gatewayApi.testMyModel,
    onSuccess: (result) => {
      invalidatePersonalModelCaches(queryClient)
      if (result.success) {
        toast({ title: '连接成功', description: result.message })
      } else {
        toast({ title: '连接失败', description: result.message, variant: 'destructive' })
      }
    },
    onError: (e: Error) => {
      toast({ title: '测试出错', description: e.message, variant: 'destructive' })
    },
  })

  return { createMutation, updateMutation, deleteMutation, testMutation }
}
