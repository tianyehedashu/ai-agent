import { render, screen } from '@testing-library/react'
import { describe, expect, it, afterEach } from 'vitest'

import { OverlayScope, useOverlayPortalContainer } from '@/lib/ui-overlay'

function PortalContainerProbe(): React.JSX.Element {
  const container = useOverlayPortalContainer()
  return <span data-testid="portal-container">{container ? 'scoped' : 'body'}</span>
}

describe('OverlayScope', () => {
  afterEach(() => {
    document.body.style.removeProperty('pointer-events')
  })

  it('provides scoped portal container to descendants', () => {
    render(
      <OverlayScope>
        <PortalContainerProbe />
      </OverlayScope>
    )

    expect(screen.getByTestId('portal-container')).toHaveTextContent('scoped')
    expect(document.querySelector('[data-overlay-portal-mount]')).not.toBeNull()
    expect(document.querySelector('[data-overlay-scope]')).not.toBeNull()
  })

  it('clears portal mount and body lock on unmount', async () => {
    const { unmount: unmountTree } = render(
      <OverlayScope>
        <div data-testid="block">content</div>
      </OverlayScope>
    )

    const mount = document.querySelector('[data-overlay-portal-mount]') as HTMLDivElement
    const wrapper = document.createElement('div')
    wrapper.setAttribute('data-radix-popper-content-wrapper', '')
    mount.appendChild(wrapper)
    document.body.style.pointerEvents = 'none'

    unmountTree()

    expect(document.querySelector('[data-overlay-scope]')).toBeNull()
    // React 负责移除 mount；手动 DOM 不应被 teardown 清空
    await Promise.resolve()
    expect(document.body.style.pointerEvents).toBe('')
  })

  it('uses body fallback outside OverlayScope', () => {
    render(<PortalContainerProbe />)
    expect(screen.getByTestId('portal-container')).toHaveTextContent('body')
  })
})
