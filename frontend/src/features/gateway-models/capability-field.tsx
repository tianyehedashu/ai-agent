/**
 * 团队模型 capability 选择：标签与下拉均为中文，提交值仍为后端枚举。
 */

import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { CAPABILITIES, CAPABILITY_LABELS } from '@/features/gateway-models/constants'
import { Info } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

export interface CapabilityFieldProps {
  id: string
  value: string
  onValueChange: (value: string) => void
  /** 注册表单等场景显示说明图标 */
  showTooltip?: boolean
  /** 批量导入等场景显示一行辅助说明 */
  showHint?: boolean
  className?: string
}

export function CapabilityField({
  id,
  value,
  onValueChange,
  showTooltip = false,
  showHint = false,
  className,
}: CapabilityFieldProps): React.JSX.Element {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <div className="flex items-center gap-1">
        <Label htmlFor={id}>模型能力</Label>
        {showTooltip ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" aria-label="模型能力说明">
                <Info className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-xs">
              决定模型走哪类 OpenAI 兼容路由（如对话、图片、Embedding）；下方特性标签与此不同。
            </TooltipContent>
          </Tooltip>
        ) : null}
      </div>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger id={id}>
          <SelectValue placeholder="选择模型能力" />
        </SelectTrigger>
        <SelectContent>
          {CAPABILITIES.map((item) => (
            <SelectItem key={item} value={item}>
              {CAPABILITY_LABELS[item]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {showHint ? (
        <p className="text-xs text-muted-foreground">
          决定这批模型用于哪类调用路由；对话模型通常选「聊天 / 文本生成」。
        </p>
      ) : null}
    </div>
  )
}
