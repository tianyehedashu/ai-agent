# Code Check 报告

检查范围：遗留代码、兼容/过渡代码、重复代码、架构与目录合理性。  
检查时间：基于当前代码库快照（含「避免保存空对话」实施后的复核）。  
**修复记录**：已按建议执行高/中优先级项（见文末「已修复」）。

---

## 一、遗留 / 死代码

### 1. 重复的 CheckpointService（若仍存在）

| 位置 | 说明 |
|------|------|
| `backend/domains/agent/application/checkpoint_service.py` | **在用**：被 `libs.api.deps`、`chat_router`、单测引用 |
| `backend/domains/agent/infrastructure/checkpoint_service.py` | **若存在**：与 application 版重复且无引用，应删除 |

**建议**：若 `infrastructure/checkpoint_service.py` 仍存在，则删除；应用层仅保留 application 层 CheckpointService。**已确认**：infrastructure 下无同名文件，仅存在 `checkpoint_cache.py`、`langgraph_checkpointer.py` 等，无需删除。

### 2. 迁移链占位符

`backend/alembic/versions/20260128_add_encrypted_key.py` 中：

- `down_revision = 'c1d2e3f4g5h6'` 为占位 ID，与现有迁移链可能不一致。

**建议**：用 `alembic history` 确认当前链，将 `down_revision` 改为实际上一版 revision，保证链连续且可回滚。**已确认**：`alembic history` 显示链为 `c1d2e3f4g5h6 -> d2e3f4g5h6i7`，与文件一致，无需修改。

### 3. 前端「创建会话」API 的用法（非遗留）

实施「延迟创建」后，侧栏「新建对话」不再调用 `sessionApi.create()`，仅做 `navigate('/chat')`。

- **`frontend/src/api/session.ts`** 中的 `create()` 仍保留且**不算遗留**：后端 `POST /api/v1/sessions` 仍被集成测试、ChatUseCase 无 session_id 时创建会话等使用；前端 API 保留便于日后「带 agentId 创建」等能力。
- **结论**：无需删除 `sessionApi.create`，属有意保留的 API。

---

## 二、兼容 / 过渡代码

### 1. 有意保留的「兼容」说明（可保留）

- **LLM 多厂商**：gateway、providers、embeddings 等处的「OpenAI 兼容格式」「推理模型兼容 content/reasoning_content」等。
- **FastAPI Users**：identity 域下用户表、Schema、JWT 的兼容说明。
- **LangGraph / 存储**：langgraph_store、langgraph_checkpointer 的向后兼容与 namespace 逻辑。
- **bcrypt**：`domains/identity/infrastructure/authentication.py` 中 `CryptContext(..., deprecated="auto")` 为库的推荐写法，可保留。

无需修改，保持注释与行为一致即可。

### 2. 已弃用但仍保留的 API（已文档化）

- **chat_use_case._execute_agent_and_save**：docstring 中已标 `.. deprecated::`，新代码使用流式接口即可。

---

## 三、重复与不一致

### 1. 前端：会话按日期分组逻辑重复（本次重点）【已修复】

| 位置 | 说明 |
|------|------|
| `frontend/src/pages/chat/components/chat-sidebar.tsx` | 原 `groupSessions(sessions)` |
| `frontend/src/components/layout/sidebar.tsx` | 原同名、同逻辑 |

**已做**：新增 `frontend/src/lib/session-utils.ts`，导出 `groupSessionsByDate(sessions)`；两处侧栏改为 `import { groupSessionsByDate } from '@/lib/session-utils'` 并用 `useMemo(() => groupSessionsByDate(sessions), [sessions])`，重复逻辑已消除。

### 2. 前端：两个 SessionItem 组件（可接受）

- **chat-sidebar** 内：`SessionItem`（带标题、相对时间、删除，可折叠样式）。
- **layout sidebar** 内：另一 `SessionItem`（带编辑标题、删除，不同布局）。

两者职责相似但展示和交互不同（一个偏聊天页侧栏，一个偏全局侧栏），目前保留两个组件可接受；若未来要统一侧栏形态，再考虑抽成「会话列表项」通用组件 + 样式/行为配置。

### 3. 后端：数据库会话依赖 get_session vs get_db【已落实】

