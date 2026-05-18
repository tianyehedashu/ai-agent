/** bundle-preload：个人模型 chunk（无 workspace 依赖） */

export function preloadPersonalModelDetailPane(): void {
  void import('./personal-model-detail-pane')
}

export function preloadPersonalModelsWorkspace(): void {
  void import('./personal-models-workspace')
}

export function preloadPersonalModelForm(): void {
  void import('./personal-model-form')
}
