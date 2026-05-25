/**
 * @see current-api-key-field.tsx
 */

import type { ReactElement } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CurrentApiKeyField } from './current-api-key-field'

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

function renderWithQueryClient(ui: ReactElement): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('CurrentApiKeyField', () => {
  it('shows masked value by default', () => {
    renderWithQueryClient(
      <CurrentApiKeyField
        label="API Key"
        maskedValue="sk-1…2345"
        revealFn={vi.fn().mockResolvedValue({ api_key: 'sk-full' })}
      />
    )
    expect(screen.getByDisplayValue('sk-1…2345')).toBeInTheDocument()
  })

  it('reveals full key when switch is toggled on', async () => {
    const revealFn = vi.fn().mockResolvedValue({ api_key: 'sk-full-secret' })
    renderWithQueryClient(
      <CurrentApiKeyField label="API Key" maskedValue="sk-1…2345" revealFn={revealFn} />
    )
    fireEvent.click(screen.getByRole('switch', { name: '显示完整密钥' }))
    await waitFor(() => {
      expect(screen.getByDisplayValue('sk-full-secret')).toBeInTheDocument()
    })
    expect(revealFn).toHaveBeenCalledOnce()
  })

  it('does not render reveal switch when canReveal is false', () => {
    renderWithQueryClient(
      <CurrentApiKeyField
        label="API Key"
        maskedValue="sk-1…2345"
        revealFn={vi.fn()}
        canReveal={false}
      />
    )
    expect(screen.queryByRole('switch', { name: '显示完整密钥' })).not.toBeInTheDocument()
  })
})
