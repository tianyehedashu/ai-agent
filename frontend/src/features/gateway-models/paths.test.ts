import { describe, expect, it } from 'vitest'

import {
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
    expect(teamModelsFilteredHref()).toBe('/gateway/models?tab=team')
  })

  it('teamModelsFilteredHref with credential', () => {
    expect(teamModelsFilteredHref('cred-1')).toBe('/gateway/models?tab=team&credentialId=cred-1')
  })

  it('teamModelsRegisterHref locks credential', () => {
    expect(teamModelsRegisterHref('cred-1')).toBe(
      '/gateway/models?tab=team&credentialId=cred-1&view=register'
    )
  })

  it('teamModelDetailHref includes credential context', () => {
    expect(teamModelDetailHref('model-1', { credentialId: 'cred-1' })).toBe(
      '/gateway/models/model-1?tab=team&credentialId=cred-1'
    )
  })

  it('credentialDetailHref encodes id', () => {
    expect(credentialDetailHref('cred/1')).toBe('/gateway/credentials/cred%2F1')
  })

  it('teamModelsIndexHref matches filtered without credential', () => {
    expect(teamModelsIndexHref()).toBe(teamModelsFilteredHref())
    expect(credentialsTeamListHref()).toBe('/gateway/credentials?tab=team')
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
