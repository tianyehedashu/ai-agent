import { ApiError, type FieldError } from '@/api/errors'

import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

/** 将 RFC 7807 ``errors[]`` 的 loc 转为 react-hook-form 字段路径（去掉 body 前缀）。 */
export function fieldPathFromLoc(loc: FieldError['loc']): string {
  const parts = loc.filter((part) => part !== 'body')
  return parts.map(String).join('.')
}

/**
 * 将 API 422 字段错误写入表单；返回 true 表示已应用至少一条字段错误。
 */
export function applyApiFieldErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>
): boolean {
  if (!(error instanceof ApiError) || !error.errors?.length) {
    return false
  }
  let applied = false
  for (const fieldError of error.errors) {
    const path = fieldPathFromLoc(fieldError.loc)
    if (!path) continue
    setError(path as Path<T>, { message: fieldError.msg })
    applied = true
  }
  return applied
}

/** 优先返回字段级首条错误，否则返回 ApiError.message。 */
export function apiErrorFormMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.errors?.length) {
    return error.errors[0]?.msg ?? error.message
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }
  return fallback
}
