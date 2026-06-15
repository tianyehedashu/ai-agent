import { Button } from '@/components/ui/button'
import { Loader2, Trash2, X } from '@/lib/lucide-icons'

export interface QuotaFormShellProps {
  icon: React.ReactNode
  title: string
  pending: boolean
  deletePending: boolean
  editingBudgetId: string | null
  onCancel: () => void
  onDelete?: (budgetId: string) => void
  onSubmit: () => void
  children: React.ReactNode
  borderClass: string
}

export function QuotaFormShell({
  icon,
  title,
  pending,
  deletePending,
  editingBudgetId,
  onCancel,
  onDelete,
  onSubmit,
  children,
  borderClass,
}: QuotaFormShellProps): React.JSX.Element {
  const isEditing = editingBudgetId !== null

  return (
    <div className={`space-y-3 rounded-md border p-3 ${borderClass}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {icon}
          <p className="text-sm font-medium">{title}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onCancel}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      {children}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        {isEditing && onDelete ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-destructive hover:text-destructive"
            disabled={deletePending || pending}
            onClick={() => {
              onDelete(editingBudgetId)
            }}
          >
            {deletePending ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="mr-1 h-3 w-3" />
            )}
            删除
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={onCancel}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-7 text-xs"
            disabled={pending}
            onClick={onSubmit}
          >
            {pending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            保存
          </Button>
        </div>
      </div>
    </div>
  )
}
