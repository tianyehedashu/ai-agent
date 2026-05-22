# 产品信息 AI 生成 - 完整实施计划

> 本文档整合产品信息 AI 生成页面的功能、原子能力、Job/Step 串联、提示词模板、一键异步 API 与后台查看等设计，形成可执行的实施计划。

**目标**：新增「产品信息 AI 生成」页面与后端能力，支持产品/竞品链接、名称、关键词、图片输入，拆分为原子能力（图片分析、商品链接分析、竞品链接分析、视频脚本、8 图提示词），每项能力提示词可编辑/保存/恢复模板，步骤间结果复用，支持 8 图生成与视频生成（复用现有），持久化与图片预览，并提供外部一键异步调用与后台查看。

**架构**：Agent 域内；Job + Step 模型串联原子能力；模板按能力维度管理；一键 API 仅异步，通过 Job 详情后台查看。

**技术栈**：后端 Python/FastAPI/SQLAlchemy，前端 React/TypeScript/TanStack Query/Tailwind。

---

## 一、功能与设计摘要

### 1.1 原子能力列表

| capability_id | 名称 | 输入 | 输出 | 依赖前步 |
|--------------|------|------|------|----------|
| image_analysis | 图片分析 | image_urls | image_descriptions[] | 无 |
| product_link_analysis | 商品链接分析 | product_link, product_name?, keywords? | product_info | 无 |
| competitor_link_analysis | 竞品链接分析 | competitor_link | competitor_info | 无 |
| video_script | 视频脚本/分镜 | product_info, competitor_info?, keywords? | script/storyboard | Step 2,3 |
| image_gen_prompts | 8 图生成提示词 | product_info, script?, 风格等 | prompts[8]（第 1 条白底） | Step 2,4 |

### 1.2 串联与复用

- 一个 **Job** 包含多个 **Step**，按 sort_order 顺序执行。
- 执行某步时，后端自动将前面步骤的 `output_snapshot` 注入当前步输入。
- 8 图生成、视频生成复用现有 API，可从 Job 的 Step 输出中取提示词/参考图。

### 1.3 提示词管理（每能力）

- **系统默认模板**：只读，用于「恢复模板」。
- **用户模板**：可 CRUD，按 capability_id 归属。
- 前端：编辑当前提示词 → 保存为模板 / 恢复为默认 / 从模板选择。

### 1.4 外部一键调用

- **POST /api/v1/product-info/run**：仅异步。创建 Job、后台执行各步，立即返回 job_id 与 poll_url。
- **GET /api/v1/product-info/jobs/{job_id}**：后台查看进度与结果，供前端与外部轮询。

### 1.5 持久化与预览

- Job、Step、用户模板、8 图生成任务均持久化。
- 输入图片与生成的 8 图均以 URL 存储，前端在输入区、结果区、历史详情中统一做图片预览。

### 1.6 工作流定位与是否使用 LangGraph

**是否算工作流**：是。产品信息管道（图片分析 → 商品链接分析 → 竞品分析 → 视频脚本 → 8 图提示词）是一条**有顺序、有数据依赖的工作流**，只是当前为线性管道，无分支/循环。

**是否必须用 LangGraph**：不必。两种实现方式均可：

| 方式 | 说明 | 适用 |
|------|------|------|
| **应用层编排（当前计划）** | 在 ProductInfoUseCase 中按顺序调用各能力、把前步 output 注入下一步；持久化仍用 Job/Step 表。 | 首版、实现简单、易排查；线性管道足够。 |
| **LangGraph 实现** | 将管道建模为 LangGraph：每能力一个节点，状态为共享 state（inputs + 各步 output）；边为线性或按条件跳转。执行 = 调用 graph.invoke；持久化可在每节点后写 Step 或使用 LangGraph checkpointer。 | 与现有对话 Agent（[langgraph_agent](backend/domains/agent/infrastructure/engine/langgraph_agent.py)）统一；后续若需「脚本确认后再生成 8 图」等人机交互，可加 interrupt 节点。 |

**建议**：

- **首版**：采用应用层编排即可，不强制引入 LangGraph，按现有实施计划推进。
- **若希望与 Agent 域统一、或预留人机交互**：可在 Phase 2 将「管道执行」改为基于 LangGraph 的线性图（StateGraph，节点 = 各 capability 执行函数，state = 当前 Job 的 inputs + 已完成的 step 的 output_snapshot），Job/Step 表仍保留用于列表、详情与后台查看；图只负责执行与可选检查点。

**LangGraph 可选方案（若采用）**：

