/**
 * @see route-model-add-combobox.tsx
 */

import type React from 'react'

import { fireEvent, render, screen, waitFor, type RenderResult } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { GatewayModel } from '@/api/gateway'
import { TooltipProvider } from '@/components/ui/tooltip'

import { RouteModelAddCombobox } from './route-model-add-combobox'

function renderCombobox(ui: React.ReactElement): RenderResult {
  return render(<TooltipProvider>{ui}</TooltipProvider>)
}

function gatewayModel(partial: Partial<GatewayModel> & Pick<GatewayModel, 'name'>): GatewayModel {
  const { name, ...rest } = partial
  return {
    id: rest.id ?? name,
    tenant_id: 'team-1',
    team_id: 'team-1',
    name,
    capability: 'chat',
    real_model: rest.real_model ?? name,
    credential_id: 'cred-1',
    provider: rest.provider ?? 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: rest.last_test_status ?? 'success',
    last_tested_at: null,
    last_test_reason: null,
    created_at: '',
    ...rest,
  }
}

const MODEL_A = gatewayModel({
  id: '1',
  name: 'deepseek-chat',
  provider: 'deepseek',
  real_model: 'deepseek-chat',
})
const MODEL_B = gatewayModel({
  id: '2',
  name: 'deepseek-reasoner',
  provider: 'deepseek',
  real_model: 'deepseek-reasoner',
})

describe('RouteModelAddCombobox', () => {
  it('opens a wide popover and picks a model', async () => {
    const onPick = vi.fn()
    renderCombobox(
      <RouteModelAddCombobox
        candidates={[MODEL_A, MODEL_B]}
        onPick={onPick}
        triggerLabel="添加主模型"
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '添加主模型' }))

    await screen.findByPlaceholderText('搜索模型别名、通道…')
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    fireEvent.click(screen.getByText('deepseek-reasoner'))

    await waitFor(() => {
      expect(onPick).toHaveBeenCalledWith('deepseek-reasoner')
    })
  })

  it('filters candidates by search input', () => {
    renderCombobox(
      <RouteModelAddCombobox
        candidates={[MODEL_A, MODEL_B]}
        onPick={vi.fn()}
        triggerLabel="添加主模型"
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '添加主模型' }))
    fireEvent.change(screen.getByPlaceholderText('搜索模型别名、通道…'), {
      target: { value: 'reasoner' },
    })

    expect(screen.getByText('deepseek-reasoner')).toBeInTheDocument()
    expect(screen.queryByText('deepseek-chat')).not.toBeInTheDocument()
  })
})
