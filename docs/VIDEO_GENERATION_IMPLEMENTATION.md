# 视频生成方案与实现说明

本文档完整描述当前项目中「亚马逊 / 产品视频生成」的方案与实现，涵盖后端、前端、厂商对接、数据模型与使用方式，便于维护与扩展。

---

## 一、方案概述

### 1.1 能力

- **创建视频任务**：用户或 Agent 提交提示词、参考图、站点、模型与时长，创建一条视频生成任务。
- **提交到厂商**：任务可自动或手动提交到 GIIKIN 视频生成 API（图生视频工作流）。
- **任务查询**：列表、详情、轮询状态；轮询结果会更新状态、`result`、`video_url`、`error_message`。
- **多端入口**：Web 端「视频任务」页面（创建 + 历史）、Agent 对话内工具（提交 / 轮询 / 产品·竞品调研）。

### 1.2 技术要点

- **后端**：DDD 分层（Presentation → Application → Domain ← Infrastructure），所有权过滤（注册用户 / 匿名用户）。
- **厂商对接**：OAuth2 client_credentials、任务提交（workflow/run）、状态查询（workflow/query），结果中解析 `video_url`。
- **前端**：统一 API 层（snake_case ↔ camelCase）、类型与常量集中（types、constants），页面与详情弹窗复用同一套任务模型。

---

## 二、架构与目录

### 2.1 后端

```
backend/
├── bootstrap/
│   ├── config.py                    # GIIKIN 配置：giikin_client_id, giikin_client_secret, giikin_base_url
│   └── main.py                      # 挂载 video_task_router → /api/v1/video-tasks
├── libs/api/
│   └── deps.py                      # get_video_task_service(db) → VideoTaskUseCase
├── domains/agent/
│   ├── application/
│   │   └── video_task_use_case.py  # 用例：list/get/create/update/submit/poll/cancel
│   ├── infrastructure/
│   │   ├── models/
│   │   │   └── video_gen_task.py   # ORM 模型 + video_url 属性（从 result 解析）
│   │   ├── repositories/
│   │   │   └── video_gen_task_repository.py  # 带所有权过滤的 CRUD
│   │   ├── video_api/
│   │   │   ├── __init__.py
│   │   │   └── client.py            # VideoAPIClient：Token、submit、poll、poll_until_complete
│   │   └── tools/
│   │       └── amazon_video_tools.py  # Agent 工具：submit、poll、产品调研、竞品调研
│   └── presentation/
│       └── video_task_router.py    # REST：列表/创建/详情/更新/提交/轮询/取消/删除
└── alembic/versions/
    ├── 20260202_add_video_gen_tasks.py      # 建表 video_gen_tasks
    └── 20260205_add_video_model_duration.py # 增加 model、duration 字段
```

### 2.2 前端

```
frontend/src/
├── api/
│   └── videoTask.ts                 # videoTaskApi：list/get/create/update/submit/poll/cancel/delete
├── types/
│   └── video-task.ts                # VideoGenTask、VideoTaskCreateInput、VideoModel、VideoDuration 等
├── constants/
│   └── video-task.ts                # VIDEO_TASK_MARKETPLACES、VIDEO_TASK_MARKETPLACE_FLAGS
├── pages/video-tasks/
│   ├── index.tsx                    # 创建页 + 当前任务进度（轮询）
│   ├── history.tsx                  # 历史列表（分页、筛选、详情入口）
│   └── components/
│       ├── create-form.tsx          # 创建表单：提示词、参考图、站点、模型、时长、提交
│       └── detail-dialog.tsx        # 任务详情弹窗：状态、结果、视频链接、操作
└── App.tsx                          # 路由：/video-tasks、/video-tasks/history
```

---

## 三、数据模型

