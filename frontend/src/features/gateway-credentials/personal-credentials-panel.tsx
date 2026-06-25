/**
 * 个人凭据编辑弹窗（统一凭据工作区复用）。
 */

import { useCallback } from 'react'
import type React from 'react'

import { useMutation } from '@tanstack/react-query'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type PersonalGatewayModel,
  type ProviderCredential,
} from '@/api/gateway'
import type { GatewayBudget } from '@/api/gateway/budgets'
import { Button } from '@/components/ui/button'
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PersonalCredentialBudgetInline } from '@/features/gateway-budget/personal-credential-budget-inline'
import { useToast } from '@/hooks/use-toast'

import { CredentialEditFields } from './credential-edit-fields'
import { useCredentialEditForm } from './use-credential-edit-form'

export function PersonalCredentialEditDialog({
  cred,
  userId,
  personalBudgets,
  myModels,
  onClose,
  onSaved,
}: Readonly<{
  cred: ProviderCredential
  userId: string
  personalBudgets: readonly GatewayBudget[]
  myModels: readonly PersonalGatewayModel[]
  onClose: () => void
  onSaved: () => void
}>): React.ReactElement {
  const { toast } = useToast()
  const form = useCredentialEditForm({ cred, trackIsActive: true })

  const revealFn = useCallback(() => gatewayApi.revealMyCredential(cred.id), [cred.id])

  const updateMutation = useMutation({
    mutationFn: (body: GatewayCredentialUpdateBody) => gatewayApi.updateMyCredential(cred.id, body),
    onSuccess: () => {
      toast({ title: '凭据已更新' })
      onSaved()
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const handleSave = (): void => {
    if (!form.canSave) return
    updateMutation.mutate(form.buildUpdateBody())
  }

  return (
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>编辑凭据</DialogTitle>
        <DialogDescription>
          修改账号名称、启用状态或密钥；默认显示掩码，需要时可查看完整明文，或点「更换」输入新密钥后保存。
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-3 py-2">
        <CredentialEditFields
          cred={cred}
          idPrefix="my-cred"
          form={form}
          showActiveSwitch
          revealFn={revealFn}
        />
        {userId ? (
          <div className="rounded-md border bg-muted/20 p-3">
            <p className="mb-2 text-xs text-muted-foreground">平台预算</p>
            <PersonalCredentialBudgetInline
              credentialId={cred.id}
              userId={userId}
              budgets={[...personalBudgets]}
              myModels={[...myModels]}
            />
          </div>
        ) : null}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          取消
        </Button>
        <Button onClick={handleSave} disabled={updateMutation.isPending || !form.canSave}>
          {updateMutation.isPending ? '保存中…' : '保存'}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}
