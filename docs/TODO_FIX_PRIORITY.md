# TODO 修复优先级

基于项目内源码 TODO 核查结论，按**用户影响、依赖顺序、投入产出**排定的修复优先级。  
“真 TODO” 指仍为占位/mock、无替代实现的项；“非真 TODO” 为设计占位，不纳入修复。

---

## 修复原则（必守）

| 原则 | 说明 |
|------|------|
| **DRY** | 复用现有类型、组件、工具函数；不重复造轮子。 |
| **用框架** | 项目已有的技术栈必须沿用：前端 `react-hook-form` + `zod` + `@/components/ui/form` 做表单；后端按 `domains/` 分层、`libs/` 基础设施。 |
| **选型需确认** | 涉及**库/协议/实现选型**（如 MCP Client 用官方 SDK 还是自研、Studio 执行器用 LangGraph 还是其他）时，**先列出可选方案与优劣，再与负责人确认**，不得直接实现。 |

---

## 选型确认 checkpoint（实施前须停步确认）

以下事项涉及选型，修复前需**产出简要选型说明并确认**，再动手实现。

| 事项 | 可选方向 | 说明 |
|------|----------|------|
| **P1 MCP Client** | ✅ **已选：LangChain `langchain-mcp-adapters`**（见下方选型结论）。对接：`parse_url_to_connection` + `MCPServerConfig` → `connections`；LangChain Tool 薄包装为 BaseTool 后注册。 |
| **P2 Studio 测试执行** | ① LangGraph / 现有 Agent 引擎 ② 专用工作流运行时 ③ 仅前端 mock + 后端占位 | 须明确：是否复用现有 LangGraph 图、事件格式与前端约定。 |
| **P3 远程沙箱** | ① 某云/自建 API ② 不做，保留 `NotImplementedError` | 若做，须明确调用方、计费与隔离边界。 |
| **P3 A2A Client** | ① HTTP/gRPC 调用远端 Agent ② 消息队列 ③ 不做，保留 stub | 若做，须明确协议与发现机制。 |

---

### P1 MCP Client 选型结论（已确认）

**问题：** MCP Client（`client.py` 的 connect / list_tools / call_tool / health_check）用 **LangChain** 还是 **`mcp` 库**？

**结论：采用 ② LangChain `langchain-mcp-adapters`** 实现 MCP 客户端，更符合「MCP 本来就是给 LangChain 用」的定位。

| 方案 | 说明 | 优劣 |
|------|------|------|
| **① 官方 `mcp` 包** | 使用 `mcp.client` 的 `ClientSession` + stdio/sse/http transport，在 `client.py` 内手写 connect / list_tools / call_tool。 | ✅ 与现有 FastMCP 同栈；✅ 无新依赖。❌ 协议与连接逻辑需自行维护；❌ 与 LangChain/LangGraph 工具链脱节。 |
| **② LangChain `langchain-mcp-adapters`** | 使用 `MultiServerMCPClient(connections=...)`，`get_tools()` 得到 **LangChain 工具**；用一层薄包装（LangChain Tool → BaseTool：`execute()` 内调 `tool.ainvoke()`）接入现有 `ToolRegistry`。 | ✅ MCP 官方与 LangChain 的桥梁，专为「给 LangChain 用」设计；✅ 连接、拉工具、调用由适配器统一处理，支持 stdio/SSE/HTTP；✅ 不改动现有 Agent 流程（仍为 `ToolRegistry` + `BaseTool` + `execute()`），仅 MCP 来源改为 adapters + 薄包装。❌ 需新增依赖 `langchain-mcp-adapters`。 |

**实施要点（② LangChain）：**

- 新增依赖：`langchain-mcp-adapters`（与现有 `langchain`/`langgraph` 同生态）。
- 用 `parse_url_to_connection` 与 `MCPServerConfig` 构造 `MultiServerMCPClient` 的 `connections`（stdio/sse/http 与现有 url 配置一致）。
- `MCPToolService.get_mcp_tools()`：通过 adapters 的 `get_tools()` 拿到 LangChain 工具列表，对每个工具做 **LangChain Tool → BaseTool** 薄包装（name/description/parameters 透出，`execute(**kwargs)` 调用 `tool.ainvoke(kwargs)`），再 `register` 到现有 `ToolRegistry`。
- 连接测试（`mcp_use_case.test_connection`）：用同一 client 建连并调用 `list_tools` 或等价能力作为健康检查，用结果更新 `connection_status` / `available_tools`。

