# 代码检查报告 (code-check)

结合项目规范（CLAUDE.md、backend/frontend CODE_STANDARDS）对当前代码库进行扫描，结论与建议如下。

---

## 一、遗留 / 未使用代码

### 1. `VideoTaskCreateDialog`（create-dialog.tsx）— 已修复

- **位置**: `frontend/src/pages/video-tasks/components/create-dialog.tsx`（已删除）
- **处理**: 已删除未使用的 `create-dialog.tsx`，并更新 `backend/docs/AMAZON_VIDEO_INTEGRATION.md` 中的前端结构描述（改为 create-form + detail-dialog，补充 history.tsx）。

---

## 二、兼容 / 过渡代码

以下为合理或可接受的兼容逻辑，仅做记录，无需立刻改动：

| 位置 | 说明 |
|------|------|
| `backend/bootstrap/config.py` / `llm/__init__.py` / `embeddings.py` | `dashscope_api_base` 使用 dashscope 兼容模式 URL，属供应商兼容配置 |
| `backend/domains/identity/infrastructure/authentication.py` | `CryptContext(..., deprecated="auto")` 为 passlib 推荐用法 |
| `backend/alembic/versions/20260128_add_encrypted_key.py` | 迁移中 `encrypted_key = 'legacy_key'` 为历史数据兼容，保留即可 |
| `backend/domains/studio/application/workflow_use_case.py` | `# Backward compatibility alias` 显式标注兼容别名，可保留 |

---

## 三、重复代码 (DRY)

### 1. 市场/站点列表与展示 — 已修复

- **处理**: 已新增 `frontend/src/constants/video-task.ts`，定义 `VIDEO_TASK_MARKETPLACES` 与 `VIDEO_TASK_MARKETPLACE_FLAGS`；`create-form.tsx`、`history.tsx`、`detail-dialog.tsx` 已统一从此处引用。

### 2. 模型与时长规则（前后端各一份）

- **现状**:
  - 后端: `video_task_use_case.py` 中 `valid_models`、`valid_durations`（按模型）校验。
  - 前端: `create-form.tsx` 中 `models`、`getDurations(model)` 控制可选模型与时长。
- **建议**: 不在前端复写后端规则；前端以「当前支持的模型与时长」为展示/交互约束即可。建议在 backend 或文档中注明「模型/时长合法集合以 use_case 为准」，前端若新增模型/时长选项需与后端同步（或后续考虑由后端提供一档只读配置接口）。

---

## 四、类型安全（与规范不符）

- **规范**: CLAUDE.md 要求尽量避免 `# type: ignore`（Python）、`any` / `as any` / `@ts-ignore`（TS）。
- **现状**: 未发现前端 `any`/`@ts-ignore`；后端存在多处 `# type: ignore`（如 `video_task_use_case.py` 第 283 行、conftest、session_router、base_repository 等）。
- **建议**: 不强制本次修改；后续可逐处替换为更精确类型或断言（如 `cast`、明确返回类型），减少 ignore。

---

## 五、TODO / 未实现逻辑

以下为代码中的 TODO，建议在需求或排期允许时收敛或实现：

| 位置 | 内容 |
|------|------|
| `video_task_use_case.py` | ~~`_submit_to_vendor` / `_poll_vendor` TODO~~ — 已更新为「通过 VideoAPIClient 调用 GIIKIN API」说明 |
| `amazon_video_tools.py` | 产品调研、竞品调研的「TODO: 实现真实…」 |
| `studio/presentation/router.py` | 测试执行的 TODO |
| `evaluation/presentation/router.py` | 完整评估流程的 TODO |
| `studio/infrastructure/studio/codegen.py` | 节点/路由逻辑的 TODO |
| `langgraph_store.py` / `tiered_memory.py` | 与 checkpointer/会话历史相关的 TODO |
| `frontend/src/pages/studio/index.tsx` | 「TODO: 实现测试运行」 |

---

## 六、架构与目录

- **分层**: 视频任务相关代码符合 DDD：`video_task_router` → `VideoTaskUseCase` → `VideoGenTaskRepository` / `VideoAPIClient`，presentation/application/infrastructure 边界清晰。
- **目录**: `backend/domains/agent/` 下 `application`、`presentation`、`infrastructure/models`、`infrastructure/repositories`、`infrastructure/video_api` 划分合理；前端 `pages/video-tasks` + `components`、`api/videoTask.ts`、`types/video-task.ts` 也符合现有前端规范。
- **结论**: 未发现架构不当或目录不合理问题。

---

## 七、建议执行顺序（已执行部分）

1. ~~**立即**: 处理 `create-dialog.tsx`~~ — 已删除并更新文档。
2. ~~**短期**: 抽离市场列表到公共常量~~ — 已抽离至 `constants/video-task.ts`，create-form / history / detail-dialog 已统一引用。
3. ~~**video_task_use_case TODO**~~ — 已更新 _submit_to_vendor / _poll_vendor 注释。
4. **中期**: 其余 TODO 与 `# type: ignore` 可按排期逐步收敛。

---

*报告由 code-check 流程生成，基于当前仓库状态。*
