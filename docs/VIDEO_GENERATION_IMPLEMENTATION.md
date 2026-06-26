# 视频生成方案与实现说明

本文档描述当前项目中「产品视频生成」的方案与实现：视频生成统一走 **AI Gateway**（`LiteLLM avideo_generation`），与对话 / 生图共用计费、归因与模型目录；前端模型选择复用 `ModelSelector`（`listMode='video'`），与聊天体验一致。

> 旧方案（直连 GIIKIN 厂商 API、`VideoAPIClient`、`vendor_creator_id`）已全面移除，所有入口（Web、Agent 工具、llm-server MCP、动态 MCP 工具）统一走 `VideoTaskUseCase` → Gateway。

---

## 一、方案概述

### 1.1 能力

- **创建视频任务**：用户提交提示词、参考图、站点、模型与时长，创建一条视频生成任务。
- **大模型调用**：任务提交后经 Gateway 代理调用上游视频模型（OpenAI `/v1/videos` 兼容），统一计费与归因。
- **任务查询**：列表、详情、轮询状态；后台 task 完成后回写 `status` / `result` / `video_url` / `error_message`。
- **多端入口**：Web 端「视频任务」页面、Listing Studio 视频预览区、llm-server MCP 工具。

### 1.2 技术要点

- **后端**：DDD 分层；`VideoTaskUseCase` 依赖 `GatewayProxyProtocol.video_generation`；LiteLLM 为同步阻塞调用，通过后台 `asyncio.Task` 等待，前端轮询只读 DB。
- **模型目录**：`video_gen_catalog` 读取网关 `model_type=video` 的可见模型（含 `durations` / `max_reference_images`），供校验与前端元数据展示。
- **前端**：模型选择复用 `ModelSelector`（`listMode='video'`，数据源 `GET /gateway/models/available`）；durations 元数据来自 `GET /video-tasks/models`。

---

## 二、架构与目录

### 2.1 后端

```
backend/
├── domains/agent/
│   ├── application/
│   │   ├── video_task_use_case.py    # 用例：list/get/create/submit/poll/cancel/retry；_spawn_generation 走 Gateway
│   │   └── video_gen_catalog.py      # list_merged_video_models：网关 model_type=video 合并目录
│   ├── infrastructure/
│   │   ├── models/video_gen_task.py  # ORM 模型 + video_url 属性（从 result 解析，Gateway 优先）
│   │   ├── repositories/video_gen_task_repository.py
│   │   ├── tools/amazon_video_tools.py     # Agent 工具：submit/poll/research（走 use case）
│   │   └── mcp_server/dynamic_tool_factory.py  # amazon_video_submit/poll（走 use case）
│   └── presentation/video_task_router.py  # REST：列表/创建/详情/更新/提交/轮询/取消/删除/模型目录
├── domains/gateway/
│   ├── application/
│   │   ├── ports.py                  # GatewayProxyProtocol.video_generation
│   │   ├── internal_bridge.py        # GatewayBridge.video_generation（内部域调用入口）
│   │   ├── proxy_use_case.py         # ProxyUseCase.video_generation
│   │   ├── proxy_litellm_client.py   # LiteLLM avideo_generation 适配
│   │   └── billing_context.py        # resolve_billing_context：解析 user_id / team_id
│   └── application/sql_model_catalog.py  # 网关模型目录读取（model_type=video）
├── libs/api/deps.py                  # get_video_task_service(db, session_service)
└── bootstrap/main.py                 # 挂载 video_task_router → /api/v1/video-tasks
```

### 2.2 前端

```
frontend/src/
├── api/videoTask.ts                  # videoTaskApi：listModels/list/get/create/...（model 默认 null）
├── types/video-task.ts               # VideoGenTask、VideoCatalogModelOption、VideoModel=string、VideoDuration=number
├── constants/video-task.ts           # VIDEO_TASK_MARKETPLACES、VIDEO_TASK_MARKETPLACE_FLAGS、EXAMPLE_PROMPTS
├── components/model-selector.tsx     # 通用模型选择器（listMode='video'）
└── pages/
    ├── video-tasks/components/create-form.tsx          # ModelSelector + catalog durations
    └── listing-studio/components/video-preview-section.tsx  # 同上
```

---

## 三、数据模型

### 3.1 库表：video_gen_tasks

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| tenant_id | UUID | 租户 |
| session_id | UUID, nullable | 关联会话 |
| workflow_id | VARCHAR, nullable | 上游任务 ID（来自 Gateway 响应 `id`） |
| run_id | VARCHAR, nullable | 兼容字段 |
| status | VARCHAR(20) | pending / running / completed / failed / cancelled |
| prompt_text | TEXT, nullable | 提示词 |
| prompt_source | VARCHAR(50), nullable | 来源：user_provided / agent_generated / product_info::\<jobId\> |
| model | VARCHAR | 网关 `model_type=video` 的模型 ID |
| duration | INT | 秒；允许值见 catalog `durations` |
| reference_images | JSONB | 参考图 URL 数组 |
| marketplace | VARCHAR(10) | jp / us / de / uk / fr / it / es |
| result | JSONB, nullable | Gateway 返回的完整响应 |
| error_message | TEXT, nullable | 失败时的错误信息 |
| video_url | — | 属性：从 `result.video.url` / `result.url` 解析，不入库 |
| created_at / updated_at | TIMESTAMP | 审计时间 |

