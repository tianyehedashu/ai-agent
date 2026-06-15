import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PlaygroundModelField } from './playground-model-field'

import type { ModelCandidate } from './playground-mode-filter'

const MODEL_A: ModelCandidate = {
  name: 'deepseek-chat',
  scope: 'team',
  status: 'success',
  capability: 'chat',
  provider: 'deepseek',
}

const MODEL_B: ModelCandidate = {
  name: 'deepseek-reasoner',
  scope: 'team',
  status: 'success',
  capability: 'chat',
  provider: 'deepseek',
}

const baseProps = {
  modelSelectId: 'model-select',
  modelCustomId: 'model-custom',
  model: 'deepseek-chat',
  customModel: false,
  onModelChange: vi.fn(),
  onCustomModelChange: vi.fn(),
  routeCandidates: [],
  teamCandidates: [MODEL_A, MODEL_B],
  personalCandidates: [],
  filteredModels: [MODEL_A, MODEL_B],
  selectedCandidate: MODEL_A,
  selectedRoute: undefined,
  priceByName: new Map(),
  currency: 'CNY' as const,
  playgroundMode: 'chat' as const,
  modelsLoading: false,
}

describe('PlaygroundModelField', () => {
  it('opens combobox and picks a model', async () => {
    const onCustomModelChange = vi.fn()
    render(<PlaygroundModelField {...baseProps} onCustomModelChange={onCustomModelChange} />)

    fireEvent.click(screen.getByRole('combobox'))

    await screen.findByPlaceholderText('搜索模型别名、路由…')
    fireEvent.click(screen.getByText('deepseek-reasoner'))

    await waitFor(() => {
      expect(onCustomModelChange).toHaveBeenCalledWith(false, 'deepseek-reasoner')
    })
  })

  it('filters candidates by search input', () => {
    render(<PlaygroundModelField {...baseProps} />)

    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.change(screen.getByPlaceholderText('搜索模型别名、路由…'), {
      target: { value: 'reasoner' },
    })

    const listbox = screen.getByRole('listbox')
    expect(within(listbox).getByText('deepseek-reasoner')).toBeInTheDocument()
    expect(within(listbox).queryByText('deepseek-chat')).not.toBeInTheDocument()
  })

  it('switches to manual input mode', async () => {
    const onCustomModelChange = vi.fn()
    render(<PlaygroundModelField {...baseProps} onCustomModelChange={onCustomModelChange} />)

    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.click(screen.getByText('✏️ 手动输入…'))

    await waitFor(() => {
      expect(onCustomModelChange).toHaveBeenCalledWith(true, '')
    })
  })
})
