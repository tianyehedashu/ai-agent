"""
Workflow Use Case - Workflow management use case.

Manages Agent workflow CRUD operations.
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.studio.infrastructure.studio.codegen import LangGraphCodeGen
from domains.studio.infrastructure.studio.parser import LangGraphParser
from shared.infrastructure.db.database import get_async_session
from domains.studio.infrastructure.models.workflow import Workflow, WorkflowVersion
from utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowUseCase:
    """Workflow use case."""

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
        Create workflow.

        Args:
            name: Name
            description: Description
            user_id: User ID
            code: Initial code

        Returns:
            Created workflow
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

            # Create initial version
            await self._create_version(session, workflow, "Initial version")

            return workflow

    async def get(self, workflow_id: str) -> Workflow | None:
        """Get workflow."""
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
        """List user's workflows."""
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
        Update workflow.

        Args:
            workflow_id: Workflow ID
            name: New name
            description: New description
            code: New code
            config: New config

        Returns:
            Updated workflow
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
        """Delete workflow."""
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
        Parse code.

        Args:
            code: Python code

        Returns:
            React Flow format nodes and edges
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
        Generate code from visual definition.

        Args:
            nodes: React Flow nodes
            edges: React Flow edges

        Returns:
            Generated Python code
        """
        return self.codegen.from_react_flow(nodes, edges)

    async def save_version(
        self,
        workflow_id: str,
        message: str = "",
    ) -> WorkflowVersion | None:
        """
        Save new version.

        Args:
            workflow_id: Workflow ID
            message: Version message

        Returns:
            Created version
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
        """List workflow versions."""
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
        Restore to specified version.

        Args:
            workflow_id: Workflow ID
            version: Version number

        Returns:
            Restored workflow
        """
        async with get_async_session() as session:
            # Get version
            result = await session.execute(
                select(WorkflowVersion).where(
                    WorkflowVersion.workflow_id == uuid.UUID(workflow_id),
                    WorkflowVersion.version == version,
                )
            )
            wf_version = result.scalar_one_or_none()

            if not wf_version:
                return None

            # Get workflow
            result = await session.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return None

            # Restore code and config
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
        """Create version."""
        # Get latest version number
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
        """Generate default code."""
        return f'''"""
{name}

Agent workflow definition.
"""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    """Agent state."""
    messages: Sequence[dict]
    next_action: str


# ========== Node functions ==========

def process_input(state: AgentState):
    """Process input."""
    return state


def generate_response(state: AgentState):
    """Generate response."""
    return state


# ========== Graph definition ==========

graph = StateGraph(AgentState)

# Add nodes
graph.add_node("process_input", process_input)
graph.add_node("generate_response", generate_response)

# Add edges
graph.add_edge("process_input", "generate_response")
graph.add_edge("generate_response", END)

# Set entry point
graph.set_entry_point("process_input")

# Compile graph
app = graph.compile()
'''


# Backward compatibility alias
WorkflowService = WorkflowUseCase
