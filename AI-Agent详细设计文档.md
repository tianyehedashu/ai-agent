# 🛠️ AI Agent 系统详细设计文档

> 基于架构设计的技术实现方案，包含技术选型、目录规范、模块设计、接口定义等

---

## 一、技术选型

### 1.1 技术栈总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              技术栈全景                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  前端层                                                                     │
│  ├─ 框架: React 18 + Vite (纯SPA，无需SEO)                                 │
│  ├─ UI: Tailwind CSS + shadcn/ui                                           │
│  ├─ 可视化编排: React Flow (Code-First，代码为底层，UI为渲染层)            │
│  ├─ 状态: Zustand                                                          │
│  ├─ 实时通信: Server-Sent Events (SSE)                                     │
│  └─ 代码编辑: Monaco Editor (Python 代码编辑，与可视化双向同步)            │
│                                                                             │
│  后端层                                                                     │
│  ├─ 框架: FastAPI (Python 3.11+)                                           │
│  ├─ 异步: asyncio + uvicorn                                                │
│  ├─ 任务队列: Celery + Redis                                               │
│  ├─ WebSocket: FastAPI WebSocket                                           │
│  └─ 进程管理: Supervisor / PM2                                             │
│                                                                             │
│  Agent 核心                                                                 │
│  ├─ LLM接入: LiteLLM (统一接口)                                            │
│  ├─ Agent框架: 自研 (轻量可控)                                             │
│  ├─ 工具协议: MCP (Model Context Protocol)                                 │
│  └─ 代码沙箱: Docker + gVisor / E2B                                        │
│                                                                             │
│  数据层                                                                     │
│  ├─ 主数据库: PostgreSQL 15                                                │
│  ├─ 向量数据库: Qdrant (生产) / Chroma (开发)                              │
│  ├─ 缓存: Redis 7                                                          │
│  ├─ 对象存储: MinIO / S3                                                   │
│  └─ 搜索: Elasticsearch (可选)                                             │
│                                                                             │
│  运维层                                                                     │
│  ├─ 容器: Docker + Docker Compose                                          │
│  ├─ 编排: Kubernetes (生产环境)                                            │
│  ├─ 监控: Prometheus + Grafana                                             │
│  ├─ 日志: Loki + Promtail                                                  │
│  └─ 链路追踪: OpenTelemetry + Jaeger                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心依赖版本

```yaml
# Python 后端依赖
python: ">=3.11"
fastapi: ">=0.109.0"
uvicorn: ">=0.27.0"
pydantic: ">=2.5.0"
sqlalchemy: ">=2.0.0"
alembic: ">=1.13.0"
celery: ">=5.3.0"
redis: ">=5.0.0"
litellm: ">=1.20.0"
qdrant-client: ">=1.7.0"
chromadb: ">=0.4.0"
tiktoken: ">=0.5.0"
httpx: ">=0.26.0"
python-multipart: ">=0.0.6"
pyjwt: ">=2.8.0"

# 类型检查与代码质量
pyright: ">=1.1.350"        # 类型检查
ruff: ">=0.2.0"             # Linting + 格式化
libcst: ">=1.1.0"           # Code-First 代码操作

# LSP 集成 (可选)
python-lsp-server: ">=1.10.0"
pylsp-mypy: ">=0.6.8"

# 前端依赖
react: ">=18.2.0"
vite: ">=5.0.0"
typescript: ">=5.3.0"
tailwindcss: ">=3.4.0"
zustand: ">=4.5.0"
reactflow: ">=11.10.0"
@monaco-editor/react: ">=4.6.0"
```

### 1.3 LLM 模型选型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              模型选型矩阵                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  场景                模型                    原因                           │
│  ─────────────────────────────────────────────────────────────────────────  │
│  主力模型            Claude 3.5 Sonnet      推理强、上下文长、工具调用好    │
│  备用模型            GPT-4o                 稳定、生态好                    │
│  快速响应            GPT-4o-mini            成本低、速度快                  │
│  长上下文            Claude 3.5 / Gemini    200K窗口                        │
│  代码生成            Claude 3.5 Sonnet      代码能力最强                    │
│  本地部署            Qwen2.5-72B / Llama3   数据安全、无网络依赖            │
│  嵌入模型            text-embedding-3-small 性价比高                        │
│                                                                             │
│  降级策略:                                                                  │
│  Claude Sonnet → GPT-4o → GPT-4o-mini → 本地模型 → 返回错误                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、项目目录结构

### 2.1 整体目录规范

