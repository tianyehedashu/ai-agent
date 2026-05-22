import { describe, expect, it } from 'vitest'

import { formatBatchDeleteConfirmLabel } from './utils'

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
