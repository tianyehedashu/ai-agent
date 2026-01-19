/**
 * SessionNotice 组件测试
 */

import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import type { SessionRecreationData } from '@/types'

import { SessionNotice } from './session-notice'

describe('SessionNotice', () => {
  const mockDismiss = vi.fn()

  const baseRecreationData: SessionRecreationData = {
    sessionId: 'test-session-123',
    isNew: false,
    isRecreated: true,
    previousState: {
      sessionId: 'old-session-456',
      cleanedAt: new Date().toISOString(),
      cleanupReason: 'idle_timeout',
      packagesInstalled: ['numpy', 'pandas', 'requests'],
      filesCreated: ['data.csv', 'output.txt'],
      commandCount: 15,
      totalDurationMs: 120000,
    },
    message: null,
  }

  beforeEach(() => {
    mockDismiss.mockClear()
  })

  it('renders nothing when previousState is null', () => {
    const data: SessionRecreationData = {
      ...baseRecreationData,
      previousState: null,
    }
    const { container } = render(<SessionNotice data={data} onDismiss={mockDismiss} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders session recreation notice with packages', () => {
    render(<SessionNotice data={baseRecreationData} onDismiss={mockDismiss} />)

    expect(screen.getByText('运行环境已重建')).toBeInTheDocument()
    expect(screen.getByText('已安装的包')).toBeInTheDocument()
    expect(screen.getByText(/numpy, pandas, requests/)).toBeInTheDocument()
  })

  it('renders session recreation notice with files', () => {
    render(<SessionNotice data={baseRecreationData} onDismiss={mockDismiss} />)

    expect(screen.getByText('已创建的文件')).toBeInTheDocument()
    expect(screen.getByText(/data.csv, output.txt/)).toBeInTheDocument()
  })

  it('renders command count', () => {
    render(<SessionNotice data={baseRecreationData} onDismiss={mockDismiss} />)
    expect(screen.getByText(/之前执行了 15 条命令/)).toBeInTheDocument()
  })

  it('calls onDismiss when close button is clicked', () => {
    render(<SessionNotice data={baseRecreationData} onDismiss={mockDismiss} />)

    const closeButton = screen.getByRole('button', { name: '关闭通知' })
    fireEvent.click(closeButton)

    expect(mockDismiss).toHaveBeenCalledTimes(1)
  })

  it('shows custom message when provided', () => {
    const dataWithMessage: SessionRecreationData = {
      ...baseRecreationData,
      message: '自定义提示消息',
    }
    render(<SessionNotice data={dataWithMessage} onDismiss={mockDismiss} />)

    expect(screen.getByText('自定义提示消息')).toBeInTheDocument()
  })

  it('truncates long package lists', () => {
    const dataWithManyPackages: SessionRecreationData = {
      ...baseRecreationData,
      previousState: {
        ...baseRecreationData.previousState!,
        packagesInstalled: ['pkg1', 'pkg2', 'pkg3', 'pkg4', 'pkg5', 'pkg6', 'pkg7'],
      },
    }
    render(<SessionNotice data={dataWithManyPackages} onDismiss={mockDismiss} />)

    expect(screen.getByText(/等 7 个包/)).toBeInTheDocument()
  })

  it('shows appropriate cleanup reason text', () => {
    render(<SessionNotice data={baseRecreationData} onDismiss={mockDismiss} />)
    expect(screen.getByText(/由于长时间未活动/)).toBeInTheDocument()
  })
})
