/**
 * Playground Token 用量解析单测
 */

import { describe, expect, it } from 'vitest'

import { resolvePlaygroundTokenUsage } from './playground-token-usage'

describe('resolvePlaygroundTokenUsage', () => {
  it('仅有 totalTokens 时返回 total', () => {
    expect(resolvePlaygroundTokenUsage({ totalTokens: 1429 })).toEqual({ total: 1429 })
  })

  it('仅有 prompt + completion 时推导 total', () => {
    expect(resolvePlaygroundTokenUsage({ promptTokens: 1200, completionTokens: 229 })).toEqual({
      total: 1429,
      prompt: 1200,
      completion: 229,
    })
  })

  it('三者齐全且 total 与 sum 不一致时以 API total 为准', () => {
    expect(
      resolvePlaygroundTokenUsage({
        totalTokens: 1500,
        promptTokens: 1200,
        completionTokens: 229,
      })
    ).toEqual({ total: 1500, prompt: 1200, completion: 229 })
  })

  it('全无用量时返回 null', () => {
    expect(resolvePlaygroundTokenUsage({})).toBeNull()
  })

  it('仅有 prompt 或仅有 completion 且无 total 时返回 null', () => {
    expect(resolvePlaygroundTokenUsage({ promptTokens: 100 })).toBeNull()
    expect(resolvePlaygroundTokenUsage({ completionTokens: 50 })).toBeNull()
  })
})
