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

  it('select all current page adds all visible refs', async () => {
    const onConfirm = vi.fn()
    renderDialog({ onConfirm })

    fireEvent.click(screen.getByLabelText(/全选当前页/))
    fireEvent.click(screen.getByRole('button', { name: /到主模型池/ }))

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(['collab/model-a', 'collab/model-b'])
    })
  })

  it('paginates candidates and keeps selection across pages', async () => {
    // 构造 60 个模型，验证分页（每页 50 条）
    const manyModels: RoutePickerModel[] = Array.from({ length: 60 }, (_, idx) =>
      pickerModel({
        id: `m-${String(idx)}`,
        name: `collab/model-${String(idx).padStart(2, '0')}`,
        registry_name: `model-${String(idx).padStart(2, '0')}`,
      })
    )
    const onConfirm = vi.fn()
    render(
      <TooltipProvider>
        <RouteModelBatchPickerDialog
          open
          onOpenChange={vi.fn()}
          candidates={manyModels}
          excludeNames={[]}
          onConfirm={onConfirm}
        />
      </TooltipProvider>
    )

    // 第一页应显示 50 条，且分页控件可见
    expect(screen.getByText(/共 60 项/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '下一页' })).toBeEnabled()

    // 全选当前页（50 条）
    fireEvent.click(screen.getByLabelText(/全选当前页/))
    expect(screen.getByText(/已选 50 项 \/ 共 60 项/)).toBeInTheDocument()

    // 翻到第二页
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    expect(screen.getByRole('button', { name: '上一页' })).toBeEnabled()

    // 第二页全选（剩余 10 条）
    fireEvent.click(screen.getByLabelText(/全选当前页/))
    expect(screen.getByText(/已选 60 项 \/ 共 60 项/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /到主模型池/ }))
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1)
      const callArgs = onConfirm.mock.calls[0] as [string[]]
      expect(callArgs[0]).toHaveLength(60)
    })
  })

  it('filters candidates by capability', async () => {
    const chatModel = pickerModel({ id: '1', name: 'collab/chat-a', capability: 'chat' })
    const imageModel = pickerModel({ id: '2', name: 'collab/image-a', capability: 'image' })
    const embeddingModel = pickerModel({
      id: '3',
      name: 'collab/embed-a',
      capability: 'embedding',
    })
    const onConfirm = vi.fn()
    render(
      <TooltipProvider>
        <RouteModelBatchPickerDialog
          open
          onOpenChange={vi.fn()}
          candidates={[chatModel, imageModel, embeddingModel]}
          excludeNames={[]}
          onConfirm={onConfirm}
        />
      </TooltipProvider>
    )

    // 默认全部可见，共 3 项
    expect(screen.getByText(/共 3 项/)).toBeInTheDocument()
    expect(screen.getByText('collab/chat-a')).toBeInTheDocument()
    expect(screen.getByText('collab/image-a')).toBeInTheDocument()
    expect(screen.getByText('collab/embed-a')).toBeInTheDocument()

    // 选择能力 = 图片生成
    fireEvent.click(screen.getByLabelText('能力'))
    fireEvent.click(screen.getByRole('option', { name: '图片生成（/v1/images）' }))

    // 仅剩 image 模型
    expect(screen.getByText(/共 1 项/)).toBeInTheDocument()
    expect(screen.queryByText('collab/chat-a')).not.toBeInTheDocument()
    expect(screen.getByText('collab/image-a')).toBeInTheDocument()
    expect(screen.queryByText('collab/embed-a')).not.toBeInTheDocument()

    // 选中并确认
    fireEvent.click(screen.getByLabelText(/全选当前页/))
    fireEvent.click(screen.getByRole('button', { name: /到主模型池/ }))
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(['collab/image-a'])
    })
  })

  it('filters candidates by feature tags (AND logic)', async () => {
    const visionModel = pickerModel({
      id: '1',
      name: 'collab/vision-a',
      registry_name: 'vision-a',
      model_types: ['text', 'image'],
      selector_capabilities: { supports_vision: true },
    })
    const toolsModel = pickerModel({
      id: '2',
      name: 'collab/tools-a',
      registry_name: 'tools-a',
      selector_capabilities: { supports_tools: true },
    })
    const visionToolsModel = pickerModel({
      id: '3',
      name: 'collab/vision-tools-a',
      registry_name: 'vision-tools-a',
      model_types: ['text', 'image'],
      selector_capabilities: { supports_vision: true, supports_tools: true },
    })
    const plainModel = pickerModel({
      id: '4',
      name: 'collab/plain-a',
      registry_name: 'plain-a',
    })
    const onConfirm = vi.fn()
    render(
      <TooltipProvider>
        <RouteModelBatchPickerDialog
          open
          onOpenChange={vi.fn()}
          candidates={[visionModel, toolsModel, visionToolsModel, plainModel]}
          excludeNames={[]}
          onConfirm={onConfirm}
        />
      </TooltipProvider>
    )

    // 默认全部可见，共 4 项
    expect(screen.getByText(/共 4 项/)).toBeInTheDocument()

    // 点击"图片理解"特性 chip
    fireEvent.click(screen.getByRole('button', { name: '图片理解' }))
    // 仅剩 vision 和 vision-tools（都支持图片理解）
    expect(screen.getByText(/共 2 项/)).toBeInTheDocument()
    expect(screen.getByText('collab/vision-a')).toBeInTheDocument()
    expect(screen.queryByText('collab/tools-a')).not.toBeInTheDocument()
    expect(screen.getByText('collab/vision-tools-a')).toBeInTheDocument()
    expect(screen.queryByText('collab/plain-a')).not.toBeInTheDocument()

    // 再点击"工具调用"特性 chip（AND 逻辑：需同时满足图片理解 + 工具调用）
    fireEvent.click(screen.getByRole('button', { name: '工具调用' }))
    // 仅剩 vision-tools
    expect(screen.getByText(/共 1 项/)).toBeInTheDocument()
    expect(screen.queryByText('collab/vision-a')).not.toBeInTheDocument()
    expect(screen.getByText('collab/vision-tools-a')).toBeInTheDocument()

    // 清除特性筛选
    fireEvent.click(screen.getByRole('button', { name: '清除' }))
    expect(screen.getByText(/共 4 项/)).toBeInTheDocument()

    // 仅选"工具调用"
    fireEvent.click(screen.getByRole('button', { name: '工具调用' }))
    expect(screen.getByText(/共 2 项/)).toBeInTheDocument()
    expect(screen.getByText('collab/tools-a')).toBeInTheDocument()
    expect(screen.getByText('collab/vision-tools-a')).toBeInTheDocument()
    expect(screen.queryByText('collab/vision-a')).not.toBeInTheDocument()

    // 选中并确认
    fireEvent.click(screen.getByLabelText(/全选当前页/))
    fireEvent.click(screen.getByRole('button', { name: /到主模型池/ }))
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(['collab/tools-a', 'collab/vision-tools-a'])
    })
  })
})
