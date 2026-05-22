import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  hasOpenRadixOverlay,
  installOverlayPointerGuard,
  registerSidebarNavigate,
  releaseStuckBodyPointerEvents,
} from './overlay-pointer-guard'

describe('hasOpenRadixOverlay', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('detects open listbox', () => {
    const listbox = document.createElement('div')
    listbox.setAttribute('role', 'listbox')
    listbox.setAttribute('data-state', 'open')
    document.body.appendChild(listbox)
    expect(hasOpenRadixOverlay()).toBe(true)
  })
})

describe('releaseStuckBodyPointerEvents', () => {
  afterEach(() => {
    document.body.style.removeProperty('pointer-events')
    document.body.innerHTML = ''
  })

  it('clears body pointer-events when no modal is open', () => {
    document.body.style.pointerEvents = 'none'
    releaseStuckBodyPointerEvents()
    expect(document.body.style.pointerEvents).toBe('')
  })

  it('does not clear when a dialog is open', () => {
    document.body.style.pointerEvents = 'none'
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    dialog.setAttribute('data-state', 'open')
    document.body.appendChild(dialog)

    releaseStuckBodyPointerEvents()
    expect(document.body.style.pointerEvents).toBe('none')
  })

  it('does not clear while a radix overlay is still open', () => {
    document.body.style.pointerEvents = 'none'
    const listbox = document.createElement('div')
    listbox.setAttribute('role', 'listbox')
    listbox.setAttribute('data-state', 'open')
    document.body.appendChild(listbox)

    releaseStuckBodyPointerEvents()
    expect(document.body.style.pointerEvents).toBe('none')
  })
})

describe('installOverlayPointerGuard', () => {
  afterEach(() => {
    document.body.style.removeProperty('pointer-events')
    document.body.innerHTML = ''
  })

  it('releases stuck pointer-events on pointerdown', () => {
    const cleanup = installOverlayPointerGuard()
    document.body.style.pointerEvents = 'none'

    document.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
    expect(document.body.style.pointerEvents).toBe('')

    cleanup()
  })

  it('dismisses open overlay when clicking sidebar nav link', () => {
    const cleanup = installOverlayPointerGuard()
    const navigate = vi.fn()
    registerSidebarNavigate(navigate)

    const sidebar = document.createElement('aside')
    sidebar.setAttribute('data-app-sidebar', '')
    const link = document.createElement('a')
    link.setAttribute('href', '/ai-agent/video-tasks')
    sidebar.appendChild(link)
    document.body.appendChild(sidebar)

    const listbox = document.createElement('div')
    listbox.setAttribute('role', 'listbox')
    listbox.setAttribute('data-state', 'open')
    document.body.appendChild(listbox)

    link.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
    expect(navigate).toHaveBeenCalledWith('/video-tasks')

    cleanup()
    registerSidebarNavigate(() => {})
  })
})
