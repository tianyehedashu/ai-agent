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

  it('serializes limit_images into upstream rule body', () => {
    const realModelsByCredential = buildRealModelsByCredentialMap({
      teamModels: [{ credential_id: 'c1', real_model: 'dall-e-3' }],
    })
    const rules = buildBatchRules(
      {
        ...withLimits,
        limit_tokens: '',
        limit_images: '50',
        modelNames: ['dall-e-3'],
      },
      { realModelsByCredential }
    )
    expect(rules).toHaveLength(1)
    expect(rules?.[0]).toMatchObject({
      layer: 'upstream',
      credential_id: 'c1',
      model_name: 'dall-e-3',
      limit_images: 50,
    })
    // 未填的限额字段不应出现在 body 上
    expect(rules?.[0].limit_tokens).toBeUndefined()
    expect(rules?.[0].limit_usd).toBeUndefined()
    expect(rules?.[0].limit_requests).toBeUndefined()
  })

  it('emits rule with limit_images only when other limits are empty (upstream)', () => {
    const realModelsByCredential = buildRealModelsByCredentialMap({
      teamModels: [{ credential_id: 'c1', real_model: 'dall-e-3' }],
    })
    const rules = buildBatchRules(
      {
        ...DEFAULT_BATCH_FORM,
        layer: 'upstream' as const,
        allCredentials: false,
        allModels: false,
        credentialIds: ['c1'],
        modelNames: ['dall-e-3'],
        limit_usd: '',
        limit_tokens: '',
        limit_requests: '',
        limit_images: '100',
      },
      { realModelsByCredential }
    )
    expect(rules).toHaveLength(1)
    expect(rules?.[0].limit_images).toBe(100)
  })

  it('serializes limit_images into platform rule body', () => {
    const rules = buildBatchRules({
      ...DEFAULT_BATCH_FORM,
      layer: 'platform' as const,
      subjectMode: 'tenant' as const,
      allModels: false,
      modelNames: ['dall-e-3'],
      limit_usd: '',
      limit_tokens: '',
      limit_requests: '',
      limit_images: '50',
    })
    expect(rules).toHaveLength(1)
    expect(rules?.[0]).toMatchObject({
      layer: 'platform',
      target_kind: 'tenant',
      limit_images: 50,
    })
  })

  it('serializes limit_images into downstream rule body', () => {
    const rules = buildBatchRules({
      ...DEFAULT_BATCH_FORM,
      layer: 'downstream' as const,
      allModels: false,
      modelNames: ['dall-e-3'],
      keyIds: ['vkey-1'],
      limit_usd: '',
      limit_tokens: '',
      limit_requests: '',
      limit_images: '30',
    })
    expect(rules).toHaveLength(1)
    expect(rules?.[0]).toMatchObject({
      layer: 'downstream',
      access_kind: 'vkey',
      access_id: 'vkey-1',
      limit_images: 30,
    })
  })

  it('returns null when only limit_images is empty along with others', () => {
    const realModelsByCredential = buildRealModelsByCredentialMap({
      teamModels: [{ credential_id: 'c1', real_model: 'dall-e-3' }],
    })
    const rules = buildBatchRules(
      {
        ...DEFAULT_BATCH_FORM,
        layer: 'upstream' as const,
        allCredentials: false,
        allModels: false,
        credentialIds: ['c1'],
        modelNames: ['dall-e-3'],
        limit_usd: '',
        limit_tokens: '',
        limit_requests: '',
        limit_images: '',
      },
      { realModelsByCredential }
    )
    expect(rules).toBeNull()
  })
})
