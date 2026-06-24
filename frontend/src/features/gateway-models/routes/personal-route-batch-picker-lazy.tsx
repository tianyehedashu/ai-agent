import { lazy, Suspense } from 'react'

import { Loader2 } from '@/lib/lucide-icons'

import { usePersonalRouteCallableModelsBatch } from './use-personal-route-callable-models'

const RouteModelBatchPickerDialog = lazy(async () => {
  const mod = await import('./route-model-batch-picker-dialog')
  return { default: mod.RouteModelBatchPickerDialog }
})

export interface PersonalRouteBatchPickerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  excludeNames: readonly string[]
  onConfirm: (routeRefs: string[]) => void
}

export function PersonalRouteBatchPicker({
  open,
  onOpenChange,
  excludeNames,
  onConfirm,
}: PersonalRouteBatchPickerProps): React.JSX.Element | null {
  const { items, isLoading } = usePersonalRouteCallableModelsBatch({ enabled: open })

  if (!open) {
    return null
  }

  return (
    <Suspense
      fallback={
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" />
        </div>
      }
    >
      <RouteModelBatchPickerDialog
        open={open}
        onOpenChange={onOpenChange}
        candidates={items}
        excludeNames={excludeNames}
        onConfirm={onConfirm}
        isLoadingCandidates={isLoading}
      />
    </Suspense>
  )
}
