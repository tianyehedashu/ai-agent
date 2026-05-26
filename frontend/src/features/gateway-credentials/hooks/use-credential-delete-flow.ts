/**
 * 凭据删除确认弹窗状态与稳定回调（workspace 复用）。
 */

import { useCallback, useRef, useState } from 'react'

import type { ProviderCredential } from '@/api/gateway/credentials'

import { credentialDetailTeamId } from '../credential-permissions'

import type { GatewayCredentialMutations } from './use-gateway-credential-mutations'

export interface CredentialDeleteFlow {
  credentialPendingDelete: ProviderCredential | null
  isDeletePending: boolean
  handleDeleteCredential: (credential: ProviderCredential) => void
  handleDeleteDialogOpenChange: (open: boolean) => void
  handleDeleteConfirm: () => void
}

export function useCredentialDeleteFlow(
  mutations: GatewayCredentialMutations,
  routeTeamId: string
): CredentialDeleteFlow {
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const pendingRef = useRef<ProviderCredential | null>(null)
  pendingRef.current = credentialPendingDelete

  const handleDeleteCredential = useCallback((credential: ProviderCredential) => {
    setCredentialPendingDelete(credential)
  }, [])

  const handleDeleteDialogOpenChange = useCallback((open: boolean) => {
    if (!open) {
      setCredentialPendingDelete(null)
    }
  }, [])

  const handleDeleteConfirm = useCallback(() => {
    const pending = pendingRef.current
    if (pending === null) return
    mutations.deleteMutation.mutate(
      {
        id: pending.id,
        credentialTeamId: credentialDetailTeamId(pending, routeTeamId),
      },
      {
        onSuccess: () => {
          setCredentialPendingDelete(null)
        },
      }
    )
  }, [mutations.deleteMutation, routeTeamId])

  return {
    credentialPendingDelete,
    isDeletePending: mutations.deleteMutation.isPending,
    handleDeleteCredential,
    handleDeleteDialogOpenChange,
    handleDeleteConfirm,
  }
}
