/**
 * 设置页「我的凭据」列表中 API Key 掩码行的展示逻辑（纯函数，便于单测）。
 */

export function displayListApiKeyMasked(
  showFullMaskedInList: boolean,
  hasAuthSession: boolean,
  apiKeyMasked: string
): string {
  if (!hasAuthSession) {
    return '········（已隐藏）'
  }
  return showFullMaskedInList ? apiKeyMasked : '········（已隐藏）'
}
