import { describe, expect, it, vi } from 'vitest'

import {
  hrefToRouterPath,
  navigateFromSidebarOverlayGuard,
  registerSidebarNavigate,
} from './overlay-nav-bridge'

describe('hrefToRouterPath', () => {
  it('strips APP_ROOT basename from sidebar href', () => {
    expect(hrefToRouterPath('/ai-agent/video-tasks')).toBe('/video-tasks')
    expect(hrefToRouterPath('/ai-agent/settings')).toBe('/settings')
    expect(hrefToRouterPath('/ai-agent')).toBe('/')
  })

  it('passes through paths without basename prefix', () => {
    expect(hrefToRouterPath('/video-tasks')).toBe('/video-tasks')
  })
})

describe('navigateFromSidebarOverlayGuard', () => {
  it('navigates with router-relative path', () => {
    const navigate = vi.fn()
    registerSidebarNavigate(navigate)
    navigateFromSidebarOverlayGuard('/ai-agent/video-tasks')
    expect(navigate).toHaveBeenCalledWith('/video-tasks')
    registerSidebarNavigate(() => {})
  })
})