### 3.1 库表：video_gen_tasks

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID, nullable | 注册用户 ID |
| anonymous_user_id | VARCHAR(100), nullable | 匿名用户 ID |
| session_id | UUID, nullable | 关联会话 |
| workflow_id | VARCHAR(100), nullable | 厂商工作流 ID |
| run_id | VARCHAR(100), nullable | 厂商运行 ID |
| status | VARCHAR(20) | pending / running / completed / failed / cancelled |
| prompt_text | TEXT, nullable | 提示词 |
| prompt_source | VARCHAR(50), nullable | 来源：user_provided / agent_generated / template |
| model | VARCHAR(50) | openai::sora1.0 / openai::sora2.0 |
| duration | INT | 5/10/15/20（sora1）；5/10/15（sora2） |
| reference_images | JSONB | 参考图 URL 数组 |
| marketplace | VARCHAR(10) | jp / us / de / uk / fr / it / es |
| result | JSONB, nullable | 厂商返回的完整结果（含 video_handle 等） |
| error_message | TEXT, nullable | 失败时的错误信息 |
| created_at / updated_at | TIMESTAMP | 审计时间 |

说明：`video_url` 不存库，由模型属性从 `result` 中解析（支持扁平或嵌套 `result.video_handle.generate_videos[0].video_url`）。

### 3.2 任务状态

| 状态 | 含义 |
|------|------|
| pending | 待提交到厂商 |
| running | 已提交，厂商生成中 |
| completed | 生成完成，可取 video_url |
| failed | 生成失败，有 error_message |
| cancelled | 已取消 |

### 3.3 厂商状态码（GIIKIN）

| 码 | 常量 | 含义 |
|----|------|------|
| 0 | - | 未知 |
| 1 | STATUS_RUNNING | 运行中 |
| 2 | STATUS_COMPLETED | 已完成 |
| 3 | STATUS_FAILED | 失败 |
| 4 | STATUS_CANCELED | 已取消 |
| 5 | STATUS_TERMINATED | 已终止 |
| 6 | STATUS_CONTINUED_AS_NEW | 已重新创建 |
| 7 | STATUS_TIMED_OUT | 超时 |

---

## 四、后端实现要点

### 4.1 配置（bootstrap/config.py）

```python
giikin_client_id: str | None = None
giikin_client_secret: str | None = None
giikin_base_url: str = "https://openapi.giikin.com"
```

环境变量见 `env.example`：`GIIKIN_CLIENT_ID`、`GIIKIN_CLIENT_SECRET`、`GIIKIN_BASE_URL`。

### 4.2 VideoAPIClient（video_api/client.py）

- **认证**：`_get_token()` 使用 client_credentials，Token 缓存至过期前 5 分钟。
- **提交**：`submit(prompt, reference_images, marketplace, model, duration)` → POST workflow/run，body 含 `workflow_type: amazon.material.image2video`、`inputs.video_handle.generate_videos[].config`（prompt/model/duration）、`image_urls`；返回 `(workflow_id, run_id)`。
- **查询**：`poll(workflow_id, run_id)` → GET workflow/query，返回 `(status, result)`；完成时 `result` 内含视频信息。
- **轮询直到结束**：`poll_until_complete(..., initial_delay=240, poll_interval=30, max_wait=900)`（可选，当前用例未用）。
- **工具方法**：`extract_video_url(result)` 从 `result.result.video_handle.generate_videos[0].video_url` 取 URL。

### 4.3 VideoTaskUseCase（application）

- **list_tasks(skip, limit, status)**：按所有权过滤，按创建时间倒序，返回 `(list[dict], total)`。
- **get_task(task_id)**：所有权校验，返回单任务 dict。
- **create_task(...)**：校验 user_id/anonymous_user_id、marketplace、model、duration；调用 repo.create；可选 `auto_submit` 时调用 `_submit_to_vendor`。
- **update_task(task_id, **kwargs)**：仅更新允许字段。
- **submit_task(task_id)**：仅 pending 且含 prompt_text 可提交；调用 `_submit_to_vendor`，写回 workflow_id、run_id、status=running。
- **poll_task(task_id, once)**：若已非 running/pending 直接返回当前状态；否则调用 `_poll_vendor`，根据厂商 status 更新 status/result/error_message，完成时清空 error_message。
- **cancel_task(task_id)**：仅 pending/running 可取消，置 status=cancelled。
- **_submit_to_vendor(task)**：VideoAPIClient.submit，写回 workflow_id、run_id、status；缺凭证或异常时占位或 status=failed、error_message。
- **_poll_vendor(task)**：VideoAPIClient.poll；status=2 完成写 result；3 或负数或 4/5/7 失败并写 error_message；异常时 status=failed。

