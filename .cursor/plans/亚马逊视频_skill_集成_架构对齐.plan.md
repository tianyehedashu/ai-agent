---
name: 亚马逊视频集成
overview: 单一最佳方案：任务域 + 本库视频 API + 内置工具 + MCP + 前端任务列表 + 产品/竞品调研工具 + MCP 提示词 + LangChain Deep Agents 多 Agent 编排；不复用原 Skill 脚本与模板，完全在本项目内按当前架构实现。
todos: []
isProject: false
---

# 亚马逊视频集成计划（单一方案 + 详细执行计划）

## 一、采用的最佳方案（唯一方案）


| 维度          | 采用方案                                | 说明                                                                                                                                                                                                          |
| ----------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **提交/轮询**   | 本库服务直调厂商 API                        | Agent 域内 video API 客户端（httpx）直调 GIIKIN 等厂商接口；无外部脚本。                                                                                                                                                         |
| **多 Agent** | LangChain Deep Agents（`deepagents`） | 引入 [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)，编排 Agent 使用 write_todos、task 委托产品/竞品/分镜子 Agent，调用 amazon_video_submit / amazon_video_poll；与现有 LangGraph checkpointer、memory 对接。 |
| **产品/竞品调研** | 调研工具                                | 内置工具 `amazon_product_research`、`amazon_competitor_research`，入参 link/描述，返回结构化摘要；工具内可调用 LLM 总结或复用 WebFetch，子 Agent 或编排 Agent 调用后在对话中展示。                                                                       |
| **提示词与模板**  | MCP 动态 Prompt                       | 复用现有 MCP 动态 Prompt，server_id=amazon_video_prompts；模板 list/get/add/update/remove 在本库配置，前端提示词管理对该 server 做列表与编辑。                                                                                              |
| **任务与前端**   | 任务域 + 任务列表页                         | 表 video_gen_tasks，API list/get/create/update/poll；前端 /video-tasks 列表 + 详情 + 轮询，snake_case → camelCase。                                                                                                      |


