import { describe, expect, it } from 'vitest'

import {
  builtinReasoningPlaygroundHint,
  resolveThinkingParamForModel,
  thinkingHintForModel,
  thinkingParamFromCapabilities,
  thinkingParamLabel,
} from './thinking-param'

describe('thinkingParamFromCapabilities', () => {
  it('读取 thinking_param 标签', () => {
    expect(thinkingParamFromCapabilities({ thinking_param: 'dashscope_enable_thinking' })).toBe(
      'dashscope_enable_thinking'
    )
  })

  it('仅有 supports_reasoning 时不猜测', () => {
    expect(thinkingParamFromCapabilities({ supports_reasoning: true })).toBeNull()
  })
})

describe('resolveThinkingParamForModel', () => {
  it('优先 API 标签', () => {
    expect(
      resolveThinkingParamForModel('gpt-4', {
        thinking_param: 'anthropic_extended',
      })
    ).toBe('anthropic_extended')
  })

  it('无 API 时按模型名推断 qwen3', () => {
    expect(resolveThinkingParamForModel('qwen3.6-max-preview')).toBe('dashscope_enable_thinking')
  })

  it('无 API 时按模型名推断 reasoner', () => {
    expect(resolveThinkingParamForModel('deepseek-reasoner')).toBe('builtin_reasoning')
  })

  it('无 API 时按模型名推断 deepseek v4', () => {
    expect(resolveThinkingParamForModel('deepseek-v4-pro-260425')).toBe('deepseek_v4_thinking')
  })
})

describe('thinkingParamLabel', () => {
  it('返回展示文案', () => {
    expect(thinkingParamLabel('dashscope_enable_thinking')).toBe('Qwen3 思考')
    expect(thinkingParamLabel('none')).toBeNull()
  })
})

describe('thinkingHintForModel', () => {
  it('普通模型提示勿传 enable_thinking', () => {
    const hint = thinkingHintForModel('gpt-4o-mini', 'openai')
    expect(hint).toContain('不支持')
  })

  it('Qwen3 提示 stream 与 extra_body', () => {
    const hint = thinkingHintForModel('qwen3-max', 'openai', {
      thinking_param: 'dashscope_enable_thinking',
    })
    expect(hint).toContain('enable_thinking')
    expect(hint).toContain('stream')
  })

  it('DeepSeek V4 提示 extra_body.thinking', () => {
    const hint = thinkingHintForModel('deepseek-v4-pro-260425', 'openai', {
      thinking_param: 'deepseek_v4_thinking',
    })
    expect(hint).toContain('extra_body.thinking')
    expect(hint).toContain('reasoning_content')
  })
})

describe('builtinReasoningPlaygroundHint', () => {
  it('仅 builtin 返回提示', () => {
    expect(builtinReasoningPlaygroundHint('builtin_reasoning')).toContain('reasoning_content')
    expect(builtinReasoningPlaygroundHint('none')).toBeNull()
  })
})
