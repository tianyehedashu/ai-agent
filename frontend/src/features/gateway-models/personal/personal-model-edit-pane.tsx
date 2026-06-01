import { useCallback } from 'react'

import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { usePersonalModelMutations } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import { personalModelDetailHref } from '@/features/gateway-models/paths'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Loader2 } from '@/lib/lucide-icons'

import { PersonalModelForm, type PersonalModelFormValues } from './personal-model-form'

interface PersonalModelEditPaneProps {
  modelId: string
}

export function PersonalModelEditPane({ modelId }: PersonalModelEditPaneProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const { toast } = useToast()

  const { data: credentials = [], isLoading: credsLoading } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
  })

  const { data: model, isLoading: modelsLoading } = useQuery({
    queryKey: ['gateway', 'my-models', modelId],
    queryFn: () => gatewayApi.getMyModel(modelId),
    enabled: modelId !== '',
  })

  const { updateMutation } = usePersonalModelMutations()

  const handleResyncCapabilities = useCallback((): void => {
    if (!model) return
    updateMutation.mutate(
      { id: model.id, body: { resync_capabilities: true } },
      {
        onSuccess: () => {
          toast({ title: '能力已从 LiteLLM 同步' })
        },
      }
    )
  }, [model, updateMutation, toast])

  const handleSubmit = useCallback(
    (values: PersonalModelFormValues): void => {
      if (!model) return
      if (!values.display_name || !values.model_id || !values.credential_id) {
        toast({ title: '请填写必填项并选择凭据', variant: 'destructive' })
        return
      }
      updateMutation.mutate(
        {
          id: model.id,
          body: {
            display_name: values.display_name,
            model_id: values.model_id,
            credential_id: values.credential_id,
            is_active: model.is_active,
            model_types: values.model_types,
          },
        },
        {
          onSuccess: () => {
            navigate(personalModelDetailHref(teamId, modelId))
          },
        }
      )
    },
    [model, modelId, navigate, teamId, updateMutation, toast]
  )

  const handleCancel = useCallback((): void => {
    navigate(personalModelDetailHref(teamId, modelId))
  }, [navigate, modelId, teamId])

  if (credsLoading || modelsLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载…
      </div>
    )
  }

  if (!model) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        未找到该模型，可能已被删除。
      </p>
    )
  }

  return (
    <PersonalModelForm
      mode="edit"
      credentials={credentials}
      initial={model}
      onSubmit={handleSubmit}
      onCancel={handleCancel}
      isSubmitting={updateMutation.isPending}
      onResyncCapabilities={handleResyncCapabilities}
      isResyncing={updateMutation.isPending}
    />
  )
}
