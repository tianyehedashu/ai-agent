"""
Agent Catalog Domain Models - Agent 目录领域模型

定义 Agent 目录领域的核心实体和值对象
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass
class AgentConfig:
    """Agent 配置值对象"""

    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_iterations: int = 20
    tools: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentEntity:
    """Agent 实体"""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    system_prompt: str
    config: AgentConfig
    description: str | None = None
    is_public: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        name: str,
        system_prompt: str,
        config: AgentConfig | None = None,
        description: str | None = None,
    ) -> "AgentEntity":
        """创建新的 Agent 实体"""
        return cls(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            system_prompt=system_prompt,
            config=config or AgentConfig(),
            description=description,
        )