---

## 优先级总览

| 优先级 | 范围 | 说明 |
|--------|------|------|
| **P0** | 快速见效 | 用户可见、改动小、无下游依赖 |
| **P1** | MCP 核心 | 连接/工具列表/调用/健康检查、连接测试 |
| **P2** | Studio 测试运行 | 后端真实执行 + 前端调用与展示 |
| **P3** | 基础设施 | 评估、远程沙箱、记忆、A2A |
| **可选** | 消警 | codegen 占位 TODO → 普通注释 |

---

## P0：快速见效（优先修复）

### 1. MCP 编辑对话框 ✅ 已完成

| 项目 | 说明 |
|------|------|
| **位置** | `frontend/src/pages/mcp/index.tsx` → `onEdit`；`detail-drawer` 已有编辑按钮 |
| **现状** | 点击编辑仅 `toast.info('编辑功能即将推出')`；后端 `PUT /api/v1/mcp/servers/:id`、`mcpApi.updateServer` 已存在 |
| **修复** | 新增 `EditDialog`，**使用项目表单框架**（`react-hook-form` + `zod` + `Form`/`FormField`）；表单：`display_name`、`url`、`enabled`；提交调用 `updateServer`；MCP 页 `onEdit(server)` 时打开弹窗并传入 `server` |
| **产出** | 用户可在详情抽屉中编辑 MCP 服务器并保存 |
| **完成说明** | 已实现：`frontend/src/pages/mcp/components/edit-dialog.tsx` 使用 `useForm` + `zodResolver(formSchema)` + `Form`/`FormField`，与 `AgentDialog`、`ApiKeyCreateDialog` 一致；MCP 页已接入 `EditDialog` 并移除 TODO/toast 占位；单测对 `EditDialog` 做了 mock，构建与用例通过。 |

---

## P1：MCP 核心能力

### 2. MCP Client 真实协议实现（client.py 四处 TODO）

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/agent/infrastructure/tools/mcp/client.py`：`connect`、`list_tools`、`call_tool`、`health_check` |
| **现状** | 全为 stub：`list_tools` 返回 `[]`，`call_tool` 返回 `"Not implemented yet"`；`MCPToolService` → `ConfiguredMCPManager` → `MCPClient`，Chat 用 MCP 工具但拿不到真实列表与结果 |
| **选型结论** | 见上文 **P1 MCP Client 选型结论**：采用 **LangChain `langchain-mcp-adapters`**，MCP 客户端「给 LangChain 用」由适配器统一实现。 |
| **修复** | 新增依赖 `langchain-mcp-adapters`；用 `MultiServerMCPClient` + `parse_url_to_connection`/`MCPServerConfig` 建连；`get_tools()` 得到 LangChain 工具后做薄包装（LangChain Tool → BaseTool）并注册；`test_connection` 用同一 client 做健康检查并更新状态。 |
| **依赖** | 无；完成后再做连接测试 |
| **产出** | Chat 可真实拉取并调用 MCP 工具 |

### 3. MCP 连接测试（mcp_use_case）

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/agent/application/mcp_use_case.py` → `test_connection` |
| **现状** | 使用 `_get_mock_tools_for_server` 硬编码模拟；未走真实 MCP |
| **修复** | 在 **2** 完成后：创建 `MCPClient`，连接目标 server，执行 `health_check` 或 `list_tools`，用结果更新 `connection_status` / `available_tools`，不再用 mock |
| **依赖** | 依赖 **2** |
| **产出** | 管理端「测试连接」反映真实 MCP 可达性与工具列表 |

---

## P2：Studio 测试运行

