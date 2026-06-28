import { describe, expect, test, vi, beforeEach } from 'vitest'

vi.mock('@/api/user-image-upload', () => ({
  uploadUserImage: vi.fn(),
}))

import { ApiError } from '@/api/errors'
import { uploadUserImage } from '@/api/user-image-upload'

import {
  DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES,
  detectImageMimeFromBytes,
  fileToDataUrl,
  formatReferenceImageIngestError,
  ingestReferenceImage,
  isImageFileCandidate,
  normalizeImageFile,
  readImageFromClipboard,
  REFERENCE_IMAGE_ACCEPT_ERROR,
  toAbsoluteImageUrl,
} from './reference-image-ingest'

const mockedUpload = vi.mocked(uploadUserImage)

const PNG_HEAD = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] as const

function makePngFile(sizeBytes: number, name = 'test.png', type = 'image/png'): File {
  const buffer = new Uint8Array(Math.max(sizeBytes, PNG_HEAD.length))
  buffer.set(PNG_HEAD, 0)
  return new File([buffer], name, { type })
}

describe('detectImageMimeFromBytes', () => {
  test('detects png signature', () => {
    expect(detectImageMimeFromBytes(new Uint8Array(PNG_HEAD))).toBe('image/png')
  })

  test('detects jpeg signature', () => {
    expect(detectImageMimeFromBytes(new Uint8Array([0xff, 0xd8, 0xff, 0x00]))).toBe('image/jpeg')
  })
})

describe('isImageFileCandidate', () => {
  test('rejects zero-byte file', () => {
    expect(isImageFileCandidate(new File([], 'a.png', { type: 'image/png' }))).toBe(false)
  })

  test('accepts empty mime clipboard-sized blob', () => {
    expect(isImageFileCandidate(new File([new Uint8Array(4)], 'screenshot', { type: '' }))).toBe(
      true
    )
  })
})

describe('fileToDataUrl', () => {
  test('returns data URL string', async () => {
    const file = makePngFile(8)
    const url = await fileToDataUrl(file)
    expect(url.startsWith('data:image/png;base64,')).toBe(true)
  })
})

describe('readImageFromClipboard', () => {
  test('reads image from files list', () => {
    const file = makePngFile(8)
    const data = {
      files: {
        length: 1,
        item: (i: number) => (i === 0 ? file : null),
      },
      items: [],
    } as unknown as DataTransfer
    expect(readImageFromClipboard(data)?.name).toBe('test.png')
  })

  test('reads image from files list with empty mime', () => {
    const file = new File([new Uint8Array(PNG_HEAD)], 'screenshot', { type: '' })
    const data = {
      files: {
        length: 1,
        item: (i: number) => (i === 0 ? file : null),
      },
      items: [],
    } as unknown as DataTransfer
    expect(readImageFromClipboard(data)?.type).toBe('')
  })
})

describe('normalizeImageFile', () => {
  test('infers png from magic bytes when mime empty', async () => {
    const file = new File([new Uint8Array(PNG_HEAD)], 'shot', { type: '' })
    const normalized = await normalizeImageFile(file)
    expect(normalized.type).toBe('image/png')
    expect(normalized.name).toBe('shot.png')
  })

  test('infers jpeg from extension when mime empty', async () => {
    const file = new File([new Uint8Array([0xff, 0xd8, 0xff, 0x00, 0x00])], 'photo.jpg', {
      type: '',
    })
    const normalized = await normalizeImageFile(file)
    expect(normalized.type).toBe('image/jpeg')
  })

  test('rejects empty file', async () => {
    await expect(normalizeImageFile(new File([], 'a.png', { type: '' }))).rejects.toThrow(
      '图片文件为空'
    )
  })

  test('rejects non-image bytes without extension', async () => {
    await expect(
      normalizeImageFile(new File([new Uint8Array([1, 2, 3, 4])], 'blob', { type: '' }))
    ).rejects.toThrow(REFERENCE_IMAGE_ACCEPT_ERROR)
  })
})

describe('toAbsoluteImageUrl', () => {
  test('prefixes relative listing-studio path', () => {
    expect(
      toAbsoluteImageUrl('/ai-agent/api/v1/listing-studio/images/a.jpg', 'http://localhost:5173')
    ).toBe('http://localhost:5173/ai-agent/api/v1/listing-studio/images/a.jpg')
  })

  test('leaves https cdn url unchanged', () => {
    expect(toAbsoluteImageUrl('https://cdn.example.com/a.png', 'http://localhost:5173')).toBe(
      'https://cdn.example.com/a.png'
    )
  })

  test('leaves data url unchanged', () => {
    const data = 'data:image/png;base64,abc'
    expect(toAbsoluteImageUrl(data, 'http://localhost:5173')).toBe(data)
  })
})

describe('ingestReferenceImage', () => {
  beforeEach(() => {
    mockedUpload.mockReset()
  })

  test('small file uses inline data URL', async () => {
    const file = makePngFile(100)
    const result = await ingestReferenceImage(file, { maxInlineBytes: 512 })
    expect(result.startsWith('data:image/png;base64,')).toBe(true)
    expect(mockedUpload).not.toHaveBeenCalled()
  })

  test('large file uploads and returns https url', async () => {
    mockedUpload.mockResolvedValue({
      url: 'https://cdn.example.com/a.png',
      content_type: 'image/png',
      size_bytes: DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES + 1,
    })
    const file = makePngFile(DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES + 1)
    const result = await ingestReferenceImage(file, {
      maxInlineBytes: DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES,
    })
    expect(result).toBe('https://cdn.example.com/a.png')
    expect(mockedUpload).toHaveBeenCalledOnce()
  })

  test('large file upload converts relative api path to absolute url', async () => {
    mockedUpload.mockResolvedValue({
      url: '/ai-agent/api/v1/listing-studio/images/a89f.jpg',
      content_type: 'image/jpeg',
      size_bytes: DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES + 1,
    })
    const file = makePngFile(DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES + 1)
    const result = await ingestReferenceImage(file, {
      maxInlineBytes: DEFAULT_REFERENCE_IMAGE_INLINE_MAX_BYTES,
    })
    expect(result).toMatch(
      /^https?:\/\/[^/]+\/ai-agent\/api\/v1\/listing-studio\/images\/a89f\.jpg$/
    )
    expect(mockedUpload).toHaveBeenCalledOnce()
  })

  test('rejects non-image mime', async () => {
    const file = new File(['x'], 'a.txt', { type: 'text/plain' })
    await expect(ingestReferenceImage(file)).rejects.toThrow(REFERENCE_IMAGE_ACCEPT_ERROR)
  })

  test('ingests empty mime clipboard png as data url', async () => {
    const file = new File([new Uint8Array(PNG_HEAD)], 'shot', { type: '' })
    const result = await ingestReferenceImage(file, { maxInlineBytes: 512 })
    expect(result.startsWith('data:image/png;base64,')).toBe(true)
  })
})

describe('formatReferenceImageIngestError', () => {
  test('maps 401 to login hint', () => {
    expect(formatReferenceImageIngestError(new ApiError(401, 'Unauthorized'))).toContain('登录')
  })

  test('maps 413 to size hint', () => {
    expect(formatReferenceImageIngestError(new ApiError(413, 'Payload Too Large'))).toContain(
      '过大'
    )
  })
})
