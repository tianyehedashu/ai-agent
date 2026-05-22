/**
 * @see upstream-import-utils.ts
 */

import { describe, expect, it } from 'vitest'

import type { CredentialUpstreamItem } from '@/api/gateway'

import { countProbeItems, isImportableUpstreamItem, registeredLabel } from './upstream-import-utils'

describe('isImportableUpstreamItem', () => {
  it('treats already_registered as not importable', () => {
    const item: CredentialUpstreamItem = { id: 'gpt-4', already_registered: true }
    expect(isImportableUpstreamItem(item)).toBe(false)
  })

  it('treats empty inferred_model_types as not importable', () => {
    const item: CredentialUpstreamItem = {
      id: 'text-embedding-3',
      inferred_model_types: [],
    }
    expect(isImportableUpstreamItem(item, 'openai')).toBe(false)
  })

  it('allows rows with inferred types', () => {
    const item: CredentialUpstreamItem = {
      id: 'gpt-4o',
      inferred_model_types: ['text', 'image'],
    }
    expect(isImportableUpstreamItem(item, 'openai')).toBe(true)
  })
})

describe('countProbeItems', () => {
  it('counts registered vs importable', () => {
    const items: CredentialUpstreamItem[] = [{ id: 'a', already_registered: true }, { id: 'b' }]
    expect(countProbeItems(items)).toEqual({ total: 2, registered: 1, importable: 1 })
  })
})

describe('registeredLabel', () => {
  it('formats single alias', () => {
    expect(
      registeredLabel({ id: 'x', already_registered: true, registered_names: ['my-alias'] })
    ).toBe('已注册 · my-alias')
  })
})
