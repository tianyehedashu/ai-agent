/**
 * @see route-model-pool.tsx
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { GatewayModel } from '@/api/gateway'
import { TooltipProvider } from '@/components/ui/tooltip'

import { RouteFallbackModelPicker, RouteOrderedModelPicker } from './route-model-pool'

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

const MODEL_A = gatewayModel({ id: '1', name: 'model-a' })
const MODEL_B = gatewayModel({ id: '2', name: 'model-b', provider: 'anthropic' })
const MODEL_C = gatewayModel({ id: '3', name: 'model-c', provider: 'deepseek' })

describe('RouteOrderedModelPicker', () => {
  it('does not render full catalog when nothing is selected', () => {
    render(
      <RouteOrderedModelPicker
        models={[MODEL_A, MODEL_B, MODEL_C]}
        selected={[]}
        onSelectedChange={vi.fn()}
        label="主模型"
      />
    )

    expect(screen.getByText('尚未配置主模型')).toBeInTheDocument()
    expect(screen.queryByText('model-a')).not.toBeInTheDocument()
    expect(screen.queryByText('model-b')).not.toBeInTheDocument()
    expect(screen.queryByText('model-c')).not.toBeInTheDocument()
  })

  it('renders only selected models', () => {
    render(
      <RouteOrderedModelPicker
        models={[MODEL_A, MODEL_B, MODEL_C]}
        selected={['model-a', 'model-c']}
        onSelectedChange={vi.fn()}
        label="主模型"
      />
    )

    expect(screen.getByText('model-a')).toBeInTheDocument()
    expect(screen.getByText('model-c')).toBeInTheDocument()
    expect(screen.queryByText('model-b')).not.toBeInTheDocument()
  })

  it('calls onSelectedChange when removing a model', () => {
    const onSelectedChange = vi.fn()
    render(
      <RouteOrderedModelPicker
        models={[MODEL_A, MODEL_B]}
        selected={['model-a', 'model-b']}
        onSelectedChange={onSelectedChange}
        label="主模型"
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '移除 model-a' }))

    expect(onSelectedChange).toHaveBeenCalledWith(['model-b'])
  })
})

describe('RouteFallbackModelPicker', () => {
  it('does not render full catalog when nothing is selected', () => {
    render(
      <RouteFallbackModelPicker
        models={[MODEL_A, MODEL_B]}
        selected={[]}
        onSelectedChange={vi.fn()}
        label="通用 Fallback"
        excludeNames={[]}
      />
    )

    expect(screen.getByText('尚未配置')).toBeInTheDocument()
    expect(screen.queryByText('model-a')).not.toBeInTheDocument()
    expect(screen.queryByText('model-b')).not.toBeInTheDocument()
  })

  it('renders only selected fallback models', () => {
    render(
      <RouteFallbackModelPicker
        models={[MODEL_A, MODEL_B, MODEL_C]}
        selected={['model-b']}
        onSelectedChange={vi.fn()}
        label="通用 Fallback"
        excludeNames={['model-a']}
      />
    )

    expect(screen.getByText('model-b')).toBeInTheDocument()
    expect(screen.queryByText('model-a')).not.toBeInTheDocument()
    expect(screen.queryByText('model-c')).not.toBeInTheDocument()
  })

  it('adds a model via combobox in RouteOrderedModelPicker', async () => {
    const onSelectedChange = vi.fn()
    render(
      <TooltipProvider>
        <RouteOrderedModelPicker
          models={[MODEL_A, MODEL_B, MODEL_C]}
          selected={[]}
          onSelectedChange={onSelectedChange}
          label="主模型"
        />
      </TooltipProvider>
    )

    // Click the "添加主模型" button to open the combobox
    fireEvent.click(screen.getByRole('button', { name: '添加主模型' }))

    // Wait for the combobox to open and show the list
    await screen.findByPlaceholderText('搜索模型别名、通道…')

    // Click on a model item to select it
    fireEvent.click(screen.getByText('model-b'))

    // Verify onSelectedChange was called with the new model added
    await waitFor(() => {
      expect(onSelectedChange).toHaveBeenCalledWith(['model-b'])
    })
  })
})
