/**
 * VirtualKeyRevealDialog
 */

import type { ReactElement } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { VirtualKeyRevealDialog } from './virtual-key-reveal-dialog'

const { revealKeyMock } = vi.hoisted(() => ({
  revealKeyMock: vi.fn<[string, string], Promise<{ plain_key: string }>>(),
}))

vi.mock('@/api/gateway', () => ({
  gatewayApi: {
    revealKey: revealKeyMock,
  },
}))

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

function renderWithQueryClient(ui: ReactElement): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('VirtualKeyRevealDialog', () => {
  it('opens reveal request and shows plain key', async () => {
    revealKeyMock.mockResolvedValueOnce({ plain_key: 'sk-gw-test-plain' })

    renderWithQueryClient(
      <VirtualKeyRevealDialog
        teamId="team-1"
        target={{ id: 'key-1', name: '生产', masked_key: 'sk-gw-***ab12' }}
        onClose={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('sk-gw-test-plain')).toBeInTheDocument()
    })
    expect(revealKeyMock).toHaveBeenCalledWith('team-1', 'key-1')
  })

  it('calls onClose when user dismisses dialog', async () => {
    const onClose = vi.fn()
    revealKeyMock.mockResolvedValueOnce({ plain_key: 'sk-gw-x' })

    renderWithQueryClient(
      <VirtualKeyRevealDialog
        teamId="team-1"
        target={{ id: 'key-1', name: '生产', masked_key: 'sk-gw-***ab12' }}
        onClose={onClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('sk-gw-x')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '关闭' }))
    expect(onClose).toHaveBeenCalled()
  })
})
