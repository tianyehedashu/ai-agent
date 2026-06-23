/** bundle-preload：悬停/聚焦时预加载统一模型列表 chunk */

export function preloadUnifiedModelsWorkspace(): void {
  void import('./unified-models-workspace')
}

/** 预加载「添加模型」各归属注册页 chunk（bundle-preload） */
export function preloadAddModelRegisterViews(): void {
  void import('../personal/personal-model-preload').then((m) => {
    m.preloadPersonalModelsWorkspace()
    m.preloadPersonalModelForm()
  })
  void import('../team/preloads').then((m) => {
    m.preloadModelNavigation()
  })
}
