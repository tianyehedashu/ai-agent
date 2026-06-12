/** bundle-preload：个人模型 chunk（无 workspace 依赖） */

export { preloadPersonalModelDetailPane } from '../detail/preload'

export function preloadPersonalModelsWorkspace(): void {
  void import('./personal-models-workspace')
}

export function preloadPersonalModelForm(): void {
  void import('./personal-model-form')
}
