/**
 * StepOutputView 组件单测
 */

import type { ReactElement } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import type { ProductInfoJobStep } from '@/types/product-info'

import { StepOutputView } from './step-output-view'

function renderWithProviders(ui: ReactElement): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

function mockStep(overrides: Partial<ProductInfoJobStep> = {}): ProductInfoJobStep {
  return {
    id: 'step-1',
    job_id: 'job-1',
    sort_order: 1,
    capability_id: 'image_analysis',
    input_snapshot: null,
    output_snapshot: { image_descriptions: [{ description: '图1描述' }] },
    meta_prompt: null,
    generated_prompt: null,
    prompt_used: '分析图片',
    prompt_template_id: null,
    status: 'completed',
    error_message: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:01Z',
    ...overrides,
  }
}

describe('StepOutputView', () => {
  it('展示能力名称与已完成状态', () => {
    renderWithProviders(<StepOutputView step={mockStep()} defaultExpanded={true} />)
    expect(screen.getByText(/图片分析/)).toBeInTheDocument()
    expect(screen.getByText(/已完成/)).toBeInTheDocument()
  })

  it('展开时展示输出内容', () => {
    renderWithProviders(<StepOutputView step={mockStep()} defaultExpanded={true} />)
    expect(screen.getByText(/图1描述/)).toBeInTheDocument()
  })

  it('包含复制按钮', () => {
    renderWithProviders(<StepOutputView step={mockStep()} defaultExpanded={true} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('失败步骤展示 error_message', () => {
    renderWithProviders(
      <StepOutputView
        step={mockStep({ status: 'failed', error_message: '网络错误' })}
        defaultExpanded={true}
      />
    )
    expect(screen.getAllByText(/网络错误/).length).toBeGreaterThanOrEqual(1)
  })

  it('image_gen_prompts 步骤展示 8 图提示词区块', () => {
    renderWithProviders(
      <StepOutputView
        step={mockStep({
          capability_id: 'image_gen_prompts',
          output_snapshot: { prompts: ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8'] },
        })}
        defaultExpanded={true}
      />
    )
    expect(screen.getByText(/8 图提示词/)).toBeInTheDocument()
    expect(screen.getByText(/第1张（白底）/)).toBeInTheDocument()
    expect(screen.getByText('p1')).toBeInTheDocument()
  })
})
