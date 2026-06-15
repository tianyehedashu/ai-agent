import { describe, expect, it } from 'vitest'

import { DEFAULT_BATCH_FORM } from './quota-batch-form'
import { buildBatchRules, buildRealModelsByCredentialMap } from './quota-batch-rules'

const withLimits = {
  ...DEFAULT_BATCH_FORM,
  layer: 'upstream' as const,
  allCredentials: false,
  allModels: false,
  credentialIds: ['c1', 'c2'],
  modelNames: ['gpt-4o'],
  limit_tokens: '1000000',
}

describe('buildBatchRules upstream', () => {
  it('filters credential×model pairs to registered real_models only', () => {
    const realModelsByCredential = buildRealModelsByCredentialMap({
      teamModels: [
        {
          credential_id: 'c1',
          real_model: 'gpt-4o',
        },
      ],
    })
    const rules = buildBatchRules(withLimits, { realModelsByCredential })
    expect(rules).toHaveLength(1)
    expect(rules?.[0]).toMatchObject({
      layer: 'upstream',
      credential_id: 'c1',
      model_name: 'gpt-4o',
      limit_tokens: 1_000_000,
    })
  })

  it('emits one all-models rule per credential when allModels is true', () => {
    const rules = buildBatchRules(
      {
        ...withLimits,
        allModels: true,
        modelNames: [],
        credentialIds: ['c1', 'c2'],
      },
      { realModelsByCredential: buildRealModelsByCredentialMap({ teamModels: [] }) }
    )
    expect(rules).toHaveLength(2)
    expect(rules?.every((rule) => rule.model_name === undefined)).toBe(true)
  })
})
