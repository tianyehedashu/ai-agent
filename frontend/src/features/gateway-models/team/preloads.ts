/** bundle-preload：悬停/聚焦时预加载团队模型相关 chunk */

import { preloadRegisterModelForm } from './register-model-preload'
import { preloadTeamModelDetailPane } from './team-model-detail-preload'

export { preloadRegisterModelForm, preloadTeamModelDetailPane }

export function preloadTeamModelsWorkspace(): void {
  void import('./team-models-workspace')
}

export function preloadTeamModelsGroupedWorkspace(): void {
  void import('./team-models-grouped-workspace')
}

/** 列表 ↔ 详情 ↔ 注册 常见跳转组合预加载 */
export function preloadModelNavigation(): void {
  preloadTeamModelsWorkspace()
  preloadTeamModelDetailPane()
  preloadRegisterModelForm()
}
