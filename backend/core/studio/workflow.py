"""
Workflow Service - 工作流服务

管理 Agent 工作流的 CRUD 操作
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.studio.codegen import LangGraphCodeGen
from core.studio.parser import LangGraphParser
from db.database import get_async_session
from models.workflow import Workflow, WorkflowVersion
from utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowService:
    """工作流服务"""

    def __init__(self) -> None:
        self.parser = LangGraphParser()
        self.codegen = LangGraphCodeGen()

    async def create(
        self,
        name: str,
        description: str,
        user_id: str,
        code: str | None = None,
    ) -> Workflow:
        """
        创建工作流

        Args:
            name: 名称
            description: 描述
            user_id: 用户 ID
            code: 初始代码

        Returns:
            创建的工作流
        """
        async with get_async_session() as session:
            workflow = Workflow(
                id=uuid.uuid4(),
                name=name,
                description=description,
                user_id=uuid.UUID(user_id),
                code=code or self._default_code(name),
                config={},
                is_published=False,
            )

            session.add(workflow)
            await session.commit()
            await session.refresh(workflow)

            # 创建初始版本
            await self._create_version(session, workflow, "Initial version")

            return workflow

    async def get(self, workflow_id: str) -> Workflow | None:
        """获取工作流"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Workflow]:
        """列出用户的工作流"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Workflow)
                .where(Workflow.user_id == uuid.UUID(user_id))
                .order_by(Workflow.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def update(
        self,
        workflow_id: str,
        name: str | None = None,
        description: str | None = None,
        code: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Workflow | None:
        """
        更新工作流

        Args:
            workflow_id: 工作流 ID
            name: 新名称
            description: 新描述
            code: 新代码
            config: 新配置

        Returns:
            更新后的工作流
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return None

            if name is not None:
                workflow.name = name
            if description is not None:
                workflow.description = description
            if code is not None:
                workflow.code = code
            if config is not None:
                workflow.config = config

            workflow.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(workflow)

            return workflow

    async def delete(self, workflow_id: str) -> bool:
        """删除工作流"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return False

            await session.delete(workflow)
            await session.commit()

            return True

    async def parse_code(self, code: str) -> dict[str, Any]:
        """
        解析代码

        Args:
            code: Python 代码

        Returns:
            React Flow 格式的节点和边
        """
        try:
            workflow_def = self.parser.parse(code)
            return self.parser.to_react_flow(workflow_def)
        except ValueError as e:
            return {"error": str(e), "nodes": [], "edges": []}

    async def generate_code(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> str:
        """
        从可视化定义生成代码

        Args:
            nodes: React Flow 节点
            edges: React Flow 边

        Returns:
            生成的 Python 代码
        """
        return self.codegen.from_react_flow(nodes, edges)

    async def save_version(
        self,
        workflow_id: str,
        message: str = "",
    ) -> WorkflowVersion | None:
        """
        保存新版本

        Args:
            workflow_id: 工作流 ID
            message: 版本说明

        Returns:
            创建的版本
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return None

            return await self._create_version(session, workflow, message)

    async def list_versions(
        self,
        workflow_id: str,
        limit: int = 20,
    ) -> list[WorkflowVersion]:
        """列出工作流版本"""
        async with get_async_session() as session:
            result = await session.execute(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == uuid.UUID(workflow_id))
                .order_by(WorkflowVersion.version.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def restore_version(
        self,
        workflow_id: str,
        version: int,
    ) -> Workflow | None:
        """
        恢复到指定版本

        Args:
            workflow_id: 工作流 ID
            version: 版本号

        Returns:
            恢复后的工作流
        """
        async with get_async_session() as session:
            # 获取版本
            result = await session.execute(
                select(WorkflowVersion).where(
                    WorkflowVersion.workflow_id == uuid.UUID(workflow_id),
                    WorkflowVersion.version == version,
                )
            )
            wf_version = result.scalar_one_or_none()

            if not wf_version:
                return None

            # 获取工作流
            result = await session.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return None

            # 恢复代码和配置
            workflow.code = wf_version.code
            workflow.config = wf_version.config
            workflow.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(workflow)

            return workflow

    async def _create_version(
        self,
        session: AsyncSession,
        workflow: Workflow,
        message: str,
    ) -> WorkflowVersion:
        """创建版本"""
        # 获取最新版本号
        result = await session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow.id)
            .order_by(WorkflowVersion.version.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        new_version = (latest.version + 1) if latest else 1

        version = WorkflowVersion(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            version=new_version,
            code=workflow.code,
            config=workflow.config,
            message=message,
        )

        session.add(version)
        await session.commit()
        await session.refresh(version)

        return version

    def _default_code(self, name: str) -> str:
        """生成默认代码"""
        return f'''"""
{name}

Agent 工作流定义
"""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    """Agent 状态"""
    messages: Sequence[dict]
    next_action: str


# ========== 节点函数 ==========

def process_input(state: AgentState):
    """处理输入"""
    return state


def generate_response(state: AgentState):
    """生成响应"""
    return state


# ========== 图定义 ==========

graph = StateGraph(AgentState)

# 添加节点
graph.add_node("process_input", process_input)
graph.add_node("generate_response", generate_response)

# 添加边
graph.add_edge("process_input", "generate_response")
graph.add_edge("generate_response", END)

# 设置入口点
graph.set_entry_point("process_input")

# 编译图
app = graph.compile()
'''
