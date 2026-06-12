import { useEffect, useRef } from 'react'

const HIGHLIGHT_CLASS = 'ring-2 ring-primary ring-offset-2 ring-offset-background'

export function useCredentialHighlight(credentialId: string | undefined): void {
  const highlightedRef = useRef<string | null>(null)

  useEffect(() => {
    const id = credentialId?.trim() ?? ''
    if (!id || highlightedRef.current === id) return

    const timer = window.setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-credential-id="${CSS.escape(id)}"]`)
      if (!el) return
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      el.classList.add(HIGHLIGHT_CLASS)
      highlightedRef.current = id
      window.setTimeout(() => {
        el.classList.remove(HIGHLIGHT_CLASS)
      }, 2000)
    }, 100)

    return () => {
      window.clearTimeout(timer)
    }
  }, [credentialId])
}
