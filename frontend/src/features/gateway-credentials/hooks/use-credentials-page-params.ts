import { useCallback, useEffect } from 'react'

import { useSearchParams } from 'react-router-dom'

export type CredentialsPageView = 'create' | 'edit'

export interface UseCredentialsPageParamsOptions {
  onBeforeTabChange?: () => void
}

export interface UseCredentialsPageParamsResult {
  credentialId: string
  view: CredentialsPageView | null
  searchParams: URLSearchParams
  setSearchParams: ReturnType<typeof useSearchParams>[1]
  clearCredentialHighlight: () => void
  setView: (next: CredentialsPageView | null) => void
}

export function parseCredentialsPageView(raw: string | null): CredentialsPageView | null {
  if (raw === 'create' || raw === 'edit') return raw
  return null
}

export function useCredentialsPageParams(
  options: UseCredentialsPageParamsOptions = {}
): UseCredentialsPageParamsResult {
  const { onBeforeTabChange } = options
  const [searchParams, setSearchParams] = useSearchParams()

  useEffect(() => {
    if (!searchParams.get('tab')) return
    onBeforeTabChange?.()
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('tab')
        return next
      },
      { replace: true }
    )
  }, [onBeforeTabChange, searchParams, setSearchParams])

  const credentialId = searchParams.get('credentialId') ?? ''
  const view = parseCredentialsPageView(searchParams.get('view'))

  const clearCredentialHighlight = useCallback((): void => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('credentialId')
        return next
      },
      { replace: true }
    )
  }, [setSearchParams])

  const setView = useCallback(
    (next: CredentialsPageView | null): void => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev)
          if (next === null) {
            params.delete('view')
          } else {
            params.set('view', next)
          }
          return params
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  return {
    credentialId,
    view,
    searchParams,
    setSearchParams,
    clearCredentialHighlight,
    setView,
  }
}
