import { describe, expect, it } from 'vitest'

import {
  isMultiGrantVirtualKey,
  parseProxyModelsToCandidates,
  proxyModelItemToCandidate,
} from '@/features/gateway-playground/playground-proxy-models'
import { virtualKeyAllowsModelName } from '@/features/gateway-playground/playground-proxy-team'

describe('playground-proxy-models', () => {
  it('proxyModelItemToCandidate 使用 list id（可含 slug 前缀）', () => {
    const candidate = proxyModelItemToCandidate({
      id: 'acme/gpt-4o',
      capability: 'chat',
      owned_by: 'openai',
      model_types: ['text'],
      gateway: { callable: true, connectivity_status: 'success', team_slug: 'acme' },
    })
    expect(candidate?.name).toBe('acme/gpt-4o')
    expect(candidate?.teamSlug).toBe('acme')
  })

  it('parseProxyModelsToCandidates 跳过不可调用项', () => {
    const items = parseProxyModelsToCandidates([
      { id: 'gpt-4o', gateway: { callable: true, connectivity_status: 'success' } },
      { id: 'broken', gateway: { callable: false } },
    ])
    expect(items.map((m) => m.name)).toEqual(['gpt-4o'])
  })

  it('isMultiGrantVirtualKey', () => {
    expect(isMultiGrantVirtualKey(undefined)).toBe(false)
    expect(isMultiGrantVirtualKey(['a'])).toBe(false)
    expect(isMultiGrantVirtualKey(['a', 'b'])).toBe(true)
  })
})

describe('virtualKeyAllowsModelName', () => {
  it('允许 slug 前缀匹配注册名白名单', () => {
    expect(virtualKeyAllowsModelName('team-a/gpt-4o', ['gpt-4o'])).toBe(true)
    expect(virtualKeyAllowsModelName('team-a/gpt-4o', ['other'])).toBe(false)
  })

  it('空白名单表示不限制', () => {
    expect(virtualKeyAllowsModelName('any/model', [])).toBe(true)
    expect(virtualKeyAllowsModelName('any/model', undefined)).toBe(true)
  })
})
