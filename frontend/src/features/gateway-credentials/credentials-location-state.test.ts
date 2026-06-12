import { describe, expect, it } from 'vitest'

import { resolveCredentialsListTab } from './credentials-location-state'
import { parseCredentialsPageView } from './hooks/use-credentials-page-params'

describe('parseCredentialsPageView', () => {
  it('parses create and edit', () => {
    expect(parseCredentialsPageView('create')).toBe('create')
    expect(parseCredentialsPageView('edit')).toBe('edit')
    expect(parseCredentialsPageView(null)).toBeNull()
  })
})

describe('resolveCredentialsListTab', () => {
  it('prefers location state', () => {
    expect(resolveCredentialsListTab(null, { credentialsTab: 'personal' }, 'team')).toBe('personal')
  })

  it('falls back to credential scope', () => {
    expect(resolveCredentialsListTab(null, null, 'system')).toBe('system')
    expect(resolveCredentialsListTab(null, null, 'user')).toBe('personal')
  })
})
