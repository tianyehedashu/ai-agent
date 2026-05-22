import { describe, expect, it } from 'vitest'

import { BATCH_IMPORT_MAX, chunkBatchImportItems } from './utils'

describe('chunkBatchImportItems', () => {
  it('returns empty for no items', () => {
    expect(chunkBatchImportItems([])).toEqual([])
  })

  it('splits at BATCH_IMPORT_MAX', () => {
    const items = Array.from({ length: 55 }, (_, i) => ({
      upstream_model_id: `m-${String(i)}`,
      model_types: ['text'],
    }))
    const chunks = chunkBatchImportItems(items)
    expect(chunks).toHaveLength(2)
    expect(chunks[0]).toHaveLength(BATCH_IMPORT_MAX)
    expect(chunks[1]).toHaveLength(5)
  })
})
