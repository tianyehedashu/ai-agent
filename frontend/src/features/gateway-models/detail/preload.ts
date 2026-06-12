/** 模型详情 pane 懒加载 preload（个人 / 团队 / 统一列表 hover）。 */

export function preloadPersonalModelDetailPane(): void {
  void import('../personal/personal-model-detail-pane')
}

export function preloadTeamModelDetailPane(): void {
  void import('../team/team-model-detail-pane')
}

export function preloadGatewayModelDetailPanes(): void {
  preloadPersonalModelDetailPane()
  preloadTeamModelDetailPane()
}
