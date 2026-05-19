import type React from 'react'

import { imageSrcFromItem, type ParsedImageItem } from '../media-parse'

interface ImageGenOutputProps {
  items: ParsedImageItem[]
}

export function ImageGenOutput({ items }: ImageGenOutputProps): React.JSX.Element | null {
  if (items.length === 0) return null
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map((item, index) => {
        const src = imageSrcFromItem(item)
        const key = item.url ?? `b64-${String(index)}`
        return (
          <figure key={key} className="space-y-2 rounded-md border bg-background p-2">
            {src ? (
              <img
                src={src}
                alt={`生成图片 ${String(index + 1)}`}
                className="max-h-64 w-full rounded object-contain"
              />
            ) : null}
            {item.url ? (
              <figcaption className="truncate font-mono text-xs text-muted-foreground">
                <a href={item.url} target="_blank" rel="noreferrer" className="hover:underline">
                  打开原图
                </a>
              </figcaption>
            ) : null}
          </figure>
        )
      })}
    </div>
  )
}