### 3.2 任务状态

| 状态 | 含义 |
|------|------|
| pending | 已创建，未提交 |
| running | 后台 task 正在调用 Gateway |
| completed | Gateway 返回 video_url |
| failed | 调用失败或未返回 video_url |
| cancelled | 用户取消（后台 task 不可中断，仅置状态） |

---

## 四、后端实现要点

### 4.1 Gateway 桥接

- **`GatewayProxyProtocol.video_generation`**（`domains/gateway/application/ports.py`）：内部域调用入口，参数 `prompt / ctx / model / seconds / reference_image_urls`，返回 OpenAI 兼容 dict（含 `id` / `status` / `video.url`）。
- **`GatewayBridge.video_generation`**（`internal_bridge.py`）：解析 team_id、确保系统 vkey、构建 `ProxyContext`（`capability=VIDEO_GENERATION`），委托 `ProxyUseCase.video_generation`。
- **`ProxyUseCase.video_generation`**（`proxy_use_case.py`）：经 `proxy_litellm_client` 调 `LiteLLM avideo_generation`（同步阻塞，默认 600s）。
- **计费归因**：`resolve_billing_context(db)` 解析当前 `user_id` / `team_id`，写入 `GatewayCallContext`。

### 4.2 VideoTaskUseCase（application）

- **create_task(...)**：校验 marketplace、model（从 `list_merged_video_models`）、duration（从 catalog `durations`）；复用 `SessionApplicationPort` 建会话；`auto_submit=True` 时调 `_spawn_generation`。
- **submit_task(task_id)**：仅 pending 且含 prompt_text 可提交；调 `_spawn_generation`。
- **poll_task(task_id, once)**：只读 DB（后台 task 完成后自动写入终态）；`once` 兼容旧参数。
- **cancel_task / retry_task**：cancel 置 CANCELLED；retry 重置字段后重新 `_spawn_generation`。
- **_spawn_generation(task)**：`resolve_billing_context` 解析 user_id/team_id（需登录用户，否则 `REQUIRES_AUTH`），调 `_spawn_background_generation`。
- **_run_generation_background(...)**：在独立 `get_session_context()` 中：置 RUNNING → 调 `get_gateway_proxy().video_generation(...)` → 成功写 COMPLETED + video_url，失败写 FAILED + error_message。后台 task 引用存入 `_BACKGROUND_TASKS` 防 GC。

### 4.3 video_gen_catalog

- **`list_merged_video_models(session)`**：读网关 `model_type=video` 可见行（`value` = 网关 model_id），从 `capabilities` 解析 `max_reference_images`、`supports_image_to_video`，从 `video_durations` tag 解析 `durations`（无则回退 `{5,10,15}`）。
- **`allowed_durations_for_video_model(catalog, model)`**：返回指定模型允许的时长集合，供 use case 校验。

### 4.4 所有权与依赖

- 接口依赖 `AuthUser` / `OptionalUser`；创建时传 `principal_id=current_user.id`，与 Chat 一致。
- 会话校验走 `SessionApplicationPort`：带 `session_id` 创建时非本人会话返回 403。
- `VideoGenTaskRepository` 继承 `OwnedRepositoryBase`，按 tenant 过滤。
- `get_video_task_service(db, session_service)` 在 `libs.api.deps` 定义，注入 `SessionUseCase`。

---

## 五、REST API

基础路径：`/api/v1/video-tasks`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /models | 视频模型目录（网关 model_type=video，含 durations 元数据） |
| GET | / | 列表，query: skip, limit, status, session_id, prompt_source |
| POST | / | 创建，body: VideoTaskCreate |
| GET | /{task_id} | 详情 |
| PATCH | /{task_id} | 更新 |
| POST | /{task_id}/submit | 提交到 Gateway |
| POST | /{task_id}/poll | 轮询（只读 DB） |
| POST | /{task_id}/cancel | 取消 |
| POST | /{task_id}/retry | 重试 |
| DELETE | /{task_id} | 删除 |

创建请求体示例：

```json
{
  "prompt_text": "产品展示视频...",
  "reference_images": ["https://example.com/img.jpg"],
  "marketplace": "jp",
  "model": null,
  "duration": 5,
  "auto_submit": true
}
```

- `model` 为空时后端取可见目录首个；`duration` 允许值由该模型 catalog `durations` 决定。
- 响应字段与 `VideoTaskResponse` 一致（id、status、model、duration、result、error_message、video_url 等）。

---

## 六、前端实现要点

### 6.1 API 层（api/videoTask.ts）

