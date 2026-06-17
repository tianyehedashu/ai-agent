import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import {
  applyQuotaWindowPreset,
  QUOTA_WINDOW_PRESETS,
  resolveQuotaWindowPreset,
  type QuotaWindowPresetValue,
} from './quota-window-presets'

import type { QuotaBatchFormValues } from './quota-batch-form'

export interface QuotaUsdLimitFieldProps {
  id?: string
  label?: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  placeholder?: string
  inputClassName?: string
  labelClassName?: string
}

export function QuotaUsdLimitField({
  id,
  label = '费用上限 (USD)',
  value,
  onChange,
  disabled = false,
  placeholder = '例如 100',
  inputClassName = 'h-9 text-base tabular-nums',
  labelClassName = 'text-xs',
}: QuotaUsdLimitFieldProps): React.JSX.Element {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className={labelClassName}>
        {label}
      </Label>
      <Input
        id={id}
        className={inputClassName}
        inputMode="decimal"
        placeholder={placeholder}
        value={value}
        disabled={disabled}
        onChange={(e) => {
          onChange(e.target.value)
        }}
      />
    </div>
  )
}

export interface QuotaTokenLimitFieldProps {
  id?: string
  mode: 'wan' | 'raw'
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  inputClassName?: string
  labelClassName?: string
}

export function QuotaTokenLimitField({
  id,
  mode,
  value,
  onChange,
  disabled = false,
  inputClassName,
  labelClassName = 'text-xs text-muted-foreground',
}: QuotaTokenLimitFieldProps): React.JSX.Element {
  const label = mode === 'wan' ? '或 Token 上限（万，可选）' : 'Token 限额'
  const placeholder = mode === 'wan' ? '留空则不限 Token' : '如 1000000'
  const defaultInputClass = mode === 'wan' ? 'h-8 tabular-nums' : 'h-9 tabular-nums'

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className={labelClassName}>
        {label}
      </Label>
      <Input
        id={id}
        className={inputClassName ?? defaultInputClass}
        inputMode={mode === 'wan' ? 'decimal' : 'numeric'}
        type={mode === 'raw' ? 'number' : undefined}
        step={mode === 'raw' ? '1' : undefined}
        min={mode === 'raw' ? '0' : undefined}
        placeholder={placeholder}
        value={value}
        disabled={disabled}
        onChange={(e) => {
          onChange(e.target.value)
        }}
      />
    </div>
  )
}

export interface QuotaRequestLimitFieldProps {
  id?: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

export function QuotaRequestLimitField({
  id,
  value,
  onChange,
  disabled = false,
}: QuotaRequestLimitFieldProps): React.JSX.Element {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        请求数限额
      </Label>
      <Input
        id={id}
        type="number"
        step="1"
        min="0"
        value={value}
        disabled={disabled}
        placeholder="如 1000"
        className="h-9 tabular-nums"
        onChange={(e) => {
          onChange(e.target.value)
        }}
      />
    </div>
  )
}

export interface QuotaLimitValueFieldsProps {
  limitUsd: string
  onLimitUsdChange: (value: string) => void
  tokenMode: 'wan' | 'raw'
  limitTokens: string
  onLimitTokensChange: (value: string) => void
  limitRequests?: string
  onLimitRequestsChange?: (value: string) => void
  disabled?: boolean
  layout?: 'stack' | 'grid'
  usdLabel?: string
  usdPlaceholder?: string
  usdId?: string
  tokensId?: string
  requestsId?: string
}