### 4.4 VideoGenTask 模型（video_url）

- `video_url` 为属性：从 `self.result` 解析，支持 `result` 或 `result["result"]` 下 `video_handle.generate_videos[0].video_url`。

### 4.5 所有权与依赖

- 所有接口依赖 `AuthUser`；`_get_user_ids(current_user)` 得到 `(user_id, anonymous_user_id)`。
- `VideoGenTaskRepository` 继承 `OwnedRepositoryBase`，自动按 `user_id`/`anonymous_user_id` 过滤。
- `get_video_task_service(db)` 在 `libs.api.deps` 中定义，由 FastAPI 注入 `DbSession`。

---

## 五、REST API

基础路径：`/api/v1/video-tasks`（由 bootstrap/main 挂载）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | 列表，query: skip, limit, status |
| POST | / | 创建，body: VideoTaskCreate |
| GET | /{task_id} | 详情 |
| PATCH | /{task_id} | 更新，body: VideoTaskUpdate |
| POST | /{task_id}/submit | 提交到厂商 |
| POST | /{task_id}/poll | 轮询，query: once |
| POST | /{task_id}/cancel | 取消 |
| DELETE | /{task_id} | 仅 pending 可删（实现为取消） |

创建请求体示例（含 model/duration）：

```json
{
  "prompt_text": "产品展示视频...",
  "prompt_source": "user_provided",
  "reference_images": ["https://example.com/img.jpg"],
  "marketplace": "jp",
  "model": "openai::sora1.0",
  "duration": 5,
  "auto_submit": true
}
```

响应字段与 `VideoTaskResponse` 一致（id、status、workflow_id、run_id、model、duration、result、error_message、video_url、created_at、updated_at 等）。

---

## 六、前端实现要点

### 6.1 API 层（api/videoTask.ts）

- `BackendVideoTask` / `BackendVideoTaskListResponse`：与后端 snake_case 一致。
- `toFrontendVideoTask`：转 camelCase，含 videoUrl。
- `toBackendCreateRequest` / `toBackendUpdateRequest`：提交/更新时转 snake_case，默认 model、duration。
- `videoTaskApi`：list(options)、get(id)、create(data)、update(id, data)、submit(id)、poll(id, once)、cancel(id)、delete(id)。

### 6.2 类型与常量

- **types/video-task.ts**：VideoTaskStatus、VideoModel、VideoDuration、VideoGenTask、VideoTaskCreateInput、VideoTaskUpdateInput、VideoTaskListResponse。
- **constants/video-task.ts**：VIDEO_TASK_MARKETPLACES（value/label/flag）、VIDEO_TASK_MARKETPLACE_FLAGS；create-form、history、detail-dialog 共用。

### 6.3 页面与组件

- **index.tsx**：欢迎区 + 示例提示 + CreateForm；创建后展示当前任务进度（TaskProgress），轮询使用 `videoTaskApi.poll(id, true)` + refetchInterval；可跳转历史。
- **create-form.tsx**：提示词、参考图（多行 URL、缩略图与删除）、站点/模型/时长下拉、提交；创建时传 model、duration、autoSubmit: true。
- **history.tsx**：列表分页与状态筛选、卡片展示（站点、状态、时间）、详情弹窗、取消等操作。
- **detail-dialog.tsx**：展示任务详情、状态、result、video_url（链接）、error_message；可触发提交/轮询/取消。

### 6.4 路由

