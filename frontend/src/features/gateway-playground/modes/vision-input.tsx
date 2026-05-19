import type React from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface VisionInputProps {
  imageUrlId: string
  imageUrl: string
  onImageUrlChange: (value: string) => void
  disabled?: boolean
  label?: string
}

export function VisionInput({
  imageUrlId,
  imageUrl,
  onImageUrlChange,
  disabled,
  label = '参考图片 URL',
}: VisionInputProps): React.JSX.Element {
  const trimmed = imageUrl.trim()
  return (
    <div className="space-y-1.5">
      <Label htmlFor={imageUrlId}>{label}</Label>
      <Input
        id={imageUrlId}
        value={imageUrl}
        onChange={(e) => {
          onImageUrlChange(e.target.value)
        }}
        placeholder="https://… 或 data:image/…;base64,…"
        disabled={disabled}
        spellCheck={false}
        className="font-mono text-sm"
        translate="no"
      />
      {trimmed ? (
        <img
          src={trimmed}
          alt="参考图预览"
          className="mt-2 max-h-40 max-w-full rounded-md border object-contain"
          onError={(e) => {
            ;(e.target as HTMLImageElement).style.display = 'none'
          }}
        />
      ) : null}
    </div>
  )
}
