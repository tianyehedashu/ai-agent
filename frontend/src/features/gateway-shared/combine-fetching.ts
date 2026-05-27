/** 合并多个 query 的 isFetching 状态 */
export function combineFetching(...flags: readonly boolean[]): boolean {
  return flags.some(Boolean)
}
