import { describe, expect, it } from 'vitest'

import {
  buildLogGridTemplateColumns,
  computeLogTableMinWidth,
  DEFAULT_LOG_LIST_COLUMN_WIDTHS,
} from '@/features/gateway-usage/log-list-column-layout'

describe('buildLogGridTemplateColumns', () => {
  it('builds full grid with caller', () => {
    expect(buildLogGridTemplateColumns({ showCallerColumn: true })).toBe(
      '152px 120px 220px 128px 120px 96px 96px 88px 80px 76px 72px minmax(160px, 1fr)'
    )
  })

  it('omits caller column when hidden', () => {
    expect(buildLogGridTemplateColumns({ showCallerColumn: false })).toBe(
      '152px 220px 128px 120px 96px 96px 88px 80px 76px 72px minmax(160px, 1fr)'
    )
  })

  it('uses custom invoke name width', () => {
    expect(
      buildLogGridTemplateColumns(
        { showCallerColumn: false },
        { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS, invokeName: 320 }
      )
    ).toBe('152px 320px 128px 120px 96px 96px 88px 80px 76px 72px minmax(160px, 1fr)')
  })

  it('uses custom request id min width', () => {
    expect(
      buildLogGridTemplateColumns(
        { showCallerColumn: false },
        { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS, requestId: 240 }
      )
    ).toBe('152px 220px 128px 120px 96px 96px 88px 80px 76px 72px minmax(240px, 1fr)')
  })
})

describe('computeLogTableMinWidth', () => {
  it('matches template column sum with caller', () => {
    const options = { showCallerColumn: true }
    expect(computeLogTableMinWidth(options)).toBe(1408)
  })

  it('shrinks when caller column hidden', () => {
    expect(computeLogTableMinWidth({ showCallerColumn: false })).toBe(1288)
  })
})