```
ai-agent/
├── 📁 docs/                          # 文档
│   ├── architecture.md               # 架构设计
│   ├── api.md                        # API文档
│   └── deployment.md                 # 部署文档
│
├── 📁 frontend/                      # 前端项目 (React + Vite)
│   ├── 📁 src/
│   │   ├── 📁 components/            # 组件
│   │   │   ├── 📁 ui/                # shadcn/ui 基础组件
│   │   │   ├── 📁 chat/              # 对话相关组件
│   │   │   ├── 📁 workflow/          # 工作流编排组件 (React Flow)
│   │   │   ├── 📁 agent/             # Agent相关组件
│   │   │   └── 📁 common/            # 公共组件
│   │   ├── 📁 pages/                 # 页面
│   │   │   ├── Chat.tsx              # 对话界面
│   │   │   ├── Workflow.tsx          # 工作流编排
│   │   │   ├── Agents.tsx            # Agent管理
│   │   │   ├── Debug.tsx             # 调试页面 (时间旅行)
│   │   │   └── Settings.tsx          # 设置页面
│   │   ├── 📁 stores/                # Zustand 状态管理
│   │   │   ├── chat.ts               # 对话状态
│   │   │   ├── workflow.ts           # 工作流状态
│   │   │   ├── agent.ts              # Agent状态
│   │   │   └── user.ts               # 用户状态
│   │   ├── 📁 hooks/                 # 自定义 Hooks
│   │   ├── 📁 lib/                   # 工具库
│   │   │   ├── api.ts                # API客户端
│   │   │   ├── utils.ts              # 工具函数
│   │   │   └── constants.ts          # 常量定义
│   │   ├── 📁 types/                 # 类型定义
│   │   ├── App.tsx                   # 根组件
│   │   ├── main.tsx                  # 入口
│   │   └── index.css                 # 全局样式 (Tailwind)
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── package.json
│
├── 📁 backend/                       # 后端项目
│   ├── 📁 app/                       # 应用主目录
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 入口
│   │   └── config.py                 # 配置管理
│   │
│   ├── 📁 api/                       # API路由
│   │   ├── __init__.py
│   │   ├── 📁 v1/                    # API版本
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 路由汇总
│   │   │   ├── chat.py               # 对话API
│   │   │   ├── agent.py              # Agent API
│   │   │   ├── tool.py               # 工具API
│   │   │   ├── memory.py             # 记忆API
│   │   │   └── user.py               # 用户API
│   │   └── deps.py                   # 依赖注入
│   │
│   ├── 📁 core/                      # 核心模块
│   │   ├── __init__.py
│   │   ├── 📁 agent/                 # Agent核心
│   │   │   ├── __init__.py
│   │   │   ├── engine.py             # Agent引擎 (增强版)
│   │   │   ├── loop.py               # Main Loop
│   │   │   ├── context.py            # 上下文管理
│   │   │   ├── checkpoint.py         # 检查点管理 (借鉴 LangGraph)
│   │   │   ├── termination.py        # 终止条件 (借鉴 AutoGen)
│   │   │   └── reasoning.py          # 推理模式
│   │   ├── 📁 memory/                # 记忆系统
│   │   │   ├── __init__.py
│   │   │   ├── manager.py            # 记忆管理器
│   │   │   ├── short_term.py         # 短期记忆
│   │   │   ├── long_term.py          # 长期记忆
│   │   │   └── retriever.py          # 记忆检索
│   │   ├── 📁 tool/                  # 工具系统
│   │   │   ├── __init__.py
│   │   │   ├── registry.py           # 工具注册
│   │   │   ├── executor.py           # 工具执行
│   │   │   ├── docker_executor.py    # Docker沙箱执行 (借鉴 AutoGen)
│   │   │   ├── 📁 builtin/           # 内置工具
│   │   │   │   ├── file.py           # 文件操作
│   │   │   │   ├── shell.py          # Shell命令
│   │   │   │   ├── web.py            # 网络请求
│   │   │   │   └── search.py         # 搜索工具
│   │   │   └── 📁 mcp/               # MCP扩展
│   │   │       ├── client.py         # MCP客户端
│   │   │       └── server.py         # MCP服务端
│   │   └── 📁 llm/                   # 模型网关
│   │       ├── __init__.py
│   │       ├── gateway.py            # 统一网关
│   │       ├── router.py             # 模型路由
│   │       └── providers/            # 模型提供商
│   │           ├── openai.py
│   │           ├── anthropic.py
│   │           └── local.py
│   │
│   ├── 📁 models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── base.py                   # 基础模型
│   │   ├── user.py                   # 用户模型
│   │   ├── agent.py                  # Agent模型
│   │   ├── session.py                # 会话模型
│   │   ├── message.py                # 消息模型
│   │   ├── memory.py                 # 记忆模型
│   │   └── tool.py                   # 工具模型
│   │
│   ├── 📁 schemas/                   # Pydantic Schema
│   │   ├── __init__.py
│   │   ├── request.py                # 请求Schema
│   │   ├── response.py               # 响应Schema
│   │   ├── agent.py                  # Agent Schema
│   │   └── message.py                # 消息Schema
│   │
│   ├── 📁 services/                  # 业务服务
│   │   ├── __init__.py
│   │   ├── chat.py                   # 对话服务
│   │   ├── agent.py                  # Agent服务
│   │   ├── user.py                   # 用户服务
│   │   ├── execution_tracer.py       # 执行追踪 (运行时状态可视化)
│   │   ├── code_validator.py         # 代码验证器 (语法+类型+lint+架构)
│   │   ├── code_fixer.py             # 代码自动修复 (LLM驱动)
│   │   ├── lsp_proxy.py              # LSP代理服务 (Pyright)
│   │   ├── sandbox_executor.py       # 沙箱执行器 (Docker)
│   │   └── code_quality_pipeline.py  # 代码质量流水线
│   │
│   ├── 📁 db/                        # 数据库
│   │   ├── __init__.py
│   │   ├── database.py               # 数据库连接
│   │   ├── 📁 migrations/            # 数据库迁移
│   │   └── 📁 repositories/          # 数据仓库
│   │       ├── base.py
│   │       ├── user.py
│   │       ├── agent.py
│   │       └── session.py
│   │
│   ├── 📁 utils/                     # 工具函数
│   │   ├── __init__.py
│   │   ├── token.py                  # Token计算
│   │   ├── security.py               # 安全工具
│   │   └── helpers.py                # 辅助函数
│   │
│   ├── 📁 workers/                   # 后台任务
│   │   ├── __init__.py
│   │   ├── celery_app.py             # Celery配置
│   │   └── tasks.py                  # 异步任务
│   │
│   ├── 📁 tests/                     # 测试
│   │   ├── 📁 unit/                  # 单元测试
│   │   ├── 📁 integration/           # 集成测试
│   │   └── conftest.py               # 测试配置
│   │
│   ├── requirements.txt              # 依赖
│   ├── requirements-dev.txt          # 开发依赖
│   ├── alembic.ini                   # 迁移配置
│   └── pyproject.toml                # 项目配置
│
├── 📁 tools/                         # 独立工具服务
│   ├── 📁 sandbox/                   # 代码沙箱
│   │   ├── Dockerfile
│   │   └── executor.py
│   └── 📁 browser/                   # 浏览器自动化
│       ├── Dockerfile
│       └── browser_use.py
│
├── 📁 deploy/                        # 部署配置
│   ├── 📁 docker/                    # Docker配置
│   │   ├── Dockerfile.backend
│   │   ├── Dockerfile.frontend
│   │   └── docker-compose.yml
│   ├── 📁 k8s/                       # Kubernetes配置
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   └── 📁 nginx/                     # Nginx配置
│       └── nginx.conf
│
├── 📁 scripts/                       # 脚本
│   ├── setup.sh                      # 初始化脚本
│   ├── dev.sh                        # 开发启动
│   └── deploy.sh                     # 部署脚本
│
├── .env.example                      # 环境变量示例
├── .gitignore
├── README.md
└── Makefile                          # 常用命令
```

### 2.2 命名规范

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              命名规范                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Python:                                                                    │
│  ├─ 文件名: snake_case (user_service.py)                                   │
│  ├─ 类名: PascalCase (UserService)                                         │
│  ├─ 函数/变量: snake_case (get_user, user_name)                            │
│  ├─ 常量: UPPER_SNAKE_CASE (MAX_TOKENS)                                    │
│  └─ 私有: _开头 (_private_method)                                          │
│                                                                             │
│  TypeScript:                                                                │
│  ├─ 文件名: kebab-case (user-service.ts) 或 PascalCase (UserCard.tsx)      │
│  ├─ 组件: PascalCase (ChatMessage)                                         │
│  ├─ 函数/变量: camelCase (getUserData, userName)                           │
│  ├─ 类型/接口: PascalCase (IUserData, UserType)                            │
│  └─ 常量: UPPER_SNAKE_CASE (API_BASE_URL)                                  │
│                                                                             │
│  数据库:                                                                    │
│  ├─ 表名: snake_case 复数 (users, chat_sessions)                           │
│  ├─ 字段名: snake_case (created_at, user_id)                               │
│  └─ 索引名: idx_表名_字段名 (idx_users_email)                               │
│                                                                             │
│  API:                                                                       │
│  ├─ 路径: kebab-case (/api/v1/chat-sessions)                               │
│  ├─ 查询参数: snake_case (?page_size=10)                                   │
│  └─ 请求体: camelCase (JSON) { "userId": "xxx" }                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心模块详细设计

### 3.1 Agent Engine (Agent引擎)

