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
  COMMON_PERIOD_TIMEZONES,
  formatTimezoneLabel,
  isCalendarPeriodResetVisible,
  isMonthlyPeriodReset,
  timeStringToMinutes,
} from './period-reset-utils'

export interface PeriodResetFieldsProps {
  layer: 'platform' | 'upstream' | 'downstream'
  period?: string
  windowSeconds?: string
  resetStrategy?: string | null
  periodTimezone: string
  periodResetTime: string
  periodResetDay: number
  onPeriodTimezoneChange: (value: string) => void
  onPeriodResetTimeChange: (value: string) => void
  onPeriodResetDayChange: (value: number) => void
  disabled?: boolean
}

export function PeriodResetFields({
  layer,
  period,
  windowSeconds,
  resetStrategy,
  periodTimezone,
  periodResetTime,
  periodResetDay,
  onPeriodTimezoneChange,
  onPeriodResetTimeChange,
  onPeriodResetDayChange,
  disabled,
}: PeriodResetFieldsProps) {
  const visible = isCalendarPeriodResetVisible({
    layer,
    period,
    windowSeconds,
    resetStrategy,
  })
  if (!visible) return null

  const monthly = isMonthlyPeriodReset({ layer, period, windowSeconds, resetStrategy })

  return (
    <div className="space-y-3 rounded-md border border-dashed p-3">
      <p className="text-xs text-muted-foreground">
        周期起点按所选时区的本地时刻计算；当月无该日时，在当月最后一天重置（与 Stripe
        月付周期一致）。
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="period-timezone">时区</Label>
          <Select value={periodTimezone} onValueChange={onPeriodTimezoneChange} disabled={disabled}>
            <SelectTrigger id="period-timezone">
              <SelectValue placeholder="选择时区" />
            </SelectTrigger>
            <SelectContent>
              {COMMON_PERIOD_TIMEZONES.map((tz) => (
                <SelectItem key={tz} value={tz}>
                  {formatTimezoneLabel(tz)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="period-reset-time">日切时刻</Label>
          <Input
            id="period-reset-time"
            type="time"
            value={periodResetTime}
            onChange={(e) => {
              onPeriodResetTimeChange(e.target.value)
            }}
            disabled={disabled}
          />
        </div>
        {monthly ? (
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="period-reset-day">月切日（1–31）</Label>
            <Input
              id="period-reset-day"
              type="number"
              min={1}
              max={31}
              value={periodResetDay}
              onChange={(e) => {
                const n = Number(e.target.value)
                if (Number.isFinite(n)) onPeriodResetDayChange(Math.min(31, Math.max(1, n)))
              }}
              disabled={disabled}
            />
            {periodResetDay === 31 ? (
              <p className="text-xs text-muted-foreground">等同每月月底重置</p>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function periodResetMinutesFromTime(time: string): number {
  return timeStringToMinutes(time) ?? 0
}