### 4. Studio 后端测试执行

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/studio/presentation/router.py` → `POST /test/run` |
| **现状** | 仅 `event_generator()` 模拟固定 SSE 事件 |
| **⏸ 选型确认** | 见上文 **选型确认 checkpoint**「P2 Studio 测试执行」。确认后再实现。 |
| **修复** | 按确认方案对接工作流执行：解析 `workflow_id` / 图定义，真实跑图，将 `node_enter` / `node_exit` / `completed` 等以 SSE 推送 |
| **产出** | 测试运行 API 返回真实执行事件 |

### 5. Studio 前端测试运行

| 项目 | 说明 |
|------|------|
| **位置** | `frontend/src/pages/studio/index.tsx` → `runTest` |
| **现状** | 只有 `setIsLoading` + TODO，未调后端 |
| **修复** | `runTest` 内 `fetch` `/api/v1/studio/.../test/run`（或项目内实际路径），消费 SSE，更新 UI（进度、节点状态、结果）；与 **4** 对齐事件格式 |
| **依赖** | 可与 **4** 并行开发，最终对接 **4** |
| **产出** | 用户点击运行即触发真实工作流并在前端看到执行过程 |

---

## P3：基础设施（按需排期）

### 6. Evaluation 完整流程

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/evaluation/presentation/router.py`：`evaluate_task_completion`、`evaluate_gaia` |
| **现状** | 直接 `501 NOT_IMPLEMENTED` |
| **修复** | 从 DB 加载 Agent，创建评估器，跑 task/GAIA 基准，写回报告；具体实现依赖评估域设计 |
| **产出** | 任务完成率、GAIA 评估接口可用 |

### 7. 远程沙箱执行器

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/agent/infrastructure/sandbox/factory.py` → `SandboxMode.REMOTE` |
| **现状** | `NotImplementedError` |
| **修复** | 实现 `RemoteExecutor`（如调用远端 API / 集群），在 factory 中按 `REMOTE` 返回；或明确不做则移除/标记为 future |
| **产出** | 支持远程沙箱模式，或明确排除 |

### 8. TieredMemory 短期记忆召回（checkpointer）

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/agent/infrastructure/memory/tiered_memory.py` → `_recall_short_term` |
| **现状** | 直接 `return []`；`TieredMemoryManager` 尚未接入 Chat |
| **修复** | 在接入 TieredMemory 到 Chat 时一并做：从 LangGraph checkpointer 取会话历史，转换为 `MemoryItem`，支持语义筛选/截断后返回；若 checkpointer 不支持语义检索，可做时间窗口 + 简单关键词过滤 |
| **产出** | 短期记忆召回可用，为上下文压缩等提供输入 |

### 9. A2A Client 实际调用

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/agent/infrastructure/a2a/client.py` → `call_agent` |
| **现状** | 返回 `"Not implemented yet"`；`A2AClient` 未被引用 |
| **修复** | 若做 A2A：实现 HTTP/gRPC 等调用远端 Agent，或发任务到消息队列；若不做则保留 stub 并标注为 future，或移出主流程 |
| **产出** | 需要 A2A 时具备真实调用路径 |

---

## 可选：消除 Sonar 等 TODO 告警

### 10. Codegen 占位 TODO

| 项目 | 说明 |
|------|------|
| **位置** | `backend/domains/studio/infrastructure/studio/codegen.py`：生成代码中的 `# TODO: 实现节点逻辑`、`# TODO: 实现路由逻辑` |
| **现状** | 设计如此，为用户填写占位 |
| **修复** | 改为非 TODO 注释，如 `# 在此实现节点逻辑`、`# 在此实现路由逻辑`，避免被 Sonar 识别为 TODO |
| **产出** | 减少误报，不改变生成逻辑 |

---

## 推荐实施顺序

1. **P0**：MCP 编辑对话框 ✅ 已完成（含 EditDialog 使用 react-hook-form + zod + Form 的重构）。
2. **P1**：MCP Client 真实协议 → MCP 连接测试。
3. **P2**：Studio 后端测试执行 + 前端测试运行（可部分并行）。
4. **P3**：按产品需求择机做 Evaluation、远程沙箱、TieredMemory 短期召回、A2A。
5. **可选**：codegen 注释替换，在需消警时做。

---

## 非真 TODO（不修复）

- **codegen 占位**：生成模板内的 “实现节点/路由逻辑” 为刻意占位，非遗漏实现；若仅消警见 **10**。