- `/video-tasks` → VideoTasksPage
- `/video-tasks/history` → VideoTasksHistoryPage

---

## 七、Agent 工具

### 7.1 amazon_video_submit

- **参数**：prompt（必填）、reference_images、marketplace、session_id。
- **实现**：获取权限上下文与 DB 会话，调用 `VideoTaskUseCase.create_task(..., prompt_source="agent_generated", auto_submit=True)`；未传 model/duration，使用后端默认（sora1.0、5s）。
- **返回**：task_id、workflow_id、run_id、status、message。

### 7.2 amazon_video_poll

- **参数**：task_id（必填）、once。
- **实现**：同 use case 的 poll_task，返回最新任务状态（含 status、video_url、error_message 等）。

### 7.3 amazon_product_research

- **参数**：product_link、extra_description、reference_images。
- **实现**：至少填一项；返回结构化「调研指引」JSON，供 Agent 使用 web_fetch 等工具自行完成调研并生成报告。

### 7.4 amazon_competitor_research

- **参数**：competitor_link、competitor_description。
- **实现**：至少填一项；返回结构化「竞品调研指引」JSON，由 Agent 后续完成分析。

---

## 七.5 llm-server MCP 工具（视频任务）

通过 **llm-server** 暴露的 Streamable HTTP MCP 提供两个原生工具，封装与 Web 端相同的视频任务后端接口，供 Cursor 等 MCP 客户端调用。调用方需使用带 `mcp:llm-server` 权限的 API Key 认证。

### video_create_task

- **参数**：prompt（必填）、reference_images、marketplace、model、duration、auto_submit。
- **实现**：从 MCP 上下文取 `user_id`，设置 `PermissionContext` 后调用 `VideoTaskUseCase.create_task`（与 REST 创建任务一致），返回 JSON 字符串。
- **返回**：success、id、status、workflow_id、run_id、message；失败时 success=false、error。

### video_poll_task

- **参数**：task_id（必填，UUID 字符串）。
- **实现**：校验 user_id 与 task_id 格式，设置 `PermissionContext` 后调用 `VideoTaskUseCase.poll_task(task_id, once=True)`，向厂商拉取一次并更新库。
- **返回**：success、id、status、workflow_id、run_id、video_url、error_message；失败时 success=false、error。

定义位置：`backend/domains/agent/infrastructure/mcp_server/servers/llm_server.py`。

---

## 八、数据库迁移

- `20260202_add_video_gen_tasks.py`：创建 `video_gen_tasks` 表（含上述字段，不含 model/duration）。
- `20260205_add_video_model_duration.py`：为 `video_gen_tasks` 增加 `model`、`duration` 列（含 server_default）。

执行：`cd backend && alembic upgrade head`。

---

## 九、配置与运行

### 9.1 环境变量（.env）

```bash
# GIIKIN 视频生成 API
GIIKIN_CLIENT_ID=your-giikin-client-id
GIIKIN_CLIENT_SECRET=your-giikin-client-secret
GIIKIN_BASE_URL=https://openapi.giikin.com
```

### 9.2 注意事项

- Token：VideoAPIClient 自动缓存并刷新 OAuth2 token。
- 轮询：前端按需调用 poll（如每 5 秒）；后端单次 poll 即向厂商查一次并更新库。
- 完成时：`result` 写入库，`video_url` 由模型属性从 result 解析，API 响应中包含 `video_url`。
- 失败时：`status=failed`，`error_message` 从厂商 result 的 message/error_message/error 或异常信息写入。
- 删除：仅 pending 可删，实现为取消任务。

---

## 十、相关文档

- **AMAZON_VIDEO_INTEGRATION.md**（backend/docs）：集成概述与使用流程，与本实现文档互补。
- **CODE_CHECK_REPORT.md**（docs）：代码检查中与视频任务相关的结论与修复记录。

---

*文档覆盖截至当前代码库的视频生成方案与实现，后续若有接口或表结构变更请同步更新本文档。*
