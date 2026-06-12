import { describe, expect, it } from 'vitest'

import {
  buildModelListGridTemplateColumns,
  clampModelListColumnWidth,
  computeModelListTableMinWidth,
  DEFAULT_MODEL_LIST_COLUMN_WIDTHS,
} from './model-list-column-layout'
import {
  loadModelListColumnWidths,
  resetModelListColumnWidth,
} from './model-list-column-preferences'

describe('model-list-column-layout', () => {
  it('builds grid with batch select and trailing columns', () => {
    expect(
      buildModelListGridTemplateColumns(DEFAULT_MODEL_LIST_COLUMN_WIDTHS, {
        showBatchSelect: true,
        showTrailing: true,
      })
    ).toContain('40px')
    expect(
      buildModelListGridTemplateColumns(DEFAULT_MODEL_LIST_COLUMN_WIDTHS, {
        showBatchSelect: true,
        showTrailing: true,
      })
    ).toContain('minmax(108px, auto)')
  })

  it('clamps column width to minimum', () => {
    expect(clampModelListColumnWidth('invokeName', 40)).toBe(100)
    expect(clampModelListColumnWidth('invokeName', 240)).toBe(240)
  })

  it('computes table min width from columns', () => {
    const minWidth = computeModelListTableMinWidth(DEFAULT_MODEL_LIST_COLUMN_WIDTHS, {
      showBatchSelect: true,
      showTrailing: true,
    })
    expect(minWidth).toBeGreaterThan(1200)
  })

  it('omits affiliation column from grid when hidden', () => {
    const withAffiliation = buildModelListGridTemplateColumns(DEFAULT_MODEL_LIST_COLUMN_WIDTHS, {
      showBatchSelect: false,
      showTrailing: false,
      showAffiliationColumn: true,
    })
    const withoutAffiliation = buildModelListGridTemplateColumns(DEFAULT_MODEL_LIST_COLUMN_WIDTHS, {
      showBatchSelect: false,
      showTrailing: false,
      showAffiliationColumn: false,
    })
    expect(withoutAffiliation.split(' ')).toHaveLength(withAffiliation.split(' ').length - 1)
    expect(withoutAffiliation).not.toContain(
      `${String(DEFAULT_MODEL_LIST_COLUMN_WIDTHS.affiliation)}px`
    )
  })
})

describe('model-list-column-preferences', () => {
  it('resets a single column to default', () => {
    const custom = { ...DEFAULT_MODEL_LIST_COLUMN_WIDTHS, invokeName: 320 }
    const next = resetModelListColumnWidth(custom, 'invokeName')
    expect(next.invokeName).toBe(DEFAULT_MODEL_LIST_COLUMN_WIDTHS.invokeName)
    expect(next.channel).toBe(custom.channel)
  })

  it('loads defaults when storage is empty', () => {
    expect(loadModelListColumnWidths()).toEqual(DEFAULT_MODEL_LIST_COLUMN_WIDTHS)
  })
})
