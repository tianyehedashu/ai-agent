/** bundle-preload：悬停/聚焦时预加载统一模型列表 chunk */

export function preloadUnifiedModelsWorkspace(): void {
  void import('./unified-models-workspace')
}
