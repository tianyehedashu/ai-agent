import { act } from 'react'

import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ProviderCredential } from '@/api/gateway'

import { useCredentialEditForm } from './use-credential-edit-form'

const baseCred: ProviderCredential = {
  id: 'c1',
  tenant_id: 't1',
  scope: 'team',
  scope_id: null,
  provider: 'openai',
  name: 'My Key',
  api_base: 'https://api.openai.com/v1',
  is_active: true,
  extra: null,
  created_at: '2026-01-01T00:00:00Z',
  api_key_masked: 'sk-…xxxx',
}

describe('useCredentialEditForm', () => {
  it('canSave is false when synced with original cred', () => {
    const { result } = renderHook(() => useCredentialEditForm({ cred: baseCred }))
    expect(result.current.canSave).toBe(false)
  })

  it('canSave when name changes', () => {
    const { result } = renderHook(() => useCredentialEditForm({ cred: baseCred }))
    act(() => {
      result.current.setName('Renamed')
    })
    expect(result.current.canSave).toBe(true)
    expect(result.current.buildUpdateBody().name).toBe('Renamed')
  })

  it('configManaged omits name from update body', () => {
    const { result } = renderHook(() =>
      useCredentialEditForm({ cred: baseCred, configManaged: true })
    )
    act(() => {
      result.current.setName('Renamed')
      result.current.setApiKey('sk-new')
    })
    const body = result.current.buildUpdateBody()
    expect(body.name).toBeUndefined()
    expect(body.api_key).toBe('sk-new')
  })

  it('trackIsActive includes is_active in body and synced check', () => {
    const { result } = renderHook(() =>
      useCredentialEditForm({ cred: baseCred, trackIsActive: true })
    )
    act(() => {
      result.current.setIsActive(false)
    })
    expect(result.current.canSave).toBe(true)
    expect(result.current.buildUpdateBody().is_active).toBe(false)
  })
})
