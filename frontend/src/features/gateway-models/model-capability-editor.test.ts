import { describe, expect, it } from 'vitest'

import {
  capabilityEditorValuesFromModel,
  capabilityEditorValuesFromPersonalModel,
  modelCapabilityPatchFromEditor,
  type ModelCapabilityEditorValues,
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

  it('reads context_window from selector_capabilities when tags absent', () => {
    const values = capabilityEditorValuesFromPersonalModel({
      capability: 'chat',
      selector_capabilities: { context_window: 131072 },
    })
    expect(values.contextWindow).toBe('131072')
  })

  it('prefers tags context_window over selector_capabilities', () => {
    const values = capabilityEditorValuesFromPersonalModel({
      capability: 'chat',
      tags: { context_window: 262144 },
      selector_capabilities: { context_window: 131072 },
    })
    expect(values.contextWindow).toBe('262144')
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

  it('reads context_window from tags', () => {
    const values = capabilityEditorValuesFromModel({
      capability: 'chat',
      tags: { context_window: 262144 },
    })
    expect(values.contextWindow).toBe('262144')
  })

  it('defaults context_window to empty when absent or invalid', () => {
    expect(capabilityEditorValuesFromModel({ capability: 'chat' }).contextWindow).toBe('')
    expect(
      capabilityEditorValuesFromModel({ capability: 'chat', tags: { context_window: 0 } })
        .contextWindow
    ).toBe('')
  })
})

describe('modelCapabilityPatchFromEditor context_window', () => {
  const base: ModelCapabilityEditorValues = {
    capability: 'chat',
    modelTypes: ['text'],
    upstreamCallShape: '',
    thinkingParam: '',
    contextWindow: '',
  }

  it('emits context_window into tags when set to a positive integer', () => {
    const patch = modelCapabilityPatchFromEditor({ ...base, contextWindow: '262144' }, base)
    expect(patch.tags).toEqual({ context_window: 262144 })
  })

  it('emits null to clear context_window when cleared', () => {
    const patch = modelCapabilityPatchFromEditor(base, { ...base, contextWindow: '128000' })
    expect(patch.tags).toEqual({ context_window: null })
  })

  it('ignores invalid (non-positive) context_window input', () => {
    const patch = modelCapabilityPatchFromEditor({ ...base, contextWindow: 'abc' }, base)
    expect(patch.tags).toBeUndefined()
  })

  it('merges context_window with thinking_param changes without overwriting', () => {
    const patch = modelCapabilityPatchFromEditor(
      { ...base, contextWindow: '32000', thinkingParam: 'none' },
      base
    )
    expect(patch.tags).toEqual({
      thinking_param: 'none',
      thinking_param_locked: true,
      context_window: 32000,
    })
  })

  it('sets image gen tags when switching capability to image', () => {
    const patch = modelCapabilityPatchFromEditor(
      { ...base, capability: 'image', modelTypes: ['image_gen'] },
      base
    )
    expect(patch.capability).toBe('image')
    expect(patch.tags).toEqual({
      supports_image_gen: true,
      supports_txt2img: true,
    })
  })
})
