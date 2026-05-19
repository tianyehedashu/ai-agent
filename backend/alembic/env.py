"""
Alembic Environment Configuration

数据库迁移环境配置
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from bootstrap.config import settings

# 导入所有领域模型以确保它们被注册到 SQLAlchemy。
# 每个域显式从自己的 infrastructure.models 模块导入，避免跨域 re-export
# （历史上 gateway.infrastructure.models.__init__ 曾 re-export tenancy.Team —
#  这条捷径让分层边界变模糊，已删除，env.py 直接显式 import 即可）。
from domains.agent.infrastructure.models.agent import Agent  # noqa: F401
from domains.agent.infrastructure.models.mcp_dynamic_prompt import MCPDynamicPrompt  # noqa: F401
from domains.agent.infrastructure.models.mcp_dynamic_tool import MCPDynamicTool  # noqa: F401
from domains.agent.infrastructure.models.mcp_server import MCPServer  # noqa: F401
from domains.agent.infrastructure.models.memory import Memory  # noqa: F401
from domains.agent.infrastructure.models.message import Message  # noqa: F401
from domains.agent.infrastructure.models.product_image_gen_task import (  # noqa: F401
    ProductImageGenTask,
)
from domains.agent.infrastructure.models.product_info_job import ProductInfoJob  # noqa: F401
from domains.agent.infrastructure.models.product_info_job_step import (  # noqa: F401
    ProductInfoJobStep,
)
from domains.agent.infrastructure.models.product_info_prompt_template import (  # noqa: F401
    ProductInfoPromptTemplate,
)
from domains.agent.infrastructure.models.video_gen_task import VideoGenTask  # noqa: F401
from domains.gateway.infrastructure.models.alert import (  # noqa: F401
    GatewayAlertEvent,
    GatewayAlertRule,
)
from domains.gateway.infrastructure.models.budget import GatewayBudget  # noqa: F401
from domains.gateway.infrastructure.models.entitlement_plan import (  # noqa: F401
    EntitlementPlan,
    EntitlementPlanQuota,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel  # noqa: F401
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute  # noqa: F401
from domains.gateway.infrastructure.models.metrics_hourly import (  # noqa: F401
    GatewayMetricsHourly,
)
from domains.gateway.infrastructure.models.pricing_downstream import (  # noqa: F401
    DownstreamModelPricing,
)
from domains.gateway.infrastructure.models.pricing_upstream import (  # noqa: F401
    UpstreamModelPricing,
)
from domains.gateway.infrastructure.models.provider_credential import (  # noqa: F401
    ProviderCredential,
)
from domains.gateway.infrastructure.models.provider_plan import (  # noqa: F401
    ProviderPlan,
    ProviderPlanQuota,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog  # noqa: F401
from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey  # noqa: F401
from domains.identity.infrastructure.models.api_key import (  # noqa: F401
    ApiKey,
    ApiKeyGatewayGrant,
    ApiKeyUsageLog,
)
from domains.identity.infrastructure.models.user import User  # noqa: F401
from domains.session.infrastructure.models.session import Session  # noqa: F401
from domains.tenancy.infrastructure.models.team import Team, TeamMember  # noqa: F401

# 导入所有模型以确保它们被注册
from libs.orm.base import Base

# this is the Alembic Config object
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
