import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'

import {
  formatSingleGatewayModelDeleteDescription,
  type GatewayModelDeleteScope,
} from '../model-delete-copy'

export interface GatewayModelDeleteConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  displayLabel: string
  scope?: GatewayModelDeleteScope
  title?: string
  pending?: boolean
  onConfirm: () => void
}

/** 单条模型删除确认（详情页与列表行删除共用 ConfirmAlertDialog 封装）。 */
export function GatewayModelDeleteConfirmDialog({
  open,
  onOpenChange,
  displayLabel,
  scope = 'team',
  title = '删除模型',
  pending = false,
  onConfirm,
}: GatewayModelDeleteConfirmDialogProps): React.JSX.Element {
  return (
    <ConfirmAlertDialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={formatSingleGatewayModelDeleteDescription(displayLabel, scope)}
      confirmLabel="确认删除"
      pending={pending}
      onConfirm={onConfirm}
    />
  )
}
