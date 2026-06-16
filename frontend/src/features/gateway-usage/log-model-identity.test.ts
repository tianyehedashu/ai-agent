import { describe, expect, it } from 'vitest'

import {
  buildLogModelCatalogIndex,
  resolveLogModelIdentity,
} from '@/features/gateway-usage/log-model-identity'

describe('resolveLogModelIdentity', () => {
  const catalog = buildLogModelCatalogIndex([
    {
      id: 'model-1',
      name: 'Doubao-Lite-online',
      real_model: 'ep-abc',
      tags: { display_name: '豆包 Lite 线上' },
    },
  ])

  it('maps persisted fields and resolves display name by gateway model id', () => {
    const identity = resolveLogModelIdentity(
      {
        route_name: 'dobao-route',
        real_model: 'ep-abc',
        deployment_gateway_model_id: 'model-1',
        deployment_model_name: 'Doubao-Lite-online',
      },
      catalog
    )
    expect(identity.invokeName).toBe('dobao-route')
    expect(identity.upstreamName).toBe('ep-abc')
    expect(identity.displayName).toBe('豆包 Lite 线上')
    expect(identity.registrationName).toBe('Doubao-Lite-online')
    expect(identity.gatewayModelId).toBe('model-1')
  })

  it('omits display name when it equals invoke name', () => {
    const identity = resolveLogModelIdentity(
      {
        route_name: '豆包 Lite 线上',
        real_model: 'ep-abc',
        deployment_gateway_model_id: 'model-1',
        deployment_model_name: 'Doubao-Lite-online',
      },
      catalog
    )
    expect(identity.displayName).toBeNull()
  })

  it('falls back to log fields without catalog', () => {
    const identity = resolveLogModelIdentity({
      route_name: 'client-model',
      real_model: 'volcengine/foo',
      deployment_gateway_model_id: null,
      deployment_model_name: null,
    })
    expect(identity.invokeName).toBe('client-model')
    expect(identity.upstreamName).toBe('volcengine/foo')
    expect(identity.displayName).toBeNull()
  })
})
