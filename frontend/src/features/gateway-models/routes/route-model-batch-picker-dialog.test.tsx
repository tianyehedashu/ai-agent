/**
 * @see route-model-batch-picker-dialog.tsx
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { TooltipProvider } from '@/components/ui/tooltip'

import { RouteModelBatchPickerDialog } from './route-model-batch-picker-dialog'

import type { RoutePickerModel } from './use-personal-route-callable-models'

vi.mock('@/features/gateway-teams/use-gateway-teams', () => ({
  useGatewayMemberTeamNameMap: () => new Map([['team-1', '协作团队']]),
}))

function pickerModel(
  partial: Partial<RoutePickerModel> & Pick<RoutePickerModel, 'name'>
): RoutePickerModel {
  const { name, ...rest } = partial
  return {
    id: rest.id ?? name,
    tenant_id: rest.tenant_id ?? 'team-1',
    team_id: rest.team_id ?? 'team-1',
    name,
    registry_name: rest.registry_name ?? name.split('/').pop() ?? name,
    team_kind: rest.team_kind ?? 'shared',
    team_slug: rest.team_slug ?? 'collab',
    prefix_dispatchable: rest.prefix_dispatchable ?? true,
    capability: 'chat',
    real_model: rest.real_model ?? name,
    credential_id: 'cred-1',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: 'success',
    last_tested_at: null,
    last_test_reason: null,
    created_at: '',
    ...rest,
  } as RoutePickerModel
}

const MODEL_A = pickerModel({ id: '1', name: 'collab/model-a', registry_name: 'model-a' })
const MODEL_B = pickerModel({ id: '2', name: 'collab/model-b', registry_name: 'model-b' })

function renderDialog(
  props: Partial<React.ComponentProps<typeof RouteModelBatchPickerDialog>> = {}
): ReturnType<typeof render> {
  return render(
    <TooltipProvider>
      <RouteModelBatchPickerDialog
        open
        onOpenChange={vi.fn()}
        candidates={[MODEL_A, MODEL_B]}
        excludeNames={[]}
        onConfirm={vi.fn()}
        {...props}
      />
    </TooltipProvider>
  )
}

describe('RouteModelBatchPickerDialog', () => {
  it('merges selected route refs on confirm', async () => {
    const onConfirm = vi.fn()
    renderDialog({ onConfirm })

    fireEvent.click(screen.getByRole('checkbox', { name: /collab\/model-a/i }))
    fireEvent.click(screen.getByRole('checkbox', { name: /collab\/model-b/i }))
    fireEvent.click(screen.getByRole('button', { name: /到主模型池/ }))

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(['collab/model-a', 'collab/model-b'])
    })
  })

  it('excludes already selected names from candidates', () => {
    renderDialog({ excludeNames: ['collab/model-a'] })
    expect(screen.queryByText('collab/model-a')).not.toBeInTheDocument()
    expect(screen.getByText('collab/model-b')).toBeInTheDocument()
  })

  it('select all filtered adds all visible refs', async () => {
    const onConfirm = vi.fn()
    renderDialog({ onConfirm })

    fireEvent.click(screen.getByLabelText(/全选当前筛选/))
    fireEvent.click(screen.getByRole('button', { name: /到主模型池/ }))

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(['collab/model-a', 'collab/model-b'])
    })
  })
})
