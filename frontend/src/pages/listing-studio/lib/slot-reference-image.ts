/**
 * Listing Studio 8 图生成 - 槽位参考图解析规则
 */

export type SlotReferenceMode = 'current' | 'source' | 'chain'

function trimToUrl(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  if (!trimmed) return null
  return trimmed
}

export function resolveProductSourceImageUrl(
  manualReferenceUrl: string | undefined,
  inputImageUrls: string[]
): string | null {
  const manual = trimToUrl(manualReferenceUrl)
  if (manual) return manual
  return trimToUrl(inputImageUrls[0])
}

export function resolveSlotReferenceImage(params: {
  mode: SlotReferenceMode
  slot: number
  currentSlotUrl?: string | null
  sourceImageUrl?: string | null
  slot1GeneratedUrl?: string | null
  explicitReferenceUrl?: string | null
}): string | null {
  const explicit = trimToUrl(params.explicitReferenceUrl)
  if (explicit) return explicit

  const source = trimToUrl(params.sourceImageUrl)
  const current = trimToUrl(params.currentSlotUrl)
  const slot1 = trimToUrl(params.slot1GeneratedUrl)

  if (params.mode === 'current') {
    return current ?? source
  }

  if (params.mode === 'source') {
    return source
  }

  // chain — batch generation
  if (params.slot <= 1) {
    return source
  }
  return slot1 ?? source
}
