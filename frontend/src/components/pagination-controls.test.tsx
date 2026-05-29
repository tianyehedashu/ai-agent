import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PaginationControls } from './pagination-controls'

describe('PaginationControls', () => {
  it('total 为 0 时不渲染', () => {
    const { container } = render(
      <PaginationControls
        page={1}
        page_size={20}
        total={0}
        has_next={false}
        has_prev={false}
        onPageChange={vi.fn()}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('展示页码文案并触发上一页/下一页', () => {
    const onPageChange = vi.fn()
    render(
      <PaginationControls
        page={2}
        page_size={20}
        total={45}
        has_next
        has_prev
        onPageChange={onPageChange}
      />
    )

    expect(screen.getByText('第 21–40 条，共 45 条 · 第 2/3 页')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '上一页' }))
    expect(onPageChange).toHaveBeenCalledWith(1)

    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    expect(onPageChange).toHaveBeenCalledWith(3)
  })

  it('首/末页时禁用对应按钮', () => {
    render(
      <PaginationControls
        page={1}
        page_size={20}
        total={10}
        has_next={false}
        has_prev={false}
        onPageChange={vi.fn()}
      />
    )

    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '下一页' })).toBeDisabled()
  })
})
