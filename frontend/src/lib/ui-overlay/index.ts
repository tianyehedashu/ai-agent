export { OverlayScope, type OverlayScopeProps } from './overlay-scope'
export { OverlayScopeProvider } from './overlay-scope-context'
export {
  useOverlayScope,
  useOverlayPortalContainer,
  useOverlayScopeId,
} from './overlay-scope-hooks'
export {
  releaseUiOverlayLock,
  dismissOpenRadixLayers,
  deferReleaseUiOverlayLock,
  deferDismissOpenRadixLayers,
} from './release-overlay-lock'
export { useOverlayPortalReady } from './overlay-portal-ready'
export { registerSidebarNavigate } from './overlay-nav-bridge'
export {
  hasOpenRadixOverlay,
  releaseStuckBodyPointerEvents,
  installOverlayPointerGuard,
} from './overlay-pointer-guard'
export { teardownOverlayScope, teardownAllOverlayScopes } from './teardown-overlay-scope'
