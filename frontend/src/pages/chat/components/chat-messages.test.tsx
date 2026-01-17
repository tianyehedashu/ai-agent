import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import ChatMessages from './chat-messages'

test('renders process panel with events (default expanded)', () => {
  render(
    <ChatMessages
      messages={[
        {
          id: 'm1',
          role: 'assistant',
          content: 'final',
          createdAt: 't',
          metadata: { runId: 'r1' },
        },
      ]}
      streamingContent=""
      isLoading={false}
      pendingToolCalls={[]}
      processRuns={{
        r1: [
          { id: 'e1', kind: 'thinking', timestamp: 't1', payload: { status: 'start' } },
          { id: 'e2', kind: 'tool_call', timestamp: 't2', payload: { name: 'read_file' } },
        ],
      }}
    />
  )

  expect(screen.getByText('全过程')).toBeInTheDocument()
  expect(screen.getByText('thinking')).toBeInTheDocument()
  expect(screen.getByText('read_file')).toBeInTheDocument()
})
