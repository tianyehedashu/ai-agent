import { describe, expect, it } from 'vitest'

import {
  needsVolcengineImageEndpointSetup,
  parseVolcengineImageEndpointId,
} from './volcengine-image-readiness'

describe('parseVolcengineImageEndpointId', () => {
  it('reads trimmed ep id from extra', () => {
    expect(parseVolcengineImageEndpointId({ image_endpoint_id: ' ep-m-1 ' })).toBe('ep-m-1')
  })

  it('returns null when missing or blank', () => {
    expect(parseVolcengineImageEndpointId({})).toBeNull()
    expect(parseVolcengineImageEndpointId({ image_endpoint_id: '  ' })).toBeNull()
    expect(parseVolcengineImageEndpointId(null)).toBeNull()
  })
})

describe('needsVolcengineImageEndpointSetup', () => {
  it('is true only for volcengine image without endpoint', () => {
    expect(needsVolcengineImageEndpointSetup('volcengine', 'image', {})).toBe(true)
    expect(
      needsVolcengineImageEndpointSetup('volcengine', 'image', {
        image_endpoint_id: 'ep-m-1',
      })
    ).toBe(false)
    expect(needsVolcengineImageEndpointSetup('volcengine', 'chat', {})).toBe(false)
    expect(needsVolcengineImageEndpointSetup('openai', 'image', {})).toBe(false)
  })
})
