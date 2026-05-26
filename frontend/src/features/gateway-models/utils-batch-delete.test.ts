import { describe, expect, it, vi } from 'vitest'

import {
  chunkIdsForBatchOperation,
  filterDeletableFailedModels,
  filterSelectedIdsInView,
  formatBatchDeleteConfirmLabel,
  runChunkedBatchDelete,
} from './utils'

describe('formatBatchDeleteConfirmLabel', () => {
  it('returns empty for no names', () => {
    expect(formatBatchDeleteConfirmLabel([])).toBe('')
  })

  it('lists all names when count <= 10', () => {
    const label = formatBatchDeleteConfirmLabel(['a', 'b'])
    expect(label).toContain('确定删除以下 2 个模型')
    expect(label).toContain('a、b')
  })

  it('truncates long name lists', () => {
    const names = Array.from({ length: 12 }, (_, i) => `m${String(i)}`)
    const label = formatBatchDeleteConfirmLabel(names)
    expect(label).toContain('确定删除以下 12 个模型')
    expect(label).toContain('以及 4 个其他')
  })
})

describe('filterDeletableFailedModels', () => {
  it('returns only failed models that pass canDelete', () => {
    const models = [
      { id: '1', capability: 'chat', last_test_status: 'failed' as const },
      { id: '2', capability: 'chat', last_test_status: 'success' as const },
      { id: '3', capability: 'chat', last_test_status: 'failed' as const },
    ]
    const result = filterDeletableFailedModels(models, (m) => m.id !== '3')
    expect(result.map((m) => m.id)).toEqual(['1'])
  })
})

describe('chunkIdsForBatchOperation', () => {
  it('splits ids into chunks of max size', () => {
    const ids = Array.from({ length: 5 }, (_, i) => String(i))
    expect(chunkIdsForBatchOperation(ids, 2)).toEqual([['0', '1'], ['2', '3'], ['4']])
  })

  it('returns empty for no ids', () => {
    expect(chunkIdsForBatchOperation([])).toEqual([])
  })
})

describe('filterSelectedIdsInView', () => {
  it('keeps only ids present in visible set', () => {
    const selected = new Set(['a', 'b', 'c'])
    const visible = new Set(['b', 'c', 'd'])
    expect([...filterSelectedIdsInView(selected, visible)]).toEqual(['b', 'c'])
  })
})

describe('runChunkedBatchDelete', () => {
  it('merges results from multiple chunks', async () => {
    const mutateFn = vi
      .fn()
      .mockResolvedValueOnce({
        succeeded: ['a'],
        failed: [],
        grants_removed: 1,
        budgets_removed: 0,
      })
      .mockResolvedValueOnce({
        succeeded: ['b'],
        failed: [{ id: 'c', code: 'x', message: 'fail' }],
        grants_removed: 2,
        budgets_removed: 1,
      })

    const result = await runChunkedBatchDelete(['a', 'b', 'c'], mutateFn, 2)

    expect(mutateFn).toHaveBeenCalledTimes(2)
    expect(result.succeeded).toEqual(['a', 'b'])
    expect(result.failed).toHaveLength(1)
    expect(result.grants_removed).toBe(3)
    expect(result.budgets_removed).toBe(1)
  })
})
