import { describe, expect, it } from 'vitest'

import {
  capabilityEditorValuesFromModel,
  capabilityEditorValuesFromPersonalModel,
} from './model-capability-editor'

describe('capabilityEditorValuesFromPersonalModel', () => {
  it('preserves all allowed model types for vision row', () => {
    const values = capabilityEditorValuesFromPersonalModel({
      capability: 'chat',
      model_types: ['text', 'image'],
      selector_capabilities: { supports_vision: true },
    })
    expect(values.modelTypes).toEqual(['text', 'image'])
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