export function QuotaLimitValueFields({
  limitUsd,
  onLimitUsdChange,
  tokenMode,
  limitTokens,
  onLimitTokensChange,
  limitRequests,
  onLimitRequestsChange,
  disabled = false,
  layout = 'stack',
  usdLabel,
  usdPlaceholder,
  usdId,
  tokensId,
  requestsId,
}: QuotaLimitValueFieldsProps): React.JSX.Element {
  const showRequests = limitRequests !== undefined && onLimitRequestsChange !== undefined

  if (layout === 'grid') {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <QuotaUsdLimitField
          id={usdId}
          label="USD 限额"
          value={limitUsd}
          onChange={onLimitUsdChange}
          disabled={disabled}
          placeholder={usdPlaceholder ?? '如 100'}
          inputClassName="h-9 tabular-nums"
          labelClassName="text-xs text-muted-foreground"
        />
        <QuotaTokenLimitField
          id={tokensId}
          mode={tokenMode}
          value={limitTokens}
          onChange={onLimitTokensChange}
          disabled={disabled}
        />
        {showRequests ? (
          <QuotaRequestLimitField
            id={requestsId}
            value={limitRequests}
            onChange={onLimitRequestsChange}
            disabled={disabled}
          />
        ) : null}
      </div>
    )
  }

  return (
    <>
      <QuotaUsdLimitField
        id={usdId}
        label={usdLabel ?? '费用上限 (USD)'}
        value={limitUsd}
        onChange={onLimitUsdChange}
        disabled={disabled}
        placeholder={usdPlaceholder ?? '例如 100'}
      />
      <QuotaTokenLimitField
        id={tokensId}
        mode={tokenMode}
        value={limitTokens}
        onChange={onLimitTokensChange}
        disabled={disabled}
      />
    </>
  )
}

export function QuotaPlatformPeriodSelect({
  value,
  onChange,
  disabled = false,
}: {
  value: QuotaBatchFormValues['period']
  onChange: (value: QuotaBatchFormValues['period']) => void
  disabled?: boolean
}): React.JSX.Element {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">重置周期</Label>
      <Select
        value={value}
        disabled={disabled}
        onValueChange={(v) => {
          onChange(v as QuotaBatchFormValues['period'])
        }}
      >
        <SelectTrigger className="h-8">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="daily">每日零点重置</SelectItem>
          <SelectItem value="monthly">每月 1 日重置</SelectItem>
          <SelectItem value="total">累计总量（不重置）</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

export interface QuotaWindowPresetFieldsProps {
  windowSeconds: string
  onWindowSecondsChange: (value: string) => void
  disabled?: boolean
  presetSelectId?: string
  customInputId?: string
  /** 覆盖默认说明文案；缺省时按预设给出（每日/每月=固定重置，自定义=滚动）。 */
  helperText?: string
}

const WINDOW_PRESET_HELPER: Record<QuotaWindowPresetValue, string> = {
  '0': '按整个套餐有效期累计，不重置。',
  '86400': '每日到下方设定的时刻重置（按所选时区）。',
  '2592000': '每月到下方设定的日 / 时刻重置（按所选时区）。',
  custom: '自定义秒数为滚动窗口：统计最近这段时间、随时间连续滑动，无固定重置时刻。',
}

export function QuotaWindowPresetFields({
  windowSeconds,
  onWindowSecondsChange,
  disabled = false,
  presetSelectId,
  customInputId,
  helperText,
}: QuotaWindowPresetFieldsProps): React.JSX.Element {
  const windowPreset = resolveQuotaWindowPreset(windowSeconds)
  const resolvedHelper = helperText ?? WINDOW_PRESET_HELPER[windowPreset]

  const handleWindowPresetChange = (preset: QuotaWindowPresetValue): void => {
    onWindowSecondsChange(applyQuotaWindowPreset(preset, windowSeconds))
  }

  return (
    <div className="space-y-1.5">
      <Label className="text-xs">统计窗口</Label>
      <Select value={windowPreset} disabled={disabled} onValueChange={handleWindowPresetChange}>
        <SelectTrigger id={presetSelectId} className="h-8">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {QUOTA_WINDOW_PRESETS.map((preset) => (
            <SelectItem key={preset.value} value={preset.value}>
              {preset.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {windowPreset === 'custom' ? (
        <Input
          id={customInputId}
          className="mt-2 h-8"
          inputMode="numeric"
          placeholder="自定义秒数，如 3600"
          value={windowSeconds}
          disabled={disabled}
          onChange={(e) => {
            onWindowSecondsChange(e.target.value)
          }}
        />
      ) : null}
      <p className="text-[11px] text-muted-foreground">{resolvedHelper}</p>
    </div>
  )
}
