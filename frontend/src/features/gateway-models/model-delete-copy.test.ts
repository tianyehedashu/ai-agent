import { describe, expect, it } from 'vitest'

import {
  formatSingleGatewayModelDeleteDescription,
  resolveGatewayModelDeleteScope,
} from './model-delete-copy'

describe('model-delete-copy', () => {
  it('formats personal delete description without route whitelist hint', () => {
    expect(formatSingleGatewayModelDeleteDescription('My GPT', 'personal')).toContain('My GPT')
    expect(formatSingleGatewayModelDeleteDescription('My GPT', 'personal')).not.toContain(
      '虚拟 Key'
    )
  })

  it('formats team delete description with route whitelist hint', () => {
    expect(formatSingleGatewayModelDeleteDescription('team/gpt', 'team')).toContain('虚拟 Key')
  })

  it('resolves delete scope from list scope', () => {
    expect(resolveGatewayModelDeleteScope('personal')).toBe('personal')
    expect(resolveGatewayModelDeleteScope('team')).toBe('team')
    expect(resolveGatewayModelDeleteScope('system')).toBe('team')
  })
})
