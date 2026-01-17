import { act } from 'react'

import { renderHook, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { useChat } from '@/hooks/use-chat'
import type { ChatEvent } from '@/types'

vi.mock('@/api/chat', () => ({
  chatApi: {
    sendMessage: vi.fn((_req, onEvent: (event: ChatEvent) => void) => {
      onEvent({ type: 'thinking', data: { iteration: 1, status: 'start' }, timestamp: 't1' })
      onEvent({
        type: 'tool_call',
        data: { id: 'tc1', name: 'read_file', arguments: {} },
        timestamp: 't2',
      })
      onEvent({
        type: 'tool_result',
        data: { toolCallId: 'tc1', success: true, output: 'ok' },
        timestamp: 't3',
      })
      onEvent({ type: 'done', data: { final_message: { content: 'done' } }, timestamp: 't4' })
      return Promise.resolve()
    }),
  },
}))

test('useChat tracks process timeline and attaches runId', async () => {
  const { result } = renderHook(() => useChat())

  await act(async () => {
    await result.current.sendMessage('hi')
  })

  await waitFor(() => {
    const assistant = result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.metadata?.runId).toBeTruthy()
    const runId = assistant?.metadata?.runId as string
    expect(result.current.processRuns[runId]).toHaveLength(4)
  })
})