```python
# backend/core/agent/engine.py

from typing import AsyncGenerator, Optional
from pydantic import BaseModel

class AgentConfig(BaseModel):
    """Agent 配置"""
    agent_id: str
    name: str
    system_prompt: str
    model: str = "claude-3-5-sonnet-20241022"
    max_iterations: int = 10
    tools: list[str] = []
    temperature: float = 0.7
    max_tokens: int = 4096

class TerminationCondition(BaseModel):
    """终止条件配置 (借鉴 AutoGen)"""
    max_iterations: int = 20              # 最大循环次数
    max_tokens: int = 100000              # Token预算上限
    timeout_seconds: int = 600            # 超时时间
    stop_texts: list[str] = []            # 检测到特定文本时终止

class InterruptConfig(BaseModel):
    """Human-in-the-Loop 配置 (借鉴 LangGraph)"""
    interrupt_before: list[str] = []      # 执行前需确认的工具
    interrupt_after: list[str] = []       # 执行后需确认的工具
    auto_approve_patterns: list[str] = [] # 自动批准的工具模式

class AgentEngine:
    """Agent 执行引擎 (增强版)"""
    
    def __init__(
        self,
        config: AgentConfig,
        context_manager: ContextManager,
        tool_executor: ToolExecutor,
        agent_llm_facade: AgentLlmFacade,
        memory_manager: MemoryManager,
        checkpointer: Checkpointer,
        termination: TerminationCondition = None,
        interrupt_config: InterruptConfig = None,
    ):
        self.config = config
        self.context = context_manager
        self.tools = tool_executor
        self.llm = agent_llm_facade
        self.memory = memory_manager
        self.checkpointer = checkpointer
        self.termination = termination or TerminationCondition()
        self.interrupt_config = interrupt_config or InterruptConfig()
        
    async def run(
        self,
        user_input: str,
        session_id: str,
        resume_from: str = None,  # 从检查点恢复
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        执行 Agent Main Loop (增强版)
        
        新增能力:
        - 终止条件检查
        - 检查点持久化
        - Human-in-the-Loop 中断
        - 沙箱隔离执行
        """
        # 从检查点恢复
        if resume_from:
            state = await self.checkpointer.load(resume_from)
            iteration = state.iteration
            total_tokens = state.total_tokens
        else:
            iteration = 0
            total_tokens = 0
            
        start_time = datetime.utcnow()
        
        while True:
            iteration += 1
            
            # 0. 终止条件检查 (借鉴 AutoGen)
            termination_reason = self._check_termination(
                iteration=iteration,
                total_tokens=total_tokens,
                start_time=start_time,
            )
            if termination_reason:
                yield AgentEvent(
                    type="terminated",
                    data={"reason": termination_reason, "iteration": iteration}
                )
                break
            
            # 1. 组装上下文
            context = await self.context.build(
                session_id=session_id,
                user_input=user_input,
                system_prompt=self.config.system_prompt,
            )
            
            # 2. 保存检查点 (借鉴 LangGraph)
            checkpoint_id = await self.checkpointer.save(
                session_id=session_id,
                step=iteration,
                state=SessionState(
                    messages=context.messages,
                    iteration=iteration,
                    total_tokens=total_tokens,
                )
            )
            
            yield AgentEvent(type="thinking", data={
                "iteration": iteration,
                "checkpoint_id": checkpoint_id,
            })
            
            # 3. 调用模型
            response = await self.llm.chat(
                messages=context.messages,
                tools=self.tools.get_definitions(),
                model=self.config.model,
                temperature=self.config.temperature,
                stream=True,
            )
            
            # 4. 处理流式响应
            full_response = ""
            tool_calls = []
            
            async for chunk in response:
                if chunk.type == "text":
                    full_response += chunk.content
                    yield AgentEvent(type="text", data={"content": chunk.content})
                elif chunk.type == "tool_call":
                    tool_calls.append(chunk.tool_call)
                elif chunk.type == "usage":
                    total_tokens += chunk.tokens
            
            # 5. 如果有工具调用
            if tool_calls:
                for tool_call in tool_calls:
                    yield AgentEvent(type="tool_call", data=tool_call.model_dump())
                    
                    # Human-in-the-Loop 检查 (借鉴 LangGraph)
                    if self._needs_human_approval(tool_call.name):
                        # 保存检查点并中断
                        interrupt_checkpoint = await self.checkpointer.save(
                            session_id=session_id,
                            step=iteration,
                            state=SessionState(
                                messages=context.messages,
                                pending_tool_call=tool_call,
                                iteration=iteration,
                                total_tokens=total_tokens,
                            )
                        )
                        yield AgentEvent(
                            type="interrupt",
                            data={
                                "checkpoint_id": interrupt_checkpoint,
                                "pending_action": tool_call.model_dump(),
                                "reason": "requires_human_approval",
                            }
                        )
                        return  # 暂停执行，等待恢复
                    
                    # 执行工具 (沙箱隔离)
                    result = await self.tools.execute(
                        name=tool_call.name,
                        arguments=tool_call.arguments,
                        session_id=session_id,
                    )
                    
                    yield AgentEvent(type="tool_result", data=result.model_dump())
                    
                    # 将工具结果加入上下文
                    await self.context.add_tool_result(
                        session_id=session_id,
                        tool_call=tool_call,
                        result=result,
                    )
                
                # 继续循环
                user_input = None
                continue
            
            # 6. 没有工具调用，返回最终结果
            await self.context.add_assistant_message(
                session_id=session_id,
                content=full_response,
            )
            
            # 更新记忆
            await self.memory.process(
                session_id=session_id,
                content=full_response,
            )
            
            # 保存最终检查点
            await self.checkpointer.save(
                session_id=session_id,
                step=iteration,
                state=SessionState(
                    messages=context.messages,
                    iteration=iteration,
                    total_tokens=total_tokens,
                    completed=True,
                )
            )
            
            yield AgentEvent(type="done", data={
                "content": full_response,
                "total_tokens": total_tokens,
                "iterations": iteration,
            })
            break
    
    def _check_termination(
        self,
        iteration: int,
        total_tokens: int,
        start_time: datetime,
    ) -> Optional[str]:
        """检查终止条件"""
        if iteration > self.termination.max_iterations:
            return f"max_iterations_exceeded ({self.termination.max_iterations})"
        if total_tokens > self.termination.max_tokens:
            return f"token_budget_exceeded ({self.termination.max_tokens})"
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        if elapsed > self.termination.timeout_seconds:
            return f"timeout ({self.termination.timeout_seconds}s)"
        return None
    
    def _needs_human_approval(self, tool_name: str) -> bool:
        """检查是否需要人工确认"""
        # 检查是否在中断列表中
        if tool_name in self.interrupt_config.interrupt_before:
            # 检查是否匹配自动批准模式
            for pattern in self.interrupt_config.auto_approve_patterns:
                if fnmatch.fnmatch(tool_name, pattern):
                    return False
            return True
        return False
    
    async def resume(
        self,
        checkpoint_id: str,
        action: str,  # "approve", "modify", "reject"
        modified_args: dict = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """从中断处恢复执行"""
        state = await self.checkpointer.load(checkpoint_id)
        
        if action == "reject":
            yield AgentEvent(type="rejected", data={"checkpoint_id": checkpoint_id})
            return
        
        tool_call = state.pending_tool_call
        if action == "modify" and modified_args:
            tool_call.arguments = modified_args
        
        # 执行被批准的工具
        result = await self.tools.execute(
            name=tool_call.name,
            arguments=tool_call.arguments,
            session_id=state.session_id,
        )
        
        yield AgentEvent(type="tool_result", data=result.model_dump())
        
        # 继续执行
        async for event in self.run(
            user_input=None,
            session_id=state.session_id,
            resume_from=checkpoint_id,
        ):
            yield event

class AgentEvent(BaseModel):
    """Agent 事件"""
    type: str  # thinking, text, tool_call, tool_result, interrupt, done, error, terminated
    data: dict
```

