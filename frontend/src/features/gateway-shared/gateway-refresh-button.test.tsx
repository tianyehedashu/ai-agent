import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { GatewayRefreshButton } from './gateway-refresh-button'

describe('GatewayRefreshButton', () => {
  it('calls onRefresh when clicked', () => {
    const onRefresh = vi.fn()
    render(<GatewayRefreshButton isFetching={false} onRefresh={onRefresh} />)

    fireEvent.click(screen.getByRole('button', { name: '刷新' }))
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('disables button while fetching', () => {
    render(<GatewayRefreshButton isFetching={true} onRefresh={() => undefined} />)

    expect(screen.getByRole('button', { name: '刷新' })).toBeDisabled()
  })

  it('uses custom aria label', () => {
    render(
      <GatewayRefreshButton
        isFetching={false}
        ariaLabel="刷新团队列表"
        onRefresh={() => undefined}
      />
    )

    expect(screen.getByRole('button', { name: '刷新团队列表' })).toBeInTheDocument()
  })
})