- 定义状态 TypedDict：含 `job_id`, `inputs`, `image_descriptions`, `product_info`, `competitor_info`, `video_script`, `image_gen_prompts`, `current_step`, `error`。
- 节点：`node_image_analysis`, `node_product_link_analysis`, … 每个节点读 state、调对应能力、写回 state 并持久化到 Step。
- 边：START → image_analysis → product_link_analysis → competitor_link_analysis → video_script → image_gen_prompts → END（或根据 steps 参数动态加边）。
- 一键 run：创建 Job 后，`graph.ainvoke(initial_state, config=…)` 在后台执行；外部仍通过 GET job 详情查看进度（可从 Step 表汇总，或从 checkpointer 读）。

---

## 二、数据模型与迁移

### 2.1 表结构

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| product_info_jobs | 工作流实例 | id, user_id, anonymous_user_id, session_id, title, status, created_at, updated_at |
| product_info_job_steps | 步骤执行记录 | id, job_id, sort_order, capability_id, input_snapshot, output_snapshot, prompt_used, prompt_template_id, status, error_message |
| product_info_prompt_templates | 用户提示词模板 | id, user_id, anonymous_user_id, capability_id, name, content, prompts(JSON，仅 image_gen_prompts), created_at, updated_at |
| product_image_gen_tasks | 8 图生成任务 | id, user_id, anonymous_user_id, job_id(可选), step_id(可选), status, prompts(JSONB), result_images(JSONB), error_message |

- Job.status：draft | running | completed | failed | partial  
- Step.status：pending | running | completed | failed  
- 所有权：Job/Step/模板/8图任务均带 user_id 或 anonymous_user_id，与现有 VideoGenTask 一致。

### 2.2 系统默认提示词

- 每个 capability_id 对应一条默认提示词，存配置或代码常量，不落库；通过 API 只读返回。

### 2.3 迁移脚本

- 新建 Alembic 迁移：创建上述四张表及索引（job_id, user_id, capability_id 等）。
- 位置：`backend/alembic/versions/`。

---

## 三、后端实施计划

### Phase 1：基础设施与模型

**Task 1.1 域内目录与常量**

- 在 `backend/domains/agent/` 下确认或新增：
  - `application/product_info_use_case.py`（Job/Step 编排、步骤执行、依赖解析）
  - `application/product_info_prompt_service.py`（默认模板读取、用户模板 CRUD）
  - `infrastructure/models/product_info_job.py`、`product_info_job_step.py`、`product_info_prompt_template.py`
  - `infrastructure/models/product_image_gen_task.py`（若尚未存在）
  - `infrastructure/repositories/` 对应 Repository
- 定义常量：`CAPABILITY_IDS`、各能力的默认提示词（或从配置文件加载）。

**Task 1.2 ORM 模型**

- 实现 ProductInfoJob、ProductInfoJobStep、ProductInfoPromptTemplate、ProductImageGenTask（含 OwnedMixin、外键、JSONB 字段）。
- 在 `domains/agent/infrastructure/models/__init__.py` 中导出。

**Task 1.3 Alembic 迁移**

- 编写迁移脚本，创建四张表及必要索引，执行验证。

**Task 1.4 Repository 层**

- ProductInfoJobRepository、ProductInfoJobStepRepository、ProductInfoPromptTemplateRepository、ProductImageGenTaskRepository（若与现有 video 任务分离则新建）。
- 提供 create/get/list/update 等基础方法，按 user_id/anonymous_user_id 过滤。

---

### Phase 2：原子能力执行与依赖注入

**Task 2.1 能力执行器**

- 为每个 capability_id 实现执行逻辑（调用 LLM/Vision、爬虫等）：
  - image_analysis：Vision + 提示词 → image_descriptions
  - product_link_analysis：抓取链接 + LLM → product_info
  - competitor_link_analysis：同上 → competitor_info
  - video_script：LLM(product_info, competitor_info, keywords) → script
  - image_gen_prompts：LLM(product_info, script) → 8 条 prompt（第 1 条白底）
- 入参/出参使用明确的结构体或 dict 约定，便于写入 Step 的 input_snapshot/output_snapshot。

**Task 2.2 依赖矩阵**

- 在配置或代码中定义：每个 capability_id 依赖哪些 step 的 output（如 video_script 依赖 step 2、3）。
- ProductInfoUseCase 中：根据 job 内已完成的 step 的 output_snapshot 拼装当前步的完整输入。

**Task 2.3 单步执行 API 与 UseCase**

- ProductInfoUseCase.run_step(job_id, capability_id, sort_order, user_input, prompt, prompt_template_id)：
  - 解析依赖，注入前步 output；
  - 调用对应能力执行器；
  - 写入 Step 的 input_snapshot、output_snapshot、status。
- 暴露为 **POST /api/v1/product-info/jobs/{job_id}/steps**（或 PATCH 重跑某步），Request Body 含 capability_id、sort_order、user_input、prompt、prompt_template_id。

---

### Phase 3：Job 与模板 API

**Task 3.1 Job CRUD**

