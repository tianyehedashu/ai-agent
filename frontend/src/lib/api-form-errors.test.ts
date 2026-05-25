import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/errors'

import { applyApiFieldErrors, apiErrorFormMessage, fieldPathFromLoc } from './api-form-errors'

describe('fieldPathFromLoc', () => {
  it('strips body prefix', () => {
    expect(fieldPathFromLoc(['body', 'name'])).toBe('name')
    expect(fieldPathFromLoc(['body', 'grants', 0, 'scope'])).toBe('grants.0.scope')
  })
})

describe('applyApiFieldErrors', () => {
  it('maps ApiError.errors to setError', () => {
    const setError = vi.fn()
    const error = new ApiError(422, 'Validation failed', {
      code: 'VALIDATION_ERROR',
      errors: [{ loc: ['body', 'name'], msg: 'Field required', type: 'missing' }],
    })
    expect(applyApiFieldErrors(error, setError)).toBe(true)
    expect(setError).toHaveBeenCalledWith('name', { message: 'Field required' })
  })

  it('returns false for non-ApiError', () => {
    const setError = vi.fn()
    expect(applyApiFieldErrors(new Error('x'), setError)).toBe(false)
    expect(setError).not.toHaveBeenCalled()
  })
})

describe('apiErrorFormMessage', () => {
  it('prefers first field error message', () => {
    const error = new ApiError(422, 'Validation failed', {
      errors: [{ loc: ['body', 'name'], msg: 'Field required', type: 'missing' }],
    })
    expect(apiErrorFormMessage(error, 'fallback')).toBe('Field required')
  })
})
