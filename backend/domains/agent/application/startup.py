"""Agent application startup and shutdown hooks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI  # noqa: TC002

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from domains.agent.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from domains.agent.infrastructure.sandbox import SandboxManager, SandboxPolicy
from libs.config import get_execution_config_service
from libs.db.database import get_session_factory
from utils.logging import get_logger

logger = get_logger(__name__)


async def run_agent_startup(app: FastAPI) -> None:
    """Checkpointer, sandbox manager, and default MCP servers."""
    try:
        global_checkpointer = LangGraphCheckpointer(storage_type="postgres")
        await global_checkpointer.setup()
        app.state.checkpointer = global_checkpointer
        logger.info("Global checkpointer initialized and setup completed")
    except Exception as e:
        logger.error("Failed to initialize global checkpointer: %s", e, exc_info=True)
        global_checkpointer = LangGraphCheckpointer(storage_type="memory")
        await global_checkpointer.setup()
        app.state.checkpointer = global_checkpointer
        logger.warning("Using MemorySaver as fallback for checkpointer")

    try:
        from domains.agent.infrastructure.sandbox.executor import PersistentDockerExecutor

        orphans = await PersistentDockerExecutor.cleanup_orphaned_containers(
            max_age_seconds=300,
        )
        if orphans:
            logger.info(
                "Cleaned up %d orphaned containers on startup: %s",
                len(orphans),
                orphans,
            )
    except Exception as e:
        logger.warning("Failed to cleanup orphaned containers: %s", e)

    try:
        config_service = get_execution_config_service()
        execution_config = config_service.load_for_agent("default")
        sandbox_policy = SandboxPolicy.from_config(
            execution_config.sandbox.docker.sandbox_policy,
        )
        logger.debug("Loaded SandboxPolicy from config: %s", sandbox_policy)
    except Exception as e:
        logger.warning("Failed to load SandboxPolicy from config, using defaults: %s", e)
        sandbox_policy = None

    sandbox_manager = SandboxManager.get_instance(policy=sandbox_policy)
    await sandbox_manager.start()
    app.state.sandbox_manager = sandbox_manager
    logger.info("SandboxManager started")

    try:
        from domains.agent.application.mcp_init import init_default_mcp_servers

        await init_default_mcp_servers()
        logger.info("Default MCP servers initialization completed")
    except Exception as e:
        logger.warning("Failed to initialize default MCP servers: %s", e)


async def run_agent_shutdown(app: FastAPI) -> None:
    """Sandbox manager and checkpointer teardown."""
    if hasattr(app.state, "sandbox_manager"):
        await app.state.sandbox_manager.stop()
        logger.info("SandboxManager stopped")

    if hasattr(app.state, "checkpointer"):
        try:
            await app.state.checkpointer.cleanup()
        except Exception as e:
            logger.warning("Error cleaning up checkpointer: %s", e)


@asynccontextmanager
async def agent_streamable_http_lifespan() -> AsyncGenerator[None, None]:
    """Streamable HTTP MCP servers lifecycle (wraps app request serving)."""
    from domains.agent.application.mcp_server_facade import (
        initialize_mcp_servers,
        sync_dynamic_prompts_for_streamable_http,
        sync_dynamic_tools_for_streamable_http,
    )

    async with initialize_mcp_servers():
        try:
            session_factory = get_session_factory()
            async with session_factory() as db:
                await sync_dynamic_tools_for_streamable_http(db)
                await sync_dynamic_prompts_for_streamable_http(db)
                await db.commit()
            logger.info("Dynamic tools and prompts synced for Streamable HTTP MCP servers")
        except Exception as e:
            logger.warning("Failed to sync dynamic tools/prompts on startup: %s", e)
        yield
