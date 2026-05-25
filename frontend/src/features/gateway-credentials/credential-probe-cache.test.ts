/**
 * @see credential-probe-cache.ts
 */

import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import type { CredentialProbeResult } from '@/api/gateway'

import {
  PROBE_CACHE_STALE_MS,
  credentialProbeCacheKey,
  invalidateCredentialProbeCache,
  isProbeCacheFresh,
} from './credential-probe-cache'

function sampleProbe(credentialId: string): CredentialProbeResult {
  return {
    credential_id: credentialId,
    probe_at: new Date().toISOString(),
    support: 'unsupported',
    upstream: 'none',
    items: [],
    message: 'test',
    http_status: null,
  }
}

describe('credentialProbeCacheKey', () => {
  it('includes scope and credential id', () => {
    expect(credentialProbeCacheKey('team', 'cred-1')).toEqual([
      'gateway',
      'credential-probe',
      'team',
      'cred-1',
    ])
    expect(credentialProbeCacheKey('system', 'cred-sys')).toEqual([
      'gateway',
      'credential-probe',
      'system',
      'cred-sys',
    ])
  })
})

describe('isProbeCacheFresh', () => {
  it('returns false when cache is empty', () => {
    const client = new QueryClient()
    const key = credentialProbeCacheKey('team', 'cred-1')
    expect(isProbeCacheFresh(client, key)).toBe(false)
  })

  it('returns true within stale window', () => {
    const client = new QueryClient()
    const key = credentialProbeCacheKey('team', 'cred-1')
    client.setQueryData(key, sampleProbe('cred-1'))
    expect(isProbeCacheFresh(client, key)).toBe(true)
  })

  it('returns false after stale window', () => {
    vi.useFakeTimers()
    const client = new QueryClient()
    const key = credentialProbeCacheKey('user', 'cred-2')
    client.setQueryData(key, sampleProbe('cred-2'))
    vi.advanceTimersByTime(PROBE_CACHE_STALE_MS + 1)
    expect(isProbeCacheFresh(client, key)).toBe(false)
    vi.useRealTimers()
  })
})

describe('invalidateCredentialProbeCache', () => {
  it('removes cached probe for scope and credential', () => {
    const client = new QueryClient()
    const key = credentialProbeCacheKey('team', 'cred-x')
    client.setQueryData(key, sampleProbe('cred-x'))
    invalidateCredentialProbeCache(client, 'team', 'cred-x')
    expect(client.getQueryData(key)).toBeUndefined()
  })
})
