import { describe, expect, it } from 'vitest'

import { platformRoleLabel } from './platform-user-role-labels'

describe('platformRoleLabel', () => {
  it('returns Chinese label for known roles', () => {
    expect(platformRoleLabel('admin')).toBe('平台管理员')
    expect(platformRoleLabel('viewer')).toBe('只读账号')
  })

  it('returns raw role for unknown values', () => {
    expect(platformRoleLabel('custom')).toBe('custom')
  })
})
