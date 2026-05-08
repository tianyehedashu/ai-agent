/**
 * 图片灯箱 - 全屏预览，支持 Esc 关闭与 a11y（dialog、焦点）
 */

import { useEffect, useRef } from 'react'

import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface ImageLightboxProps {
  /** 图片 URL，为 null 时不渲染 */
  src: string | null
  onClose: () => void
  className?: string
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

export function ImageLightbox({
  src,
  onClose,
  className,
}: ImageLightboxProps): React.JSX.Element | null {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!src) return
    closeRef.current?.focus()
  }, [src])

  useEffect(() => {
    if (!src) return
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
      if (e.key === 'Tab') {
        const el = document.querySelector('[data-image-lightbox]')
        if (!el) return
        const focusable = el.querySelectorAll<HTMLElement>(FOCUSABLE)
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [src, onClose])

  if (!src) return null

  return (
    <div
      data-image-lightbox
      role="dialog"
      aria-modal="true"
      aria-label="图片预览"
      className={cn('fixed inset-0 z-50 flex items-center justify-center bg-black/80', className)}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <button
        ref={closeRef}
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 rounded-md bg-black/50 p-2 text-white hover:bg-black/70 focus:outline-none focus:ring-2 focus:ring-white"
        aria-label="关闭"
      >
        <X className="h-5 w-5" />
      </button>
      <img
        src={src}
        alt="预览"
        className="max-h-[90vh] max-w-[90vw] object-contain"
        referrerPolicy="no-referrer"
        onClick={(e) => {
          e.stopPropagation()
        }}
      />
    </div>
  )
}
