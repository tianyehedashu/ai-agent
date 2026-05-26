import type React from 'react'

import type { ProviderCredential } from '@/api/gateway/credentials'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  credentialDeleteDescription,
  type CredentialDeleteVariant,
} from '@/features/gateway-credentials/credential-delete-descriptions'

interface CredentialDeleteConfirmDialogProps {
  credential: ProviderCredential | null
  isPending: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  variant?: CredentialDeleteVariant
}

export function CredentialDeleteConfirmDialog({
  credential,
  isPending,
  onOpenChange,
  onConfirm,
  variant = 'managed',
}: CredentialDeleteConfirmDialogProps): React.JSX.Element {
  return (
    <AlertDialog open={credential !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除凭据</AlertDialogTitle>
          <AlertDialogDescription>
            {credential ? credentialDeleteDescription(credential, variant) : ''}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>取消</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={isPending || credential === null}
            onClick={onConfirm}
          >
            {isPending ? '删除中…' : '删除'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