- `toBackendCreateRequest`：`model` 默认 `null`（后端取首个）；`listModels` 返回 `VideoCatalogModelOption[]`（`source` 默认 `gateway`）。
- `videoTaskApi`：listModels / list / get / create / update / submit / poll / cancel / retry / delete。

### 6.2 类型与常量

- **types/video-task.ts**：`VideoModel = string`、`VideoDuration = number`、`VideoCatalogModelOption`（含 durations / maxReferenceImages / supportsImageToVideo / source）。
- **constants/video-task.ts**：仅保留 `VIDEO_TASK_MARKETPLACES`、`VIDEO_TASK_MARKETPLACE_FLAGS`、`VIDEO_TASK_EXAMPLE_PROMPTS`；**已移除** `VIDEO_MODELS` / `getVideoDurations` / `VideoModelOption`（模型与时长改由后端 catalog 提供）。

### 6.3 模型选择与时长

- **ModelSelector**（`listMode='video'`）：数据源 `GET /gateway/models/available?mode=video`，与聊天模型选择 UX 一致。
- **durations**：`useQuery(['video-tasks','models'])` 拉 `/video-tasks/models`，建 `catalogMap`；选中模型后从其 `durations` 渲染时长下拉；模型为空时自动选 catalog 首个，时长不在范围内时回退首个。
- 适用组件：`create-form.tsx`、`video-preview-section.tsx`。

### 6.4 页面与组件

- **video-tasks/index.tsx**：欢迎区 + 示例提示 + CreateForm；创建后展示进度（轮询）。
- **create-form.tsx**：ModelSelector + 时长下拉 + 参考图 + 站点 + 提示词优化。
- **history.tsx**：列表分页与状态筛选、详情弹窗。
- **detail-dialog.tsx**：任务详情、状态、result、video_url、操作。

---

## 七、MCP 工具

所有 MCP 视频工具均封装 `VideoTaskUseCase`，随 use case 改造一并走 Gateway，无直连厂商逻辑。

### 7.1 llm-server MCP 工具

`backend/domains/agent/infrastructure/mcp_server/servers/llm_server.py` 暴露两个工具，与 Web 端同一套后端接口：

- **video_create_task**：参数 prompt / reference_images / marketplace / model / duration / auto_submit；`model` 为空时取可见目录首个；设置 `PermissionContext` 后调 `create_task`。
- **video_poll_task**：参数 task_id；调 `poll_task(once=True)`（只读 DB）。

调用方需带 `mcp:llm-server` 权限的 API Key。

### 7.2 动态 MCP 工具 amazon_video_*

`backend/domains/agent/infrastructure/mcp_server/dynamic_tool_factory.py` 的 `amazon_video_submit` / `amazon_video_poll` 同样走 `VideoTaskUseCase`：

- **amazon_video_submit**：参数 prompt / reference_images / marketplace；`auto_submit=True` 创建并提交，返回 `task_id`。
- **amazon_video_poll**：参数 `task_id`（注意：旧版为 `workflow_id, run_id`，已统一为 `task_id`）；返回 status / video_url。

工具在 MCP 请求上下文内通过 `get_mcp_user_id()` + `PermissionContextComposer` 解析当前用户。

### 7.3 Agent 工具（amazon_video_tools.py）

`AmazonVideoSubmitTool` / `AmazonVideoPollTool`（Agent 对话内工具）同样封装 `VideoTaskUseCase`，与上述入口一致。

---

## 八、数据库迁移

- `20260202_add_video_gen_tasks.py`：创建 `video_gen_tasks` 表。
- `20260205_add_video_model_duration.py`：增加 `model`、`duration` 列。

执行：`cd backend && alembic upgrade head`。

---

## 九、配置与运行

### 9.1 模型配置

视频模型在 **Gateway 管理面**配置：`system_gateway_models` / `system_provider_credentials` 中 `model_type=video`，`tags` 可声明 `video_durations`（如 `5,10,15`）与 `max_reference_images`。无需额外环境变量。

### 9.2 注意事项

- **后台 task**：`avideo_generation` 阻塞调用在 `asyncio.Task` 中等待；进程重启会丢失运行中的 task（DB 仍为 running，需人工置 failed 后 retry）。
- **轮询**：前端按需调 `poll`（如每 5s），后端只读 DB，不再触达上游。
- **完成**：`result` 写库，`video_url` 从 `result.video.url` / `result.url` 解析。
- **失败**：异常或未返回 video_url 时 `status=failed`，`error_message` 写入。
- **取消**：仅置 CANCELLED，后台 task 不可中断。

---

## 十、相关文档

- Gateway 域架构：[backend/docs/gateway/AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../backend/docs/gateway/AI_GATEWAY_DOMAIN_ARCHITECTURE.md)
- 旧 GIIKIN 集成（归档）：[backend/docs/archive/AMAZON_VIDEO_INTEGRATION.md](../backend/docs/archive/AMAZON_VIDEO_INTEGRATION.md)

---

*文档覆盖截至当前代码库的视频生成方案与实现，后续若有接口或表结构变更请同步更新本文档。*
