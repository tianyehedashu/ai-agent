import { describe, expect, it } from 'vitest'

import { shouldInvalidateGlobalSession } from './session-invalidation'

describe('shouldInvalidateGlobalSession', () => {
  it('403 永不触发全局登出', () => {
    expect(shouldInvalidateGlobalSession(403, { detail: 'Permission denied' }, true)).toBe(false)
  })

  it('无 token 的 401 不触发', () => {
    expect(shouldInvalidateGlobalSession(401, { detail: 'Authentication required' }, false)).toBe(
      false
    )
  })

  it('Authentication required 不触发（匿名访问受保护资源）', () => {
    expect(shouldInvalidateGlobalSession(401, { detail: 'Authentication required' }, true)).toBe(
      false
    )
  })

  it('权限类 detail（误标 401）不触发', () => {
    expect(shouldInvalidateGlobalSession(401, { detail: 'Permission denied: admin' }, true)).toBe(
      false
    )
    expect(shouldInvalidateGlobalSession(401, { detail: 'Required role: admin' }, true)).toBe(false)
  })

  it('Invalid or expired token 触发', () => {
    expect(shouldInvalidateGlobalSession(401, { detail: 'Invalid or expired token' }, true)).toBe(
      true
    )
  })
})
