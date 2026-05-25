import { describe, expect, it } from 'vitest'

import {
  gatewayModelsByCredentialInvalidatePrefix,
  gatewayModelsByCredentialQueryKey,
} from './query-keys'

describe('gatewayModelsByCredentialQueryKey', () => {
  it('includes teamId and tab for reads', () => {
    expect(gatewayModelsByCredentialQueryKey('team-1', 'cred-1', 'system')).toEqual([
      'gateway',
      'models',
      'team-1',
      'by-credential',
      'cred-1',
      'system',
    ])
  })

  it('invalidate prefix matches read key without tab', () => {
    expect(gatewayModelsByCredentialInvalidatePrefix('cred-1', 'team-1')).toEqual([
      'gateway',
      'models',
      'team-1',
      'by-credential',
      'cred-1',
    ])
  })
})
