"""含 ``tenant_id`` 且可能承载匿名 orphan 数据的表（清理 / 迁移共用）。"""

from __future__ import annotations

# Alembic shadow → deterministic tenant 迁移：所有含 tenant_id 的业务表。
TENANT_SCOPED_TABLES_FOR_MIGRATION: tuple[str, ...] = (
    "sessions",
    "agents",
    "video_gen_tasks",
    "product_image_gen_tasks",
    "product_info_jobs",
    "product_info_prompt_templates",
    "memories",
    "mcp_servers",
    "api_keys",
    "api_key_gateway_grants",
    "gateway_models",
    "gateway_routes",
    "gateway_virtual_keys",
    "gateway_alert_rules",
    "provider_credentials",
    "gateway_alert_events",
)

# 定期清理：须含 ``updated_at``（BaseModel）；sessions 级联 messages。
ORPHAN_TENANT_CLEANUP_TABLES: tuple[str, ...] = (
    "sessions",
    "agents",
    "video_gen_tasks",
    "product_image_gen_tasks",
    "product_info_jobs",
    "product_info_prompt_templates",
    "memories",
    "mcp_servers",
    "api_keys",
    "api_key_gateway_grants",
    "gateway_models",
    "gateway_routes",
    "gateway_virtual_keys",
    "gateway_alert_rules",
    "provider_credentials",
    "gateway_alert_events",
)

__all__ = [
    "ORPHAN_TENANT_CLEANUP_TABLES",
    "TENANT_SCOPED_TABLES_FOR_MIGRATION",
]
