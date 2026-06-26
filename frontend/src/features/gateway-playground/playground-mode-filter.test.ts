import { describe, expect, it } from 'vitest'

import {
  ensurePlaygroundSelectionModelLoaded,
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

  it('shows routes before all primary models are paginated in when no credential filter', () => {
    const result = filterPlaygroundRouteCandidates(routes, '', [], 'chat')
    expect(result.map((r) => r.name)).toEqual(['route-a', 'route-b'])
  })

  it('requires all primary models in loaded candidates when credential filter is active', () => {
    const result = filterPlaygroundRouteCandidates(routes, 'cred-team', [chatModel], 'chat')
    expect(result.map((r) => r.name)).toEqual(['route-b'])
  })

  it('filters routes by playground mode capabilities', () => {
    const result = filterPlaygroundRouteCandidates(routes, '', [chatModel, visionModel], 'vision')
    expect(result.map((r) => r.name)).toEqual(['route-a'])
  })

  it('keeps shared routes when team credential filter omits owner primary models', () => {
    const sharedRoutes = [
      {
        enabled: true,
        virtual_model: 'shared-alias',
        primary_models: ['owner-only-model'],
        isSharedRoute: true,
        ownerDisplay: 'Alice',
      },
    ]
    const result = filterPlaygroundRouteCandidates(sharedRoutes, 'cred-team', [chatModel], 'chat')
    expect(result).toEqual([
      {
        name: 'shared-alias',
        primaryModels: ['owner-only-model'],
        kind: 'shared',
        ownerDisplay: 'Alice',
      },
    ])
  })
})

describe('ensurePlaygroundSelectionModelLoaded', () => {
  it('loads primary models when selection is a virtual route', () => {
    const loaded: string[] = []
    ensurePlaygroundSelectionModelLoaded(
      'route-a',
      [{ name: 'route-a', primaryModels: ['chat-model', 'vision-model'] }],
      (name) => {
        loaded.push(name)
      }
    )
    expect(loaded).toEqual(['chat-model', 'vision-model'])
  })

  it('loads primary models from raw routes when filtered candidates omit the route', () => {
    const loaded: string[] = []
    ensurePlaygroundSelectionModelLoaded(
      'route-a',
      [],
      (name) => {
        loaded.push(name)
      },
      [{ virtual_model: 'route-a', primary_models: ['chat-model', 'vision-model'] }]
    )
    expect(loaded).toEqual(['chat-model', 'vision-model'])
  })

  it('loads model name directly when selection is not a route', () => {
    const loaded: string[] = []
    ensurePlaygroundSelectionModelLoaded('chat-model', [], (name) => {
      loaded.push(name)
    })
    expect(loaded).toEqual(['chat-model'])
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
