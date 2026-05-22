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

const DESTRUCTIVE_ACTION_CLASS =
  'bg-destructive text-destructive-foreground hover:bg-destructive/90'

export interface ConfirmAlertDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  descriptionClassName?: string
  confirmLabel?: string
  cancelLabel?: string
  pending?: boolean
  destructive?: boolean
  onConfirm: () => void
}

/** 危险操作二次确认（替代 window.confirm） */
export function ConfirmAlertDialog({
  open,
  onOpenChange,
  title,
  description,
  descriptionClassName,
  confirmLabel = '确认',
  cancelLabel = '取消',
  pending = false,
  destructive = true,
  onConfirm,
}: ConfirmAlertDialogProps): React.JSX.Element {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription className={descriptionClassName}>
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            className={destructive ? DESTRUCTIVE_ACTION_CLASS : undefined}
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? `${confirmLabel}中…` : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
