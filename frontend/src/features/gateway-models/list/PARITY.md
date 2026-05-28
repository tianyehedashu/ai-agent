# Gateway 模型列表统一 · 功能对照表（PARITY）

> PR 回归 SSOT。Workspace 接入前逐项勾选；任一 **Blocker** 失败禁止合并。

## 入口

| 入口             | preset                             | Workspace                             |
| ---------------- | ---------------------------------- | ------------------------------------- |
| Personal         | `PERSONAL_LIST_CAPABILITIES`       | `PersonalModelsWorkspace`             |
| Team Grouped     | `TEAM_GROUPED_CAPABILITIES`        | `TeamModelsGroupedWorkspace`          |
| System Admin     | `SYSTEM_ADMIN_CAPABILITIES`        | `TeamModelsWorkspace listMode=system` |
| System Browse    | `SYSTEM_BROWSE_CAPABILITIES`       | `SystemModelsBrowseWorkspace`         |
| Credential Embed | `EMBEDDED_CREDENTIAL_CAPABILITIES` | `CredentialModelsCard`                |

## 能力矩阵

| 能力                           |  Personal   | Team Grouped | System Admin | System Browse | Embed |
| ------------------------------ | :---------: | :----------: | :----------: | :-----------: | :---: |
| 列表 + 分页                    |      ☐      |      ☐       |      ☐       |  ☐ infinite   |   ☐   |
| 搜索                           |     ☐ q     |  ☐ q + team  |     ☐ q      |   ☐ 本地 q    |   —   |
| 凭据筛选                       |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 通道 / 能力筛选                |      ☐      |      ☐       |      ☐       |    ☐ 本地     |   —   |
| 健康筛选 (HealthStrip)         |      ☐      |      ☐       |      ☐       |       —       |   —   |
| credentialBanner / URL 深链    |      ☐      |      ☐       |      ☐       |       —       |   —   |
| modelId 高亮 / URL             |      ☐      |      ☐       |      ☐       |       —       |   —   |
| Channel Info Tooltip           |      ☐      |      ☐       |      ☐       |       ☐       |   —   |
| 用量 24h/7d/30d 行内           |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 行内启停 Switch                | ☐ is_active |  ☐ enabled   |      ☐       |       —       |   —   |
| 行内删除 + Confirm             |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 行内导航详情 + preload         |      ☐      |      ☐       |      ☐       |       —       |   ☐   |
| 批量勾选                       |      ☐      |      ☐       |      ☐       |       —       |   —   |
| BatchBar `onSelection`         |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 批量测试已选                   |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 批量同步能力                   |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 批量删除已选                   |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 删除筛选下全部（Toolbar 菜单） |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 删除不可用 (failed)            |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 探活 Banner + scrollToFirst    |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 刷新（含相关 query）           |      ☐      |      ☐       |      ☐       |       ☐       |   —   |
| SystemModelAdminMeta           |      —      |      —       |      ☐       |       —       |   —   |
| 注册视图（不在 Shell）         |      ☐      |      ☐       |      ☐       |       —       |   —   |
| 空态 onboarding                |      ☐      |      ☐       |      ☐       |       ☐       |   ☐   |
| requiresSearch（团队过多）     |      —      |      ☐       |      —       |       —       |   —   |
| 翻页 off-page hint             |      —      |      ☐       |      —       |       —       |   —   |

## 权限 gate

| 维度                      | 预期                                                      |
| ------------------------- | --------------------------------------------------------- |
| 未登录                    | Personal 拒入                                             |
| 非 PlatformAdmin          | System Admin → 降级 `SYSTEM_BROWSE_CAPABILITIES`          |
| `canWrite=false`          | 隐藏 BatchBar、行 Switch、行删除、添加模型                |
| 行级 `canManage=false`    | 禁用 Switch；不显示删除；批量 Checkbox disabled + Tooltip |
| 行级 `configManaged=true` | 不可批量选；不可单删；Tooltip 说明                        |
| System Browse             | preset `readonly`；所有写操作不渲染                       |
| Embedded                  | 无 Toolbar/BatchBar/分组；行可点进详情                    |

## Blocker 回归项

- [ ] Personal：三行展示（display_name / routeName / model_id）
- [ ] Personal：URL `credentialId` 深链
- [ ] Personal：导入后探活流
- [ ] Personal：BatchBar `onSelection` 后 **删除筛选下全部** 仍在 Toolbar 二级菜单
- [ ] Personal：行内 Switch `is_active` loading/disabled 正确
- [ ] Team Grouped：行 mutate 携带 `teamId`
- [ ] Team Grouped：URL `credentialId` / `modelId` 深链
- [ ] Team Grouped：批量勾选 + canManage/canDelete gate
- [ ] System Admin：URL `credentialId` / `modelId` 不变
- [ ] System Admin：SystemModelAdminMeta 完整（可见性 Select 不被裁切）
- [ ] System Admin：用量 24h/7d/30d + 行内文案
- [ ] System Browse：readonly preset；本地搜索/通道筛选；无写按钮
- [ ] Embedded：无 Toolbar/BatchBar；行导航可用

## 手测脚本（摘要）

1. 五个入口各打开列表，确认 preset 能力开关与上表一致。
2. 分别以 Owner / Member(read) / PlatformAdmin / 匿名 四类角色验证权限 gate。
3. 批量：勾选 → 测试/同步/删除；Toolbar 菜单 → 删除筛选下全部。
4. 探活：全量/未测/失败删除；Banner scrollToFirst。
5. 深链：`?credentialId=`、`?modelId=` 高亮与筛选。

## 组件包状态（FE1）

| 文件                             | 状态                                                                     |
| -------------------------------- | ------------------------------------------------------------------------ |
| `types.ts`                       | ✅ 已创建                                                                |
| `adapters.ts` + test             | ✅ 已创建                                                                |
| `capabilities.ts`                | ✅ 已创建                                                                |
| `list-presets.ts`                | ✅ 已创建                                                                |
| `gateway-model-list-row.tsx`     | ✅ 已创建                                                                |
| `gateway-model-list-toolbar.tsx` | ✅ 已创建                                                                |
| `gateway-model-batch-bar.tsx`    | ✅ 已创建                                                                |
| `gateway-model-list-shell.tsx`   | ✅ 已创建                                                                |
| `gateway-model-grouped-list.tsx` | ✅ 已创建                                                                |
| `index.ts`                       | ✅ 已创建                                                                |
| Workspace 接入                   | ✅ 五入口已接入                                                          |
| 删旧文件                         | ✅ 旧列表组件已删除                                                      |
| 后端新端点                       | ✅ my-models usage/resync + managed-team usage                           |
| 单元/集成测试                    | ✅ adapters.test + 后端 unit tests（resync/usage）；integration 用例已补 |