### 3.2 Checkpointer (检查点管理器) - 借鉴 LangGraph

```python
# backend/core/agent/checkpoint.py

from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import json

class SessionState(BaseModel):
    """会话状态快照"""
    session_id: str
    messages: list[dict]
    iteration: int
    total_tokens: int
    pending_tool_call: Optional[dict] = None
    completed: bool = False
    metadata: dict = {}

class Checkpoint(BaseModel):
    """检查点"""
    id: str
    session_id: str
    step: int
    state: SessionState
    created_at: datetime
    parent_id: Optional[str] = None

class Checkpointer:
    """检查点管理器 - 支持状态持久化和时间旅行"""
    
    def __init__(self, storage: CheckpointStorage):
        self.storage = storage
    
    async def save(
        self,
        session_id: str,
        step: int,
        state: SessionState,
        parent_id: str = None,
    ) -> str:
        """保存检查点"""
        checkpoint = Checkpoint(
            id=generate_checkpoint_id(),
            session_id=session_id,
            step=step,
            state=state,
            created_at=datetime.utcnow(),
            parent_id=parent_id,
        )
        await self.storage.save(checkpoint)
        return checkpoint.id
    
    async def load(self, checkpoint_id: str) -> SessionState:
        """加载检查点状态"""
        checkpoint = await self.storage.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        return checkpoint.state
    
    async def get_latest(self, session_id: str) -> Optional[Checkpoint]:
        """获取最新检查点"""
        return await self.storage.get_latest(session_id)
    
    async def list_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Checkpoint]:
        """列出历史检查点 (用于时间旅行调试)"""
        return await self.storage.list_by_session(session_id, limit)
    
    async def diff(
        self,
        checkpoint_id_1: str,
        checkpoint_id_2: str,
    ) -> dict:
        """对比两个检查点的差异"""
        state1 = await self.load(checkpoint_id_1)
        state2 = await self.load(checkpoint_id_2)
        
        return {
            "messages_added": len(state2.messages) - len(state1.messages),
            "tokens_delta": state2.total_tokens - state1.total_tokens,
            "new_messages": state2.messages[len(state1.messages):],
        }

class RedisCheckpointStorage:
    """Redis 检查点存储 (开发环境)"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 86400 * 7  # 7天过期
    
    async def save(self, checkpoint: Checkpoint):
        key = f"checkpoint:{checkpoint.id}"
        await self.redis.setex(
            key,
            self.ttl,
            checkpoint.model_dump_json(),
        )
        # 维护会话索引
        await self.redis.zadd(
            f"checkpoints:{checkpoint.session_id}",
            {checkpoint.id: checkpoint.step},
        )
    
    async def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        key = f"checkpoint:{checkpoint_id}"
        data = await self.redis.get(key)
        if data:
            return Checkpoint.model_validate_json(data)
        return None

class PostgresCheckpointStorage:
    """PostgreSQL 检查点存储 (生产环境)"""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def save(self, checkpoint: Checkpoint):
        await self.db.execute(
            """
            INSERT INTO checkpoints (id, session_id, step, state, created_at, parent_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            checkpoint.id,
            checkpoint.session_id,
            checkpoint.step,
            checkpoint.state.model_dump_json(),
            checkpoint.created_at,
            checkpoint.parent_id,
        )
```

### 3.3 Context Manager (上下文管理器)

```python
# backend/core/agent/context.py

from typing import Optional
from pydantic import BaseModel

class ContextConfig(BaseModel):
    """上下文配置"""
    max_tokens: int = 100000           # 最大Token数
    system_prompt_tokens: int = 1000   # 系统提示预留
    output_tokens: int = 4000          # 输出预留
    recent_messages: int = 20          # 保留最近消息数
    memory_tokens: int = 10000         # 记忆预留

class Context(BaseModel):
    """上下文结构"""
    messages: list[dict]
    total_tokens: int
    truncated: bool = False

class ContextManager:
    """上下文管理器"""
    
    def __init__(
        self,
        config: ContextConfig,
        memory_retriever: MemoryRetriever,
        token_counter: TokenCounter,
    ):
        self.config = config
        self.memory = memory_retriever
        self.counter = token_counter
        
    async def build(
        self,
        session_id: str,
        user_input: Optional[str],
        system_prompt: str,
    ) -> Context:
        """
        构建上下文
        
        组装顺序:
        1. System Prompt
        2. 召回的记忆
        3. 对话历史
        4. 工具结果 (如有)
        5. 当前输入
        """
        messages = []
        available_tokens = self.config.max_tokens - self.config.output_tokens
        
        # 1. System Prompt (必须)
        system_tokens = self.counter.count(system_prompt)
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        available_tokens -= system_tokens
        
        # 2. 召回记忆
        if user_input:
            memories = await self.memory.retrieve(
                query=user_input,
                session_id=session_id,
                max_tokens=min(self.config.memory_tokens, available_tokens // 4),
            )
            if memories:
                memory_content = self._format_memories(memories)
                memory_tokens = self.counter.count(memory_content)
                messages.append({
                    "role": "system",
                    "content": f"相关记忆:\n{memory_content}"
                })
                available_tokens -= memory_tokens
        
        # 3. 对话历史
        history = await self._get_session_history(session_id)
        history_messages, history_tokens = self._fit_history(
            history, 
            available_tokens - 500  # 预留给当前输入
        )
        messages.extend(history_messages)
        available_tokens -= history_tokens
        
        # 4. 当前输入
        if user_input:
            messages.append({
                "role": "user",
                "content": user_input
            })
        
        total_tokens = self.counter.count_messages(messages)
        
        return Context(
            messages=messages,
            total_tokens=total_tokens,
            truncated=len(history_messages) < len(history),
        )
    
    def _fit_history(
        self, 
        history: list[dict], 
        max_tokens: int
    ) -> tuple[list[dict], int]:
        """
        将历史消息适配到Token预算内
        策略: 保留最近的消息，直到达到预算
        """
        result = []
        total_tokens = 0
        
        # 从最新的消息开始
        for msg in reversed(history):
            msg_tokens = self.counter.count(msg["content"])
            if total_tokens + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            total_tokens += msg_tokens
        
        return result, total_tokens
    
    async def add_tool_result(
        self,
        session_id: str,
        tool_call: ToolCall,
        result: ToolResult,
    ):
        """添加工具调用结果到会话"""
        await self._save_message(session_id, {
            "role": "assistant",
            "tool_calls": [tool_call.model_dump()]
        })
        await self._save_message(session_id, {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result.output,
        })
```

### 3.4 Tool System (工具系统)

