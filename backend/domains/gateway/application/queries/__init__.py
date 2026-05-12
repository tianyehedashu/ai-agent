"""Gateway 应用层查询入口（CQRS Query，管理面）"""

from domains.gateway.application.queries.gateway_management_queries import (
    GatewayManagementQueryService,
)

__all__ = [
    "GatewayManagementQueryService",
]
