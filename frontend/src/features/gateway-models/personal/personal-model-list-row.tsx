import { memo } from 'react'

import { Link } from 'react-router-dom'

import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { channelLabel } from '@/features/gateway-models/utils'
import { Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { ModelTestStatus, ModelType } from '@/types/user-model'
import { MODEL_TYPE_LABELS } from '@/types/user-model'

interface PersonalModelListRowProps {
  id: string
  displayName: string
  provider: string
  virtualName: string
  modelId: string
  modelTypes: ModelType[]
  lastTestStatus: ModelTestStatus
  lastTestedAt: string | null
  lastTestReason: string | null
  detailHref: string
  selected: boolean
  onSelectChange: (id: string, selected: boolean) => void
  onDelete?: (id: string) => void
  onPreloadNavigate?: () => void
}

export const PersonalModelListRow = memo(function PersonalModelListRow({
  id,
  displayName,
  provider,
  virtualName,
  modelId,
  modelTypes,
  lastTestStatus,
  lastTestedAt,
  lastTestReason,
  detailHref,
  selected,
  onSelectChange,
  onDelete,
  onPreloadNavigate,
}: PersonalModelListRowProps): React.JSX.Element {
  return (
    <li
      data-connectivity-model-id={id}
      className="[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]"
    >
      <div className="flex items-stretch">
        <div className="flex items-center px-3">
          <Checkbox
            checked={selected}
            onCheckedChange={(checked) => {
              onSelectChange(id, checked === true)
            }}
            aria-label={`选择 ${displayName}`}
            onClick={(e) => {
              e.stopPropagation()
            }}
          />
        </div>
        <Link
          to={detailHref}
          className={cn(
            'block min-w-0 flex-1 px-2 py-3 transition-colors hover:bg-muted/40',
            selected && 'bg-muted/20'
          )}
          onMouseEnter={onPreloadNavigate}
          onFocus={onPreloadNavigate}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium">{displayName}</span>
            <ModelStatusBadge
              status={lastTestStatus}
              testedAt={lastTestedAt}
              reason={lastTestReason}
              compact
            />
            <Badge variant="outline" className="shrink-0 text-xs">
              {channelLabel(provider)}
            </Badge>
            {modelTypes.map((t) => (
              <Badge key={t} variant="secondary" className="shrink-0 text-xs">
                {MODEL_TYPE_LABELS[t]}
              </Badge>
            ))}
          </div>
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">{virtualName}</p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{modelId}</p>
        </Link>
        {onDelete ? (
          <div className="flex items-center px-2">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
              aria-label={`删除 ${displayName}`}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onDelete(id)
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ) : null}
      </div>
    </li>
  )
})
