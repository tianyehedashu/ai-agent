import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import ChatMessages from './chat-messages'

test('renders process panel with events (collapsed by default)', () => {
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
          {
            id: 'e1',
            kind: 'thinking',
            timestamp: '2025-01-01T00:00:00Z',
            payload: { status: 'start' },
          },
          {
            id: 'e2',
            kind: 'tool_call',
            timestamp: '2025-01-01T00:00:01Z',
            payload: { tool_name: 'read_file' },
          },
          { id: 'e3', kind: 'done', timestamp: '2025-01-01T00:00:02Z', payload: {} },
        ],
      }}
    />
  )

  // 新 UI 默认折叠，显示 "执行完成" 标题
  expect(screen.getByText('执行完成')).toBeInTheDocument()
  // 显示步骤数
  expect(screen.getByText(/\d+ 步/)).toBeInTheDocument()
  // 显示统计徽章
  expect(screen.getByText(/思考 1/)).toBeInTheDocument()
  expect(screen.getByText(/工具 1/)).toBeInTheDocument()
})
