import { describe, expect, it } from 'vitest'

import {
  affiliationLabelForModel,
  filterUnifiedModelEntries,
  matchesHealthFilter,
  paginateUnifiedModelEntries,
  shouldShowUnifiedAffiliationColumn,
  shouldShowUnifiedTeamFilter,
  summarizeUnifiedModelsHealth,
} from './unified-models-filters'

import type { GatewayModelListItem } from '../list/types'

function item(
  partial: Partial<GatewayModelListItem> & Pick<GatewayModelListItem, 'id' | 'scope' | 'title'>
): GatewayModelListItem {
  return {
    subtitle: 'openai · gpt-4',
    upstreamModelId: 'gpt-4',
    provider: 'openai',
    capability: 'chat',
    modelTypes: ['text'],
    enabled: true,
    lastTestStatus: 'success',
    lastTestedAt: null,
    lastTestReason: null,
    teamId: null,
    source: {} as GatewayModelListItem['source'],
    ...partial,
  }
}

describe('unified-models-filters', () => {
  const teamNameById = new Map([['t1', 'Alpha Team']])

  const entries = [
    item({ id: 'p1', scope: 'personal', title: 'My GPT' }),
    item({ id: 't1', scope: 'team', title: 'team-gpt', teamId: 't1' }),
    item({ id: 's1', scope: 'system', title: 'sys-gpt' }),
  ]

  it('filters by scope', () => {
    const teamOnly = filterUnifiedModelEntries(entries, {
      search: '',
      scopeFilter: 'team',
      teamNameById,
    })
    expect(teamOnly).toHaveLength(1)
    expect(teamOnly[0]?.id).toBe('t1')
  })

  it('matches team name in search', () => {
    const found = filterUnifiedModelEntries(entries, {
      search: 'alpha',
      scopeFilter: 'all',
      teamNameById,
    })
    expect(found.map((e) => e.id)).toEqual(['t1'])
  })

  it('paginates filtered results', () => {
    const filtered = filterUnifiedModelEntries(entries, {
      search: '',
      scopeFilter: 'all',
      teamNameById,
    })
    const page = paginateUnifiedModelEntries(filtered, 1, 2)
    expect(page.items).toHaveLength(2)
    expect(page.total).toBe(3)
    expect(page.has_next).toBe(true)
  })

  it('affiliationLabelForModel resolves team', () => {
    expect(affiliationLabelForModel(entries[1], teamNameById)).toBe('Alpha Team')
  })

  it('filters by provider and health', () => {
    const failed = item({
      id: 'p2',
      scope: 'personal',
      title: 'fail',
      provider: 'openai',
      lastTestStatus: 'failed',
    })
    const teamFailed = item({
      id: 't2',
      scope: 'team',
      title: 'team-fail',
      provider: 'openai',
      teamId: 't1',
      lastTestStatus: 'failed',
    })
    const all = [...entries, failed, teamFailed]
    const openaiOk = filterUnifiedModelEntries(all, {
      search: '',
      scopeFilter: 'all',
      teamNameById,
      providerFilter: 'openai',
      healthFilter: 'success',
    })
    expect(openaiOk.map((e) => e.id)).toEqual(['p1', 't1', 's1'])
  })

  it('filters by credential id', () => {
    const withCred = item({
      id: 'p2',
      scope: 'personal',
      title: 'cred-bound',
      credentialId: 'cred-99',
    })
    const found = filterUnifiedModelEntries([...entries, withCred], {
      search: '',
      scopeFilter: 'all',
      teamNameById,
      credentialFilter: 'cred-99',
    })
    expect(found).toHaveLength(1)
    expect(found[0]?.id).toBe('p2')
  })

  it('filters by team id', () => {
    const teamB = item({ id: 't2', scope: 'team', title: 'team-b', teamId: 't2' })
    const all = [...entries, teamB]
    const alphaOnly = filterUnifiedModelEntries(all, {
      search: '',
      scopeFilter: 'all',
      teamNameById,
      teamFilter: 't1',
    })
    expect(alphaOnly.map((e) => e.id)).toEqual(['t1'])
  })

  it('shouldShowUnifiedAffiliationColumn hides when scope or team is locked', () => {
    expect(shouldShowUnifiedAffiliationColumn('all', '')).toBe(true)
    expect(shouldShowUnifiedAffiliationColumn('team', '')).toBe(true)
    expect(shouldShowUnifiedAffiliationColumn('all', 't1')).toBe(false)
    expect(shouldShowUnifiedAffiliationColumn('personal', '')).toBe(false)
    expect(shouldShowUnifiedAffiliationColumn('system', '')).toBe(false)
  })

  it('shouldShowUnifiedTeamFilter on all or team scope with multiple teams', () => {
    expect(shouldShowUnifiedTeamFilter('all', 2)).toBe(true)
    expect(shouldShowUnifiedTeamFilter('team', 2)).toBe(true)
    expect(shouldShowUnifiedTeamFilter('all', 1)).toBe(false)
    expect(shouldShowUnifiedTeamFilter('personal', 2)).toBe(false)
    expect(shouldShowUnifiedTeamFilter('system', 2)).toBe(false)
  })

  it('health summary stays stable when failed filter yields empty list', () => {
    const base = filterUnifiedModelEntries(entries, {
      search: '',
      scopeFilter: 'all',
      teamNameById,
      healthFilter: 'all',
    })
    const summary = summarizeUnifiedModelsHealth(base)
    expect(summary.failed).toBe(0)
    expect(summary.total).toBe(3)

    const failedOnly = base.filter((entry) => matchesHealthFilter(entry, 'failed'))
    expect(failedOnly).toHaveLength(0)
    expect(summarizeUnifiedModelsHealth(failedOnly).total).toBe(0)
    expect(summary.total).toBe(3)
  })
})
