import React, { act } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { chatApi } from '@/api/chat'
import { useChat } from '@/hooks/use-chat'
import type { ChatEvent } from '@/types'

function createWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

const defaultSendMessageImpl = (
  _req: unknown,
  onEvent: (event: ChatEvent) => void
): Promise<void> => {
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
}

vi.mock('@/api/chat', () => ({
  chatApi: {
    sendMessage: vi.fn((req: unknown, onEvent: (event: ChatEvent) => void) =>
      defaultSendMessageImpl(req, onEvent)
    ),
  },
}))

test('useChat tracks process timeline and attaches runId', async () => {
  const { result } = renderHook(() => useChat(), { wrapper: createWrapper() })

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

test('background stream keeps session state when view switches away', async () => {
  let resolveFirst!: () => void
  let resolveContinue!: () => void
  const firstEventFired = new Promise<void>((r) => {
    resolveFirst = r
  })
  const continueStream = new Promise<void>((r) => {
    resolveContinue = r
  })

  /* eslint-disable-next-line @typescript-eslint/unbound-method -- vi.mocked().mockImplementationOnce(callback) is safe */
  vi.mocked(chatApi.sendMessage).mockImplementationOnce(
    vi.fn(async (_req, onEvent) => {
      onEvent({ type: 'thinking', data: { iteration: 1, status: 'processing' }, timestamp: 't1' })
      resolveFirst()
      await continueStream
      onEvent({
        type: 'tool_call',
        data: { tool_call_id: 'tc1', tool_name: 'read_file', arguments: {} },
        timestamp: 't2',
      })
      onEvent({
        type: 'tool_result',
        data: { tool_call_id: 'tc1', success: true, output: 'ok' },
        timestamp: 't3',
      })
      onEvent({ type: 'done', data: { final_message: { content: 'done' } }, timestamp: 't4' })
    })
  )

  const { result, rerender } = renderHook((opts: { sessionId?: string }) => useChat(opts), {
    initialProps: { sessionId: 'session-a' },
    wrapper: createWrapper(),
  })

  const sendPromise = act(async () => {
    await result.current.sendMessage('hi')
  })

  await firstEventFired
  act(() => {
    rerender({ sessionId: 'session-b' })
  })
  expect(result.current.messages).toHaveLength(0)

  resolveContinue()
  await sendPromise

  act(() => {
    rerender({ sessionId: 'session-a' })
  })

  await waitFor(() => {
    const assistant = result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.content).toBe('done')
    const runId = assistant?.metadata?.runId as string
    expect(result.current.processRuns[runId].length).toBeGreaterThanOrEqual(3)
  })
})

test('useChat clears loading state and persists run timeline on stream error', async () => {
  /* eslint-disable-next-line @typescript-eslint/unbound-method -- vi.mocked().mockImplementationOnce(callback) is safe */
  vi.mocked(chatApi.sendMessage).mockImplementationOnce(
    vi.fn((_req, onEvent) => {
      onEvent({
        type: 'error',
        data: { error: '无可用文本模型。请配置 DEFAULT_MODEL 或执行 make seed-gateway 同步目录。' },
        timestamp: 't1',
      })
      return Promise.resolve()
    })
  )

  const onError = vi.fn()
  const { result } = renderHook(() => useChat({ onError }), { wrapper: createWrapper() })

  await act(async () => {
    await result.current.sendMessage('hi')
  })

  expect(onError).toHaveBeenCalled()
  expect(result.current.isLoading).toBe(false)
  expect(result.current.currentRunId).toBeNull()

  const assistant = result.current.messages.find((m) => m.role === 'assistant')
  expect(assistant?.metadata?.runId).toBeTruthy()
  const runId = assistant?.metadata?.runId as string
  expect(result.current.processRuns[runId]).toEqual(
    expect.arrayContaining([expect.objectContaining({ kind: 'error' })])
  )
})

test('first message with session_created: subsequent events still apply to view', async () => {
  /* eslint-disable-next-line @typescript-eslint/unbound-method -- vi.mocked().mockImplementationOnce(callback) is safe */
  vi.mocked(chatApi.sendMessage).mockImplementationOnce(
    vi.fn((_req, onEvent) => {
      onEvent({
        type: 'session_created',
        data: { session_id: 'new-session-id' },
        timestamp: 't0',
      })
      onEvent({ type: 'thinking', data: { iteration: 1, status: 'start' }, timestamp: 't1' })
      onEvent({
        type: 'tool_call',
        data: { tool_call_id: 'tc1', tool_name: 'read_file', arguments: {} },
        timestamp: 't2',
      })
      onEvent({
        type: 'tool_result',
        data: { tool_call_id: 'tc1', success: true, output: 'ok' },
        timestamp: 't3',
      })
      onEvent({ type: 'done', data: { final_message: { content: 'reply' } }, timestamp: 't4' })
      return Promise.resolve()
    })
  )

  const onSessionCreated = vi.fn()
  const { result } = renderHook(() => useChat({ sessionId: undefined, onSessionCreated }), {
    wrapper: createWrapper(),
  })

  await act(async () => {
    await result.current.sendMessage('hi')
  })

  expect(onSessionCreated).toHaveBeenCalledWith('new-session-id')
  await waitFor(() => {
    const assistant = result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.content).toBe('reply')
    expect(assistant?.metadata?.runId).toBeTruthy()
    const runId = assistant?.metadata?.runId as string
    expect(result.current.processRuns[runId].length).toBeGreaterThanOrEqual(1)
  })
})
