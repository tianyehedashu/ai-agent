import { describe, expect, it } from 'vitest'

import { buildBatchRules } from '@/features/gateway-budget/quota-batch-rules'
import { buildModelQuotaDefaultForm } from '@/features/gateway-models/detail/model-detail-quota-utils'

describe('model detail quota batch payload', () => {
  it('builds single platform rule for locked model', () => {
    const form = buildModelQuotaDefaultForm({
      modelName: 'alias-model',
      credentialId: 'cred-1',
      layer: 'platform',
    })
    const withLimits = { ...form, limit_usd: '10' }
    const rules = buildBatchRules(withLimits)
    expect(rules).toHaveLength(1)
    expect(rules?.[0]).toMatchObject({
      layer: 'platform',
      target_kind: 'tenant',
      model_name: 'alias-model',
      period: 'monthly',
      limit_usd: 10,
    })
  })

  it('builds upstream rule with credential and model', () => {
    const form = buildModelQuotaDefaultForm({
      modelName: 'alias-model',
      credentialId: 'cred-1',
      layer: 'upstream',
    })
    const withLimits = { ...form, limit_tokens: '500000' }
    const rules = buildBatchRules(withLimits)
    expect(rules).toHaveLength(1)
    expect(rules?.[0]).toMatchObject({
      layer: 'upstream',
      credential_id: 'cred-1',
      model_name: 'alias-model',
      limit_tokens: 500000,
    })
  })
})
