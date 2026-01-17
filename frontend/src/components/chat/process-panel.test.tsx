import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { ProcessPanel } from '@/components/chat/process-panel'

test('shows summary counts and error state', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'thinking', timestamp: 't1', payload: {} },
        { id: 'e2', kind: 'tool_call', timestamp: 't2', payload: { name: 'read_file' } },
        { id: 'e3', kind: 'error', timestamp: 't3', payload: { error: 'boom' } },
      ]}
    />
  )

  expect(screen.getByText(/思考\s*1/)).toBeInTheDocument()
  expect(screen.getByText(/工具\s*1/)).toBeInTheDocument()
  expect(screen.getByText(/错误\s*1/)).toBeInTheDocument()
  expect(screen.getByText('boom')).toBeInTheDocument()
})
