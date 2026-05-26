import type { GatewayModel } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  resolveThinkingParamForModel,
  thinkingParamLabel,
} from '@/features/gateway-shared/thinking-param'
import { Info } from '@/lib/lucide-icons'
import { MODEL_TYPE_LABELS } from '@/types/user-model'

import { capabilityLabel } from '../constants'

export function ModelCapabilityBadges({
  model,
  compact = false,
}: {
  model: GatewayModel
  compact?: boolean
}): React.JSX.Element {
  const types = model.model_types ?? []
  const sc = model.selector_capabilities
  const thinkingParam = resolveThinkingParamForModel(model.name, sc)
  const thinkingLabel = thinkingParamLabel(thinkingParam)
  const extraTags: string[] = []
  if (thinkingLabel) {
    extraTags.push(thinkingLabel)
  } else if (sc?.supports_reasoning === true) {
    extraTags.push('reasoning')
  }
  if (sc?.supports_json_mode === false) extraTags.push('无 JSON 模式')

  return (
    <div className={compact ? 'flex flex-wrap items-center gap-1' : 'flex flex-col gap-1.5'}>
      <div className="flex items-center gap-1">
        <Badge variant="outline" className="text-xs" title={model.capability}>
          {capabilityLabel(model.capability)}
        </Badge>
        {!compact ? (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                  aria-label="能力说明"
                >
                  <Info className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-xs text-xs leading-relaxed">
                模型能力决定 OpenAI 兼容 HTTP 入口；下方芯片为产品特性标签。
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}
      </div>
      {(types.length > 0 || extraTags.length > 0) && (
        <div className="flex flex-wrap gap-1">
          {types.map((t) => (
            <Badge key={t} variant="secondary" className="text-xs font-normal">
              {MODEL_TYPE_LABELS[t] ?? t}
            </Badge>
          ))}
          {extraTags.map((t) => (
            <Badge key={t} variant="outline" className="text-xs font-normal">
              {t}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