```python
# backend/core/tool/registry.py

from typing import Callable, Any
from pydantic import BaseModel
import json

class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: dict  # JSON Schema
    category: str = "builtin"
    requires_confirmation: bool = False

class ToolRegistry:
    """工具注册中心"""
    
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}
        
    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
        category: str = "builtin",
        requires_confirmation: bool = False,
    ):
        """注册工具"""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            category=category,
            requires_confirmation=requires_confirmation,
        )
        self._handlers[name] = handler
        
    def get_definitions(self, names: list[str] = None) -> list[dict]:
        """获取工具定义 (OpenAI Function格式)"""
        tools = self._tools.values()
        if names:
            tools = [t for t in tools if t.name in names]
        
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in tools
        ]
    
    def get_handler(self, name: str) -> Callable:
        """获取工具处理函数"""
        return self._handlers.get(name)

# 工具注册示例
tool_registry = ToolRegistry()

# 注册文件读取工具
tool_registry.register(
    name="read_file",
    description="读取指定路径的文件内容。适用于需要查看文件内容的场景。",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径"
            },
            "encoding": {
                "type": "string",
                "description": "文件编码，默认utf-8",
                "default": "utf-8"
            }
        },
        "required": ["path"]
    },
    handler=read_file_handler,
    category="file",
)

# 注册Shell命令工具
tool_registry.register(
    name="run_shell",
    description="执行Shell命令。适用于需要运行系统命令的场景。请谨慎使用。",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的Shell命令"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间(秒)，默认30",
                "default": 30
            }
        },
        "required": ["command"]
    },
    handler=run_shell_handler,
    category="system",
    requires_confirmation=True,
)
```

```python
# backend/core/tool/executor.py

from typing import Any
from pydantic import BaseModel

class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    metadata: dict = {}

class ToolExecutor:
    """工具执行器"""
    
    def __init__(
        self,
        registry: ToolRegistry,
        docker_executor: Optional[DockerExecutor] = None,
    ):
        self.registry = registry
        self.docker_executor = docker_executor
        
    async def execute(
        self,
        name: str,
        arguments: dict,
        session_id: str,
    ) -> ToolResult:
        """执行工具"""
        
        # 1. 获取工具定义
        tool = self.registry._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"工具不存在: {name}"
            )
        
        # 2. 参数校验
        try:
            self._validate_arguments(tool.parameters, arguments)
        except ValueError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"参数错误: {str(e)}"
            )
        
        # 3. 获取处理函数
        handler = self.registry.get_handler(name)
        
        # 4. 执行
        try:
            if self.docker_executor and tool.category in ["code", "shell"]:
                # 在 Docker 沙箱中执行 (借鉴 AutoGen)
                result = await self.docker_executor.execute(
                    tool_name=name,
                    handler=handler,
                    arguments=arguments,
                )
            else:
                # 直接执行
                result = await handler(**arguments)
            
            # 5. 格式化输出
            output = self._format_output(result)
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"tool": name, "args": arguments}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"执行失败: {str(e)}"
            )
    
    def _format_output(self, result: Any, max_length: int = 10000) -> str:
        """格式化输出，限制长度"""
        if isinstance(result, str):
            output = result
        elif isinstance(result, (dict, list)):
            output = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            output = str(result)
        
        if len(output) > max_length:
            output = output[:max_length] + f"\n...[截断，共{len(output)}字符]"
        
        return output
```

### 3.4.1 Docker 沙箱执行器 (借鉴 AutoGen)

```python
# backend/core/tool/docker_executor.py

import docker
import tempfile
import os
from pydantic import BaseModel

class DockerConfig(BaseModel):
    """Docker 执行器配置"""
    image: str = "python:3.11-slim"
    timeout: int = 60
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    network_mode: str = "none"  # 禁用网络提高安全性
    work_dir: str = "/workspace"
    auto_remove: bool = True

class DockerExecutor:
    """Docker 沙箱执行器 - 安全隔离执行代码"""
    
    def __init__(self, config: DockerConfig = None):
        self.config = config or DockerConfig()
        self.client = docker.from_env()
        
    async def execute(
        self,
        tool_name: str,
        handler: Callable,
        arguments: dict,
    ) -> str:
        """在 Docker 容器中执行代码"""
        
        # 创建临时工作目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 准备执行脚本
            if tool_name == "run_python":
                script_path = os.path.join(temp_dir, "script.py")
                with open(script_path, "w") as f:
                    f.write(arguments.get("code", ""))
                cmd = ["python", "/workspace/script.py"]
                
            elif tool_name == "run_shell":
                script_path = os.path.join(temp_dir, "script.sh")
                with open(script_path, "w") as f:
                    f.write(arguments.get("command", ""))
                cmd = ["bash", "/workspace/script.sh"]
            else:
                raise ValueError(f"不支持的工具: {tool_name}")
            
            try:
                # 运行容器
                container = self.client.containers.run(
                    image=self.config.image,
                    command=cmd,
                    volumes={
                        temp_dir: {
                            "bind": self.config.work_dir,
                            "mode": "rw"
                        }
                    },
                    working_dir=self.config.work_dir,
                    mem_limit=self.config.memory_limit,
                    cpu_period=100000,
                    cpu_quota=int(100000 * self.config.cpu_limit),
                    network_mode=self.config.network_mode,
                    remove=self.config.auto_remove,
                    detach=False,
                    stdout=True,
                    stderr=True,
                )
                
                # 解码输出
                if isinstance(container, bytes):
                    return container.decode("utf-8")
                return str(container)
                
            except docker.errors.ContainerError as e:
                return f"执行错误:\n{e.stderr.decode('utf-8') if e.stderr else str(e)}"
            except docker.errors.ImageNotFound:
                return f"镜像不存在: {self.config.image}"
            except docker.errors.APIError as e:
                return f"Docker API 错误: {str(e)}"
    
    async def execute_with_timeout(
        self,
        tool_name: str,
        handler: Callable,
        arguments: dict,
    ) -> str:
        """带超时的执行"""
        import asyncio
        
        try:
            return await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: asyncio.run(self.execute(tool_name, handler, arguments))
                ),
                timeout=self.config.timeout
            )
        except asyncio.TimeoutError:
            return f"执行超时 ({self.config.timeout}秒)"
```

### 3.5 Memory System (记忆系统)

