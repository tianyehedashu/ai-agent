import { describe, expect, it } from 'vitest'

import { effectiveCapabilities } from './capabilities'
import { TEAM_GROUPED_CAPABILITIES } from './list-presets'

describe('effectiveCapabilities · 创建者私有贡献者', () => {
  it('admin (canWrite) 保留全部能力', () => {
    const caps = effectiveCapabilities(TEAM_GROUPED_CAPABILITIES, {
      canWrite: true,
      canContribute: true,
      isPlatformAdmin: false,
    })
    expect(caps.rowToggleEnabled).toBe(true)
    expect(caps.rowDelete).toBe(true)
    expect(caps.batchSelect).toBe(true)
    expect(caps.deleteAllFiltered).toBe(true)
  })

  it('member (canContribute, 非 admin) 保留行级/勾选能力，但关闭跨筛选批量删除', () => {
    const caps = effectiveCapabilities(TEAM_GROUPED_CAPABILITIES, {
      canWrite: false,
      canContribute: true,
      isPlatformAdmin: false,
    })
    // 行级与勾选能力开启——具体归属由 Row callback 裁剪到自有模型
    expect(caps.rowToggleEnabled).toBe(true)
    expect(caps.rowDelete).toBe(true)
    expect(caps.batchSelect).toBe(true)
    expect(caps.batchDelete).toBe(true)
    expect(caps.batchTest).toBe(true)
    expect(caps.batchResync).toBe(true)
    expect(caps.deleteFailed).toBe(true)
    // 跨「当前筛选」全量删除会触及他人模型——仅 admin
    expect(caps.deleteAllFiltered).toBe(false)
  })

  it('只读访客 (既非 write 也非 contribute) 关闭全部写能力', () => {
    const caps = effectiveCapabilities(TEAM_GROUPED_CAPABILITIES, {
      canWrite: false,
      canContribute: false,
      isPlatformAdmin: false,
    })
    expect(caps.rowToggleEnabled).toBe(false)
    expect(caps.rowDelete).toBe(false)
    expect(caps.batchSelect).toBe(false)
    expect(caps.batchDelete).toBe(false)
    expect(caps.deleteAllFiltered).toBe(false)
  })

  it('未显式提供 canContribute 时回退到 canWrite（兼容仅管理员场景）', () => {
    const adminOnly = effectiveCapabilities(TEAM_GROUPED_CAPABILITIES, {
      canWrite: true,
      isPlatformAdmin: false,
    })
    expect(adminOnly.rowToggleEnabled).toBe(true)
    expect(adminOnly.deleteAllFiltered).toBe(true)

    const readOnly = effectiveCapabilities(TEAM_GROUPED_CAPABILITIES, {
      canWrite: false,
      isPlatformAdmin: false,
    })
    expect(readOnly.rowToggleEnabled).toBe(false)
    expect(readOnly.deleteAllFiltered).toBe(false)
  })
})
