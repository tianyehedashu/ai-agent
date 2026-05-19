import type React from 'react'

import type { MyPriceRow } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PricingBadge } from '@/features/gateway-pricing/pricing-badge'
import { CheckCircle2, CircleDashed, XCircle } from '@/lib/lucide-icons'
import type { DisplayCurrency } from '@/types/money'
import type { ModelTestStatus } from '@/types/user-model'

import {
  PLAYGROUND_MODE_LABELS,
  type ModelCandidate,
  type PlaygroundMode,
} from './playground-mode-filter'

export const CUSTOM_MODEL_SENTINEL = '__custom__'

export interface PlaygroundModelFieldProps {
  modelSelectId: string
  modelCustomId: string
  model: string
  customModel: boolean
  onModelChange: (value: string) => void
  onCustomModelChange: (custom: boolean, model?: string) => void
  teamCandidates: ModelCandidate[]
  personalCandidates: ModelCandidate[]
  filteredModels: ModelCandidate[]
  selectedCandidate: ModelCandidate | undefined
  priceByName: Map<string, MyPriceRow>
  currency: DisplayCurrency
  playgroundMode: PlaygroundMode
  modelsLoading: boolean
}

export function PlaygroundModelField({
  modelSelectId,
  modelCustomId,
  model,
  customModel,
  onModelChange,
  onCustomModelChange,
  teamCandidates,
  personalCandidates,
  filteredModels,
  selectedCandidate,
  priceByName,
  currency,
  playgroundMode,
  modelsLoading,
}: Readonly<PlaygroundModelFieldProps>): React.JSX.Element {
  const handleSelectChange = (value: string): void => {
    if (value === CUSTOM_MODEL_SENTINEL) {
      onCustomModelChange(true, '')
      return
    }
    onCustomModelChange(false, value)
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={customModel ? modelCustomId : modelSelectId}>
        模型 <span className="text-destructive">*</span>
      </Label>
      {customModel ? (
        <div className="flex gap-2">
          <Input
            id={modelCustomId}
            value={model}
            onChange={(e) => {
              onModelChange(e.target.value)
            }}
            placeholder="输入模型别名或虚拟路由名"
            autoComplete="off"
            spellCheck={false}
            className="font-mono"
            translate="no"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              onCustomModelChange(false, filteredModels[0]?.name ?? '')
            }}
            disabled={filteredModels.length === 0}
          >
            从列表选
          </Button>
        </div>
      ) : (
        <Select value={model} onValueChange={handleSelectChange}>
          <SelectTrigger id={modelSelectId} className="font-mono">
            <SelectValue
              placeholder={
                filteredModels.length === 0
                  ? `暂无支持「${PLAYGROUND_MODE_LABELS[playgroundMode]}」的模型`
                  : '选择模型'
              }
            />
          </SelectTrigger>
          <SelectContent>
            {teamCandidates.length > 0 ? (
              <SelectGroup>
                <SelectLabel>团队模型</SelectLabel>
                {teamCandidates.map((item) => (
                  <ModelOption
                    key={`team-${item.name}`}
                    item={item}
                    priceRow={priceByName.get(item.name)}
                    currency={currency}
                  />
                ))}
              </SelectGroup>
            ) : null}
            {personalCandidates.length > 0 ? (
              <SelectGroup>
                <SelectLabel>个人模型</SelectLabel>
                {personalCandidates.map((item) => (
                  <ModelOption
                    key={`personal-${item.name}`}
                    item={item}
                    priceRow={priceByName.get(item.name)}
                    currency={currency}
                  />
                ))}
              </SelectGroup>
            ) : null}
            <SelectItem value={CUSTOM_MODEL_SENTINEL}>
              <span className="text-muted-foreground">✏️ 手动输入…</span>
            </SelectItem>
          </SelectContent>
        </Select>
      )}
      <ModelHint
        loading={modelsLoading}
        selected={selectedCandidate}
        empty={filteredModels.length === 0}
        mode={playgroundMode}
      />
    </div>
  )
}

function ModelOption({
  item,
  priceRow,
  currency,
}: Readonly<{
  item: ModelCandidate
  priceRow?: MyPriceRow
  currency: DisplayCurrency
}>): React.JSX.Element {
  return (
    <SelectItem value={item.name}>
      <span className="flex w-full items-center justify-between gap-3">
        <span className="min-w-0 flex-1 truncate font-mono" translate="no">
          {item.name}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <PricingBadge row={priceRow} currency={currency} className="hidden sm:inline" />
          <ModelStatusBadge status={item.status} />
        </span>
      </span>
    </SelectItem>
  )
}

function ModelStatusBadge({ status }: Readonly<{ status: ModelTestStatus }>): React.JSX.Element {
  if (status === 'success') {
    return (
      <Badge variant="outline" className="gap-1 border-emerald-500/40 text-emerald-600">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        已通过
      </Badge>
    )
  }
  if (status === 'failed') {
    return (
      <Badge variant="outline" className="gap-1 border-destructive/40 text-destructive">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        失败
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <CircleDashed className="h-3 w-3" aria-hidden="true" />
      未测试
    </Badge>
  )
}

function ModelHint({
  loading,
  selected,
  empty,
  mode,
}: Readonly<{
  loading: boolean
  selected: ModelCandidate | undefined
  empty: boolean
  mode: PlaygroundMode
}>): React.JSX.Element | null {
  if (loading) {
    return <p className="text-xs text-muted-foreground">加载中…</p>
  }
  if (empty) {
    return (
      <p className="text-xs text-muted-foreground">
        暂无支持「{PLAYGROUND_MODE_LABELS[mode]}」的模型。
      </p>
    )
  }
  if (selected?.status === 'failed') {
    return <p className="text-xs text-destructive">连通性测试失败。</p>
  }
  return null
}
