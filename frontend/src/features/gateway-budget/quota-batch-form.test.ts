import { describe, expect, it } from 'vitest'

import {
  DEFAULT_BATCH_FORM,
  patchQuotaBatchFormForLayer,
  patchQuotaBatchFormForSubjectMode,
} from './use-quota-center'

describe('patchQuotaBatchFormForLayer', () => {
  it('clears credential ids when switching to platform', () => {
    const next = patchQuotaBatchFormForLayer(
      { ...DEFAULT_BATCH_FORM, layer: 'upstream', credentialIds: ['c1'] },
      'platform'
    )
    expect(next.credentialIds).toEqual([])
    expect(next.layer).toBe('platform')
  })

  it('clears user ids when switching to downstream', () => {
    const next = patchQuotaBatchFormForLayer(
      { ...DEFAULT_BATCH_FORM, userIds: ['u1'], subjectMode: 'users' },
      'downstream'
    )
    expect(next.userIds).toEqual([])
    expect(next.subjectMode).toBe('keys')
  })
})

describe('patchQuotaBatchFormForSubjectMode', () => {
  it('clears key ids when selecting tenant', () => {
    const next = patchQuotaBatchFormForSubjectMode(
      { ...DEFAULT_BATCH_FORM, subjectMode: 'keys', keyIds: ['k1'] },
      'tenant'
    )
    expect(next.keyIds).toEqual([])
    expect(next.subjectMode).toBe('tenant')
  })
})
