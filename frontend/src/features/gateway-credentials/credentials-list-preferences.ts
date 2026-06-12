/**
 * 凭据列表 UI 偏好（localStorage）。
 */

const SHOW_FULL_MASK_KEY = 'gateway.credentials.showFullMask'

export function readShowFullCredentialMask(): boolean {
  try {
    return localStorage.getItem(SHOW_FULL_MASK_KEY) === '1'
  } catch {
    return false
  }
}

export function writeShowFullCredentialMask(value: boolean): void {
  try {
    localStorage.setItem(SHOW_FULL_MASK_KEY, value ? '1' : '0')
  } catch {
    // ignore quota / private mode
  }
}