- POST /api/v1/product-info/jobs：创建 Job（可选 title、session_id）。
- GET /api/v1/product-info/jobs：列表，分页，按 user、session_id、status 筛选。
- GET /api/v1/product-info/jobs/{job_id}：详情，含 steps[]（含 input_snapshot、output_snapshot），用于后台查看与前端展示。
- DELETE /api/v1/product-info/jobs/{job_id}：删除 Job（及关联 Step）。

**Task 3.2 能力与默认提示词**

- GET /api/v1/product-info/capabilities：返回能力列表（id, name, description, 输入输出简述）。
- GET /api/v1/product-info/capabilities/{capability_id}/default-prompt：返回系统默认提示词（用于恢复模板）。

**Task 3.3 用户模板 CRUD**

- GET /api/v1/product-info/capabilities/{capability_id}/templates：该能力下用户模板列表（可选含一条 is_system 的默认占位）。
- POST /api/v1/product-info/capabilities/{capability_id}/templates：保存为新用户模板（name, content 或 prompts）。
- PATCH /api/v1/product-info/templates/{template_id}：更新用户模板。
- DELETE /api/v1/product-info/templates/{template_id}：删除用户模板（仅本人）。

---

### Phase 4：一键异步与 8 图/上传

**Task 4.1 一键异步 API**

- POST /api/v1/product-info/run：
  - Body：inputs（product_link, competitor_link, product_name, keywords, image_urls）, steps（可选，默认全部）, prompts / prompt_template_ids 按能力覆盖, session_id。
  - 行为：创建 Job；将各 Step 提交到后台任务队列（或 asyncio.create_task/后台线程），立即返回 202。
  - Response：job_id, status: "running", message, poll_url: "/api/v1/product-info/jobs/{job_id}"。
- 后台执行逻辑：按 steps 顺序依次 run_step，更新 Job.status（全部完成=completed，任一步失败=failed 或 partial）。

**Task 4.2 8 图生成任务**

- POST /api/v1/product-info/image-gen：请求体含 8 条 prompt（或从 Step 5 的 output 填充）、model/size 等；创建 ProductImageGenTask，调用现有 ImageGenerator 生成 8 张图，写入 result_images。
- GET /api/v1/product-info/image-gen、GET /api/v1/product-info/image-gen/{task_id}：列表与详情（含 result_images 供预览）。

**Task 4.3 图片上传**

- POST /api/v1/product-info/upload：multipart/form-data，file；落盘或对象存储，返回 { url, content_type, size_bytes }。用于输入区与历史预览。

---

### Phase 5：路由注册与依赖注入

**Task 5.1 product_info_router**

- 新建 `backend/domains/agent/presentation/product_info_router.py`，汇总上述所有端点，使用 AuthUser、get_product_info_service、get_prompt_template_service 等依赖。
- 在 `bootstrap/main.py` 中：`app.include_router(product_info_router, prefix=f"{api_router_prefix}/product-info", tags=["Product Info"])`。

**Task 5.2 服务工厂**

- 在 `libs/api/deps.py`（或域内）提供 get_product_info_service、get_prompt_template_service，注入 DB Session 与依赖。

---

## 四、前端实施计划

### Phase 1：路由、类型与 API 客户端

**Task 1.1 类型定义**

- 新建 `frontend/src/types/product-info.ts`：Job、Step、Capability、PromptTemplate、ImageGenTask、RunRequest、UploadResponse 等，与后端 Schema 对齐。

**Task 1.2 API 客户端**

- 新建 `frontend/src/api/productInfo.ts`：jobs（list, get, create, delete）、run（one-click）、steps（run step）、capabilities（list, defaultPrompt）、templates（list, create, update, delete）、imageGen（list, get, create）、upload。使用现有 auth client 与 base URL。

**Task 1.3 路由与导航**

- 在 App.tsx 增加 `/product-info` 路由，指向 ProductInfoPage。
- 在 sidebar 导航中增加「产品信息」入口（与视频、工作台等并列）。

---

### Phase 2：页面骨架与输入区

**Task 2.1 页面骨架**

- 新建 `frontend/src/pages/product-info/index.tsx`：Tab 或 Step 容器（建议 Tab：输入与分析、8 图生成、视频生成、历史）。
- 顶部或侧边展示当前 Job 与步骤进度（若已创建 Job）。

**Task 2.2 输入区组件**

- 组件：产品链接、竞品链接、产品名称、关键词、图片上传（多张）。
- 图片上传调用 upload API，展示预览（缩略图、删除）；URL 存入 state 或 Job 的 inputs。

**Task 2.3 历史列表与详情**

- 历史 Tab：GET jobs 列表，展示 job_id、title、status、created_at；点击进入详情。
- 详情：GET job 详情，展示各 Step 的输入/输出；输入图片与 8 图结果用 img 预览（含大图弹窗）。

---

