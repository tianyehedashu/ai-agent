import { describe, expect, it } from 'vitest'

import { parseModelsScopeTab, parseScopeTab } from './constants'
import {
  credentialDetailAddModelsHref,
  credentialDetailHref,
  credentialsListHref,
  modelsIndexHref,
  personalCredentialsIndexHref,
  personalModelDetailHref,
  personalModelsIndexHref,
  personalModelsRegisterHref,
  teamModelDetailHref,
  teamModelsFilteredHref,
  teamModelsIndexHref,
  teamModelsRegisterHref,
} from './paths'

const TEAM = 'team-abc'

describe('gateway model paths', () => {
  it('modelsIndexHref without params', () => {
    expect(modelsIndexHref(TEAM)).toBe('/gateway/teams/team-abc/models')
  })

  it('teamModelsFilteredHref without credential', () => {
    expect(teamModelsFilteredHref(TEAM)).toBe('/gateway/teams/team-abc/models')
  })

  it('teamModelsFilteredHref with credential', () => {
    expect(teamModelsFilteredHref(TEAM, 'cred-1')).toBe(
      '/gateway/teams/team-abc/models?credentialId=cred-1&scope=team'
    )
  })

  it('teamModelsRegisterHref locks credential', () => {
    expect(teamModelsRegisterHref(TEAM, 'cred-1')).toBe(
      '/gateway/teams/team-abc/models?credentialId=cred-1&scope=team&view=register'
    )
  })

  it('teamModelDetailHref includes credential context', () => {
    expect(teamModelDetailHref(TEAM, 'model-1', { credentialId: 'cred-1' })).toBe(
      '/gateway/teams/team-abc/models/model-1?tab=shared&credentialId=cred-1'
    )
  })

  it('teamModelDetailHref supports system tab', () => {
    expect(teamModelDetailHref(TEAM, 'model-1', { tab: 'system' })).toBe(
      '/gateway/teams/team-abc/models/model-1?tab=system'
    )
  })

  it('credentialDetailHref encodes id', () => {
    expect(credentialDetailHref(TEAM, 'cred/1')).toBe(
      '/gateway/teams/team-abc/credentials/cred%2F1'
    )
  })

  it('credentialDetailAddModelsHref appends addModels query', () => {
    expect(credentialDetailAddModelsHref(TEAM, 'cred-1')).toBe(
      '/gateway/teams/team-abc/credentials/cred-1?addModels=1'
    )
  })

  it('credentialsListHref', () => {
    expect(credentialsListHref(TEAM)).toBe('/gateway/teams/team-abc/credentials')
  })

  it('personalCredentialsIndexHref with credentialId', () => {
    expect(personalCredentialsIndexHref(TEAM, { credentialId: 'cred-1' })).toBe(
      '/gateway/teams/team-abc/credentials?credentialId=cred-1'
    )
  })

  it('credentialsListHref with view=create', () => {
    expect(credentialsListHref(TEAM, { view: 'create' })).toBe(
      '/gateway/teams/team-abc/credentials?view=create'
    )
  })

  it('teamModelsIndexHref matches filtered without credential', () => {
    expect(teamModelsIndexHref(TEAM)).toBe(teamModelsFilteredHref(TEAM))
  })

  it('personalModelsIndexHref', () => {
    expect(personalModelsIndexHref(TEAM)).toBe('/gateway/teams/team-abc/models')
  })

  it('personalModelsRegisterHref', () => {
    expect(personalModelsRegisterHref(TEAM)).toBe(
      '/gateway/teams/team-abc/models?scope=personal&view=register'
    )
  })

  it('personalModelsRegisterHref with credentialId', () => {
    expect(personalModelsRegisterHref(TEAM, 'cred-1')).toBe(
      '/gateway/teams/team-abc/models?credentialId=cred-1&scope=personal&view=register'
    )
  })

  it('personalModelDetailHref', () => {
    expect(personalModelDetailHref(TEAM, 'pm-1')).toBe(
      '/gateway/teams/team-abc/models/pm-1?tab=personal'
    )
  })

  it('personalModelDetailHref serves as edit deep link', () => {
    expect(personalModelDetailHref(TEAM, 'pm-1')).toBe(
      '/gateway/teams/team-abc/models/pm-1?tab=personal'
    )
  })

  it('modelsIndexHref for unified browse', () => {
    expect(modelsIndexHref(TEAM)).toBe('/gateway/teams/team-abc/models')
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

  it('returns system only when allowSystem', () => {
    expect(parseScopeTab('system')).toBe('shared')
    expect(parseScopeTab('system', { allowSystem: true })).toBe('system')
  })

  it('parseModelsScopeTab always resolves system', () => {
    expect(parseModelsScopeTab('system')).toBe('system')
    expect(parseModelsScopeTab(null)).toBe('shared')
  })
})
