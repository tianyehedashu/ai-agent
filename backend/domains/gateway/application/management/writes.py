"""Gateway 管理面变更应用服务（CQRS 写侧；实现见 write_modules）。"""

from domains.gateway.application.management.write_modules import GatewayManagementWriteService

__all__ = ["GatewayManagementWriteService"]
