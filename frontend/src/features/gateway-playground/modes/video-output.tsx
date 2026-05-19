import type React from 'react'

interface VideoOutputProps {
  url?: string
}

export function VideoOutput({ url }: VideoOutputProps): React.JSX.Element | null {
  if (!url?.trim()) return null
  return (
    <div className="space-y-2">
      <video src={url} controls className="max-h-80 w-full rounded-md border bg-black" />
      <p className="font-mono text-xs text-muted-foreground">
        <a href={url} target="_blank" rel="noreferrer" className="hover:underline">
          在新标签页打开
        </a>
      </p>
    </div>
  )
}
