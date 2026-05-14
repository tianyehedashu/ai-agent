# 🤖 Agent 架构设计：配置 vs 实例 vs 应用

> **现行产品说明（2026-05）**：文内若出现「工作台」编辑/测试/部署等表述，指**历史产品形态**；当前主路径为 **对话（Chat）、Agents API、执行配置与 MCP**。内置 `domains/studio` 已移除。

> **版本**: 1.0.0
> **更新日期**: 2026-01-14
> **说明**: 明确 Agent 的定位：是配置、实例，还是独立应用？如何设计最佳架构？

---

## 📋 目录

1. [问题分析](#问题分析)
2. [Agent 的三种形态](#agent-的三种形态)
3. [架构设计方案](#架构设计方案)
4. [实现方案](#实现方案)
5. [最佳实践](#最佳实践)

---

## 问题分析

### 1.1 当前困惑

```
❓ Agent 到底是什么？
   • 是一个分层的概念（系统中的一个模块）？
   • 还是一个独立可执行的应用？
   • 还是只是一个配置/模板？

❓ 如何区分：
   • Agent 定义（Agent Definition）
   • Agent 实例（Agent Instance）
   • Agent 应用（Agent Application）
```

### 1.2 问题根源

当前架构中，`Agent` 模型同时承担了多个职责：

```python
# 当前设计：Agent 模型混合了多个概念
class Agent(BaseModel):
    # 这是配置？
    system_prompt: str
    model: str
    tools: list[str]

    # 这是实例？
    sessions: list["Session"]  # 关联的会话

    # 这是应用？
    # 如何部署？如何运行？
```

**问题**：
- ❌ 职责不清：配置、实例、应用混在一起
- ❌ 部署困难：不知道如何将 Agent 部署为独立应用
- ❌ 扩展性差：难以支持多实例、多环境

---

## Agent 的三种形态

### 2.1 形态一：Agent 定义（Agent Definition）

**定位**: Agent 的**配置模板**，定义 Agent 的能力和行为

```python
# Agent 定义 = 配置
class AgentDefinition:
    """Agent 定义 - 配置模板"""

    id: UUID
    name: str
    description: str

    # 核心配置
    system_prompt: str          # 系统提示词
    model: str                  # 使用的模型
    tools: list[str]            # 可用工具列表
    workflow_code: str          # 工作流代码（可选）

    # 执行配置
    temperature: float
    max_tokens: int
    max_iterations: int

    # 元数据
    created_by: UUID
    created_at: datetime
    updated_at: datetime
```

**特点**：
- ✅ 存储在数据库中（`agents` 表）
- ✅ 可以被多个实例共享
- ✅ 支持版本管理
- ✅ 可以被工作台编辑

**类比**：就像 Docker 镜像定义，定义了容器的配置

### 2.2 形态二：Agent 实例（Agent Instance）

**定位**: Agent 的**运行时实例**，基于定义创建，处理实际请求

```python
# Agent 实例 = 运行时
class AgentInstance:
    """Agent 实例 - 运行时"""

    id: UUID
    definition_id: UUID         # 关联的 Agent 定义

    # 运行时状态
    status: str                 # running, stopped, error
    current_sessions: int       # 当前活跃会话数

    # 实例配置（可覆盖定义）
    config_overrides: dict      # 覆盖定义的配置

    # 部署信息
    deployment_id: UUID        # 关联的部署记录
    endpoint: str              # API 端点（如果部署为服务）

    # 运行时数据
    created_at: datetime
    started_at: datetime
    stopped_at: datetime
```

**特点**：
- ✅ 基于 Agent 定义创建
- ✅ 可以有多个实例（多环境、多版本）
- ✅ 运行时状态独立
- ✅ 可以动态启动/停止

**类比**：就像 Docker 容器实例，基于镜像运行

### 2.3 形态三：Agent 应用（Agent Application）

**定位**: Agent 的**独立应用**，可以独立部署和运行

```python
# Agent 应用 = 独立服务
class AgentApplication:
    """Agent 应用 - 独立部署的服务"""

    id: UUID
    instance_id: UUID           # 关联的 Agent 实例

    # 部署配置
    deploy_type: str            # api, web, embed, standalone
    environment: str            # dev, staging, production

    # 服务配置
    endpoint: str               # API 端点
    api_key: str                # API 密钥
    rate_limit: dict            # 限流配置

    # 运行配置
    replicas: int               # 副本数
    resources: dict             # 资源限制

    # 状态
    status: str                 # running, stopped, error
    health_check_url: str       # 健康检查端点
```

**特点**：
- ✅ 可以独立部署（API、Web、嵌入组件）
- ✅ 有自己的端点、认证、限流
- ✅ 可以水平扩展（多副本）
- ✅ 可以独立监控和运维

**类比**：就像 Kubernetes Deployment，管理服务的部署和运行

---

## 架构设计方案

### 3.1 三层架构模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          三层架构模型                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: Agent Definition (定义层)                                        │
│  ────────────────────────────────────────────────────────────────────────  │
│  • 存储 Agent 配置（system_prompt, model, tools, workflow_code）          │
│  • 数据库表: agents                                                         │
│  • 可以被工作台编辑                                                        │
│  • 支持版本管理                                                            │
│                                                                             │
│  Layer 2: Agent Instance (实例层)                                          │
│  ────────────────────────────────────────────────────────────────────────  │
│  • 基于定义创建的运行时实例                                                │
│  • 数据库表: agent_instances                                               │
│  • 可以有多个实例（开发/测试/生产）                                        │
│  • 管理运行时状态                                                          │
│                                                                             │
│  Layer 3: Agent Application (应用层)                                       │
│  ────────────────────────────────────────────────────────────────────────  │
│  • 部署为独立服务的 Agent                                                  │
│  • 数据库表: agent_deployments                                             │
│  • 可以是 API、Web、嵌入组件、独立应用                                     │
│  • 管理部署和运维                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据模型设计

```python
# backend/models/agent.py

# ==================== Layer 1: Agent Definition ====================

class Agent(BaseModel):
    """Agent 定义 - 配置模板"""

    __tablename__ = "agents"

    id: UUID
    user_id: UUID
    name: str
    description: str

    # 核心配置
    system_prompt: str
    model: str
    tools: list[str]
    workflow_code: str | None = None  # 工作流代码（可选）

    # 执行配置
    temperature: float = 0.7
    max_tokens: int = 4096
    max_iterations: int = 20
    config: dict = {}  # 扩展配置

    # 元数据
    is_public: bool = False
    created_at: datetime
    updated_at: datetime

    # 关系
    instances: list["AgentInstance"] = relationship(...)
    versions: list["AgentVersion"] = relationship(...)


# ==================== Layer 2: Agent Instance ====================

class AgentInstance(BaseModel):
    """Agent 实例 - 运行时"""

    __tablename__ = "agent_instances"

    id: UUID
    agent_id: UUID              # 关联的 Agent 定义
    name: str                   # 实例名称（如：客服Agent-生产环境）
    environment: str             # dev, staging, production

    # 运行时状态
    status: str                 # pending, running, stopped, error
    current_sessions: int = 0    # 当前活跃会话数

    # 实例配置（可覆盖定义）
    config_overrides: dict = {} # 覆盖定义的配置

    # 部署信息
    deployment_id: UUID | None = None  # 关联的部署记录

    # 运行时数据
    created_at: datetime
    started_at: datetime | None = None
    stopped_at: datetime | None = None

    # 关系
    agent: Agent = relationship(...)
    deployment: "AgentDeployment" = relationship(...)
    sessions: list["Session"] = relationship(...)


# ==================== Layer 3: Agent Application ====================

class AgentDeployment(BaseModel):
    """Agent 部署 - 独立应用"""

    __tablename__ = "agent_deployments"

    id: UUID
    instance_id: UUID           # 关联的 Agent 实例
    name: str                   # 部署名称

    # 部署类型
    deploy_type: str            # api, web, embed, standalone
    environment: str             # dev, staging, production

    # 服务配置
    endpoint: str | None = None  # API 端点
    api_key: str | None = None  # API 密钥
    rate_limit: dict = {}       # 限流配置

    # 运行配置
    replicas: int = 1            # 副本数
    resources: dict = {}        # 资源限制

    # 状态
    status: str                 # pending, running, stopped, error
    health_check_url: str | None = None

    # 时间戳
    created_at: datetime
    deployed_at: datetime | None = None
    stopped_at: datetime | None = None

    # 关系
    instance: AgentInstance = relationship(...)
```

### 3.3 关系图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据关系图                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User                                                                       │
│    │                                                                        │
│    │ 1:N                                                                    │
│    ▼                                                                        │
│  Agent (Definition) ──────┐                                                 │
│    │                      │                                                 │
│    │ 1:N                  │                                                 │
│    ▼                      │                                                 │
│  AgentInstance            │                                                 │
│    │                      │                                                 │
│    │ 1:1                  │                                                 │
│    ▼                      │                                                 │
│  AgentDeployment          │                                                 │
│                           │                                                 │
│  ─────────────────────────┘                                                 │
│                                                                             │
│  Session                                                                     │
│    │                                                                        │
│    │ N:1                                                                    │
│    ▼                                                                        │
│  AgentInstance (运行时实例)                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 执行流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           执行流程                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  场景 1: 工作台测试运行                                                     │
│  ────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  用户在工作台测试 → 直接使用 Agent 定义 → AgentEngine 执行                 │
│                                                                             │
│  流程:                                                                      │
│  1. 用户在工作台选择 Agent 定义                                             │
│  2. 输入测试消息                                                            │
│  3. 系统创建临时会话（不创建实例）                                          │
│  4. AgentEngine 基于定义执行                                               │
│  5. 返回结果                                                                │
│                                                                             │
│  场景 2: 生产环境执行                                                       │
│  ────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  用户调用 API → 使用 Agent 实例 → AgentEngine 执行                        │
│                                                                             │
│  流程:                                                                      │
│  1. 用户调用 API: POST /api/v1/agents/{instance_id}/chat                  │
│  2. 系统查找 Agent 实例                                                    │
│  3. 从实例获取 Agent 定义                                                  │
│  4. 创建会话（关联到实例）                                                  │
│  5. AgentEngine 基于定义执行                                               │
│  6. 返回结果                                                                │
│                                                                             │
│  场景 3: 独立应用部署                                                       │
│  ────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  部署为独立服务 → 创建部署记录 → 启动服务实例                              │
│                                                                             │
│  流程:                                                                      │
│  1. 用户在工作台点击"部署"                                                 │
│  2. 选择 Agent 定义和部署类型（API/Web/嵌入）                             │
│  3. 系统创建 Agent 实例                                                    │
│  4. 系统创建 Agent 部署记录                                                 │
│  5. 系统启动服务（FastAPI 服务、Web 服务等）                              │
│  6. 返回部署信息（端点、API Key 等）                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 实现方案

### 4.1 Agent 定义服务

```python
# backend/services/agent_definition.py

class AgentDefinitionService:
    """Agent 定义服务"""

    async def create(
        self,
        user_id: UUID,
        name: str,
        system_prompt: str,
        model: str,
        tools: list[str],
        workflow_code: str | None = None,
    ) -> Agent:
        """创建 Agent 定义"""
        agent = Agent(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            system_prompt=system_prompt,
            model=model,
            tools=tools,
            workflow_code=workflow_code,
        )
        await self.db.save(agent)
        return agent

    async def get(self, agent_id: UUID) -> Agent:
        """获取 Agent 定义"""
        return await self.db.get(Agent, agent_id)

    async def update(
        self,
        agent_id: UUID,
        **updates,
    ) -> Agent:
        """更新 Agent 定义"""
        agent = await self.get(agent_id)
        for key, value in updates.items():
            setattr(agent, key, value)
        agent.updated_at = datetime.utcnow()
        await self.db.save(agent)
        return agent
```

### 4.2 Agent 实例服务

```python
# backend/services/agent_instance.py

class AgentInstanceService:
    """Agent 实例服务"""

    async def create_from_definition(
        self,
        agent_id: UUID,
        name: str,
        environment: str = "production",
        config_overrides: dict = {},
    ) -> AgentInstance:
        """从定义创建实例"""
        # 1. 获取 Agent 定义
        agent = await self.definition_service.get(agent_id)

        # 2. 创建实例
        instance = AgentInstance(
            id=uuid.uuid4(),
            agent_id=agent.id,
            name=name,
            environment=environment,
            status="pending",
            config_overrides=config_overrides,
        )
        await self.db.save(instance)

        return instance

    async def start(self, instance_id: UUID) -> AgentInstance:
        """启动实例"""
        instance = await self.get(instance_id)
        instance.status = "running"
        instance.started_at = datetime.utcnow()
        await self.db.save(instance)
        return instance

    async def stop(self, instance_id: UUID) -> AgentInstance:
        """停止实例"""
        instance = await self.get(instance_id)
        instance.status = "stopped"
        instance.stopped_at = datetime.utcnow()
        await self.db.save(instance)
        return instance
```

### 4.3 Agent 部署服务

```python
# backend/services/agent_deployment.py

class AgentDeploymentService:
    """Agent 部署服务"""

    async def deploy(
        self,
        instance_id: UUID,
        deploy_type: str,
        environment: str = "production",
    ) -> AgentDeployment:
        """部署 Agent 为独立应用"""
        # 1. 获取实例
        instance = await self.instance_service.get(instance_id)

        # 2. 创建部署记录
        deployment = AgentDeployment(
            id=uuid.uuid4(),
            instance_id=instance.id,
            name=f"{instance.name}-{deploy_type}",
            deploy_type=deploy_type,
            environment=environment,
            status="pending",
        )
        await self.db.save(deployment)

        # 3. 根据部署类型启动服务
        if deploy_type == "api":
            await self._deploy_as_api(deployment, instance)
        elif deploy_type == "web":
            await self._deploy_as_web(deployment, instance)
        elif deploy_type == "embed":
            await self._deploy_as_embed(deployment, instance)

        # 4. 更新状态
        deployment.status = "running"
        deployment.deployed_at = datetime.utcnow()
        await self.db.save(deployment)

        return deployment

    async def _deploy_as_api(
        self,
        deployment: AgentDeployment,
        instance: AgentInstance,
    ):
        """部署为 API 服务"""
        # 1. 生成 API 端点
        endpoint = f"https://api.example.com/v1/agents/{instance.id}"
        api_key = self._generate_api_key()

        # 2. 注册路由
        await self._register_api_route(instance, endpoint)

        # 3. 更新部署信息
        deployment.endpoint = endpoint
        deployment.api_key = api_key
        await self.db.save(deployment)

    async def _deploy_as_web(
        self,
        deployment: AgentDeployment,
        instance: AgentInstance,
    ):
        """部署为 Web 应用"""
        # 1. 生成 Web 页面
        web_url = f"https://chat.example.com/agents/{instance.id}"

        # 2. 创建 Web 页面
        await self._create_web_page(instance, web_url)

        # 3. 更新部署信息
        deployment.endpoint = web_url
        await self.db.save(deployment)
```

### 4.4 执行引擎适配

```python
# backend/core/engine/agent.py

class AgentEngine:
    """Agent 执行引擎 - 支持定义和实例"""

    def __init__(
        self,
        agent: Agent | AgentInstance,  # 支持两种类型
        llm_gateway: LLMGateway,
        tool_registry: ToolRegistry,
        # ...
    ):
        # 如果是实例，获取定义
        if isinstance(agent, AgentInstance):
            self.agent_definition = agent.agent
            self.config_overrides = agent.config_overrides
        else:
            self.agent_definition = agent
            self.config_overrides = {}

        # 构建配置（定义 + 实例覆盖）
        self.config = self._build_config(
            self.agent_definition,
            self.config_overrides,
        )

        # 初始化引擎
        self.llm = llm_gateway
        self.tools = tool_registry
        # ...

    def _build_config(
        self,
        definition: Agent,
        overrides: dict,
    ) -> AgentConfig:
        """构建执行配置（定义 + 覆盖）"""
        return AgentConfig(
            agent_id=str(definition.id),
            name=definition.name,
            system_prompt=definition.system_prompt,
            model=overrides.get("model", definition.model),
            tools=overrides.get("tools", definition.tools),
            temperature=overrides.get("temperature", definition.temperature),
            max_tokens=overrides.get("max_tokens", definition.max_tokens),
            max_iterations=overrides.get("max_iterations", definition.max_iterations),
        )
```

### 4.5 API 路由设计

```python
# backend/api/v1/agent.py

router = APIRouter(prefix="/agents", tags=["Agents"])

# ==================== Agent 定义 API ====================

@router.post("/definitions")
async def create_definition(
    data: AgentCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """创建 Agent 定义"""
    return await agent_definition_service.create(
        user_id=current_user.id,
        **data.model_dump()
    )

@router.get("/definitions/{agent_id}")
async def get_definition(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 定义"""
    return await agent_definition_service.get(agent_id)

# ==================== Agent 实例 API ====================

@router.post("/instances")
async def create_instance(
    data: InstanceCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """从定义创建实例"""
    return await agent_instance_service.create_from_definition(
        agent_id=data.agent_id,
        name=data.name,
        environment=data.environment,
        config_overrides=data.config_overrides,
    )

@router.post("/instances/{instance_id}/start")
async def start_instance(
    instance_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """启动实例"""
    return await agent_instance_service.start(instance_id)

# ==================== Agent 执行 API ====================

@router.post("/instances/{instance_id}/chat")
async def chat_with_instance(
    instance_id: UUID,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """与 Agent 实例对话"""
    # 1. 获取实例
    instance = await agent_instance_service.get(instance_id)

    # 2. 创建会话
    session = await session_service.create(
        user_id=current_user.id,
        instance_id=instance.id,
    )

    # 3. 创建引擎
    engine = AgentEngine(
        agent=instance,  # 传入实例
        llm_gateway=llm_gateway,
        tool_registry=tool_registry,
    )

    # 4. 执行
    async def event_generator():
        async for event in engine.run(
            user_input=request.message,
            session_id=str(session.id),
        ):
            yield event

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ==================== Agent 部署 API ====================

@router.post("/instances/{instance_id}/deploy")
async def deploy_instance(
    instance_id: UUID,
    data: DeployRequest,
    current_user: User = Depends(get_current_user),
):
    """部署 Agent 实例"""
    return await agent_deployment_service.deploy(
        instance_id=instance_id,
        deploy_type=data.deploy_type,
        environment=data.environment,
    )
```

---

## 最佳实践

### 5.1 使用场景映射

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          使用场景映射                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  场景                    │ 使用层级          │ 说明                          │
│  ────────────────────────────────────────────────────────────────────────  │
│  工作台创建/编辑         │ Agent Definition │ 编辑配置模板                  │
│  工作台测试运行         │ Agent Definition │ 直接使用定义测试              │
│  生产环境执行           │ Agent Instance    │ 基于定义创建实例执行          │
│  独立 API 服务          │ Agent Deployment │ 部署为独立 API                 │
│  独立 Web 应用          │ Agent Deployment │ 部署为独立 Web                │
│  嵌入组件               │ Agent Deployment │ 部署为嵌入组件                │
│  多环境部署             │ Agent Instance    │ 同一定义创建多个实例          │
│  版本管理               │ Agent Definition │ 定义支持版本                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 迁移方案

如果当前系统已经使用了 `Agent` 模型，可以这样迁移：

```python
# Step 1: 保持现有 Agent 模型作为定义
# agents 表 = Agent Definition

# Step 2: 添加实例表
# agent_instances 表 = Agent Instance

# Step 3: 添加部署表
# agent_deployments 表 = Agent Deployment

# Step 4: 迁移现有数据
# 将现有的 agents 记录视为定义
# 为每个需要运行的 agent 创建实例

# Step 5: 更新代码
# 执行时使用实例，而不是直接使用定义
```

### 5.3 推荐架构

```
推荐架构：三层分离

1. Agent Definition (定义层)
   • 存储配置模板
   • 支持版本管理
   • 可以被工作台编辑

2. Agent Instance (实例层)
   • 基于定义创建
   • 管理运行时状态
   • 支持多环境

3. Agent Deployment (应用层)
   • 独立部署服务
   • 管理端点、认证、限流
   • 支持水平扩展

优势：
✅ 职责清晰
✅ 易于扩展
✅ 支持多实例
✅ 支持独立部署
```

---

## 总结

### Agent 的定位

1. **Agent Definition（定义）**: 配置模板，存储在数据库中
2. **Agent Instance（实例）**: 运行时实例，基于定义创建
3. **Agent Deployment（应用）**: 独立应用，可以独立部署

### 关键设计原则

1. **分离关注点**: 定义、实例、应用分离
2. **支持多形态**: 可以是系统内的执行单元，也可以是独立应用
3. **灵活部署**: 支持多种部署方式（API、Web、嵌入、独立）

### 实施建议

1. **短期**: 保持现有 `Agent` 模型作为定义，添加实例和部署层
2. **中期**: 完善三层架构，支持多实例和多环境
3. **长期**: 支持独立应用部署，实现真正的 Agent 应用生态

---

<div align="center">

**定义 → 实例 → 应用：清晰的 Agent 架构**

*文档版本: v1.0.0 | 最后更新: 2026-01-14*

</div>
