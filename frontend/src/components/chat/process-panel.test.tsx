import { render, screen, fireEvent } from '@testing-library/react'
import { expect, test } from 'vitest'

import { ProcessPanel } from '@/components/chat/process-panel'

test('shows summary badges when collapsed', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'thinking', timestamp: '2025-01-01T00:00:00Z', payload: { status: 'processing' } },
        { id: 'e2', kind: 'tool_call', timestamp: '2025-01-01T00:00:01Z', payload: { tool_name: 'read_file' } },
        { id: 'e3', kind: 'tool_result', timestamp: '2025-01-01T00:00:02Z', payload: { success: false, error: 'boom' } },
        { id: 'e4', kind: 'done', timestamp: '2025-01-01T00:00:03Z', payload: {} },
      ]}
    />
  )

  // 默认折叠，显示摘要
  expect(screen.getByText('执行完成')).toBeInTheDocument()
  expect(screen.getByText(/思考 1/)).toBeInTheDocument()
  expect(screen.getByText(/工具 1/)).toBeInTheDocument()
  expect(screen.getByText(/失败 1/)).toBeInTheDocument()
})

test('shows event details when expanded', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'tool_call', timestamp: '2025-01-01T00:00:00Z', payload: { tool_name: 'search', arguments: { query: 'test' } } },
        { id: 'e2', kind: 'done', timestamp: '2025-01-01T00:00:01Z', payload: {} },
      ]}
      defaultExpanded
    />
  )

  // 展开时显示工具名
  expect(screen.getByText('search')).toBeInTheDocument()
})

test('shows tool result success and failure when expanded', () => {
  render(
    <ProcessPanel
      events={[
        {
          id: 'e1',
          kind: 'tool_result',
          timestamp: '2025-01-01T00:00:00Z',
          payload: { tool_call_id: 'tc1', success: true, output: 'File content here', duration_ms: 100 },
        },
        {
          id: 'e2',
          kind: 'tool_result',
          timestamp: '2025-01-01T00:00:01Z',
          payload: { tool_call_id: 'tc2', success: false, error: 'Tool not available' },
        },
        { id: 'e3', kind: 'done', timestamp: '2025-01-01T00:00:02Z', payload: {} },
      ]}
      defaultExpanded
    />
  )

  expect(screen.getByText(/成功.*100ms/)).toBeInTheDocument()
  expect(screen.getByText('失败')).toBeInTheDocument()
  expect(screen.getByText(/Tool not available/)).toBeInTheDocument()
})

test('shows done event stats when expanded', () => {
  render(
    <ProcessPanel
      events={[
        {
          id: 'e1',
          kind: 'done',
          timestamp: '2025-01-01T00:00:00Z',
          payload: { iterations: 2, tool_iterations: 3, total_tokens: 1500 },
        },
      ]}
      defaultExpanded
    />
  )

  expect(screen.getByText('完成')).toBeInTheDocument()
  expect(screen.getByText(/2 轮/)).toBeInTheDocument()
  expect(screen.getByText(/3 次调用/)).toBeInTheDocument()
})

test('shows loading state when not completed', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'thinking', timestamp: '2025-01-01T00:00:00Z', payload: { status: 'processing' } },
      ]}
    />
  )

  // 未完成时显示 "执行中..."
  expect(screen.getByText('执行中...')).toBeInTheDocument()
})

test('aggregates consecutive thinking events', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'thinking', timestamp: '2025-01-01T00:00:00Z', payload: { status: 'processing' } },
        { id: 'e2', kind: 'thinking', timestamp: '2025-01-01T00:00:01Z', payload: { status: 'analyzing' } },
        { id: 'e3', kind: 'thinking', timestamp: '2025-01-01T00:00:02Z', payload: { status: 'reasoning', content: 'Thinking...' } },
        { id: 'e4', kind: 'done', timestamp: '2025-01-01T00:00:03Z', payload: {} },
      ]}
      defaultExpanded
    />
  )

  // 3 个 thinking 事件应该聚合为一个
  expect(screen.getByText('思考 3 轮')).toBeInTheDocument()
  // 显示最后一个 thinking 的内容
  expect(screen.getByText(/Thinking/)).toBeInTheDocument()
})

test('expands on click', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'tool_call', timestamp: '2025-01-01T00:00:00Z', payload: { tool_name: 'test_tool' } },
        { id: 'e2', kind: 'done', timestamp: '2025-01-01T00:00:01Z', payload: {} },
      ]}
    />
  )

  // 默认折叠，不显示工具名
  expect(screen.queryByText('test_tool')).not.toBeInTheDocument()

  // 点击展开
  fireEvent.click(screen.getByText('执行完成'))

  // 展开后显示工具名
  expect(screen.getByText('test_tool')).toBeInTheDocument()
})

test('merges consecutive text events', () => {
  render(
    <ProcessPanel
      events={[
        { id: 'e1', kind: 'text', timestamp: '2025-01-01T00:00:00Z', payload: { content: 'Hello ' } },
        { id: 'e2', kind: 'text', timestamp: '2025-01-01T00:00:00Z', payload: { content: 'world!' } },
        { id: 'e3', kind: 'done', timestamp: '2025-01-01T00:00:01Z', payload: {} },
      ]}
      defaultExpanded
    />
  )

  // 合并后显示 "生成回复"
  expect(screen.getByText('生成回复')).toBeInTheDocument()
  // 合并后的内容
  expect(screen.getByText('Hello world!')).toBeInTheDocument()
})