不复用原 Skill 的 run_video_gen.py、poll_results.py 及 references/*.md；全部在本项目内实现。

---

## 二、技术栈与 DRY 复用（必须遵守）

- **后端**：模型继承 `libs.orm.base.BaseModel` + `OwnedMixin`；仓储继承 `libs.db.base_repository.OwnedRepositoryBase[VideoGenTask]`；路由用 `AuthUser`、`Depends(get_video_task_service)`；异常用 `backend/exceptions.py`；列表 API 用 skip/limit。
- **前端**：使用 `apiClient`、toFrontendXxx(backend)、`@/types`、TanStack Query。
- **工具**：继承 `BaseTool`、`@register_tool`；视频工具调用本库视频 API 服务，不加入 SANDBOX_AWARE_TOOLS。

---

## 三、详细执行计划（按阶段与步骤）

### Phase 1：任务域（模型、仓储、UseCase、API、迁移）


| 步骤  | 内容                                                                                                                                                                                                                                                                                              | 产出/验收                                      |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| 1.1 | 新增模型 `backend/domains/agent/infrastructure/models/video_gen_task.py`：继承 `BaseModel` + `OwnedMixin`，表名 `video_gen_tasks`，字段 id、user_id、anonymous_user_id、session_id、workflow_id、run_id、status、prompt_text、prompt_source、reference_images(JSONB)、marketplace、result(JSONB)、created_at、updated_at。 | 模型可被 Alembic 发现，无 lint 报错。                 |
| 1.2 | 新增 Alembic 迁移 `backend/alembic/versions/xxx_add_video_gen_tasks.py`：创建表 video_gen_tasks，含上述字段及 FK(user_id → users.id)。                                                                                                                                                                          | `alembic upgrade head` 成功，表存在。             |
| 1.3 | 新增仓储 `backend/domains/agent/infrastructure/repositories/video_gen_task_repository.py`：继承 `OwnedRepositoryBase[VideoGenTask]`，实现 `model_class`、`anonymous_user_id_column`；重写 `create` 方法（入参业务字段），其余复用 find_owned/get_owned/count_owned。                                                          | 可通过 repo.create/find_owned/get_owned 操作任务。 |
| 1.4 | 新增 UseCase `backend/domains/agent/application/video_task_use_case.py`：`VideoTaskUseCase(db)`，依赖 `VideoGenTaskRepository`；实现 list(skip, limit, status)、get(id)、create(...)、update(id, **kwargs)、poll_once(id)（内部调视频 API 轮询并更新任务）。poll_once 暂可仅更新占位，待 Phase 2 接入真实 API。                           | 单元测试或手工调用 list/get/create/update 通过。       |
| 1.5 | 在 `libs.api.deps` 中新增 `get_video_task_service(db: DbSession) -> VideoTaskUseCase`。                                                                                                                                                                                                              | 可 `Depends(get_video_task_service)`。       |
| 1.6 | 新增路由 `backend/domains/agent/presentation/video_task_router.py`：prefix `/video-tasks`，AuthUser + Depends(get_video_task_service)；实现 GET /（skip, limit, status）、GET /{id}、POST /（Body 创建）、PATCH /{id}、POST /{id}/poll；Request/Response 用 Pydantic，snake_case；归属校验用 repository.get_owned。          | 接口返回符合 Schema，401/403/404 正确。              |
| 1.7 | 在 `bootstrap/main.py` 中 `include_router(video_task_router, prefix=api_router_prefix, tags=["Video Tasks"])`。                                                                                                                                                                                    | GET /api/v1/video-tasks 可访问（需认证）。          |


### Phase 2：视频 API 服务与内置工具


| 步骤  | 内容                                                                                                                                                                                                                                                                                                                                              | 产出/验收                                              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| 2.1 | 新增视频 API 客户端 `backend/domains/agent/infrastructure/video_api/client.py`（或放在 VideoTaskUseCase 同模块内）：封装提交接口与状态/轮询接口，使用 httpx 直调 GIIKIN（或当前厂商）API；凭证从环境变量读取（如 GIIKIN_CLIENT_ID、GIIKIN_CLIENT_SECRET）；提供 `submit(prompt, reference_images, marketplace) -> (workflow_id, run_id)`、`poll(workflow_id, run_id) -> (status, result)`。需对接厂商文档实现请求/响应解析。 | 单元测试或手工调用 submit/poll 能拿到厂商返回。                     |
| 2.2 | 在 VideoTaskUseCase.create 中调用视频 API 客户端 submit，将返回的 workflow_id、run_id 写入任务，status 置为 running；在 poll_once(id) 中根据任务 workflow_id/run_id 调用 poll，更新 status、result。                                                                                                                                                                                | 创建任务后能拿到 workflow_id/run_id；poll 后任务状态与 result 更新。 |
| 2.3 | 新增内置工具 `backend/domains/agent/infrastructure/tools/amazon_video_tools.py`：`AmazonVideoSubmitTool`、`AmazonVideoPollTool`，继承 BaseTool，@register_tool；Submit 参数 prompt、reference_images、marketplace、task_id(可选)；Poll 参数 workflow_id、run_id、once；execute 内调用 VideoTaskUseCase 或直接调用视频 API 服务（需注入，可通过工具构造函数或全局 get 获取）。                              | 工具在 registry 中可见，execute 返回 ToolResult。            |
| 2.4 | 在 `backend/domains/agent/infrastructure/tools/__init__.py` 中 `import amazon_video_tools`；不加入 SANDBOX_AWARE_TOOLS。                                                                                                                                                                                                                               | 默认 tools.enabled 包含时，对话可调用两工具。                     |
| 2.5 | 在 env.example 中增加 GIIKIN_CLIENT_ID、GIIKIN_CLIENT_SECRET（或厂商约定）说明。                                                                                                                                                                                                                                                                               | 文档完整。                                              |


### Phase 3：前端任务列表（API、类型、页面、路由）


| 步骤  | 内容                                                                                                                                                                                                                                                                                                    | 产出/验收                    |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| 3.1 | 新增类型 `frontend/src/types/video-task.ts`：接口 VideoGenTask（id, status, promptText, promptSource, result, workflowId, runId, createdAt, updatedAt 等 camelCase）；列表项可定义 VideoGenTaskSummary。                                                                                                                | 类型无 any，可被 api 层引用。      |
| 3.2 | 新增 API `frontend/src/api/videoTask.ts`：定义 BackendVideoGenTask，实现 toFrontendVideoTask(backend)；封装 listVideoTasks({ skip, limit, status })、getVideoTask(id)、createVideoTask(body)、updateVideoTask(id, body)、pollVideoTask(id)，使用 apiClient，路径 /api/v1/video-tasks，请求/响应做 snake_case ↔ camelCase 转换。     | 接口与后端契约一致，转换正确。          |
| 3.3 | 新增页面 `frontend/src/pages/video-tasks/index.tsx`：列表（useQuery listVideoTasks，表格或卡片展示 id、status、prompt 摘要、createdAt、result 摘要）；支持按 status 筛选、skip/limit 分页；点击行进入详情或展开详情。详情区展示 promptText、status、workflowId、runId、result（含 videoUrl）；status 为 running 时定时调用 pollVideoTask(id) 直到 completed/failed；展示视频链接。 | 列表与详情展示正常，轮询后状态与视频链接更新。  |
| 3.4 | 在 `frontend/src/App.tsx` 中增加 `Route path="/video-tasks" element={<VideoTasksPage />}`；在 `frontend/src/components/layout/sidebar.tsx` 的 navigation 中增加 `{ name: '视频任务', href: '/video-tasks', icon: List }`（或合适图标）。                                                                                    | 侧栏可进入 /video-tasks，路由正常。 |


### Phase 4：MCP 支持


| 步骤  | 内容                                                                                                                                                                                | 产出/验收                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| 4.1 | 在 `backend/domains/agent/domain/mcp/dynamic_tool.py` 的 `DynamicToolType` 中增加 `AMAZON_VIDEO_SUBMIT`、`AMAZON_VIDEO_POLL`。                                                           | 枚举可被 UseCase 与工厂使用。         |
| 4.2 | 在 `backend/domains/agent/infrastructure/mcp_server/dynamic_tool_factory.py` 的 `build_tool_fn` 中分支上述两类型：内部调用本库视频提交/轮询服务（与 Phase 2 的客户端或 UseCase 一致），config 可含厂商端点等；参数从 MCP 工具入参传入。 | MCP 动态工具添加该类型后，调用行为与内置工具一致。 |
| 4.3 | 在 `backend/domains/agent/application/mcp_dynamic_tool_use_case.py` 的 tool_type 校验中允许 `AMAZON_VIDEO_SUBMIT`、`AMAZON_VIDEO_POLL`。                                                   | 管理端可添加/更新该类型动态工具。           |


### Phase 5：产品/竞品调研工具


| 步骤  | 内容                                                                                                                                                                                                                                       | 产出/验收                     |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| 5.1 | 新增内置工具 `amazon_product_research`：入参 product_link、extra_description（可选）；描述为「根据产品链接或描述生成产品调研摘要（品类、卖点、使用场景、目标人群）」；execute 内可调用 LLM 总结（或复用现有 WebFetch 抓取页面后再 LLM 总结），返回结构化摘要字符串。工具放在 `amazon_video_tools.py` 或新建 `amazon_research_tools.py`。 | 工具可被 Agent 调用，返回可读摘要。     |
| 5.2 | 新增内置工具 `amazon_competitor_research`：入参 competitor_link 或 competitor_description；描述为「根据竞品链接或描述生成竞品调研摘要（优缺点、差异化点）」；execute 内同样 LLM 总结或 WebFetch+LLM。                                                                                       | 同上。                       |
| 5.3 | 在 tools/**init**.py 中 import 上述模块；在 execution config 的 tools.enabled 中可配置两工具名。                                                                                                                                                           | 编排 Agent 或单 Agent 可使用两工具。 |


### Phase 6：提示词（MCP 动态 Prompt）


| 步骤  | 内容                                                                                                                                                                               | 产出/验收                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| 6.1 | 在 MCP 动态 Prompt 中为「亚马逊视频」配置 server_id=amazon_video_prompts（或使用现有 streamable_http 下某 server）：通过管理 API 或 seed 数据添加若干条 prompt 模板（如「分镜设计」「输入收集说明」），template 与 arguments_schema 按需配置。 | 可通过 list_dynamic_prompts(server_id) 查到模板。 |
| 6.2 | 前端若有「提示词管理」页，支持对 server_id=amazon_video_prompts 的 prompts 做列表与编辑；任务创建/编辑页支持从模板选择并带入 prompt_text 再编辑（可选，可与 Phase 3 一起做）。                                                          | 可选验收。                                     |


### Phase 7：LangChain Deep Agents 集成


| 步骤  | 内容                                                                                                                                                                                                                                                                                                                                                                 | 产出/验收                                      |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| 7.1 | 在 `backend/pyproject.toml` 中增加依赖 `deepagents`（版本按 PyPI 与 LangGraph 兼容性选择）；安装后确认与现有 langgraph、langchain-core 无冲突。                                                                                                                                                                                                                                                   | `pip install -e .` 成功，无版本冲突。               |
| 7.2 | 阅读 [Deep Agents Quickstart](https://docs.langchain.com/oss/python/deepagents/quickstart) 与 [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)：在本项目中创建「亚马逊视频」Deep Agent 图，编排 Agent 具备 write_todos、task 工具及 amazon_video_submit、amazon_video_poll、amazon_product_research、amazon_competitor_research；通过 task 工具将产品调研、竞品调研、分镜设计委托给子 Agent 或等价节点。 | 本地可运行 Deep Agent 图，完成一次「输入→调研→分镜→确认→提交」流程。 |
| 7.3 | 将 Deep Agent 图与现有 checkpointer、memory 对接：使用与 [LangGraphAgentEngine](backend/domains/agent/infrastructure/engine/langgraph_agent.py) 相同的 thread_id（=session_id）、checkpointer、以及现有 LongTermMemoryStore 或 Deep Agents 自带的 Store。                                                                                                                                      | 对话恢复、记忆与现有会话一致。                            |
| 7.4 | 在 ChatUseCase 中根据「亚马逊视频」Agent 或用户意图路由到 Deep Agent 图：当 session 关联的 agent_id 为亚马逊视频或检测到视频生成意图时，使用 Deep Agent 图执行而非 LangGraphAgentEngine；流式输出与事件格式与现有 chat 接口保持一致。                                                                                                                                                                                                    | 选择「亚马逊视频」会话时，走 Deep Agent 流程，前端无感。         |
| 7.5 | 配置「亚马逊视频」Agent（DB 或配置）：name、tools 列表含 amazon_video_submit、amazon_video_poll、amazon_product_research、amazon_competitor_research；system_prompt 中写明流程（输入收集→产品调研→竞品调研→分镜→A/B 确认→仅选 A 时提交）；execution config 的 tools.enabled 包含上述工具。                                                                                                                                     | 新建会话选该 Agent 时，走 Deep Agent 并展示正确流程。       |


### Phase 8：联调与收尾


| 步骤  | 内容                                                                                                         | 产出/验收          |
| --- | ---------------------------------------------------------------------------------------------------------- | -------------- |
| 8.1 | 端到端联调：从前端进入「亚马逊视频」会话 → 输入关键词/链接 → 编排 Agent 规划 → 产品/竞品调研 → 分镜展示 → 用户选 A → 提交 → 任务列表出现任务 → 轮询至完成 → 详情展示视频链接。 | 全流程无报错，结果符合预期。 |
| 8.2 | 任务列表页：创建任务（从对话外）支持用户直接填入 prompt、选择模板编辑后提交；与对话内提交的任务在同一列表展示。                                                | 两种入口任务均可见、可轮询。 |
| 8.3 | 单元测试：VideoTaskUseCase、video_api 客户端、amazon_video_tools 关键路径；MCP build_tool_fn 分支。                          | 关键用例有覆盖，CI 通过。 |
| 8.4 | 文档：在项目 README 或 docs 中简述「亚马逊视频」能力、环境变量（GIIKIN_*）、任务列表与 Deep Agents 路由。                                     | 新人可按文档跑通。      |


---

## 四、依赖关系与建议顺序

- Phase 1 为所有后端能力基础，必须先完成。
- Phase 2 依赖 Phase 1（UseCase 需调视频 API 与任务表）；Phase 3 依赖 Phase 1（API 已就绪）。
- Phase 4 依赖 Phase 2（MCP 工具调用同一视频服务）；Phase 5 可与 Phase 2 并行或稍后。
- Phase 6 可与 Phase 3 并行；Phase 7 依赖 Phase 2、5（工具已就绪），且需 Phase 1 的 session/归属。
- Phase 8 在 Phase 1–7 完成后进行。

建议实施顺序：**1 → 2 → 3 → 4 → 5 → 6 → 7 → 8**；其中 3 与 4、5 与 6 可适当并行。

---

## 五、实施要点汇总表（单页速查）


| 模块           | 路径/要点                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------- |
| 模型与迁移        | `domains/agent/infrastructure/models/video_gen_task.py`（BaseModel+OwnedMixin）；Alembic 新版本                     |
| 仓储           | `domains/agent/infrastructure/repositories/video_gen_task_repository.py`（OwnedRepositoryBase[VideoGenTask]）   |
| UseCase      | `domains/agent/application/video_task_use_case.py`（list/get/create/update/poll_once）                          |
| 依赖注入         | `libs.api.deps` 新增 get_video_task_service                                                                     |
| 路由           | `domains/agent/presentation/video_task_router.py`，prefix /video-tasks                                         |
| 挂载           | bootstrap/main.py include_router(video_task_router)                                                           |
| 视频 API       | `domains/agent/infrastructure/video_api/client.py` 或 UseCase 内封装，httpx 直调厂商 API                               |
| 内置工具         | `domains/agent/infrastructure/tools/amazon_video_tools.py`（submit/poll）+ 调研工具（product/competitor）             |
| MCP          | DynamicToolType 新增 AMAZON_VIDEO_SUBMIT/POLL；build_tool_fn 分支；UseCase 校验                                       |
| 前端 API/类型/页面 | `frontend/src/api/videoTask.ts`、`frontend/src/types/video-task.ts`、`frontend/src/pages/video-tasks/index.tsx` |
| 路由与侧栏        | App.tsx /video-tasks；sidebar「视频任务」                                                                            |
| 提示词          | MCP 动态 Prompt，server_id=amazon_video_prompts                                                                  |
| 多 Agent      | LangChain Deep Agents（deepagents），编排 Agent + write_todos + task 子 Agent + 上述工具；ChatUseCase 路由到 Deep Agent 图   |


按上述单一方案与详细执行计划实施后，视频生成能力将完全在本项目内实现，多 Agent 由 Deep Agents 负责编排与委托，任务、工具、MCP、前端与现有架构一致。