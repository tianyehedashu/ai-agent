import { describe, expect, it } from 'vitest'

import { parseScopeTab } from './constants'
import {
  credentialDetailAddModelsHref,
  credentialDetailHref,
  credentialsTeamListHref,
  personalModelDetailHref,
  personalModelEditHref,
  personalModelsIndexHref,
  personalModelsRegisterHref,
  teamModelDetailHref,
  teamModelsFilteredHref,
  teamModelsIndexHref,
  teamModelsRegisterHref,
} from './paths'

describe('gateway model paths', () => {
  it('teamModelsFilteredHref without credential', () => {
    expect(teamModelsFilteredHref()).toBe('/gateway/models?tab=shared')
  })

  it('teamModelsFilteredHref with credential', () => {
    expect(teamModelsFilteredHref('cred-1')).toBe('/gateway/models?tab=shared&credentialId=cred-1')
  })

  it('teamModelsRegisterHref locks credential', () => {
    expect(teamModelsRegisterHref('cred-1')).toBe(
      '/gateway/models?tab=shared&credentialId=cred-1&view=register'
    )
  })

  it('teamModelDetailHref includes credential context', () => {
    expect(teamModelDetailHref('model-1', { credentialId: 'cred-1' })).toBe(
      '/gateway/models/model-1?tab=shared&credentialId=cred-1'
    )
  })

  it('credentialDetailHref encodes id', () => {
    expect(credentialDetailHref('cred/1')).toBe('/gateway/credentials/cred%2F1')
  })

  it('credentialDetailAddModelsHref appends addModels query', () => {
    expect(credentialDetailAddModelsHref('cred-1')).toBe('/gateway/credentials/cred-1?addModels=1')
  })

  it('teamModelsIndexHref matches filtered without credential', () => {
    expect(teamModelsIndexHref()).toBe(teamModelsFilteredHref())
    expect(credentialsTeamListHref()).toBe('/gateway/credentials?tab=shared')
  })

  it('personalModelsIndexHref', () => {
    expect(personalModelsIndexHref()).toBe('/gateway/models?tab=personal')
  })

  it('personalModelsRegisterHref', () => {
    expect(personalModelsRegisterHref()).toBe('/gateway/models?tab=personal&view=register')
  })

  it('personalModelDetailHref', () => {
    expect(personalModelDetailHref('pm-1')).toBe('/gateway/models/pm-1?tab=personal')
  })

  it('personalModelEditHref', () => {
    expect(personalModelEditHref('pm-1')).toBe('/gateway/models/pm-1?tab=personal&view=edit')
  })
})

describe('parseScopeTab', () => {
  it('returns shared for null/unknown raw', () => {
    expect(parseScopeTab(null)).toBe('shared')
    expect(parseScopeTab('garbage')).toBe('shared')
  })

  it('returns personal for personal raw', () => {
    expect(parseScopeTab('personal')).toBe('personal')
  })

  it('returns shared for shared raw', () => {
    expect(parseScopeTab('shared')).toBe('shared')
  })

  it('compatibility: legacy ?tab=team maps to shared', () => {
    expect(parseScopeTab('team')).toBe('shared')
  })
})