```python
# backend/core/memory/manager.py

from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class MemoryItem(BaseModel):
    """记忆条目"""
    id: str
    user_id: str
    type: str  # fact, episode, procedure
    content: str
    embedding: list[float]
    importance: float = 0.5
    access_count: int = 0
    created_at: datetime
    last_accessed: datetime
    metadata: dict = {}

class MemoryManager:
    """记忆管理器"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        agent_llm_facade: AgentLlmFacade,
        db: Database,
    ):
        self.vectors = vector_store
        self.llm = llm
        self.db = db
        
    async def process(
        self,
        session_id: str,
        content: str,
    ):
        """
        处理对话，提取并存储记忆
        
        提取类型:
        - fact: 用户偏好、个人信息等事实
        - episode: 重要的对话片段
        - procedure: 常用的操作流程
        """
        # 使用LLM判断是否需要存储
        extraction = await self._extract_memories(content)
        
        for memory in extraction.memories:
            await self._store_memory(
                session_id=session_id,
                memory=memory,
            )
    
    async def _extract_memories(self, content: str) -> MemoryExtraction:
        """使用LLM提取记忆"""
        prompt = """分析以下对话内容，提取需要长期记住的信息。

对话内容:
{content}

请提取以下类型的信息（如果有）:
1. fact: 用户的偏好、习惯、个人信息
2. episode: 重要的结论、决策、约定
3. procedure: 常用的操作方式、工作流程

以JSON格式返回:
{{
  "memories": [
    {{"type": "fact", "content": "...", "importance": 0.8}},
    ...
  ]
}}

如果没有需要记住的信息，返回空数组。"""
        
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt.format(content=content)}],
            response_format={"type": "json_object"},
        )
        
        return MemoryExtraction.model_validate_json(response)
    
    async def _store_memory(
        self,
        session_id: str,
        memory: dict,
    ):
        """存储记忆"""
        # 生成embedding
        embedding = await self.llm.embed(memory["content"])
        
        # 检查是否有类似记忆
        similar = await self.vectors.search(
            embedding=embedding,
            top_k=1,
            threshold=0.9,
        )
        
        if similar:
            # 更新已有记忆
            await self._update_memory(similar[0].id, memory)
        else:
            # 创建新记忆
            item = MemoryItem(
                id=generate_id(),
                user_id=await self._get_user_id(session_id),
                type=memory["type"],
                content=memory["content"],
                embedding=embedding,
                importance=memory.get("importance", 0.5),
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
            )
            await self.vectors.insert(item)
            await self.db.save(item)

class MemoryRetriever:
    """记忆检索器"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        agent_llm_facade: AgentLlmFacade,
    ):
        self.vectors = vector_store
        self.llm = llm
        
    async def retrieve(
        self,
        query: str,
        session_id: str,
        max_tokens: int = 2000,
        top_k: int = 10,
    ) -> list[MemoryItem]:
        """
        检索相关记忆
        
        策略:
        1. 向量相似度检索
        2. 关键词匹配
        3. 重要性和时效性排序
        4. 按Token预算截断
        """
        user_id = await self._get_user_id(session_id)
        
        # 生成查询embedding
        query_embedding = await self.llm.embed(query)
        
        # 向量检索
        results = await self.vectors.search(
            embedding=query_embedding,
            filter={"user_id": user_id},
            top_k=top_k * 2,  # 多取一些，后面排序筛选
        )
        
        # 综合评分排序
        scored_results = []
        for item in results:
            score = self._calculate_score(item, query_embedding)
            scored_results.append((item, score))
        
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # 按Token预算截断
        selected = []
        current_tokens = 0
        
        for item, score in scored_results:
            item_tokens = self._count_tokens(item.content)
            if current_tokens + item_tokens > max_tokens:
                break
            selected.append(item)
            current_tokens += item_tokens
            
            # 更新访问记录
            await self._update_access(item.id)
        
        return selected
    
    def _calculate_score(
        self,
        item: MemoryItem,
        query_embedding: list[float],
    ) -> float:
        """计算综合得分"""
        # 相似度得分 (0-1)
        similarity = cosine_similarity(item.embedding, query_embedding)
        
        # 时效性得分 (0-1)
        days_old = (datetime.utcnow() - item.last_accessed).days
        recency = max(0, 1 - days_old / 30)  # 30天衰减到0
        
        # 重要性得分 (0-1)
        importance = item.importance
        
        # 综合得分
        score = similarity * 0.5 + recency * 0.3 + importance * 0.2
        
        return score
```

---

## 四、API 接口设计

### 4.1 API 路由结构

```
/api/v1
├── /auth                          # 认证
│   ├── POST /login                # 登录
│   ├── POST /register             # 注册
│   ├── POST /refresh              # 刷新Token
│   └── POST /logout               # 登出
│
├── /agents                        # Agent管理
│   ├── GET    /                   # 列表
│   ├── POST   /                   # 创建
│   ├── GET    /{id}               # 详情
│   ├── PUT    /{id}               # 更新
│   └── DELETE /{id}               # 删除
│
├── /sessions                      # 会话管理
│   ├── GET    /                   # 列表
│   ├── POST   /                   # 创建
│   ├── GET    /{id}               # 详情
│   ├── DELETE /{id}               # 删除
│   └── GET    /{id}/messages      # 消息历史
│
├── /chat                          # 对话
│   ├── POST   /                   # 发送消息 (SSE流式响应)
│   └── POST   /confirm            # 确认工具执行
│
├── /tools                         # 工具管理
│   ├── GET    /                   # 可用工具列表
│   ├── GET    /{name}             # 工具详情
│   └── POST   /{name}/test        # 测试工具
│
├── /memory                        # 记忆管理
│   ├── GET    /                   # 记忆列表
│   ├── POST   /search             # 搜索记忆
│   ├── DELETE /{id}               # 删除记忆
│   └── POST   /import             # 导入知识
│
└── /system                        # 系统
    ├── GET    /health             # 健康检查
    ├── GET    /stats              # 统计信息
    └── GET    /models             # 可用模型
```

### 4.2 核心 API 定义

```python
# backend/api/v1/chat.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str
    message: str
    agent_id: Optional[str] = None

class ChatEvent(BaseModel):
    """对话事件"""
    type: str  # thinking, text, tool_call, tool_result, done, error
    data: dict

@router.post("/")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
):
    """
    发送消息并获取流式响应
    
    返回: Server-Sent Events 流
    
    事件类型:
    - thinking: Agent正在思考
    - text: 文本输出片段
    - tool_call: 工具调用请求
    - tool_result: 工具执行结果
    - done: 完成
    - error: 错误
    """
    async def event_generator():
        try:
            async for event in agent_service.chat(
                session_id=request.session_id,
                message=request.message,
                agent_id=request.agent_id,
                user_id=current_user.id,
            ):
                yield {
                    "event": event.type,
                    "data": event.data.model_dump_json(),
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
    
    return EventSourceResponse(event_generator())

class ResumeRequest(BaseModel):
    """恢复执行请求 (Human-in-the-Loop)"""
    session_id: str
    checkpoint_id: str
    action: str  # "approve", "modify", "reject"
    modified_args: Optional[dict] = None

@router.post("/resume")
async def resume_execution(
    request: ResumeRequest,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
):
    """
    从中断点恢复执行 (借鉴 LangGraph)
    
    用于 Human-in-the-Loop 场景:
    - approve: 批准待执行的操作
    - modify: 修改参数后执行
    - reject: 拒绝操作，返回错误给 Agent
    
    返回: Server-Sent Events 流 (继续执行)
    """
    async def event_generator():
        try:
            async for event in agent_service.resume(
                session_id=request.session_id,
                checkpoint_id=request.checkpoint_id,
                action=request.action,
                modified_args=request.modified_args,
                user_id=current_user.id,
            ):
                yield {
                    "event": event.type,
                    "data": event.data.model_dump_json(),
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
    
    return EventSourceResponse(event_generator())

@router.get("/checkpoints/{session_id}")
async def list_checkpoints(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    checkpointer: Checkpointer = Depends(get_checkpointer),
):
    """
    列出会话的检查点历史 (用于时间旅行调试)
    """
    checkpoints = await checkpointer.list_history(session_id, limit)
    return [
        {
            "id": cp.id,
            "step": cp.step,
            "created_at": cp.created_at.isoformat(),
            "iteration": cp.state.iteration,
            "total_tokens": cp.state.total_tokens,
            "completed": cp.state.completed,
        }
        for cp in checkpoints
    ]

@router.get("/checkpoints/{checkpoint_id}/state")
async def get_checkpoint_state(
    checkpoint_id: str,
    current_user: User = Depends(get_current_user),
    checkpointer: Checkpointer = Depends(get_checkpointer),
):
    """
    获取检查点的完整状态 (用于调试)
    """
    state = await checkpointer.load(checkpoint_id)
    return state.model_dump()

@router.post("/checkpoints/diff")
async def diff_checkpoints(
    checkpoint_id_1: str,
    checkpoint_id_2: str,
    current_user: User = Depends(get_current_user),
    checkpointer: Checkpointer = Depends(get_checkpointer),
):
    """
    对比两个检查点的差异
    """
    return await checkpointer.diff(checkpoint_id_1, checkpoint_id_2)
```