- **最佳方案已实施**：`get_db` 作为唯一推荐入口，实现在 `libs.db.database`（转发 `get_session`）；`libs.api.deps` 仅从 `libs.db.database` 导入并 re-export `get_db` 及 `DbSession`。`authentication.get_user_db` 与 identity 的 `deps`/`router` 改为使用 `libs.db.database.get_db`，避免与 `libs.api.deps` 的循环导入。

### 4. conftest 中 override 重复【已修复】

**已做**：在 `backend/tests/conftest.py` 中新增 `_apply_db_overrides(app, db_session)`，仅注入 `get_db` 的 override；`client` 与 `dev_client` 改为调用该函数。`get_session` 无需 override：唯一使用它的 `get_user_db` 在测试中通过 patch `get_session_factory` 已间接得到测试用会话。

---

## 四、TODO / 未完成逻辑

以下为代码中明确标出的 TODO，建议按优先级列入 backlog 或实现：

| 位置 | 内容 |
|------|------|
| `frontend/src/pages/studio/index.tsx` | 实现测试运行 |
| `backend/domains/agent/infrastructure/sandbox/factory.py` | 实现远程沙箱执行器 |
| `backend/domains/agent/infrastructure/memory/tiered_memory.py` | 从 checkpointer 获取会话历史 |
| `backend/domains/agent/infrastructure/a2a/client.py` | 实际 Agent 调用逻辑 |
| `backend/domains/evaluation/presentation/router.py` | 完整评估流程 |
| `backend/domains/studio/presentation/router.py` | 实际测试执行逻辑 |
| `backend/domains/studio/infrastructure/studio/codegen.py` | 模板中的「实现节点/路由逻辑」（若为生成占位可保留） |
| `backend/tests/integration/mcp/test_mcp_server_api.py` | 实现后取消注释的断言 |

---

## 五、架构与目录

### 1. 整体符合 DDD 与规范

- 业务在 `domains/`，技术基础在 `libs/`，bootstrap 仅做装配，符合 CLAUDE.md 与 CODE_STANDARDS。
- agent / identity / studio / evaluation 域边界清晰；presentation → application → domain ← infrastructure 分层明确。

### 2. 目录与归属

- **backend/config/**：存放 toml 等配置文件；**bootstrap/config.py**：应用 Settings 与加载逻辑，分工合理。
- **CheckpointService**：仅保留在 application 层；infrastructure 层保留 checkpoint_cache、langgraph_checkpointer 等实现即可。
- **前端**：`api/`、`pages/`、`components/`、`hooks/`、`lib/`、`stores/` 划分清晰，无目录不合理问题。

### 3. 小建议

- 若后续「工作室/工作流」与「评估」扩展，可再审视 studio 与 evaluation 是否共享执行环境、指标存储等基础设施，避免重复建设；当前体量保持现状即可。

---

## 六、建议执行顺序（优先级）

1. **高**：前端抽取 `groupSessionsByDate` → **已做**（`@/lib/session-utils.ts`）。
2. **高**：若仍存在 `domains/agent/infrastructure/checkpoint_service.py` → **已确认不存在**。
3. **高**：修正 `20260128_add_encrypted_key.py` 的 `down_revision` → **已确认链正确，无需改**。
4. **中**：统一后端 DB 依赖并收敛 conftest → **已完成**：`get_db` 置于 `libs.db.database`，identity/authentication 统一用 `get_db`，conftest 仅 override `get_db`。
5. **低**：将 TODO 列表整理进 issue/backlog；对 deprecated API 做文档或下线规划。（可后续处理）

---

## 七、总结

- **遗留/死代码**：前端 `sessionApi.create` 为有意保留；infrastructure 下无重复 CheckpointService；迁移链已确认正确。
- **兼容代码**：多为合理的产品/协议兼容或已文档化的 deprecated，保持现状即可。
- **重复/不一致**：前端已抽取 `groupSessionsByDate`；后端 `get_db` 统一在 `libs.db.database`，identity/authentication 与 conftest 均已统一。
- **架构与目录**：符合项目规范，无新增不当。

**已修复**：高优先级 1～3、中优先级 4 均已完成；仅低优先级 5（TODO/backlog、deprecated 文档）可后续处理。
