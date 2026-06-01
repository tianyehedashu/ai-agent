import { describe, expect, it } from 'vitest'

import {
  capabilityEditorValuesFromModel,
  capabilityEditorValuesFromPersonalModel,
  primaryPersonalModelType,
} from './model-capability-editor'

describe('primaryPersonalModelType', () => {
  it('collapses vision row to image', () => {
    expect(
      primaryPersonalModelType({
        capability: 'chat',
        model_types: ['text', 'image'],
        selector_capabilities: { supports_vision: true },
      })
    ).toBe('image')
  })

  it('keeps text-only row as text', () => {
    expect(
      primaryPersonalModelType({
        capability: 'chat',
        model_types: ['text'],
      })
    ).toBe('text')
  })
})

describe('capabilityEditorValuesFromPersonalModel', () => {
  it('initializes single-type editor for vision row', () => {
    const values = capabilityEditorValuesFromPersonalModel({
      capability: 'chat',
      model_types: ['text', 'image'],
      selector_capabilities: { supports_vision: true },
    })
    expect(values.modelTypes).toEqual(['image'])
    expect(values.capability).toBe('chat')
  })
})

describe('capabilityEditorValuesFromModel', () => {
  it('separates editable and legacy model types for chat rows', () => {
    const values = capabilityEditorValuesFromModel({
      capability: 'chat',
      model_types: ['text', 'image', 'image_gen'],
    })
    expect(values.modelTypes).toEqual(['text', 'image'])
    expect(values.legacyModelTypes).toEqual(['image_gen'])
  })
})