```python
# backend/api/v1/agent.py

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/agents", tags=["agents"])

class AgentCreate(BaseModel):
    """创建Agent请求"""
    name: str
    description: Optional[str] = None
    system_prompt: str
    model: str = "claude-3-5-sonnet-20241022"
    tools: list[str] = []
    temperature: float = 0.7
    max_tokens: int = 4096

class AgentResponse(BaseModel):
    """Agent响应"""
    id: str
    name: str
    description: Optional[str]
    system_prompt: str
    model: str
    tools: list[str]
    created_at: datetime
    updated_at: datetime

@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    agent_repo: AgentRepository = Depends(get_agent_repo),
):
    """获取用户的Agent列表"""
    return await agent_repo.list_by_user(current_user.id)

@router.post("/", response_model=AgentResponse)
async def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
    agent_repo: AgentRepository = Depends(get_agent_repo),
):
    """创建新Agent"""
    agent = Agent(
        id=generate_id(),
        user_id=current_user.id,
        **data.model_dump(),
    )
    return await agent_repo.create(agent)

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    agent_repo: AgentRepository = Depends(get_agent_repo),
):
    """获取Agent详情"""
    agent = await agent_repo.get(agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(404, "Agent not found")
    return agent

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
    agent_repo: AgentRepository = Depends(get_agent_repo),
):
    """更新Agent"""
    agent = await agent_repo.get(agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(404, "Agent not found")
    
    return await agent_repo.update(agent_id, data.model_dump())

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    agent_repo: AgentRepository = Depends(get_agent_repo),
):
    """删除Agent"""
    agent = await agent_repo.get(agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(404, "Agent not found")
    
    await agent_repo.delete(agent_id)
    return {"success": True}
```

---

## 五、数据库设计

### 5.1 ER 图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据库 ER 图                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                │
│  │   users     │      │   agents    │      │   tools     │                │
│  ├─────────────┤      ├─────────────┤      ├─────────────┤                │
│  │ id (PK)     │──┐   │ id (PK)     │      │ id (PK)     │                │
│  │ email       │  │   │ user_id(FK) │◀─────│ name        │                │
│  │ password    │  │   │ name        │      │ description │                │
│  │ name        │  │   │ description │      │ parameters  │                │
│  │ settings    │  │   │ system_prompt│     │ category    │                │
│  │ created_at  │  │   │ model       │      │ enabled     │                │
│  └─────────────┘  │   │ tools       │      └─────────────┘                │
│                   │   │ config      │                                      │
│                   │   │ created_at  │                                      │
│                   │   └─────────────┘                                      │
│                   │          │                                             │
│                   │          │ 1:N                                         │
│                   │          ▼                                             │
│                   │   ┌─────────────┐      ┌─────────────┐                │
│                   │   │  sessions   │      │  messages   │                │
│                   │   ├─────────────┤      ├─────────────┤                │
│                   └──▶│ id (PK)     │──┐   │ id (PK)     │                │
│                       │ user_id(FK) │  │   │ session_id  │◀───┐           │
│                       │ agent_id(FK)│  │   │ role        │    │           │
│                       │ title       │  └──▶│ content     │    │           │
│                       │ status      │      │ tool_calls  │    │           │
│                       │ context     │      │ created_at  │    │           │
│                       │ created_at  │      └─────────────┘    │           │
│                       └─────────────┘                         │           │
│                                                               │           │
│  ┌─────────────┐      ┌─────────────┐                         │           │
│  │  memories   │      │ tool_calls  │─────────────────────────┘           │
│  ├─────────────┤      ├─────────────┤                                     │
│  │ id (PK)     │      │ id (PK)     │                                     │
│  │ user_id(FK) │      │ message_id  │                                     │
│  │ type        │      │ tool_name   │                                     │
│  │ content     │      │ arguments   │                                     │
│  │ embedding   │      │ result      │                                     │
│  │ importance  │      │ status      │                                     │
│  │ metadata    │      │ created_at  │                                     │
│  │ created_at  │      └─────────────┘                                     │
│  └─────────────┘                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 表结构定义

```sql
-- users: 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    avatar_url VARCHAR(500),
    settings JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- agents: Agent配置表
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    model VARCHAR(100) DEFAULT 'claude-3-5-sonnet-20241022',
    tools TEXT[] DEFAULT '{}',
    config JSONB DEFAULT '{
        "temperature": 0.7,
        "max_tokens": 4096,
        "max_iterations": 10
    }',
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agents_user_id ON agents(user_id);

-- sessions: 会话表
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    title VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active',  -- active, archived, deleted
    context JSONB DEFAULT '{}',
    message_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_agent_id ON sessions(agent_id);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);

-- messages: 消息表
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system, tool
    content TEXT,
    tool_calls JSONB,
    tool_call_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- memories: 记忆表
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,  -- fact, episode, procedure
    content TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    source_session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_type ON memories(type);

-- 向量存储 (Qdrant/Chroma 单独管理，这里记录关联)
-- memory_id -> embedding vector

-- checkpoints: 检查点表 (借鉴 LangGraph，支持时间旅行调试)
CREATE TABLE checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    step INTEGER NOT NULL,
    state JSONB NOT NULL,
    parent_id UUID REFERENCES checkpoints(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_checkpoints_session_id ON checkpoints(session_id);
CREATE INDEX idx_checkpoints_step ON checkpoints(session_id, step DESC);

-- tool_calls: 工具调用记录表
CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    tool_name VARCHAR(100) NOT NULL,
    arguments JSONB NOT NULL,
    result JSONB,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, confirmed, executed, failed, rejected
    error TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP
);

CREATE INDEX idx_tool_calls_session_id ON tool_calls(session_id);
CREATE INDEX idx_tool_calls_status ON tool_calls(status);
```

---

## 六、配置管理

### 6.1 环境变量