### Phase 3：原子能力区块与提示词

**Task 3.1 能力区块组件**

- 每个 capability 一个区块：标题、输入表单项（可从 Job 上一步 output 预填）、提示词编辑区（多行或 8 条）、操作按钮（运行、保存为模板、恢复模板、从模板选择）。
- 运行：调用 POST jobs/{id}/steps，传 user_input、prompt 或 prompt_template_id；成功后刷新 Job 详情，展示本步 output。

**Task 3.2 提示词模板选择与恢复**

- 恢复模板：GET default-prompt，将返回内容填回编辑区。
- 从模板选择：GET capabilities/{id}/templates，下拉选择一条（含系统默认），将 content 填回编辑区。
- 保存为模板：POST templates，name 弹窗输入，content 为当前编辑区内容。

---

### Phase 4：8 图与视频

**Task 4.1 8 图生成区块**

- 展示 8 个槽位（第 1 条标注白底）；每槽：提示词输入、可选模型/尺寸；支持从 Step 5 的 output 一键填充。
- 提供 8 图模板选择与保存（调用 image-gen templates API）。
- 生成：POST image-gen，轮询或跳转历史查看结果；结果区 8 宫格预览，点击大图。

**Task 4.2 视频生成 Tab**

- 复用现有视频任务创建逻辑（或嵌入 create-form）：模型、时长、参考图（可预填本页 8 图或分析结果中的图）；提交调用现有 POST /api/v1/video-tasks。

---

### Phase 5：一键执行与后台查看

**Task 5.1 一键执行按钮**

- 在「输入与分析」或全局提供「一键执行」：收集当前 inputs、steps（可选）、prompts/template_ids，调用 POST /api/v1/product-info/run。
- 收到 202 后展示 job_id 与「后台查看」链接或自动跳转 Job 详情页。

**Task 5.2 后台查看与轮询**

- Job 详情页：GET job 详情，展示 steps 进度与 output；若 status 为 running，定时轮询 GET job 直到 completed/failed。
- 结果展示：各 step 的 output_snapshot 结构化展示；图片 URL 统一预览。

---

## 五、实施顺序总览

| 阶段 | 后端 | 前端 |
|------|------|------|
| 1 | 模型与迁移、Repository、能力常量与默认提示词 | 类型、API 客户端、路由与导航 |
| 2 | 能力执行器、依赖注入、单步执行 UseCase 与 API | 页面骨架、输入区、上传与预览、历史列表与详情 |
| 3 | Job CRUD、capabilities/default-prompt、用户模板 CRUD | 各能力区块、提示词编辑/保存/恢复/选择 |
| 4 | 一键 run（异步）、8 图 image-gen、upload API | 8 图区块与预览、视频 Tab 复用 |
| 5 | 路由注册、依赖注入、联调 | 一键执行与后台查看、轮询与结果展示 |

---

## 六、API 清单（速查）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/product-info/jobs | 创建 Job |
| GET | /api/v1/product-info/jobs | Job 列表 |
| GET | /api/v1/product-info/jobs/{id} | Job 详情（后台查看） |
| DELETE | /api/v1/product-info/jobs/{id} | 删除 Job |
| POST | /api/v1/product-info/jobs/{id}/steps | 执行/重跑某步 |
| GET | /api/v1/product-info/capabilities | 能力列表 |
| GET | /api/v1/product-info/capabilities/{cid}/default-prompt | 默认提示词（恢复模板） |
| GET | /api/v1/product-info/capabilities/{cid}/templates | 用户模板列表 |
| POST | /api/v1/product-info/capabilities/{cid}/templates | 保存用户模板 |
| PATCH | /api/v1/product-info/templates/{tid} | 更新用户模板 |
| DELETE | /api/v1/product-info/templates/{tid} | 删除用户模板 |
| POST | /api/v1/product-info/run | 一键异步执行 |
| POST | /api/v1/product-info/upload | 图片上传 |
| POST | /api/v1/product-info/image-gen | 创建 8 图任务 |
| GET | /api/v1/product-info/image-gen | 8 图任务列表 |
| GET | /api/v1/product-info/image-gen/{id} | 8 图任务详情 |
| - | /api/v1/video-tasks（现有） | 视频生成复用 |

---

## 七、验收要点

- 可创建 Job，按步执行各原子能力，每步结果持久化并可被下一步复用。
- 每能力提示词可编辑、保存为用户模板、恢复为系统默认、从模板选择。
- 一键 POST /run 仅异步，返回 job_id；通过 GET job 详情可后台查看进度与结果。
- 输入图片与 8 图结果可在输入区、结果区、历史详情中预览。
- 8 图生成支持 8 槽（第 1 白底）、模板与模型参数；视频生成复用现有 API，可带本页 8 图或分析图作为参考图。

---

*文档版本：1.0 | 日期：2025-02-09*
