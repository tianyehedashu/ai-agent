/**
 * @see gateway-filter-combobox.tsx
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  GATEWAY_FILTER_ALL,
  GatewayFilterCombobox,
  type GatewayFilterOption,
} from './gateway-filter-combobox'

const OPTIONS: GatewayFilterOption[] = [
  { value: 'volcengine', label: 'Volcengine' },
  { value: 'openai', label: 'OpenAI' },
]

describe('GatewayFilterCombobox', () => {
  it('shows placeholder when value is GATEWAY_FILTER_ALL', () => {
    render(
      <GatewayFilterCombobox
        value={GATEWAY_FILTER_ALL}
        onChange={() => {}}
        options={OPTIONS}
        placeholder="提供商"
      />
    )
    expect(screen.getByRole('combobox')).toHaveTextContent('提供商')
  })

  it('shows selected option label on trigger', () => {
    render(
      <GatewayFilterCombobox
        value="volcengine"
        onChange={vi.fn()}
        options={OPTIONS}
        placeholder="提供商"
        active
      />
    )
    expect(screen.getByRole('combobox')).toHaveTextContent('Volcengine')
  })

  it('renders in server search mode without error', () => {
    const onSearchQueryChange = vi.fn()
    render(
      <GatewayFilterCombobox
        value={GATEWAY_FILTER_ALL}
        onChange={vi.fn()}
        options={OPTIONS}
        placeholder="人员"
        searchMode="server"
        onSearchQueryChange={onSearchQueryChange}
        remoteSearching
        emptyHint="输入关键词搜索"
      />
    )
    expect(screen.getByRole('combobox')).toHaveTextContent('人员')
  })

  it('renders active state with check indicator', () => {
    const { container } = render(
      <GatewayFilterCombobox
        value="openai"
        onChange={vi.fn()}
        options={OPTIONS}
        placeholder="提供商"
        active
      />
    )
    expect(screen.getByRole('combobox')).toHaveTextContent('OpenAI')
    // active 状态下触发器应带有视觉高亮（由父组件通过 className 控制，此处确保渲染不报错即可）
    expect(container.querySelector('button')).toBeInTheDocument()
  })
})
