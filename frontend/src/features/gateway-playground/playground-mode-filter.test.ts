import { describe, expect, it } from 'vitest'

import {
  filterModelsByMode,
  filterPlaygroundRouteCandidates,
  type ModelCandidate,
} from './playground-mode-filter'

const chatModel: ModelCandidate = {
  name: 'chat-model',
  scope: 'team',
  status: 'success',
  capability: 'chat',
  provider: 'openai',
  selector_capabilities: {},
  model_types: ['text'],
}

const visionModel: ModelCandidate = {
  name: 'vision-model',
  scope: 'team',
  status: 'success',
  capability: 'chat',
  provider: 'openai',
  selector_capabilities: { supports_vision: true },
  model_types: ['text', 'image'],
}

describe('filterPlaygroundRouteCandidates', () => {
  const routes = [
    {
      enabled: true,
      virtual_model: 'route-a',
      primary_models: ['chat-model', 'vision-model'],
    },
    {
      enabled: true,
      virtual_model: 'route-b',
      primary_models: ['chat-model'],
    },
    {
      enabled: false,
      virtual_model: 'route-off',
      primary_models: ['chat-model'],
    },
  ]

  it('filters disabled routes and sorts by name', () => {
    const result = filterPlaygroundRouteCandidates(routes, '', [chatModel, visionModel], 'chat')
    expect(result.map((r) => r.name)).toEqual(['route-a', 'route-b'])
  })

  it('requires all primary models when credential filter is active', () => {
    const result = filterPlaygroundRouteCandidates(routes, 'cred-team', [chatModel], 'chat')
    expect(result.map((r) => r.name)).toEqual(['route-b'])
  })

  it('filters routes by playground mode capabilities', () => {
    const result = filterPlaygroundRouteCandidates(routes, '', [chatModel, visionModel], 'vision')
    expect(result.map((r) => r.name)).toEqual(['route-a'])
  })
})

describe('filterModelsByMode', () => {
  const chatModel: ModelCandidate = {
    name: 'chat-only',
    scope: 'team',
    status: 'success',
    capability: 'chat',
    provider: 'openai',
    selector_capabilities: {},
    model_types: ['text'],
  }

  const visionModel: ModelCandidate = {
    name: 'vision',
    scope: 'team',
    status: 'success',
    capability: 'chat',
    provider: 'openai',
    selector_capabilities: { supports_vision: true },
    model_types: ['text', 'image'],
  }

  it('uses model_types for vision mode without relying on supports_vision alone', () => {
    const result = filterModelsByMode([chatModel, visionModel], 'vision')
    expect(result.map((m) => m.name)).toEqual(['vision'])
  })

  it('filters chat mode to text registry type', () => {
    const result = filterModelsByMode([chatModel, visionModel], 'chat')
    expect(result.map((m) => m.name)).toEqual(['chat-only', 'vision'])
  })
})
