"""
MCP Dynamic Prompt Use Case - MCP 动态 Prompt 用例

为客户端直连 MCP（Streamable HTTP）提供动态 Prompts 的增删改查。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.repositories.mcp_dynamic_prompt_repository import (
    MCPDynamicPromptRepository,
)
from exceptions import ConflictError, NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

SERVER_KIND_STREAMABLE_HTTP = "streamable_http"


class MCPDynamicPromptUseCase:
    """MCP 动态 Prompt 用例"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MCPDynamicPromptRepository(db)

    async def list_dynamic_prompts(self, server_name: str) -> list[dict]:
        """列出某客户端直连 MCP 的动态 Prompts（server_name 即 server_id）。"""
        rows = await self.repo.list_by_server(SERVER_KIND_STREAMABLE_HTTP, server_name)
        return [
            {
                "id": str(r.id),
                "prompt_key": r.prompt_key,
                "title": r.title,
                "description": r.description,
                "arguments_schema": r.arguments_schema or [],
                "template": r.template,
                "enabled": r.enabled,
            }
            for r in rows
        ]

    async def add_dynamic_prompt(
        self,
        server_name: str,
        prompt_key: str,
        template: str,
        title: str | None = None,
        description: str | None = None,
        arguments_schema: list[dict[str, Any]] | None = None,
    ) -> dict:
        """添加一条动态 Prompt。同 server 下 prompt_key 唯一。"""
        if not prompt_key or not prompt_key.strip():
            raise ValidationError("prompt_key is required", code="INVALID_PROMPT_KEY")
        if not (template or "").strip():
            raise ValidationError("template is required", code="INVALID_TEMPLATE")
        existing = await self.repo.get_by_prompt_key(
            SERVER_KIND_STREAMABLE_HTTP, server_name, prompt_key.strip()
        )
        if existing:
            raise ConflictError(
                f"Prompt key already exists: {prompt_key}",
                code="PROMPT_KEY_EXISTS",
            )
        row = await self.repo.add(
            server_kind=SERVER_KIND_STREAMABLE_HTTP,
            server_id=server_name,
            prompt_key=prompt_key.strip(),
            template=template.strip(),
            title=title.strip() if title else None,
            description=description.strip() if description else None,
            arguments_schema=arguments_schema or [],
            enabled=True,
        )
        await self.db.commit()
        return {
            "id": str(row.id),
            "prompt_key": row.prompt_key,
            "title": row.title,
            "description": row.description,
            "arguments_schema": row.arguments_schema or [],
            "template": row.template,
            "enabled": row.enabled,
        }

    async def update_dynamic_prompt(
        self, server_name: str, prompt_key: str, **updates: Any
    ) -> dict:
        """更新一条动态 Prompt。仅更新请求中传入的字段。prompt_key 不可改。"""
        existing = await self.repo.get_by_prompt_key(
            SERVER_KIND_STREAMABLE_HTTP, server_name, prompt_key
        )
        if not existing:
            raise NotFoundError("Dynamic prompt", f"{server_name}/{prompt_key}")
        repo_kwargs: dict[str, Any] = {}
        if "title" in updates:
            repo_kwargs["title"] = updates["title"]
        if "description" in updates:
            repo_kwargs["description"] = updates["description"]
        if "arguments_schema" in updates:
            repo_kwargs["arguments_schema"] = updates["arguments_schema"]
        if "template" in updates:
            if not (updates["template"] or "").strip():
                raise ValidationError("template cannot be empty", code="INVALID_TEMPLATE")
            repo_kwargs["template"] = updates["template"].strip()
        if "enabled" in updates:
            repo_kwargs["enabled"] = updates["enabled"]
        row = await self.repo.update_by_prompt_key(
            SERVER_KIND_STREAMABLE_HTTP,
            server_name,
            prompt_key,
            **repo_kwargs,
        )
        await self.db.commit()
        assert row is not None
        return {
            "id": str(row.id),
            "prompt_key": row.prompt_key,
            "title": row.title,
            "description": row.description,
            "arguments_schema": row.arguments_schema or [],
            "template": row.template,
            "enabled": row.enabled,
        }

    async def remove_dynamic_prompt(self, server_name: str, prompt_key: str) -> None:
        """删除一条动态 Prompt。"""
        deleted = await self.repo.delete_by_prompt_key(
            SERVER_KIND_STREAMABLE_HTTP, server_name, prompt_key
        )
        if not deleted:
            raise NotFoundError("Dynamic prompt", f"{server_name}/{prompt_key}")
        await self.db.commit()
