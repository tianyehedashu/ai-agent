/**
 * @see credential-extra-utils.ts
 */

import { describe, expect, it } from 'vitest'

import { compactExtra, extraToFormValues } from './credential-extra-utils'

describe('compactExtra', () => {
  it('drops empty strings and whitespace-only values', () => {
    expect(
      compactExtra({
        api_version: '2024-08-01-preview',
        empty: '',
        spaces: '   ',
        region: 'us-east-1',
      })
    ).toEqual({
      api_version: '2024-08-01-preview',
      region: 'us-east-1',
    })
  })

  it('trims surrounding whitespace from kept values', () => {
    expect(compactExtra({ workspace_id: '  ws-1  ' })).toEqual({ workspace_id: 'ws-1' })
  })

  it('returns empty object when input has no usable values', () => {
    expect(compactExtra({})).toEqual({})
    expect(compactExtra({ a: '', b: '   ' })).toEqual({})
  })
})

describe('extraToFormValues', () => {
  it('returns empty object for null / undefined input', () => {
    expect(extraToFormValues(null)).toEqual({})
    expect(extraToFormValues(undefined)).toEqual({})
  })

  it('keeps string values as-is', () => {
    expect(extraToFormValues({ api_version: '2024-08-01-preview', workspace_id: 'ws-1' })).toEqual({
      api_version: '2024-08-01-preview',
      workspace_id: 'ws-1',
    })
  })

  it('JSON-encodes non-string values (e.g. nested objects)', () => {
    expect(extraToFormValues({ list: [1, 2], nested: { a: 1 } })).toEqual({
      list: '[1,2]',
      nested: '{"a":1}',
    })
  })

  it('skips null / undefined values', () => {
    expect(extraToFormValues({ kept: 'yes', dropped: null, also: undefined })).toEqual({
      kept: 'yes',
    })
  })
})
