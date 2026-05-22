import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ConfirmAlertDialog } from './confirm-alert-dialog'

describe('ConfirmAlertDialog', () => {
  it('calls onConfirm when user confirms', () => {
    const onConfirm = vi.fn()

    render(
      <ConfirmAlertDialog
        open
        onOpenChange={vi.fn()}
        title="删除测试"
        description="确定执行？"
        confirmLabel="确认删除"
        onConfirm={onConfirm}
      />
    )

    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('删除测试')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('does not call onConfirm when user cancels', () => {
    const onConfirm = vi.fn()

    render(
      <ConfirmAlertDialog
        open
        onOpenChange={vi.fn()}
        title="删除测试"
        description="确定执行？"
        onConfirm={onConfirm}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('disables actions while pending', () => {
    render(
      <ConfirmAlertDialog
        open
        onOpenChange={vi.fn()}
        title="删除测试"
        description="确定执行？"
        confirmLabel="确认删除"
        pending
        onConfirm={vi.fn()}
      />
    )

    expect(screen.getByRole('button', { name: '取消' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '确认删除中…' })).toBeDisabled()
  })
})
