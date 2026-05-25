/**
 * 参考图摄入：小图内联 data URL，大图走已有用户图片上传 API
 */

import { ApiError } from '@/api/errors'
import { uploadUserImage } from '@/api/userImageUpload'

/** Playground 内联上限（低于服务端 10MB，避免 vision POST 体过大触发 413） */
export const DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES = 256 * 1024

export const REFERENCE_IMAGE_ACCEPT_ERROR = '请选择图片文件（JPG / PNG / WebP / GIF）'

const EXT_TO_MIME: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  gif: 'image/gif',
}

const MIME_TO_EXT: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
  'image/gif': 'gif',
}

const ALLOWED_IMAGE_MIMES = new Set<string>(Object.keys(MIME_TO_EXT))

const IMAGE_EXT_PATTERN = /\.([a-z0-9]+)$/i
const KNOWN_IMAGE_EXT_PATTERN = /\.(jpe?g|png|webp|gif)$/i

function mimeFromExtension(name: string): string | null {
  const match = IMAGE_EXT_PATTERN.exec(name)
  if (!match) return null
  return EXT_TO_MIME[match[1].toLowerCase()] ?? null
}

/** 读取文件头 magic bytes 推断 MIME（同步，供 normalize 使用） */
export function detectImageMimeFromBytes(bytes: Uint8Array): string | null {
  if (bytes.length < 3) return null
  if (
    bytes.length >= 4 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    return 'image/png'
  }
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return 'image/jpeg'
  }
  if (
    bytes.length >= 6 &&
    bytes[0] === 0x47 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x38
  ) {
    return 'image/gif'
  }
  if (
    bytes.length >= 12 &&
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return 'image/webp'
  }
  return null
}

function blobToArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === 'function') {
    return blob.arrayBuffer()
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (reader.result instanceof ArrayBuffer) {
        resolve(reader.result)
      } else {
        reject(new Error('无法读取图片'))
      }
    }
    reader.onerror = () => {
      reject(new Error('无法读取图片'))
    }
    reader.readAsArrayBuffer(blob)
  })
}

async function readFileHead(file: File, maxBytes = 12): Promise<Uint8Array> {
  const chunk = file.size <= maxBytes ? file : file.slice(0, maxBytes)
  const buffer = await blobToArrayBuffer(chunk)
  return new Uint8Array(buffer)
}

function ensureFileNameWithExt(name: string, ext: string): string {
  const trimmed = name.trim()
  if (KNOWN_IMAGE_EXT_PATTERN.test(trimmed)) return trimmed
  const base = trimmed.length > 0 && trimmed !== 'image.png' ? trimmed : 'paste'
  return `${base}.${ext}`
}

/** 同步粗筛：详细校验在 normalizeImageFile */
export function isImageFileCandidate(file: File): boolean {
  if (file.size <= 0) return false
  if (file.type.startsWith('image/')) return ALLOWED_IMAGE_MIMES.has(file.type)
  if (file.type === '') {
    if (mimeFromExtension(file.name) !== null) return true
    // 剪贴板截图常无扩展名；详细校验在 normalizeImageFile（magic bytes）
    return file.size > 0
  }
  return false
}

/** 将空 MIME / 需纠偏的文件规范为后端允许的 image/* */
export async function normalizeImageFile(file: File): Promise<File> {
  if (file.size <= 0) {
    throw new Error('图片文件为空')
  }

  if (file.type.startsWith('image/')) {
    if (!ALLOWED_IMAGE_MIMES.has(file.type)) {
      throw new Error(REFERENCE_IMAGE_ACCEPT_ERROR)
    }
    return file
  }

  if (file.type !== '') {
    throw new Error(REFERENCE_IMAGE_ACCEPT_ERROR)
  }

  const fromExt = mimeFromExtension(file.name)
  if (fromExt) {
    const ext = MIME_TO_EXT[fromExt]
    return new File([file], ensureFileNameWithExt(file.name, ext), { type: fromExt })
  }

  const head = await readFileHead(file)
  const fromMagic = detectImageMimeFromBytes(head)
  const mime = fromMagic
  if (!mime) {
    throw new Error(REFERENCE_IMAGE_ACCEPT_ERROR)
  }

  const ext = MIME_TO_EXT[mime]
  return new File([file], ensureFileNameWithExt(file.name, ext), { type: mime })
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
      } else {
        reject(new Error('无法读取图片'))
      }
    }
    reader.onerror = () => {
      reject(new Error('无法读取图片'))
    }
    reader.readAsDataURL(file)
  })
}

export function readImageFromClipboard(data: DataTransfer): File | null {
  const files = data.files
  if (files.length > 0) {
    for (let i = 0; i < files.length; i++) {
      const file = files.item(i)
      if (file !== null && isImageFileCandidate(file)) {
        return file
      }
    }
  }
  for (let i = 0; i < data.items.length; i++) {
    const item = data.items[i]
    if (item.kind !== 'file') continue
    if (item.type.startsWith('image/') || item.type === '') {
      const file = item.getAsFile()
      if (file && isImageFileCandidate(file)) return file
    }
  }
  return null
}

export function clipboardHasImage(data: DataTransfer): boolean {
  return readImageFromClipboard(data) !== null
}

export interface IngestReferenceImageOptions {
  maxInlineBytes?: number
}

export async function ingestReferenceImage(
  file: File,
  options?: IngestReferenceImageOptions
): Promise<string> {
  const maxInline = options?.maxInlineBytes ?? DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES
  if (
    file.size > 0 &&
    file.type.startsWith('image/') &&
    ALLOWED_IMAGE_MIMES.has(file.type) &&
    file.size <= maxInline
  ) {
    return fileToDataUrl(file)
  }

  const normalized = await normalizeImageFile(file)
  if (normalized.size <= maxInline) {
    return fileToDataUrl(normalized)
  }
  const res = await uploadUserImage(normalized)
  return res.url
}

export function formatReferenceImageIngestError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.status === 403) {
      return '请先登录后再上传图片'
    }
    if (err.status === 413) {
      return '图片过大，请压缩后重试'
    }
    if (err.status === 422) {
      return err.message || '图片格式或大小不符合要求'
    }
    return err.message
  }
  if (err instanceof Error) {
    return err.message
  }
  return String(err)
}