```bash
# .env.example

# ========================
# 应用配置
# ========================
APP_NAME=AI-Agent
APP_ENV=development  # development, staging, production
DEBUG=true
SECRET_KEY=your-secret-key-here
API_PREFIX=/api/v1

# ========================
# 服务器配置
# ========================
HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=true

# ========================
# 数据库配置
# ========================
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ai_agent
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# ========================
# Redis配置
# ========================
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ========================
# 向量数据库
# ========================
VECTOR_DB_TYPE=qdrant  # qdrant, chroma
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
CHROMA_PATH=./data/chroma

# ========================
# LLM配置
# ========================
# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# 本地模型
LOCAL_LLM_URL=http://localhost:11434

# 默认模型
DEFAULT_MODEL=claude-3-5-sonnet-20241022
EMBEDDING_MODEL=text-embedding-3-small

# ========================
# 安全配置
# ========================
JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# ========================
# 存储配置
# ========================
STORAGE_TYPE=local  # local, s3, minio
STORAGE_PATH=./data/storage
S3_BUCKET=ai-agent
S3_REGION=us-east-1
S3_ACCESS_KEY=
S3_SECRET_KEY=

# ========================
# 工具配置
# ========================
SANDBOX_ENABLED=true
SANDBOX_TIMEOUT=60
SANDBOX_MEMORY_LIMIT=512m
SANDBOX_CPU_LIMIT=1.0
SANDBOX_NETWORK_MODE=none

# ========================
# Agent 执行配置
# ========================
AGENT_MAX_ITERATIONS=20
AGENT_MAX_TOKENS=100000
AGENT_TIMEOUT_SECONDS=600

# Human-in-the-Loop 配置
HITL_ENABLED=true
HITL_INTERRUPT_TOOLS=run_shell,write_file,delete_file,send_email
HITL_AUTO_APPROVE_PATTERNS=read_*,search_*,list_*

# ========================
# 检查点配置
# ========================
CHECKPOINT_ENABLED=true
CHECKPOINT_STORAGE=redis  # redis, postgres
CHECKPOINT_TTL_DAYS=7

# ========================
# 日志配置
# ========================
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=./logs/app.log

# ========================
# 监控配置
# ========================
METRICS_ENABLED=true
TRACING_ENABLED=true
JAEGER_ENDPOINT=http://localhost:14268/api/traces
```

### 6.2 配置类

```python
# backend/app/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """应用配置"""
    
    # 应用
    app_name: str = "AI-Agent"
    app_env: str = "development"
    debug: bool = True
    secret_key: str
    api_prefix: str = "/api/v1"
    
    # 服务器
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # 数据库
    database_url: str
    database_pool_size: int = 20
    
    # Redis
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    
    # 向量数据库
    vector_db_type: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    chroma_path: str = "./data/chroma"
    
    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_model: str = "claude-3-5-sonnet-20241022"
    embedding_model: str = "text-embedding-3-small"
    
    # 安全
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    cors_origins: list[str] = ["http://localhost:3000"]
    
    # 存储
    storage_type: str = "local"
    storage_path: str = "./data/storage"
    
    # 工具沙箱
    sandbox_enabled: bool = True
    sandbox_timeout: int = 60
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0
    sandbox_network_mode: str = "none"
    
    # Agent 执行
    agent_max_iterations: int = 20
    agent_max_tokens: int = 100000
    agent_timeout_seconds: int = 600
    
    # Human-in-the-Loop
    hitl_enabled: bool = True
    hitl_interrupt_tools: list[str] = ["run_shell", "write_file", "delete_file"]
    hitl_auto_approve_patterns: list[str] = ["read_*", "search_*", "list_*"]
    
    # 检查点
    checkpoint_enabled: bool = True
    checkpoint_storage: str = "redis"
    checkpoint_ttl_days: int = 7
    
    # 日志
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

---

## 七、Docker 部署配置

### 7.1 Docker Compose

```yaml
# deploy/docker/docker-compose.yml

version: '3.8'

services:
  # 后端服务
  backend:
    build:
      context: ../../
      dockerfile: deploy/docker/Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/ai_agent
      - REDIS_URL=redis://redis:6379/0
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - db
      - redis
      - qdrant
    volumes:
      - ../../data:/app/data
    restart: unless-stopped

  # 前端服务
  frontend:
    build:
      context: ../../
      dockerfile: deploy/docker/Dockerfile.frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

  # Celery Worker
  celery:
    build:
      context: ../../
      dockerfile: deploy/docker/Dockerfile.backend
    command: celery -A app.workers.celery_app worker -l info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/ai_agent
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # PostgreSQL
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=ai_agent
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # Qdrant 向量数据库
  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    restart: unless-stopped

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ../nginx/nginx.conf:/etc/nginx/nginx.conf
      - ../nginx/ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

### 7.2 Dockerfile

```dockerfile
# deploy/docker/Dockerfile.backend

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY backend/ .

# 创建数据目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# deploy/docker/Dockerfile.frontend

FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile

# 复制代码并构建
COPY frontend/ .
RUN pnpm build

# 生产镜像
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# 复制构建产物
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

---

## 八、开发规范

### 8.1 Git 工作流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Git 分支策略                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  main ─────────────────────────────────────────────────────────▶ 生产      │
│    │                                                                        │
│    └── develop ────────────────────────────────────────────────▶ 开发      │
│           │                                                                 │
│           ├── feature/xxx ─────────────────────────────────────▶ 新功能    │
│           │                                                                 │
│           ├── fix/xxx ─────────────────────────────────────────▶ Bug修复   │
│           │                                                                 │
│           └── release/v1.0.0 ──────────────────────────────────▶ 发布      │
│                                                                             │
│  Commit Message 规范:                                                       │
│  ├─ feat: 新功能                                                           │
│  ├─ fix: Bug修复                                                           │
│  ├─ docs: 文档更新                                                         │
│  ├─ style: 代码格式                                                        │
│  ├─ refactor: 重构                                                         │
│  ├─ test: 测试                                                             │
│  └─ chore: 构建/工具                                                       │
│                                                                             │
│  示例: feat(agent): 添加ReAct推理模式支持                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 代码规范

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              代码规范                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Python:                                                                    │
│  ├─ 代码格式: Black + isort                                                │
│  ├─ 类型检查: mypy                                                         │
│  ├─ 代码检查: ruff                                                         │
│  └─ 文档风格: Google Style Docstrings                                      │
│                                                                             │
│  TypeScript:                                                                │
│  ├─ 代码格式: Prettier                                                     │
│  ├─ 代码检查: ESLint                                                       │
│  └─ 类型检查: TypeScript strict mode                                       │
│                                                                             │
│  Pre-commit 配置:                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ repos:                                                               │   │
│  │   - repo: https://github.com/psf/black                              │   │
│  │   - repo: https://github.com/pycqa/isort                            │   │
│  │   - repo: https://github.com/charliermarsh/ruff-pre-commit          │   │
│  │   - repo: https://github.com/pre-commit/mirrors-mypy                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  测试覆盖率要求: >= 80%                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 九、快速启动

### 9.1 开发环境

```bash
# 1. 克隆项目
git clone https://github.com/xxx/ai-agent.git
cd ai-agent

# 2. 复制环境变量
cp .env.example .env
# 编辑 .env 填入必要配置

# 3. 启动基础服务 (数据库、Redis、Qdrant)
docker-compose -f deploy/docker/docker-compose.yml up -d db redis qdrant

# 4. 后端开发
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# 数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload

# 5. 前端开发 (新终端)
cd frontend
pnpm install
pnpm dev

# 6. 访问
# 前端: http://localhost:3000
# 后端API: http://localhost:8000
# API文档: http://localhost:8000/docs
```

### 9.2 生产部署

```bash
# 1. 构建并启动所有服务
docker-compose -f deploy/docker/docker-compose.yml up -d --build

# 2. 查看日志
docker-compose logs -f

# 3. 数据库迁移
docker-compose exec backend alembic upgrade head

# 4. 健康检查
curl http://localhost:8000/api/v1/system/health
```

---

<div align="center">

**构建可靠、可扩展的 AI Agent 系统**

*文档版本: v2.0 | 最后更新: 2026-01-12*

*本版本融入了 LangGraph (检查点/时间旅行/Human-in-the-Loop) 和 AutoGen (终止条件/Docker沙箱) 的优秀设计*

</div>
