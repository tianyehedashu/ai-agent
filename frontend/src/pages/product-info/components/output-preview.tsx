/**
 * 本次产出预览：5 点商品描述、8 图位、视频位（等待、展示、创建一体化）
 */

import { useState } from 'react'

import { FileText, ImageIcon } from 'lucide-react'

import { ImageLightbox } from '@/components/ui/image-lightbox'
import { useProductInfoCapabilities } from '@/hooks/use-product-info-capabilities'
import type { ProductInfoJob } from '@/types/product-info'

import { getFivePointDescription } from './output-preview-shared'
import { VideoPreviewSection } from './video-preview-section'

interface OutputPreviewProps {
  currentJob: ProductInfoJob | null
  /** 当前 job 对应的 8 图结果（最近一次生成的 8 张图） */
  latestEightImages: { slot: number; url: string }[] | null
}

export function OutputPreview({
  currentJob,
  latestEightImages,
}: OutputPreviewProps): React.JSX.Element {
  const caps = useProductInfoCapabilities()
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)

  const outputKey = caps.outputKeys.product_link_analysis
  const stepProduct = currentJob?.steps?.find((s) => s.capability_id === 'product_link_analysis')
  const snapshot = stepProduct?.output_snapshot
  const productInfo = snapshot === undefined || snapshot === null ? null : snapshot[outputKey]
  const fivePoints = getFivePointDescription(productInfo)

  const images = latestEightImages ?? []
  const slots = Array.from({ length: 8 }, (_, i) => {
    const bySlot = images.find((img) => img.slot === i + 1)
    return bySlot?.url ?? null
  })

  return (
    <>
      <div className="grid gap-5 lg:grid-cols-[1fr_2fr]">
        {/* 5 点商品描述 */}
        <div className="rounded-lg border border-border/50 bg-card p-5">
          <div className="mb-3 flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-base font-medium">5 点商品描述</h3>
          </div>
          {fivePoints.length > 0 ? (
            <ul className="space-y-2">
              {fivePoints.map((line, i) => (
                <li
                  key={`${line}-${String(i)}`}
                  className="flex gap-2.5 rounded-md bg-muted/30 px-3 py-2"
                >
                  <span className="shrink-0 text-sm font-semibold text-primary">
                    {String(i + 1)}
                  </span>
                  <span className="text-sm leading-relaxed text-muted-foreground">{line}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              运行「商品链接分析」后在此展示
            </p>
          )}
        </div>

        {/* 8 图位 */}
        <div className="rounded-lg border border-border/50 bg-card p-5">
          <div className="mb-3 flex items-center gap-2">
            <ImageIcon className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-base font-medium">主图（8 张）</h3>
          </div>
          <div className="grid grid-cols-4 gap-2.5 sm:grid-cols-8">
            {slots.map((url, i) => (
              <div
                key={String(i)}
                className="aspect-square overflow-hidden rounded-md border border-border/40 bg-muted/20"
              >
                {url ? (
                  <button
                    type="button"
                    className="h-full w-full transition-transform hover:scale-[1.03]"
                    onClick={() => {
                      setLightboxUrl(url)
                    }}
                  >
                    <img
                      src={url}
                      alt=""
                      className="h-full w-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                  </button>
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-sm tabular-nums text-muted-foreground/50">
                    {String(i + 1)}
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            填写下方提示词并生成后，图片将显示在此
          </p>
        </div>
      </div>

      <VideoPreviewSection
        jobId={currentJob?.id ?? null}
        currentJob={currentJob}
        imageUrls={slots.filter((u): u is string => !!u)}
      />

      <ImageLightbox
        src={lightboxUrl}
        onClose={() => {
          setLightboxUrl(null)
        }}
      />
    </>
  )
}
