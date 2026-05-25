import type { GatewayModelBatchDeleteFailureItem } from '@/api/gateway'
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
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface ModelBatchDeleteConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  pending?: boolean
  confirmLabel?: string
  onConfirm: () => void
}

export function ModelBatchDeleteConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  pending = false,
  confirmLabel = '确认删除',
  onConfirm,
}: ModelBatchDeleteConfirmDialogProps): React.JSX.Element {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-wrap">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>取消</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? '删除中…' : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

interface ModelBatchDeleteFailedDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  failedItems: GatewayModelBatchDeleteFailureItem[]
  title?: string
  description?: string
}

export function ModelBatchDeleteFailedDialog({
  open,
  onOpenChange,
  failedItems,
  title = '部分模型未能删除',
  description = '以下条目未删除成功，其余已处理。',
}: ModelBatchDeleteFailedDialogProps): React.JSX.Element {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <ul className="max-h-60 space-y-2 overflow-y-auto text-sm">
          {failedItems.map((item) => (
            <li key={item.id} className="rounded-md border px-3 py-2">
              <p className="font-mono text-xs text-muted-foreground">{item.id}</p>
              <p className="mt-1 text-destructive">{item.message}</p>
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button
            type="button"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
