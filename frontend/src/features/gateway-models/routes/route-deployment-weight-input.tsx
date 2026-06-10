import { useCallback, useEffect, useState } from 'react'

import { Input } from '@/components/ui/input'
import { parseDeploymentWeight } from '@/features/gateway-models/routes/routing-strategy-utils'

interface RouteDeploymentWeightInputProps {
  modelName: string
  /** 当前展示值（调用方可传草稿值，失焦/Enter 时经 onChange 回传） */
  value: number
  disabled?: boolean
  onChange: (modelName: string, weight: number) => void
}

/** deployment 权重行内编辑框。仅按权重路由（weighted-pick）时展示。 */
export function RouteDeploymentWeightInput({
  modelName,
  value,
  disabled = false,
  onChange,
}: RouteDeploymentWeightInputProps): React.JSX.Element {
  const [draft, setDraft] = useState<string>(String(value))

  useEffect(() => {
    setDraft(String(value))
  }, [value])

  const commit = useCallback((): void => {
    if (disabled) return
    const next = parseDeploymentWeight(draft)
    if (next === null) {
      setDraft(String(value))
      return
    }
    if (next === value) return
    onChange(modelName, next)
  }, [draft, modelName, value, onChange, disabled])

  return (
    <span className="flex shrink-0 items-center gap-1">
      <span className="text-[10px] uppercase text-muted-foreground">w</span>
      <Input
        type="text"
        inputMode="numeric"
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value)
        }}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            ;(e.currentTarget as HTMLInputElement).blur()
          }
        }}
        aria-label={`权重 ${modelName}`}
        className="h-7 w-14 px-1 text-center tabular-nums"
      />
    </span>
  )
}
