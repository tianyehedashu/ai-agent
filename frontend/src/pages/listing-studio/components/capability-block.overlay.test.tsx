import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { getFallbackCapabilitiesConfig } from '@/hooks/use-listing-studio-capabilities'
import { OverlayScope } from '@/lib/ui-overlay'

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: undefined, isLoading: false }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

vi.mock('@/api/listingStudio', () => ({
  listingStudioApi: {},
}))

vi.mock('@/components/model-selector', () => ({
  ModelSelector: () => <div data-testid="model-selector" />,
}))

vi.mock('./step-context-panel', () => ({
  StepContextPanel: () => <div data-testid="step-context" />,
}))

vi.mock('./prompt-editor', () => ({
  PromptEditor: () => <div data-testid="prompt-editor" />,
}))

vi.mock('./step-output-view', () => ({
  StepOutputView: () => <div data-testid="step-output" />,
}))

const mockConfig = getFallbackCapabilitiesConfig()

describe('CapabilityBlock overlay scope', () => {
  it('wraps expanded panel in OverlayScope', async () => {
    const { CapabilityBlock } = await import('./capability-block')

    render(
      <CapabilityBlock
        capabilityId="image_analysis"
        stepIndex={1}
        job={null}
        inputs={{
          product_link: '',
          competitor_link: '',
          product_name: '',
          keywords: '',
          image_urls: [],
        }}
        promptByCapability={{}}
        onPromptChange={vi.fn()}
        localContext={{}}
        onLocalContextChange={vi.fn()}
        expanded
        capabilityConfig={mockConfig}
      />
    )

    expect(screen.getByLabelText('图片分析 步骤详情')).toBeInTheDocument()
    expect(document.querySelector('[data-overlay-scope]')).not.toBeNull()
    expect(document.querySelector('[data-overlay-portal-mount]')).not.toBeNull()
  })

  it('does not mount overlay scope when collapsed', async () => {
    const { CapabilityBlock } = await import('./capability-block')

    render(
      <CapabilityBlock
        capabilityId="image_analysis"
        job={null}
        inputs={{
          product_link: '',
          competitor_link: '',
          product_name: '',
          keywords: '',
          image_urls: [],
        }}
        promptByCapability={{}}
        onPromptChange={vi.fn()}
        localContext={{}}
        onLocalContextChange={vi.fn()}
        expanded={false}
        capabilityConfig={mockConfig}
      />
    )

    expect(document.querySelector('[data-overlay-scope]')).toBeNull()
  })
})

describe('OverlayScope export', () => {
  it('exports OverlayScope component', () => {
    expect(OverlayScope).toBeTypeOf('function')
  })
})
