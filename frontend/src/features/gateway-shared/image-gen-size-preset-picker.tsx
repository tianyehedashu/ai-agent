/**
 * 生图比例/尺寸预设选择器（Playground / Listing Studio 共用）。
 */

import { useId, useMemo } from 'react'
import type React from 'react'

import { Label } from '@/components/ui/label'
import {
  imageGenPresetBySize,
  imageGenPresetsForProvider,
  imageGenProviderSizeHint,
  type ImageGenSizePreset,
} from '@/features/gateway-shared/image-gen-size-presets'
import { cn } from '@/lib/utils'

export interface ImageGenSizePresetPickerProps {
  provider: string | undefined
  size: string
  onSizeChange: (size: string) => void
  /** 覆盖自动生成的 label id */
  id?: string
  /** 紧凑布局（Listing Studio 顶栏下全宽） */
  layout?: 'playground' | 'compact'
}

function AspectPreview({ preset }: { preset: ImageGenSizePreset }): React.JSX.Element {
  return (
    <div
      className="mx-auto w-full max-w-[2.75rem] rounded-sm border border-border/80 bg-muted/40"
      style={{ aspectRatio: preset.aspectRatio }}
      aria-hidden
    />
  )
}

export function ImageGenSizePresetPicker({
  provider,
  size,
  onSizeChange,
  id: idProp,
  layout = 'playground',
}: ImageGenSizePresetPickerProps): React.JSX.Element {
  const autoId = useId()
  const labelId = idProp ?? autoId
  const presets = useMemo(() => imageGenPresetsForProvider(provider), [provider])
  const selected = useMemo(
    () => imageGenPresetBySize(provider, size) ?? presets[0],
    [provider, size, presets]
  )
  const hint = imageGenProviderSizeHint(provider)

  const gridClass =
    layout === 'compact'
      ? 'grid grid-cols-3 gap-2 sm:grid-cols-6'
      : 'grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6'

  return (
    <div className={cn('space-y-2', layout === 'playground' && 'sm:col-span-2')}>
      <Label id={labelId}>比例 / 尺寸</Label>
      <div role="radiogroup" aria-labelledby={labelId} className={gridClass}>
        {presets.map((preset) => {
          const active = preset.id === selected.id
          return (
            <button
              key={preset.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => {
                onSizeChange(preset.size)
              }}
              className={cn(
                'flex flex-col items-center gap-1.5 rounded-lg border px-2 py-2.5 text-left transition-colors',
                'hover:border-primary/40 hover:bg-muted/30',
                active
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                  : 'border-border/60 bg-background'
              )}
            >
              <AspectPreview preset={preset} />
              <span className="w-full text-center text-xs font-medium leading-tight">
                {preset.label}
              </span>
              <span className="w-full text-center text-[10px] text-muted-foreground">
                {preset.aspect}
              </span>
              <span className="w-full text-center font-mono text-[10px] text-muted-foreground">
                {preset.size.replace('x', '×')}
              </span>
            </button>
          )
        })}
      </div>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}
