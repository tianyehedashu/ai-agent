import { describe, expect, it, beforeEach, afterEach } from 'vitest'

import {
  deferReleaseUiOverlayLock,
  dismissOpenRadixLayers,
  releaseUiOverlayLock,
  teardownAllOverlayScopes,
  teardownOverlayScope,
} from '@/lib/ui-overlay'

describe('releaseUiOverlayLock', () => {
  beforeEach(() => {
    document.body.style.pointerEvents = 'none'
    document.body.setAttribute('data-scroll-locked', '')
    const guard = document.createElement('span')
    guard.setAttribute('data-radix-focus-guard', '')
    document.body.appendChild(guard)
  })

  afterEach(() => {
    document.body.style.removeProperty('pointer-events')
    document.body.removeAttribute('data-scroll-locked')
    document.querySelectorAll('[data-radix-focus-guard]').forEach((el) => {
      el.remove()
    })
  })

  it('clears body pointer-events and focus guards', () => {
    releaseUiOverlayLock()
    expect(document.body.style.pointerEvents).toBe('')
    expect(document.body.hasAttribute('data-scroll-locked')).toBe(false)
    expect(document.querySelectorAll('[data-radix-focus-guard]').length).toBe(0)
  })

  it('does not remove popper wrappers managed by React', () => {
    const wrapper = document.createElement('div')
    wrapper.setAttribute('data-radix-popper-content-wrapper', '')
    const closed = document.createElement('div')
    closed.setAttribute('data-state', 'closed')
    wrapper.appendChild(closed)
    document.body.appendChild(wrapper)

    releaseUiOverlayLock()
    expect(document.querySelector('[data-radix-popper-content-wrapper]')).not.toBeNull()
    wrapper.remove()
  })

  it('dispatches Escape then releases lock', () => {
    let escapeCount = 0
    const onKeyDown = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') escapeCount += 1
    }
    document.addEventListener('keydown', onKeyDown)
    dismissOpenRadixLayers()
    document.removeEventListener('keydown', onKeyDown)
    expect(escapeCount).toBe(1)
    expect(document.body.style.pointerEvents).toBe('')
  })

  it('deferReleaseUiOverlayLock runs after microtask', async () => {
    document.body.style.pointerEvents = 'none'
    deferReleaseUiOverlayLock()
    expect(document.body.style.pointerEvents).toBe('none')
    await Promise.resolve()
    expect(document.body.style.pointerEvents).toBe('')
  })
})

describe('teardownOverlayScope', () => {
  afterEach(() => {
    document.body.style.removeProperty('pointer-events')
    document.body.removeAttribute('data-scroll-locked')
  })

  it('does not mutate portal mount children', async () => {
    const mount = document.createElement('div')
    mount.setAttribute('data-overlay-portal-mount', '')
    const wrapper = document.createElement('div')
    wrapper.setAttribute('data-radix-popper-content-wrapper', '')
    mount.appendChild(wrapper)
    document.body.appendChild(mount)
    document.body.style.pointerEvents = 'none'

    teardownOverlayScope(mount)

    expect(mount.childNodes.length).toBe(1)
    await Promise.resolve()
    expect(document.body.style.pointerEvents).toBe('')
    mount.remove()
  })
})

describe('teardownAllOverlayScopes', () => {
  afterEach(() => {
    document.body.style.removeProperty('pointer-events')
    document.body.removeAttribute('data-scroll-locked')
  })

  it('releases body lock without dispatching Escape on route change', async () => {
    document.body.style.pointerEvents = 'none'
    let escapeCount = 0
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') escapeCount += 1
    })

    teardownAllOverlayScopes()

    expect(escapeCount).toBe(0)
    await Promise.resolve()
    expect(document.body.style.pointerEvents).toBe('')
  })
})
