import { deferReleaseUiOverlayLock } from './release-overlay-lock'

/**
 * OverlayScope 卸载后的防御性清理。
 * 不手动 mutate Portal DOM（由 React 卸载负责），仅延迟释放 body 封锁。
 */
export function teardownOverlayScope(_portalMount?: HTMLElement | null): void {
  deferReleaseUiOverlayLock()
}

/**
 * 路由切换：仅释放 body 封锁，不 dispatch Escape。
 * Escape 会与 React Router transition 竞态，导致 URL 已变但页面组件未切换。
 */
export function teardownAllOverlayScopes(): void {
  deferReleaseUiOverlayLock()
}
